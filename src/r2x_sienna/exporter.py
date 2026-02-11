import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import orjson
from infrasys import TimeSeriesStorageType
from loguru import logger
from r2x_core import Plugin
from rust_ok import Err, Ok, Result

from r2x_sienna.serialization import serialize_component_to_psy

from .plugin_config import SiennaExporterConfig

PARAMETRIZED_OUTPUT_TYPES = {"value_curve", "function_data", "loss"}
OUTPUT_METADATA = {"__metadata__", "internal"}
PARAMETRIZED_FIELDS = {"direction"}


class SiennaExporter(Plugin[SiennaExporterConfig]):
    """Sienna exporter class.

    Exports a System to Sienna PSY JSON format. Requires output_path in config.
    """

    def __init__(self) -> None:
        """Initialize with internal state only."""
        self.should_export_time_series: bool = True
        self.system_data: dict = {}
        self.output_json: dict = {}

    @property
    def output_path(self) -> Path:
        """Get output path from config."""
        return Path(self.config.output_path)

    def on_validate(self) -> Result[None, str]:
        """Validate export configuration.

        Returns
        -------
        Result[None, str]
            Ok(None) on success, Err() with error message on failure
        """
        logger.debug("Validating export config (output_path={})", self.output_path)
        if not self.output_path.parent.exists():
            logger.debug("Creating output directory: {}", self.output_path.parent)
            try:
                self.output_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return Err(f"Failed to create output directory: {e}")

        return Ok(None)

    def on_export(self) -> Result[None, str]:
        """Export system to Sienna JSON format.

        Returns
        -------
        Result[None, str]
            Ok(None) on success, Err() with error message on failure
        """
        try:
            t0 = time.perf_counter()
            logger.info("Exporting system to Sienna PSY format: {}", self.output_path)

            system_information = self.system_data.get(
                "system_information", self._default_system_information()
            )
            self.output_json = {**system_information}
            self.output_json["data"] = self.system_data.get("data_information", {})

            logger.debug("Serializing components to PSY format")
            t_serialize = time.perf_counter()
            components: list[dict[str, Any]] = []
            skipped = 0
            for component in self.system._component_mgr.iter_all():
                serialized = serialize_component_to_psy(component)
                if serialized is not None:
                    components.append(serialized)
                    logger.trace(
                        "Serialized {} '{}'",
                        type(component).__name__,
                        getattr(component, "name", "<unnamed>"),
                    )
                else:
                    logger.trace(
                        "Skipped serialization of {} '{}'",
                        type(component).__name__,
                        getattr(component, "name", "<unnamed>"),
                    )
                    skipped += 1
            logger.info(
                "Serialized {} components in {:.2f}s (skipped {})",
                len(components),
                time.perf_counter() - t_serialize,
                skipped,
            )

            self.output_json["data"]["components"] = components
            self.output_json["data"]["subsystems"] = {}
            self.output_json["data"]["masked_components"] = {}

            logger.debug("Writing JSON output to {}", self.output_path)
            t_write = time.perf_counter()
            dumped_data = orjson.dumps(self.output_json)
            output_size_mb = len(dumped_data) / (1024 * 1024)
            with open(self.output_path, "wb") as f:
                f.write(dumped_data)
            logger.debug("JSON written in {:.2f}s ({:.1f} MB)", time.perf_counter() - t_write, output_size_mb)

            if self.should_export_time_series:
                self._export_time_series()

            logger.info("Export complete in {:.2f}s", time.perf_counter() - t0)
            return Ok(None)
        except Exception as e:
            logger.error("Failed to export system: {}", e)
            return Err(f"Export failed: {e}")

    def _export_time_series(self) -> None:
        """Export time series data to HDF5 format."""
        try:
            logger.debug("Converting time series storage to HDF5")
            t0 = time.perf_counter()
            self.system.convert_storage(time_series_storage_type=TimeSeriesStorageType.HDF5)

            storage_file_path = f"{self.output_path.stem}_time_series_storage.h5"
            full_storage_path = self.output_path.parent / storage_file_path

            import os

            if os.path.exists(full_storage_path):
                os.remove(full_storage_path)
                logger.debug("Removed existing HDF5 storage: {}", full_storage_path)

            logger.debug("Serializing time series to {}", full_storage_path)
            self.system._time_series_mgr.serialize({}, full_storage_path, db_name=self.system.DB_FILENAME)
            self.output_json["data"]["time_series_storage_type"] = (
                "InfrastructureSystems.Hdf5TimeSeriesStorage"
            )
            self.output_json["data"]["time_series_storage_file"] = storage_file_path
            self.output_json["data"]["internal"] = {
                "uuid": {"value": str(uuid4())},
                "ext": {},
                "units_info": None,
            }

            dumped_data = orjson.dumps(self.output_json)
            with open(self.output_path, "wb") as f:
                f.write(dumped_data)

            h5_size_mb = full_storage_path.stat().st_size / (1024 * 1024)
            logger.info(
                "Time series exported to {} ({:.1f} MB) in {:.2f}s",
                storage_file_path,
                h5_size_mb,
                time.perf_counter() - t0,
            )
        except Exception as e:
            logger.error("Failed to export time series: {}", e)
            raise

    def _default_system_information(self) -> dict[str, Any]:
        return {
            "internal": {
                "uuid": {"value": str(uuid4())},
                "ext": {},
                "units_info": None,
            },
            "units_settings": {
                "base_value": 100.0,
                "unit_system": "NATURAL_UNITS",
                "__metadata__": {"module": "InfrastructureSystems", "type": "SystemUnitsSettings"},
            },
            "frequency": 60.0,
            "runchecks": True,
            "metadata": {
                "name": None,
                "description": None,
                "__metadata__": {"module": "PowerSystems", "type": "SystemMetadata"},
            },
            "data_format_version": "5.0.0",
        }


def to_psy(
    config: Any,
    system: Any,
    system_data: dict,
    filename: str,
    /,
    *,
    write_year: int | None = None,
    **kwargs: Any,
) -> Result[None, str]:
    """Legacy function for exporting to Sienna PSY format.

    Note: This function is provided for backwards compatibility.
    New code should use SiennaExporter directly via Plugin.from_context().
    """
    from r2x_core import DataStore, PluginContext

    # Create exporter config with required output_path
    exporter_config = SiennaExporterConfig(
        output_path=str(filename),
        system_base_power=getattr(config, "system_base_power", 100.0),
        scenario=getattr(config, "scenario", "base"),
    )

    ctx: PluginContext[SiennaExporterConfig] = PluginContext(config=exporter_config, system=system)
    store = DataStore(path=Path(filename).parent)
    exporter = SiennaExporter()
    exporter._ctx = ctx  # type: ignore[assignment]
    exporter._store = store  # type: ignore[attr-defined]
    exporter.system_data = system_data

    result = exporter.on_validate()
    if result.is_err():
        raise Exception(f"Validation failed: {result.err()}")

    result = exporter.on_export()
    if result.is_err():
        raise Exception(f"Export failed: {result.err()}")
    return result
