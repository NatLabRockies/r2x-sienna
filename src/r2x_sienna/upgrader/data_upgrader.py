import json
import re
import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Protocol
from uuid import uuid4

from loguru import logger
from r2x_core import (
    SemanticVersioningStrategy,
    UpgradeStep,
    UpgradeType,
    VersionReader,
    VersionStrategy,
    run_upgrade_step,
)
from r2x_core.utils import shall_we_upgrade
from rust_ok import Err, Ok, Result

if TYPE_CHECKING:
    from r2x_core import DataStore, PluginContext

    from r2x_sienna.plugin_config import SiennaConfig


_INITIAL_TIMESTAMP_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})[T ](?P<time>\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<fraction>\d+))?(?:Z|[+-]\d{2}:\d{2})?$"
)


def _normalize_initial_timestamp(value: Any) -> Any:
    """Format timestamps for InfrastructureSystems' strict DateTime parser."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(timespec="auto")
    if not isinstance(value, str):
        return value

    match = _INITIAL_TIMESTAMP_RE.match(value.strip())
    if match is None:
        return value
    raw_fraction = match.group("fraction")
    fraction = f".{raw_fraction}" if raw_fraction and raw_fraction.strip("0") else ""
    return f"{match.group('date')}T{match.group('time')}{fraction}"


# Import upgrade_steps at module level to trigger decorator registrations.
# This must happen after SiennaUpgrader is defined (see bottom of file).
def _register_upgrade_steps() -> None:
    """Import upgrade_steps to register all upgrade step functions."""
    from r2x_sienna.upgrader import upgrade_steps  # noqa: F401


class SiennaVersionDetector(VersionReader):
    """Detect version from Sienna JSON files by reading the `data_format_version` field.

    Supports both single JSON files and directories containing JSON files.
    """

    def read_version(self, folder_path: Path) -> str | None:
        """Detect Sienna version from JSON file or directory.

        Parameters
        ----------
        folder_path : Path
            Path to JSON file or directory containing JSON files.

        Returns
        -------
        str | None
            Version string from data_format_version field, or None if not found.
        """
        import json

        path = Path(folder_path)
        if path.is_file():
            json_path = path
        else:
            p1 = path / "system.json"
            if p1.exists():
                json_path = p1
            else:
                candidates = list(path.glob("*.json"))
                if not candidates:
                    logger.debug("No JSON files found in {} for version detection", path)
                    return None
                json_path = candidates[0]

        logger.debug("Detecting Sienna version from {}", json_path)
        try:
            with open(json_path) as f:
                data = json.load(f)
                version = data.get("data_format_version") or data.get("data", {}).get("version_info", {}).get(
                    "version"
                )
                logger.debug("Detected Sienna data format version: {}", version)
                return version
        except (json.JSONDecodeError, OSError) as e:
            logger.debug("Failed to read version from {}: {}", json_path, e)
            return None


class UpgradeCallable(Protocol):
    __name__: str

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


class SiennaUpgrader:
    """Standalone upgrader class for Sienna files.

    This class handles version upgrades for Sienna JSON data files.
    It can be used directly or via the `run_sienna_upgrades()` function
    which integrates with the r2x-core plugin system.
    """

    steps: ClassVar[list[UpgradeStep]] = []  # Define upgrade steps here
    version_reader: ClassVar[VersionReader] = SiennaVersionDetector()
    version_strategy: ClassVar[VersionStrategy] = SemanticVersioningStrategy()

    @classmethod
    def register_step(
        cls,
        *,
        target_version: str,
        upgrade_type: UpgradeType = UpgradeType.FILE,
        priority: int = 0,
    ) -> Callable[[UpgradeCallable], UpgradeCallable]:
        """Decorator to register an upgrade step function.

        Parameters
        ----------
        target_version : str
            The version this step upgrades to.
        upgrade_type : UpgradeType
            The type of upgrade (FILE or SYSTEM).
        priority : int
            Priority for ordering steps (higher = earlier).

        Returns
        -------
        Callable
            Decorator function that registers the step.
        """

        def decorator(func: UpgradeCallable) -> UpgradeCallable:
            step = UpgradeStep(
                name=func.__name__,
                func=func,
                target_version=target_version,
                upgrade_type=upgrade_type,
                priority=priority,
            )
            cls.steps.append(step)
            # Sort by priority (descending) then version
            cls.steps.sort(key=lambda s: (-s.priority, s.target_version))
            return func

        return decorator

    def __init__(
        self,
        path: Path | str,
        steps: list[UpgradeStep] | None = None,
    ) -> None:
        """Initialize the Sienna upgrader.

        Parameters
        ----------
        path : Path | str
            Path to JSON file or directory containing JSON files.
        steps : list | None
            Optional list of upgrade steps. If None, uses class-level steps.
        """
        self.path = Path(path)
        self._instance_steps: list[UpgradeStep] | None = steps

    @property
    def active_steps(self) -> list[UpgradeStep]:
        """Return instance steps if set, otherwise class-level steps."""
        return self._instance_steps if self._instance_steps is not None else self.steps

    def upgrade(
        self,
        *,
        current_version: str | None = None,
        target_version: str | None = None,
        strategy: VersionStrategy | None = None,
        upgrade_type: UpgradeType = UpgradeType.FILE,
    ) -> Result[Path, str]:
        """Execute upgrade steps in order.

        Parameters
        ----------
        current_version : str | None
            Current version of the data. If None, will be detected automatically.
        target_version : str | None
            Target version to upgrade to. If None, upgrades to latest.
        strategy : VersionStrategy | None
            Version comparison strategy. If None, uses class-level strategy.
        upgrade_type : UpgradeType
            Type of upgrade to perform (FILE or FOLDER).

        Returns
        -------
        Result[Path, str]
            Ok(path) on success, Err() with error message on failure.
        """
        import json
        import time

        strategy = strategy or self.version_strategy

        if current_version is None:
            current_version = self.version_reader.read_version(self.path)
            if current_version is None:
                return Err("Could not determine Sienna version")

        logger.debug(
            "Upgrader starting: current_version={}, target_version={}, type={}",
            current_version,
            target_version or "latest",
            upgrade_type.name,
        )

        # For SYSTEM upgrades, load the JSON data, apply steps, and save back
        if upgrade_type == UpgradeType.SYSTEM:
            path = self.path
            if path.is_file():
                json_path = path
            else:
                p1 = path / "system.json"
                if p1.exists():
                    json_path = p1
                else:
                    candidates = list(path.glob("*.json"))
                    candidates = [c for c in candidates if "_metadata" not in c.name]
                    if not candidates:
                        return Err("No JSON file found for system upgrade")
                    json_path = candidates[0]

            logger.debug("Loading system data from {} for upgrade", json_path)
            try:
                with open(json_path) as f:
                    system_data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                return Err(f"Failed to load JSON: {e}")

            # Use original_version for all comparisons so multiple steps targeting
            # the same version all run (e.g., all steps targeting 5.999 run when
            # upgrading from 5.0.0)
            original_version = current_version
            modified = False
            steps_run = 0
            for step in self.active_steps:
                if step.upgrade_type != upgrade_type:
                    logger.trace(
                        "Skipping step {} (type={}, want={})",
                        step.name,
                        step.upgrade_type.name,
                        upgrade_type.name,
                    )
                    continue
                should_upgrade = shall_we_upgrade(step, current_version=original_version, strategy=strategy)
                if should_upgrade.is_err() or not should_upgrade.ok():
                    logger.trace(
                        "Skipping step {} (version check: current={}, target={})",
                        step.name,
                        original_version,
                        step.target_version,
                    )
                    continue

                logger.debug(
                    "Running upgrade step: {} (target_version={})",
                    step.name,
                    step.target_version,
                )
                t0 = time.perf_counter()
                try:
                    system_data = step.func(system_data)
                    modified = True
                    steps_run += 1
                except Exception as e:  # noqa: BLE001
                    logger.error("Upgrade step {} failed: {}", step.name, e)
                    return Err(f"Failed {step.name}: {e}")
                current_version = step.target_version
                logger.debug(
                    "Upgrade step {} completed in {:.2f}s",
                    step.name,
                    time.perf_counter() - t0,
                )

            if modified:
                try:
                    with open(json_path, "w") as f:
                        json.dump(system_data, f)
                        f.write("\n")
                    logger.info(
                        "Applied {} upgrade steps, wrote {} (now version {})",
                        steps_run,
                        json_path,
                        current_version,
                    )
                except OSError as e:
                    return Err(f"Failed to write upgraded data: {e}")
            else:
                logger.debug("No upgrade steps needed (already at target version)")

            return Ok(json_path)

        # For FILE upgrades, use the original path-based approach
        for step in self.active_steps:
            if step.upgrade_type != upgrade_type:
                continue
            should_upgrade = shall_we_upgrade(step, current_version=current_version, strategy=strategy)
            if should_upgrade.is_err() or not should_upgrade.ok():
                continue
            logger.debug("Running file upgrade step: {}", step.name)
            result = run_upgrade_step(self.path, step=step)
            if result.is_err():
                return Err(str(result.err()))
            current_version = step.target_version

        return Ok(self.path)


def _iso_8601_duration_from_milliseconds(value: Any) -> str | None:
    """Convert milliseconds to the ISO-8601 duration string used by infrasys metadata."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        # Already an ISO-8601 duration
        if stripped.startswith("P"):
            return stripped
        try:
            value = float(stripped)
        except ValueError:
            return stripped

    if isinstance(value, (int, float)):
        seconds = float(value) / 1000.0
        return f"P0DT{seconds:.3f}S"
    return None


