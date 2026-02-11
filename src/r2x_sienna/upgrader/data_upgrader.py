from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, ClassVar

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
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
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

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
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
                        step.func.__name__,
                        step.upgrade_type.name,
                        upgrade_type.name,
                    )
                    continue
                should_upgrade = shall_we_upgrade(step, current_version=original_version, strategy=strategy)
                if should_upgrade.is_err() or not should_upgrade.ok():
                    logger.trace(
                        "Skipping step {} (version check: current={}, target={})",
                        step.func.__name__,
                        original_version,
                        step.target_version,
                    )
                    continue

                logger.debug(
                    "Running upgrade step: {} (target_version={})",
                    step.func.__name__,
                    step.target_version,
                )
                t0 = time.perf_counter()
                try:
                    system_data = step.func(system_data)
                    modified = True
                    steps_run += 1
                except Exception as e:
                    logger.error("Upgrade step {} failed: {}", step.func.__name__, e)
                    return Err(f"Failed {step.func.__name__}: {e}")
                current_version = step.target_version
                logger.debug(
                    "Upgrade step {} completed in {:.2f}s",
                    step.func.__name__,
                    time.perf_counter() - t0,
                )

            if modified:
                try:
                    with open(json_path, "w") as f:
                        json.dump(system_data, f)
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
            logger.debug("Running file upgrade step: {}", step.func.__name__)
            result = run_upgrade_step(self.path, step=step)
            if result.is_err():
                return Err(str(result.err()))
            current_version = step.target_version

        return Ok(self.path)


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
    return Ok(None)


# Register all upgrade steps by importing the upgrade_steps module.
# This triggers the @SiennaUpgrader.register_step decorators.
_register_upgrade_steps()
