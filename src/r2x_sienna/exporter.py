from pathlib import Path
from typing import Any
from uuid import uuid4

import orjson
from infrasys import TimeSeriesStorageType
from loguru import logger
from r2x_core.exceptions import ExporterError
from r2x_core.exporter import BaseExporter
from r2x_core.result import Err, Ok, Result

from r2x_sienna.serialization import serialize_component_to_psy

PARAMETRIZED_OUTPUT_TYPES = {"value_curve", "function_data", "loss"}
OUTPUT_METADATA = {"__metadata__", "internal"}
PARAMETRIZED_FIELDS = {"direction"}


class SiennaExporter(BaseExporter):
    def __init__(
        self,
        config,
        system,
        /,
        *,
        data_store=None,
        system_data=None,
        output_path=None,
        export_time_series=True,
        **kwargs,
    ):
        self.should_export_time_series = export_time_series
        self.system_data = system_data or {}
        self.output_path = output_path
        self.output_json = {}

        # Pass filtered kwargs to parent to avoid overwriting methods
        # Remove any kwargs that might conflict with our methods or attributes
        filtered_kwargs = {
            k: v for k, v in kwargs.items() if k not in {"export_time_series", "system_data", "output_path"}
        }
        super().__init__(config, system, data_store=data_store, **filtered_kwargs)

    def setup_configuration(self) -> Result[None, ExporterError]:
        if self.output_path is None:
            return Err(ExporterError("output_path is required"))

        if not isinstance(self.output_path, Path):
            self.output_path = Path(self.output_path)

        if not self.output_path.parent.exists():
            try:
                self.output_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return Err(ExporterError(f"Failed to create output directory: {e}"))

        return Ok(None)

    def prepare_export(self) -> Result[None, ExporterError]:
        try:
            system_information = self.system_data.get(
                "system_information", self._default_system_information()
            )
            self.output_json = {**system_information}
            self.output_json["data"] = self.system_data.get("data_information", {})

            components = []
            for component in self.system._component_mgr.iter_all():
                serialized = serialize_component_to_psy(component)
                if serialized is not None:
                    components.append(serialized)

            self.output_json["data"]["components"] = components
            self.output_json["data"]["subsystems"] = {}
            self.output_json["data"]["masked_components"] = {}

            dumped_data = orjson.dumps(self.output_json)
            with open(self.output_path, "wb") as f:
                f.write(dumped_data)

            return Ok(None)
        except Exception as e:
            logger.error("Failed to export system: {}", e)
            return Err(ExporterError(f"Export failed: {e}"))

    def export_time_series(self) -> Result[None, ExporterError]:
        if not self.should_export_time_series:
            logger.debug("Time series export disabled, skipping")
            return Ok(None)

        try:
            self.system.convert_storage(time_series_storage_type=TimeSeriesStorageType.HDF5)

            storage_file_path = f"{self.output_path.stem}_time_series_storage.h5"
            full_storage_path = self.output_path.parent / storage_file_path

            import os

            if os.path.exists(full_storage_path):
                os.remove(full_storage_path)
                logger.debug(f"Removed existing storage file: {full_storage_path}")

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

            return Ok(None)
        except Exception as e:
            logger.error("Failed to export time series: {}", e)
            return Err(ExporterError(f"Time series export failed: {e}"))

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
            "data_format_version": "4.0.0",
        }


def to_psy(config, system, system_data, filename, /, *, write_year=None, **kwargs):
    exporter = SiennaExporter(config, system, system_data=system_data, output_path=filename, **kwargs)
    result = exporter.export()
    if result.is_err():
        raise Exception(f"Export failed: {result.error}")
    return result