def migrate_metadata(conn: "sqlite3.Connection") -> bool:
    """Migrate legacy time series metadata table layouts to the infrasys schema.

    Returns
    -------
    bool
        True if migration updated the schema/data, False when no migration was needed.
    """
    from infrasys.time_series_metadata_store import create_associations_table
    from infrasys.utils.sqlite import execute

    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(time_series_associations)")
    current_columns = [desc[1] for desc in cursor.fetchall()]
    if not current_columns:
        return False

    # Current infrasys schema already has `resolution` and `metadata_uuid`.
    # Legacy PSY4 variants can contain `resolution_ms` and/or miss `metadata_uuid`.
    if "resolution" in current_columns and "metadata_uuid" in current_columns:
        return False

    logger.debug("Migrating legacy time_series_associations metadata table")
    execute(cursor, "ALTER TABLE time_series_associations RENAME TO infrasys_metadata")
    create_associations_table(connection=conn)

    cursor.execute("SELECT * FROM infrasys_metadata")
    columns = [desc[0] for desc in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

    sql_data_to_insert: list[dict[str, Any]] = []
    for row in rows:
        initial_timestamp = row.get("initial_timestamp")
        initial_timestamp = _normalize_initial_timestamp(initial_timestamp)

        resolution = row.get("resolution")
        if resolution is None:
            resolution = _iso_8601_duration_from_milliseconds(row.get("resolution_ms"))

        horizon = row.get("horizon")
        if horizon is None:
            horizon = _iso_8601_duration_from_milliseconds(row.get("horizon_ms"))

        interval = row.get("interval")
        if interval is None:
            interval = _iso_8601_duration_from_milliseconds(row.get("interval_ms"))

        sql_data_to_insert.append(
            {
                "time_series_uuid": row.get("time_series_uuid"),
                "time_series_type": row.get("time_series_type"),
                "initial_timestamp": initial_timestamp,
                "resolution": resolution,
                "horizon": horizon,
                "interval": interval,
                "window_count": row.get("window_count"),
                "length": row.get("length"),
                "name": row.get("name"),
                "owner_uuid": row.get("owner_uuid"),
                "owner_type": row.get("owner_type"),
                "owner_category": row.get("owner_category") or row.get("time_series_category") or "Component",
                "features": row.get("features") or "[]",
                "scaling_factor_multiplier": row.get("scaling_factor_multiplier"),
                "metadata_uuid": row.get("metadata_uuid") or str(uuid4()),
                "units": row.get("units"),
            }
        )

    cursor.executemany(
        """
        INSERT INTO time_series_associations (
            time_series_uuid, time_series_type, initial_timestamp,
            resolution, horizon, interval, window_count, length, name,
            owner_uuid, owner_type, owner_category, features,
            scaling_factor_multiplier, metadata_uuid, units
        ) VALUES (
            :time_series_uuid, :time_series_type, :initial_timestamp,
            :resolution, :horizon, :interval, :window_count, :length, :name,
            :owner_uuid, :owner_type, :owner_category, :features,
            :scaling_factor_multiplier, :metadata_uuid, :units
        )
        """,
        sql_data_to_insert,
    )
    conn.commit()
    logger.debug("Migrated {} legacy time series metadata rows", len(sql_data_to_insert))
    return True


def _reconcile_metadata_uuid_references(conn: "sqlite3.Connection") -> int:
    """Backfill orphan metadata references in ``time_series_associations``.

    Why this exists
    ---------------
    Some inputs contain association rows whose ``metadata_uuid`` does not exist
    in ``time_series_metadata``. Earlier behavior deleted those rows, which can
    silently drop valid time series (for example, only one of static/forecast
    variants for the same owner type).

    What this function does
    -----------------------
    1. Verifies both required tables/columns exist.
    2. Finds orphan association groups by ``metadata_uuid``.
    3. Synthesizes a legacy-compatible metadata JSON blob for each orphan.
    4. Inserts missing rows into ``time_series_metadata`` (non-destructive).

    Returns
    -------
    int
        Number of metadata rows inserted.
    """
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(time_series_associations)")
    assoc_cols = {desc[1] for desc in cursor.fetchall()}
    if "metadata_uuid" not in assoc_cols:
        return 0

    cursor.execute("PRAGMA table_info(time_series_metadata)")
    meta_cols = {desc[1] for desc in cursor.fetchall()}
    if "metadata_uuid" not in meta_cols or "metadata" not in meta_cols:
        return 0

    cursor.execute(
        """
        SELECT
            a.metadata_uuid,
            a.time_series_uuid,
            a.time_series_type,
            a.initial_timestamp,
            a.resolution,
            a.horizon,
            a.interval,
            a.window_count,
            a.length,
            a.name,
            a.features,
            a.scaling_factor_multiplier
        FROM time_series_associations a
        WHERE a.metadata_uuid NOT IN (
            SELECT metadata_uuid FROM time_series_metadata
        )
        GROUP BY a.metadata_uuid
        """
    )
    orphan_rows = cursor.fetchall()
    if not orphan_rows:
        return 0

    # Build one metadata blob per orphan metadata_uuid using association row context.
    metadata_rows = [
        (row[0], _build_legacy_metadata_blob_from_association_row(row))
        for row in orphan_rows
        if row[0] is not None
    ]

    cursor.executemany(
        """
        INSERT OR IGNORE INTO time_series_metadata (metadata_uuid, metadata)
        VALUES (?, ?)
        """,
        metadata_rows,
    )
    inserted = cursor.rowcount if cursor.rowcount is not None else 0
    if inserted > 0:
        conn.commit()
        logger.warning(
            "Backfilled {} missing time_series_metadata rows to preserve associations",
            inserted,
        )
    return inserted


def _normalize_metadata_timestamps(conn: "sqlite3.Connection") -> int:
    """Normalize timestamps in association rows and serialized metadata blobs."""
    cursor = conn.cursor()
    updated = 0

    for table in ("infrasys_metadata", "time_series_associations"):
        cursor.execute(f"PRAGMA table_info({table})")
        columns = {desc[1] for desc in cursor.fetchall()}
        if "initial_timestamp" not in columns:
            continue
        cursor.execute(f"SELECT rowid, initial_timestamp FROM {table}")
        for rowid, timestamp in cursor.fetchall():
            normalized = _normalize_initial_timestamp(timestamp)
            if normalized != timestamp:
                cursor.execute(
                    f"UPDATE {table} SET initial_timestamp = ? WHERE rowid = ?",
                    (normalized, rowid),
                )
                updated += 1

    cursor.execute("PRAGMA table_info(time_series_metadata)")
    metadata_columns = {desc[1] for desc in cursor.fetchall()}
    if {"metadata_uuid", "metadata"}.issubset(metadata_columns):
        cursor.execute("SELECT metadata_uuid, metadata FROM time_series_metadata")
        for metadata_uuid, raw_metadata in cursor.fetchall():
            try:
                metadata = json.loads(
                    raw_metadata.decode() if isinstance(raw_metadata, bytes) else raw_metadata
                )
            except (AttributeError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            timestamp = metadata.get("initial_timestamp")
            normalized = _normalize_initial_timestamp(timestamp)
            if normalized != timestamp:
                metadata["initial_timestamp"] = normalized
                cursor.execute(
                    "UPDATE time_series_metadata SET metadata = ? WHERE metadata_uuid = ?",
                    (json.dumps(metadata, separators=(",", ":")), metadata_uuid),
                )
                updated += 1

    if updated:
        conn.commit()
    return updated


def _repair_deterministic_metadata_periods(conn: "sqlite3.Connection") -> int:
    """Normalize deterministic metadata for InfrastructureSystems.jl."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(time_series_associations)")
    association_columns = {desc[1] for desc in cursor.fetchall()}
    required_columns = {"time_series_type", "resolution", "horizon", "interval"}
    if not required_columns.issubset(association_columns):
        return 0

    cursor.execute(
        """
        UPDATE time_series_associations
        SET time_series_type = 'DeterministicSingleTimeSeries',
            horizon = COALESCE(horizon, resolution),
            interval = COALESCE(interval, horizon, resolution)
        WHERE time_series_type = 'Deterministic'
           OR (time_series_type = 'DeterministicSingleTimeSeries'
               AND (horizon IS NULL OR interval IS NULL))
        """
    )
    updated = cursor.rowcount

    cursor.execute("PRAGMA table_info(time_series_metadata)")
    metadata_columns = {desc[1] for desc in cursor.fetchall()}
    if {"metadata_uuid", "metadata"}.issubset(metadata_columns):
        cursor.execute("SELECT metadata_uuid, metadata FROM time_series_metadata")
        for metadata_uuid, raw_metadata in cursor.fetchall():
            try:
                metadata = json.loads(
                    raw_metadata.decode() if isinstance(raw_metadata, bytes) else raw_metadata
                )
            except (AttributeError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
                continue

            metadata_type = metadata.get("__metadata__", {}).get("type")
            if metadata_type != "DeterministicMetadata":
                continue

            resolution = metadata.get("resolution")
            if not resolution:
                continue
            changed = False
            if not metadata.get("horizon"):
                metadata["horizon"] = resolution
                changed = True
            if not metadata.get("interval"):
                metadata["interval"] = metadata["horizon"]
                changed = True
            if changed:
                cursor.execute(
                    "UPDATE time_series_metadata SET metadata = ? WHERE metadata_uuid = ?",
                    (json.dumps(metadata, separators=(",", ":")), metadata_uuid),
                )
                updated += 1

    if updated:
        conn.commit()
    return updated


def _build_legacy_metadata_blob_from_association_row(row: tuple[Any, ...]) -> bytes:
    """Build a metadata JSON blob compatible with InfrastructureSystems.jl legacy migration.

    Input row schema (from ``time_series_associations`` query)
    -----------------------------------------------------------
    ``(metadata_uuid, time_series_uuid, time_series_type, initial_timestamp,
    resolution, horizon, interval, window_count, length, name, features,
    scaling_factor_multiplier)``

    Output
    ------
    UTF-8 encoded compact JSON bytes with a top-level ``__metadata__`` section.
    This mirrors the serialized shape expected by Julia's
    ``_deserialize_metadata`` path used during metadata-store migrations.
    """

    (
        metadata_uuid,
        time_series_uuid,
        time_series_type,
        initial_timestamp,
        resolution,
        horizon,
        interval,
        window_count,
        length,
        name,
        features,
        scaling_factor_multiplier,
    ) = row

    metadata: dict[str, Any]
    ts_type_str = str(time_series_type) if time_series_type is not None else "SingleTimeSeries"
    resolution_ms = int(_duration_to_milliseconds(resolution))
    interval_ms = int(_duration_to_milliseconds(interval or resolution))
    horizon_ms = int(_duration_to_milliseconds(horizon or resolution))
    internal = {
        "uuid": {"value": str(metadata_uuid)},
        "shared_system_references": None,
        "units_info": None,
        "ext": None,
    }
    scaling_multiplier_payload = _parse_scaling_factor_multiplier(scaling_factor_multiplier)

    # Choose metadata type by associated time-series class.
    if ts_type_str == "DeterministicSingleTimeSeries":
        metadata = {
            "__metadata__": {"module": "InfrastructureSystems", "type": "DeterministicMetadata"},
            "name": name,
            "resolution": {"type": "Millisecond", "value": resolution_ms},
            "initial_timestamp": _normalize_initial_timestamp(initial_timestamp),
            "interval": {"type": "Millisecond", "value": interval_ms},
            "count": int(window_count or 0),
            "time_series_uuid": {"value": str(time_series_uuid)},
            "horizon": {"type": "Millisecond", "value": horizon_ms},
            "time_series_type": {
                "__metadata__": {
                    "module": "InfrastructureSystems",
                    "type": ts_type_str,
                }
            },
            "scaling_factor_multiplier": scaling_multiplier_payload,
            "features": _parse_features_dict(features),
            "internal": internal,
        }
    else:
        metadata = {
            "__metadata__": {"module": "InfrastructureSystems", "type": "SingleTimeSeriesMetadata"},
            "name": name,
            "resolution": {"type": "Millisecond", "value": resolution_ms},
            "initial_timestamp": _normalize_initial_timestamp(initial_timestamp),
            "time_series_uuid": {"value": str(time_series_uuid)},
            "length": int(length or 0),
            "scaling_factor_multiplier": scaling_multiplier_payload,
            "features": _parse_features_dict(features),
            "internal": internal,
        }

    return json.dumps(metadata, separators=(",", ":")).encode("utf-8")


def _parse_features_dict(features: Any) -> dict[str, Any]:
    """Normalize legacy ``features`` payloads into a plain dict.

    Accepted inputs:
    - ``None`` -> ``{}``
    - ``dict`` -> passthrough
    - JSON string of dict
    - JSON string of list[dict] (flattened in order)

    Unknown/invalid payloads intentionally degrade to ``{}`` to keep upgrade
    flow non-fatal.
    """
    if features is None:
        return {}
    if isinstance(features, dict):
        return features
    if isinstance(features, str):
        try:
            parsed = json.loads(features)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                out: dict[str, Any] = {}
                for item in parsed:
                    if isinstance(item, dict):
                        out.update(item)
                return out
        except json.JSONDecodeError:
            return {}
    return {}


def _parse_scaling_factor_multiplier(value: Any) -> dict[str, Any] | None:
    """Normalize scaling_factor_multiplier payloads to legacy metadata shape."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None
    return None


def _duration_to_milliseconds(value: Any) -> float:
    """Convert mixed duration formats to milliseconds.

    Supported forms:
    - ``None`` -> ``0.0``
    - ``int|float`` interpreted as milliseconds
    - ISO-8601 durations such as ``P0DT3600.000S`` and ``PT1H30M5.5S``
    - ``HH:MM:SS`` strings
    - Numeric strings

    Unrecognized values return ``0.0`` to keep metadata backfill resilient.
    """
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return 0.0

    # Matches durations like P0DT3600.000S and PT1H30M5.5S
    if text.startswith("P"):
        m = re.fullmatch(
            r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>[\d.]+)S)?)?",
            text,
        )
        if m:
            days = float(m.group("days") or 0)
            hours = float(m.group("hours") or 0)
            minutes = float(m.group("minutes") or 0)
            seconds = float(m.group("seconds") or 0)
            total_seconds = days * 86400 + hours * 3600 + minutes * 60 + seconds
            return total_seconds * 1000.0

        m_alt = re.fullmatch(r"P\d+DT([\d.]+)S", text)
        if m_alt:
            return float(m_alt.group(1)) * 1000.0

    # Matches HH:MM:SS
    if ":" in text:
        parts = text.split(":")
        if len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return (hours * 3600 + minutes * 60 + seconds) * 1000.0

    try:
        return float(text)
    except ValueError:
        return 0.0


