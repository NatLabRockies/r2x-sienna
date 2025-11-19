import atexit
import copy
import json
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import IO, Any
from uuid import UUID

import h5py
from infrasys.h5_time_series_storage import HDF5TimeSeriesStorage
from infrasys.serialization import (
    TYPE_METADATA,
    CachedTypeHelper,
    SerializedBaseType,
    SerializedComponentReference,
    SerializedQuantityType,
    SerializedType,
    SerializedTypeMetadata,
)
from infrasys.supplemental_attribute_associations import TABLE_NAME
from infrasys.supplemental_attribute_manager import SupplementalAttributeManager
from infrasys.time_series_manager import TimeSeriesManager
from infrasys.time_series_metadata_store import TimeSeriesMetadataStore
from loguru import logger
from r2x_core import BaseParser, DataFile, DataStore, Err, Ok, ParserError, Result

from r2x_sienna.models.enums import ReserveDirection, ReserveType
from r2x_sienna.models.services import VariableReserve

from .config import SiennaConfig

PARAMETRIZED_TYPES = {
    "ReserveDown": {"direction": ReserveDirection.DOWN},
    "ReserveUp": {"direction": ReserveDirection.UP},
}


class SiennaParser(BaseParser):
    """Sienna parser class."""

    def __init__(
        self,
        config: SiennaConfig | None = None,
        *,
        data_store: DataStore | None = None,
        name: str | None = None,
        auto_add_composed_components: bool = True,
        skip_validation: bool = False,
    ) -> None:
        """Initialize Sienna parser."""
        super().__init__(
            config,
            data_store=data_store,
            name=name,
            auto_add_composed_components=auto_add_composed_components,
            skip_validation=skip_validation,
        )

    def prepare_data(self) -> Result[None, ParserError]:
        """Prepare and normalize configuration and time-related data.

        Initializes internal data structures required for component building.
        Supports reading from stdin_payload when available (r2x-core 0.1.0+).

        Returns
        -------
        Result[None, ParserError]
            Ok() on success, Err() with ParserError on failure
        """
        self.skip_validation: bool = getattr(self.config, "skip_validation", False)
        self.data_information: dict[str, Any] = {}
        self.system_information: dict[str, Any] = {}
        self.component_fields: dict[str, Any] = {}

        # Store stdin_payload if provided (for r2x-core 0.1.0+ pipeline support)
        stdin_payload: IO[str] | IO[bytes] | str | bytes | None = getattr(self, "_stdin_payload", None)
        self._use_stdin = stdin_payload is not None
        if self._use_stdin:
            logger.debug("Sienna parser will read system data from stdin")
        else:
            logger.debug("Sienna parser will read system data from json_path")

        return Ok()

    def _require_config(self) -> SiennaConfig:
        """Return the parser config with a concrete type check."""
        config = self.config
        if not isinstance(config, SiennaConfig):
            raise ValueError("SiennaParser requires a SiennaConfig instance")
        return config

    def build_system_components(self) -> Result[None, ParserError]:
        """Build and add components to the system."""
        self._parse_components()
        self._parse_supplemental_attributes()
        return Ok(None)

    def build_time_series(self) -> Result[None, ParserError]:
        """Build and add time series to the system."""
        try:
            self._h5_manager()
            return Ok(None)
        except Exception as e:
            return Err(ParserError(f"Failed to build time series: {e}"))

    def _parse_components(self) -> None:
        """Create a dictionary by component type."""
        logger.info("Parsing Sienna system")
        self.uuid_map: dict[str, dict] = {}

        # Load system data from stdin or from json_path
        stdin_payload: IO[str] | IO[bytes] | str | bytes | None = getattr(self, "_stdin_payload", None)
        if self._use_stdin:
            logger.debug("Reading system data from stdin_payload")
            # Parse stdin_payload - could be IO, str, or bytes
            if stdin_payload is None:
                raise ValueError("stdin payload not available despite _use_stdin being True")

            if isinstance(stdin_payload, (str, bytes)):
                json_str = stdin_payload.decode() if isinstance(stdin_payload, bytes) else stdin_payload
                system_json = json.loads(json_str)
            else:
                # It's a file-like object
                content = stdin_payload.read()
                json_str = content.decode() if isinstance(content, bytes) else content
                system_json = json.loads(json_str)

            # Extract the system structure - stdin could provide "system" wrapper or direct data
            if "system" in system_json:
                system_data = system_json["system"]
            else:
                system_data = system_json

            json_data = system_data.pop("data", system_data.copy())
        else:
            config = self._require_config()
            if not config.json_path:
                raise ValueError("json_path must be specified in SiennaConfig when not reading from stdin")

            sys_path = Path(config.json_path)
            data_file = DataFile(name="system", fpath=sys_path)
            self.store.add_data(data_file)
            system_data = self.store.read_data(name="system")
            json_data = system_data.pop("data")

        component_data = json_data.pop("components")
        self.data_information = json_data
        components = self._first_pass(component_data)
        self.system_information = system_data
        self.attribute_manager = copy.deepcopy(json_data.get("supplemental_attribute_manager"))
        components_solved = self._resolve_component_references(components)
        self._deserialize_components(components_solved)

    def _first_pass(self, obj, parent_metadata=None):
        if isinstance(obj, dict):
            current_internal = obj.pop("internal", {})
            current_uuid = current_internal.get("uuid", {}).get("value", {})
            if "from" in obj.keys() or "to" in obj.keys():
                obj["from_to"] = obj.pop("from")
                obj["to_from"] = obj.pop("to")
            if "in" in obj.keys() or "out" in obj.keys():
                obj["input"] = obj.pop("in")
                obj["output"] = obj.pop("out")

            if "__metadata__" in obj and parent_metadata is None and current_internal:
                metadata = obj["__metadata__"]
                if metadata["type"] not in self.component_fields:
                    self.component_fields[metadata["type"]] = set(obj.keys())
                obj["__metadata__"] = {
                    "module": "r2x_sienna.models",
                    "type": metadata.get("type"),
                    "serialized_type": "base",
                }
                if parameters := metadata.get("parameters"):
                    for parameter in parameters:
                        if parameter not in PARAMETRIZED_TYPES:
                            breakpoint()
                        obj.update(PARAMETRIZED_TYPES[parameter])

            if "__metadata__" in obj and not current_internal:
                metadata = obj.pop("__metadata__")

            if "value" in obj and len(obj) == 1 and parent_metadata:
                transformed = {
                    "__metadata__": {
                        "module": "r2x_sienna.models",
                        "serialized_type": "composed_component",
                        "uuid": obj["value"],
                    }
                }
                if current_uuid:
                    obj["uuid"] = current_uuid
                    self.uuid_map[current_uuid] = {
                        "type": parent_metadata.get("type", "UnknownType"),
                        "module": parent_metadata.get("module", "r2x_sienna.models"),
                    }
                return transformed

            current_metadata = obj.get("__metadata__")
            for key, value in list(obj.items()):
                obj[key] = self._first_pass(value, current_metadata)

            if current_uuid:
                obj["uuid"] = UUID(current_uuid)
                self.uuid_map[current_uuid] = {
                    "type": current_metadata.get("type", "UnknownType")
                    if current_metadata
                    else "UnknownType",
                    "module": current_metadata.get("module", "r2x_sienna.models")
                    if current_metadata
                    else "r2x_sienna.models",
                }

        elif isinstance(obj, list):
            obj = [self._first_pass(item, parent_metadata) for item in obj]

        return obj

    def _parse_supplemental_attributes(self):
        if not self.attribute_manager:
            logger.warning("Supplemental attributes not found on the system.")
            return
        self.system._supplemental_attr_mgr = SupplementalAttributeManager(self.system._con, initialize=False)
        logger.debug("Parsing supplemental attributes")
        attributes = self._first_pass(self.attribute_manager["attributes"])
        cached_types = CachedTypeHelper()
        for sa_dict in attributes:
            metadata = SerializedTypeMetadata.validate_python(sa_dict[TYPE_METADATA])
            supplemental_attribute_type = cached_types.get_type(metadata)
            values = {x: y for x, y in sa_dict.items() if x != TYPE_METADATA}
            attr = supplemental_attribute_type(**values)
            self.system._supplemental_attr_mgr.add(None, attr, deserialization_in_progress=True)
            cached_types.add_deserialized_type(supplemental_attribute_type)

        cursor = self.system._con.cursor()
        query = f"INSERT INTO {TABLE_NAME}"
        query += "(attribute_uuid, attribute_type, component_uuid, component_type) "
        query += "VALUES(:attribute_uuid, :attribute_type, :component_uuid, :component_type)"
        cursor.executemany(query, self.attribute_manager["associations"])
        cursor.close()
        self.system._con.commit()
        return

    def _resolve_component_references(self, obj):
        if isinstance(obj, dict):
            uuid = obj.get("__metadata__", {}).get("uuid")
            if uuid in self.uuid_map:
                type_info = self.uuid_map[uuid]
                obj["__metadata__"]["module"] = type_info["module"]
                obj["__metadata__"]["type"] = type_info["type"]

            for key, value in obj.items():
                obj[key] = self._resolve_component_references(value)

        elif isinstance(obj, list):
            obj = [self._resolve_component_references(item) for item in obj]

        return obj

    def _deserialize_components(self, components: list[dict[str, Any]]) -> None:
        """Deserialize components from dictionaries and add them to the system."""
        cached_types = CachedTypeHelper()
        skipped_types = self._deserialize_components_first_pass(components, cached_types)
        if skipped_types:
            self._deserialize_components_nested(skipped_types, cached_types)

    def _deserialize_components_first_pass(
        self, components: list[dict], cached_types: CachedTypeHelper
    ) -> dict[type, list[dict[str, Any]]]:
        deserialized_types = set()
        skipped_types: dict[type, list[dict[str, Any]]] = defaultdict(list)
        for component_dict in components:
            component = self._try_deserialize_component(component_dict, cached_types)
            if component is None:
                metadata = SerializedTypeMetadata.validate_python(component_dict[TYPE_METADATA])
                assert isinstance(metadata, SerializedBaseType)
                component_type = cached_types.get_type(metadata)
                skipped_types[component_type].append(component_dict)
            else:
                deserialized_types.add(type(component))

        cached_types.add_deserialized_types(deserialized_types)
        return skipped_types

    def _deserialize_components_nested(
        self,
        skipped_types: dict[type, list[dict[str, Any]]],
        cached_types: CachedTypeHelper,
    ) -> None:
        max_iterations = len(skipped_types)
        for _ in range(max_iterations):
            deserialized_types = set()
            for component_type, components in skipped_types.items():
                component = self._try_deserialize_component(components[0], cached_types)
                if component is None:
                    continue
                if len(components) > 1:
                    for component_dict in components[1:]:
                        component = self._try_deserialize_component(component_dict, cached_types)
                        assert component is not None
                deserialized_types.add(component_type)

            for component_type in deserialized_types:
                skipped_types.pop(component_type)
            cached_types.add_deserialized_types(deserialized_types)

        if skipped_types:
            msg = f"Bug: still have types remaining to be deserialized: {skipped_types.keys()}"
            raise Exception(msg)

    def _try_deserialize_component(self, component: dict[str, Any], cached_types: CachedTypeHelper) -> Any:
        actual_component = None
        values = self._deserialize_fields(component, cached_types)
        if values is None:
            return None

        metadata = SerializedTypeMetadata.validate_python(component[TYPE_METADATA])
        component_type = cached_types.get_type(metadata)
        if component_type == VariableReserve:
            values["reserve_type"] = ReserveType.SPINNING

        if "from_bus" in component_type.model_fields and "arc" in values:
            values["from_bus"] = values["arc"].from_to
            values["to_bus"] = values["arc"].to_from

        actual_component = self.create_component(component_type, **values)
        self.system._components.add(actual_component, deserialization_in_progress=True)
        return actual_component

    def _deserialize_fields(self, component: dict[str, Any], cached_types: CachedTypeHelper) -> dict | None:
        values = {}
        for field, value in component.items():
            if isinstance(value, dict) and TYPE_METADATA in value:
                metadata = SerializedTypeMetadata.validate_python(value[TYPE_METADATA])
                if isinstance(metadata, SerializedComponentReference):
                    composed_value = self._deserialize_composed_value(metadata, cached_types)
                    if composed_value is None:
                        return None
                    values[field] = composed_value
                elif isinstance(metadata, SerializedQuantityType):
                    quantity_type = cached_types.get_type(metadata)
                    values[field] = quantity_type(value=value["value"], units=value["units"])
                else:
                    msg = f"Bug: unhandled type: {field=} {value=}"
                    raise NotImplementedError(msg)
            elif (
                isinstance(value, list)
                and value
                and isinstance(value[0], dict)
                and TYPE_METADATA in value[0]
                and value[0][TYPE_METADATA]["serialized_type"] == SerializedType.COMPOSED_COMPONENT.value
            ):
                metadata = SerializedTypeMetadata.validate_python(value[0][TYPE_METADATA])
                assert isinstance(metadata, SerializedComponentReference)
                composed_values = self._deserialize_composed_list(value, cached_types)
                if composed_values is None:
                    return None
                values[field] = composed_values
            elif field != TYPE_METADATA:
                values[field] = value

        return values

    def _deserialize_composed_value(
        self, metadata: SerializedComponentReference, cached_types: CachedTypeHelper
    ) -> Any:
        component_type = cached_types.get_type(metadata)
        if cached_types.allowed_to_deserialize(component_type):
            return self.system._components.get_by_uuid(metadata.uuid)
        return None

    def _deserialize_composed_list(
        self, components: list[dict[str, Any]], cached_types: CachedTypeHelper
    ) -> list[Any] | None:
        deserialized_components = []
        for component in components:
            metadata = SerializedTypeMetadata.validate_python(component[TYPE_METADATA])
            assert isinstance(metadata, SerializedComponentReference)
            component_type = cached_types.get_type(metadata)
            if cached_types.allowed_to_deserialize(component_type):
                deserialized_components.append(self.system._components.get_by_uuid(metadata.uuid))
            else:
                return None
        return deserialized_components

    def _h5_manager(self):
        """Load HDF5 time series data."""
        try:
            if "time_series_storage_file" not in self.data_information:
                logger.warning(
                    "No time series storage file specified in data_information. Skipping time series loading."
                )
                return

            config = self._require_config()
            if not config.json_path:
                raise ValueError("json_path must be specified in SiennaConfig to load time series data")

            json_path = Path(config.json_path)
            h5_dir = json_path.parent
            time_series_filename = self.data_information["time_series_storage_file"]
            time_series_path = Path(time_series_filename)
            if time_series_path.is_absolute():
                h5_path = time_series_path
            elif len(time_series_path.parts) > 1:
                h5_path = h5_dir / time_series_path.name
            else:
                h5_path = h5_dir / time_series_filename

            if not h5_path.exists():
                logger.warning(f"Time series file not found: {h5_path}. Skipping time series loading.")
                return

            logger.info(f"Found time series file: {h5_path}")
            storage = create_temporary_h5_storage(h5_path)
            conn = storage.get_metadata_store()
            metadata_store = TimeSeriesMetadataStore(con=conn, initialize=False)
            conn.commit()
            metadata_store._load_metadata_into_memory()
            mgr = TimeSeriesManager(con=conn, storage=storage, metadata_store=metadata_store)
            self.system._time_series_mgr = mgr

            logger.info("Successfully loaded time series data")

        except Exception as e:
            logger.warning(f"Failed to load time series data: {e}")


def create_temporary_h5_storage(source_h5_path):
    """
    Create a temporary HDF5 storage instance using an existing file as source.
    The temporary directory will be automatically cleaned up when the process exits.

    Parameters
    ----------
    source_h5_path : str or Path
        Path to the existing HDF5 file

    Returns
    -------
    tuple
        (HDF5TimeSeriesStorage instance, temporary directory Path, data information dict)
    """
    temp_dir = Path(tempfile.mkdtemp())
    atexit.register(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
    dest_h5_path = temp_dir / HDF5TimeSeriesStorage.STORAGE_FILE
    with h5py.File(source_h5_path, "r") as src_file:
        with h5py.File(dest_h5_path, "w") as dest_file:
            for key in src_file.keys():
                src_file.copy(key, dest_file)

    logger.debug("Creating temporary directory at {}", temp_dir)
    storage = HDF5TimeSeriesStorage(directory=temp_dir)
    return storage