def _upgrade_h5_time_series_metadata(h5_path: Path) -> Result[bool, str]:
    """Upgrade embedded SQLite metadata in a Sienna HDF5 time series file."""
    import sqlite3
    import tempfile

    import h5py
    import numpy as np

    H5_METADATA_KEY = "time_series_metadata"

    with h5py.File(h5_path, "r") as h5f:
        if H5_METADATA_KEY not in h5f:
            return Ok(False)
        ts_meta_bytes = bytes(h5f[H5_METADATA_KEY][:])

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(ts_meta_bytes)

    try:
        conn = sqlite3.connect(tmp_path)
        try:
            migrated = migrate_metadata(conn)
            repaired = _repair_deterministic_metadata_periods(conn)
            removed = _reconcile_metadata_uuid_references(conn)
            normalized = _normalize_metadata_timestamps(conn)
            changed = migrated or removed > 0 or normalized > 0 or repaired > 0
        finally:
            conn.close()

        if not changed:
            return Ok(False)

        with h5py.File(h5_path, "a") as h5f:
            del h5f[H5_METADATA_KEY]
            h5f.create_dataset(H5_METADATA_KEY, data=np.frombuffer(tmp_path.read_bytes(), dtype=np.uint8))
        logger.info("Upgraded legacy time series metadata schema in {}", h5_path)
        return Ok(True)
    except Exception as e:  # noqa: BLE001
        return Err(f"Failed to upgrade time series metadata in {h5_path}: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)


def _resolve_json_path(path: Path) -> Path | None:
    if path.is_file():
        return path
    p1 = path / "system.json"
    if p1.exists():
        return p1
    candidates = list(path.glob("*.json"))
    candidates = [c for c in candidates if "_metadata" not in c.name]
    return candidates[0] if candidates else None


def _resolve_time_series_h5_path(json_path: Path) -> Path | None:
    import json

    with open(json_path) as f:
        system_data = json.load(f)

    data_section = system_data.get("data", {})
    filename = data_section.get("time_series_storage_file")
    if not filename:
        return None

    h5_dir = json_path.parent
    time_series_path = Path(filename)
    if time_series_path.is_absolute():
        return time_series_path
    if len(time_series_path.parts) > 1:
        return h5_dir / time_series_path.name
    return h5_dir / filename


def run_sienna_upgrades(
    *,
    json_path: Path | str | None = None,
    store: "DataStore | None" = None,
    ctx: "PluginContext[SiennaConfig]",
) -> Result[None, str]:
    """Run Sienna file upgrades using the plugin context.

    This function is called from SiennaParser.on_upgrade() hook to perform
    any necessary data file upgrades before parsing.

    Either json_path or store must be provided. If json_path is given,
    it takes precedence over store.folder.

    Parameters
    ----------
    json_path : Path | str | None
        Direct path to the JSON file or directory. Takes precedence over store.
    store : DataStore | None
        The data store containing file information. Used as fallback if json_path not provided.
    ctx : PluginContext[SiennaConfig]
        The plugin context with version information.

    Returns
    -------
    Result[None, str]
        Ok(None) on success, Err() with error message on failure.
    """
    if json_path is not None:
        upgrade_path = Path(json_path)
    elif store is not None:
        upgrade_path = store.folder
    else:
        return Err("Either json_path or store must be provided to run_sienna_upgrades")

    logger.debug("Running Sienna upgrades on {}", upgrade_path)
    upgrader = SiennaUpgrader(upgrade_path)
    current_version = getattr(ctx, "current_version", None)

    if current_version is None:
        try:
            current_version = upgrader.version_reader.read_version(upgrade_path)
        except FileNotFoundError:
            logger.debug("No version file found at {}, skipping upgrades", upgrade_path)
            return Ok(None)
        if current_version is None:
            logger.debug("Could not detect version, skipping upgrades")
            return Ok(None)
        logger.debug("Detected current version: {}", current_version)
        if hasattr(ctx, "current_version"):
            ctx.current_version = current_version

    target_version = getattr(ctx, "target_version", None)
    version_strategy = getattr(ctx, "version_strategy", None)

    result = upgrader.upgrade(
        current_version=current_version,
        target_version=target_version,
        strategy=version_strategy,
        upgrade_type=UpgradeType.SYSTEM,
    )
    if result.is_err():
        return Err(str(result.err()))

    json_path_resolved = _resolve_json_path(upgrade_path)
    if json_path_resolved is not None:
        try:
            h5_path = _resolve_time_series_h5_path(json_path_resolved)
        except Exception as e:  # noqa: BLE001
            return Err(f"Failed to inspect JSON for time series metadata upgrade: {e}")
        if h5_path and h5_path.exists():
            h5_upgrade = _upgrade_h5_time_series_metadata(h5_path)
            if h5_upgrade.is_err():
                return Err(str(h5_upgrade.err()))

    return Ok(None)


# Register all upgrade steps by importing the upgrade_steps module.
# This triggers the @SiennaUpgrader.register_step decorators.
_register_upgrade_steps()
