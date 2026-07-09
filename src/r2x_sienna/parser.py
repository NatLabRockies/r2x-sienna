import atexit
import copy
import json
import shutil
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import IO, Any
from uuid import UUID

import h5py
from infrasys import Component
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
from r2x_core import Plugin, System, create_component
from rust_ok import Err, Ok, Result

from r2x_sienna.models.enums import ReserveDirection, ReserveType
from r2x_sienna.models.services import VariableReserve

from .plugin_config import SiennaConfig
from .upgrader.data_upgrader import run_sienna_upgrades

PARAMETRIZED_TYPES = {
    "ReserveDown": {"direction": ReserveDirection.DOWN},
    "ReserveUp": {"direction": ReserveDirection.UP},
}


class _PermFailure:
    """Singleton sentinel for components that can never be deserialized.

    Returned (instead of ``None``) by ``_try_deserialize_component`` and
    propagated through ``_deserialize_fields`` / ``_deserialize_composed_*``
    to signal a *permanent* failure — one that should not be retried.
    """


_PERM_FAILURE = _PermFailure()


class SiennaParser(Plugin[SiennaConfig]):
    """Sienna parser class with explicit SiennaConfig type hint."""

    def __init__(self) -> None:
        """Initialize with internal state only."""
        self._use_stdin: bool = False
        self.data_information: dict[str, Any] = {}
        self.system_information: dict[str, Any] = {}
        self.component_fields: dict[str, Any] = {}
        self.uuid_map: dict[str, dict] = {}
        self.attribute_manager: dict | None = None
        # UUIDs of components that permanently failed to deserialize.  Any
        # component that references one of these via a composed-ref field will
        # also be marked as a permanent failure (for required fields) or will
        # fall back to None (for optional fields).
        self.perm_failed_uuids: set[UUID] = set()
        # (type_name, component_name) pairs for all permanently-failed components,
        # used to raise a descriptive ValueError at the end.
        self.perm_failed_components: list[tuple[str, str]] = []

    def on_prepare(self) -> Result[None, str]:
        """Prepare and normalize configuration and time-related data.

        Initializes internal data structures required for component building.
        Supports reading from stdin_payload when available (r2x-core 0.2.0+).

        Returns
        -------
        Result[None, str]
            Ok(None) on success, Err() with error message on failure
        """
        self.skip_validation: bool = getattr(self.config, "skip_validation", False)

        # Store stdin_payload if provided (for r2x-core pipeline support)
        stdin_payload: IO[str] | IO[bytes] | str | bytes | None = getattr(self, "_stdin_payload", None)
        self._use_stdin = stdin_payload is not None

        config = self._require_config()
        logger.info(
            "Preparing SiennaParser (system_name={}, skip_validation={}, source={})",
            config.system_name or "<default>",
            self.skip_validation,
            "stdin" if self._use_stdin else config.json_path or "<none>",
        )

        return Ok(None)

    def on_upgrade(self) -> Result[System | None, str]:
        """Run Sienna file upgrades before building system.

        Returns
        -------
        Result[System | None, str]
            Ok(None) on success (no early system return), Err() with error message on failure
        """
        config = self._require_config()
        logger.debug("Running Sienna data upgrades for: {}", config.json_path or "<stdin>")
        t0 = time.perf_counter()
        result = run_sienna_upgrades(json_path=config.json_path, ctx=self.ctx)
        elapsed = time.perf_counter() - t0
        if result.is_err():
            logger.error("Sienna upgrades failed after {:.2f}s: {}", elapsed, result.err())
            return Err(str(result.err()))
        logger.debug("Sienna upgrades completed in {:.2f}s", elapsed)
        return Ok(None)

    def on_build(self) -> Result[System, str]:
        """Build the System from parsed data.

        Returns
        -------
        Result[System, str]
            Ok(system) on success, Err() with error message on failure
        """
        try:
            t0 = time.perf_counter()
            system_name = self.config.system_name or "Sienna"
            logger.info("Building Sienna system '{}'", system_name)
            system = System(name=system_name, system_base=self.config.system_base_power or None)
            self._ctx.system = system

            self._parse_components()
            self._parse_supplemental_attributes()
            self._h5_manager()

            elapsed = time.perf_counter() - t0
            component_count = sum(1 for _ in system._component_mgr.iter_all())
            logger.info(
                "Sienna system '{}' built in {:.2f}s ({} components)",
                system_name,
                elapsed,
                component_count,
            )
            return Ok(system)
        except Exception as e:
            return Err(f"Failed to build system: {e}")

    def _require_config(self) -> SiennaConfig:
        """Return the parser config with a concrete type check."""
        config = self.config
        if not isinstance(config, SiennaConfig):
            raise ValueError("SiennaParser requires a SiennaConfig instance")
        return config

    def _parse_components(self) -> None:
        """Create a dictionary by component type."""
        logger.info("Parsing Sienna system components")
        # Load system data from stdin or from json_path
        stdin_payload: IO[str] | IO[bytes] | str | bytes | None = getattr(self, "_stdin_payload", None)
        if self._use_stdin:
            logger.debug("Reading system data from stdin_payload")
            if stdin_payload is None:
                raise ValueError("stdin payload not available despite _use_stdin being True")

            t0 = time.perf_counter()
            if isinstance(stdin_payload, (str, bytes)):
                json_str = stdin_payload.decode() if isinstance(stdin_payload, bytes) else stdin_payload
                system_json = json.loads(json_str)
            else:
                content = stdin_payload.read()
                json_str = content.decode() if isinstance(content, bytes) else content
                system_json = json.loads(json_str)
            logger.debug("Parsed stdin JSON in {:.2f}s", time.perf_counter() - t0)

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
            file_size_mb = sys_path.stat().st_size / (1024 * 1024)
            logger.debug("Loading JSON from {} ({:.1f} MB)", sys_path, file_size_mb)
            t0 = time.perf_counter()
            with open(sys_path) as f:
                system_data = json.load(f)
            logger.debug("JSON parsed in {:.2f}s", time.perf_counter() - t0)
            json_data = system_data.pop("data")

        component_data = json_data.pop("components")
        self.data_information = json_data
        logger.info("Loaded {} raw components from source data", len(component_data))

        logger.debug("Running first pass: normalizing metadata and building UUID map")
        t0 = time.perf_counter()
        components = self._first_pass(component_data)
        logger.debug(
            "First pass complete in {:.2f}s ({} UUIDs mapped, {} component types seen)",
            time.perf_counter() - t0,
            len(self.uuid_map),
            len(self.component_fields),
        )

        self.system_information = system_data
        self.attribute_manager = copy.deepcopy(json_data.get("supplemental_attribute_manager"))

        logger.debug("Resolving component cross-references")
        t0 = time.perf_counter()
        components_solved = self._resolve_component_references(components)
        logger.debug("Reference resolution complete in {:.2f}s", time.perf_counter() - t0)

        logger.debug("Deserializing components into system")
        t0 = time.perf_counter()
        self._deserialize_components(components_solved)
        logger.debug("Component deserialization complete in {:.2f}s", time.perf_counter() - t0)

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
                comp_type = metadata.get("type", "Unknown")
                if comp_type not in self.component_fields:
                    self.component_fields[comp_type] = set(obj.keys())
                    logger.trace("First pass: new component type '{}' with fields: {}", comp_type, obj.keys())
                obj["__metadata__"] = {
                    "module": "r2x_sienna.models",
                    "type": comp_type,
                    "serialized_type": "base",
                }
                if parameters := metadata.get("parameters"):
                    for parameter in parameters:
                        if parameter not in PARAMETRIZED_TYPES:
                            logger.warning("Unknown parametrized type: {}", parameter)
                            continue
                        logger.trace(
                            "First pass: applying parametrized type '{}' to '{}'", parameter, comp_type
                        )
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
                    logger.trace(
                        "First pass: mapped composed ref uuid={} -> type={}",
                        current_uuid[:8] if isinstance(current_uuid, str) else current_uuid,
                        parent_metadata.get("type", "UnknownType"),
                    )
                return transformed

            current_metadata = obj.get("__metadata__")
            for key, value in list(obj.items()):
                obj[key] = self._first_pass(value, current_metadata)

            if current_uuid:
                obj["uuid"] = UUID(current_uuid)
                resolved_type = (
                    current_metadata.get("type", "UnknownType") if current_metadata else "UnknownType"
                )
                self.uuid_map[current_uuid] = {
                    "type": resolved_type,
                    "module": current_metadata.get("module", "r2x_sienna.models")
                    if current_metadata
                    else "r2x_sienna.models",
                }
                logger.trace(
                    "First pass: registered uuid={} as type={}",
                    current_uuid[:8] if isinstance(current_uuid, str) else current_uuid,
                    resolved_type,
                )

        elif isinstance(obj, list):
            obj = [self._first_pass(item, parent_metadata) for item in obj]

        return obj

    def _parse_supplemental_attributes(self) -> None:
        if not self.attribute_manager:
            logger.debug("No supplemental attributes found on the system, skipping")
            return

        t0 = time.perf_counter()
        self.system._supplemental_attr_mgr = SupplementalAttributeManager(self.system._con, initialize=False)
        attributes = self._first_pass(self.attribute_manager["attributes"])
        logger.debug("Deserializing {} supplemental attributes", len(attributes))

        cached_types = CachedTypeHelper()
        for sa_dict in attributes:
            metadata = SerializedTypeMetadata.validate_python(sa_dict[TYPE_METADATA])
            supplemental_attribute_type = cached_types.get_type(metadata)
            values = {x: y for x, y in sa_dict.items() if x != TYPE_METADATA}
            logger.trace("Deserializing supplemental attribute: {}", supplemental_attribute_type.__name__)
            attr = supplemental_attribute_type(**values)
            self.system._supplemental_attr_mgr.add(None, attr, deserialization_in_progress=True)
            cached_types.add_deserialized_type(supplemental_attribute_type)

        associations = self.attribute_manager["associations"]
        cursor = self.system._con.cursor()
        query = f"INSERT INTO {TABLE_NAME}"
        query += "(attribute_uuid, attribute_type, component_uuid, component_type) "
        query += "VALUES(:attribute_uuid, :attribute_type, :component_uuid, :component_type)"
        cursor.executemany(query, associations)
        cursor.close()
        self.system._con.commit()
        logger.info(
            "Attached {} supplemental attributes with {} associations in {:.2f}s",
            len(attributes),
            len(associations),
            time.perf_counter() - t0,
        )

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
        logger.debug("Deserializing {} component dicts (first pass: simple types)", len(components))
        skipped_types = self._deserialize_components_first_pass(components, cached_types)
        if skipped_types:
            skipped_count = sum(len(v) for v in skipped_types.values())
            logger.debug(
                "First pass deferred {} components across {} types, running nested resolution",
                skipped_count,
                len(skipped_types),
            )
            self._deserialize_components_nested(skipped_types, cached_types)
        else:
            logger.debug("All components deserialized in first pass")

    def _deserialize_components_first_pass(
        self, components: list[dict], cached_types: CachedTypeHelper
    ) -> dict[type, list[dict[str, Any]]]:
        deserialized_types: set[type] = set()
        skipped_types: dict[type, list[dict[str, Any]]] = defaultdict(list)
        created_count = 0
        perm_failed_count = 0
        for component_dict in components:
            component = self._try_deserialize_component(component_dict, cached_types)
            if component is _PERM_FAILURE:
                # Permanently failed — record UUID so downstream deps can fail fast.
                type_name = (
                    component_dict.get(TYPE_METADATA, {}).get("type", "?")
                    if isinstance(component_dict.get(TYPE_METADATA), dict)
                    else "?"
                )
                self._record_perm_failure(component_dict, type_name)
                perm_failed_count += 1
            elif component is None:
                metadata = SerializedTypeMetadata.validate_python(component_dict[TYPE_METADATA])
                assert isinstance(metadata, SerializedBaseType)
                component_type = cached_types.get_type(metadata)
                skipped_types[component_type].append(component_dict)
            else:
                deserialized_types.add(type(component))
                created_count += 1

        cached_types.add_deserialized_types(deserialized_types)
        logger.debug(
            "First pass: deserialized {} components ({} types), skipped {} ({} types), perm-failed {}",
            created_count,
            len(deserialized_types),
            sum(len(v) for v in skipped_types.values()),
            len(skipped_types),
            perm_failed_count,
        )
        return skipped_types

    def _deserialize_components_nested(
        self,
        skipped_types: dict[type, list[dict[str, Any]]],
        cached_types: CachedTypeHelper,
    ) -> None:
        max_iterations = len(skipped_types) + 1
        logger.debug(
            "Nested deserialization: {} deferred types, max {} iterations",
            len(skipped_types),
            max_iterations,
        )

        for iteration in range(max_iterations):
            deserialized_types: set[type] = set()
            remaining: dict[type, list[dict[str, Any]]] = {}
            perm_failed_this_iter = 0

            for component_type, components in skipped_types.items():
                pending: list[dict[str, Any]] = []
                for component_dict in components:
                    component = self._try_deserialize_component(component_dict, cached_types)
                    if component is _PERM_FAILURE:
                        # Permanently dead — record UUID, discard from retry queue.
                        self._record_perm_failure(component_dict, component_type.__name__)
                        perm_failed_this_iter += 1
                    elif component is None:
                        pending.append(component_dict)

                if pending:
                    # Some instances of this type still have unresolved references; retry next iteration
                    remaining[component_type] = pending
                else:
                    # All instances of this type are now in the system (or permanently failed)
                    deserialized_types.add(component_type)

            skipped_types = remaining
            cached_types.add_deserialized_types(deserialized_types)

            resolved_names = [t.__name__ for t in deserialized_types]
            logger.debug(
                "Nested iteration {}: resolved {} types ({}), {} remaining, {} perm-failed",
                iteration + 1,
                len(deserialized_types),
                ", ".join(resolved_names) if resolved_names else "none",
                len(skipped_types),
                perm_failed_this_iter,
            )
            if not skipped_types:
                break

            if not deserialized_types and not perm_failed_this_iter:
                # Mirror PSY.jl's explicit ordering strategy: break the cycle by
                # creating stuck components with empty lists for composed-list fields
                # that reference types not yet in the system.
                logger.debug(
                    "Nested loop stuck at {} remaining types; attempting cycle-breaking "
                    "partial deserialization (empty lists for unresolvable composed-list fields)",
                    len(skipped_types),
                )
                partial_resolved, skipped_types = self._nested_pass(skipped_types, cached_types, partial=True)
                cached_types.add_deserialized_types(partial_resolved)
                if partial_resolved:
                    logger.debug(
                        "Cycle-breaking resolved {} types: {}",
                        len(partial_resolved),
                        [t.__name__ for t in partial_resolved],
                    )
                else:
                    logger.debug("Cycle-breaking made no progress; stopping nested loop")
                    break
                if not skipped_types:
                    break

        if skipped_types or self.perm_failed_components:
            # Build error summary from BOTH still-stuck (unresolvable deps) AND
            # permanently-failed (invalid data / cascading dead ref) components.
            failed_by_type: dict[str, int] = {}

            # Stuck components (unresolvable deps after all iterations)
            for comp_type, comp_dicts in skipped_types.items():
                failed_by_type[comp_type.__name__] = failed_by_type.get(comp_type.__name__, 0) + len(
                    comp_dicts
                )
                for comp_dict in comp_dicts:
                    name = comp_dict.get("name", "<unnamed>")
                    logger.error(
                        "Failed to deserialize {} component '{}'. "
                        "This may be due to invalid data that wasn't caught by the upgrader.",
                        comp_type.__name__,
                        name,
                    )

            # Permanently-failed components (logged as WARNING by _try_deserialize_component)
            for type_name, comp_name in self.perm_failed_components:
                failed_by_type[type_name] = failed_by_type.get(type_name, 0) + 1

            total = sum(failed_by_type.values())
            type_summary = ", ".join(f"{t}: {n}" for t, n in failed_by_type.items())
            # Include a sampling of names for easy identification.
            name_sample = ", ".join(
                name for _, name in self.perm_failed_components[:10] if name != "<unnamed>"
            )
            msg = (
                f"Failed to deserialize {total} component(s) ({type_summary})"
                + (f" — including: {name_sample}" if name_sample else "")
                + ". Check the log for per-component details."
            )
            raise ValueError(msg)

    def _nested_pass(
        self,
        skipped_types: dict[type, list[dict[str, Any]]],
        cached_types: CachedTypeHelper,
        partial: bool = False,
    ) -> tuple[set[type], dict[type, list[dict[str, Any]]]]:
        """Run one deserialization iteration over skipped_types.

        Parameters
        ----------
        partial:
            When True, composed-list fields whose references cannot be resolved are
            silently set to empty lists instead of deferring the whole component.
            Use this to break circular dependencies (e.g. HydroTurbine ↔ HydroReservoir).
        """
        deserialized_types: set[type] = set()
        remaining: dict[type, list[dict[str, Any]]] = {}
        for component_type, components in skipped_types.items():
            pending: list[dict[str, Any]] = []
            for component_dict in components:
                component = self._try_deserialize_component(component_dict, cached_types, partial=partial)
                if component is _PERM_FAILURE:
                    self._record_perm_failure(component_dict, component_type.__name__)
                elif component is None:
                    pending.append(component_dict)
            if pending:
                remaining[component_type] = pending
            else:
                deserialized_types.add(component_type)
        return deserialized_types, remaining

    def _try_deserialize_component(
        self, component: dict[str, Any], cached_types: CachedTypeHelper, partial: bool = False
    ) -> Any:
        """Attempt to deserialize one component dict.

        Returns
        -------
        component object
            Successfully created and added to the system.
        None
            One or more deps are not in the system yet; retry next iteration.
        _PERM_FAILURE (sentinel)
            The component can never be created (type unknown, data invalid, or a
            required dep is permanently dead).  The caller must NOT retry it.
        """
        values = self._deserialize_fields(component, cached_types, partial=partial)
        if values is None:
            return None
        if isinstance(values, _PermFailure):
            return _PERM_FAILURE

        try:
            metadata = SerializedTypeMetadata.validate_python(component[TYPE_METADATA])
            component_type_raw = cached_types.get_type(metadata)
        except Exception as exc:
            logger.warning(
                "Cannot resolve type for component ({}): {}",
                component.get(TYPE_METADATA, {}).get("type", "?"),
                exc,
            )
            return _PERM_FAILURE

        if not isinstance(component_type_raw, type) or not issubclass(component_type_raw, Component):
            logger.warning(
                "Skipped unsupported deserialized type {}.{}",
                metadata.module,
                metadata.type,
            )
            return _PERM_FAILURE

        component_type: type[Component] = component_type_raw
        component_name = values.get("name", "<unnamed>")
        logger.trace("Deserializing {} '{}'", component_type.__name__, component_name)

        if component_type == VariableReserve:
            values["reserve_type"] = ReserveType.SPINNING

        if "from_bus" in component_type.model_fields and "arc" in values:
            values["from_bus"] = values["arc"].from_to
            values["to_bus"] = values["arc"].to_from

        result = create_component(component_type, skip_validation=self.skip_validation, **values)
        if result.is_err():
            logger.warning(
                "Failed to create component {} '{}': {}",
                component_type.__name__,
                component_name,
                result.err(),
            )
            return _PERM_FAILURE
        actual_component = result.ok()
        if actual_component is not None:
            self.system._components.add(actual_component, deserialization_in_progress=True)
            logger.trace(
                "Created {} '{}' (uuid={})",
                component_type.__name__,
                component_name,
                getattr(actual_component, "uuid", "?"),
            )
        return actual_component

    def _record_perm_failure(self, component_dict: dict[str, Any], type_name: str) -> None:
        """Register a component as permanently failed and update tracking state."""
        uuid = component_dict.get("uuid")
        if isinstance(uuid, UUID):
            self.perm_failed_uuids.add(uuid)
        comp_name = component_dict.get("name", "<unnamed>")
        self.perm_failed_components.append((type_name, comp_name))

    @staticmethod
    def _is_optional_field(component_type: type, field_name: str) -> bool:
        """Return True if *field_name* on *component_type* accepts None values.

        Uses the Pydantic v2 FieldInfo to check whether NoneType appears in
        the field's type annotation, which means the field can be omitted /
        set to None without causing a validation error.
        """
        import typing

        field_info = getattr(component_type, "model_fields", {}).get(field_name)
        if field_info is None:
            return True  # Unknown field — create_component will filter it out anyway
        return type(None) in typing.get_args(field_info.annotation)

    def _deserialize_fields(
        self, component: dict[str, Any], cached_types: CachedTypeHelper, partial: bool = False
    ) -> dict | _PermFailure | None:
        """Deserialize all fields of a component dict.

        Returns
        -------
        dict
            Resolved field values ready to be passed to create_component.
        None
            One or more composed-ref fields reference a type/UUID that isn't in
            the system yet.  The caller should defer and retry this component.
        _PERM_FAILURE (sentinel object)
            A composed-ref field references a UUID that is permanently dead AND
            the field is required (does not accept None).  The component can
            never be created; the caller should discard it permanently.
        """
        values: dict[str, Any] = {}
        comp_type_hint = (
            component.get(TYPE_METADATA, {}).get("type", "?")
            if isinstance(component.get(TYPE_METADATA), dict)
            else "?"
        )

        # Resolve the component's own type so we can check field optionality
        # when a dead-UUID is encountered.
        component_type: type | None = None
        if isinstance(component.get(TYPE_METADATA), dict):
            try:
                _meta = SerializedTypeMetadata.validate_python(component[TYPE_METADATA])
                component_type = cached_types.get_type(_meta)
            except Exception:
                pass

        for field, value in component.items():
            if isinstance(value, dict) and TYPE_METADATA in value:
                metadata = SerializedTypeMetadata.validate_python(value[TYPE_METADATA])
                if isinstance(metadata, SerializedComponentReference):
                    logger.trace(
                        "Field '{}' on {}: resolving composed ref uuid={}",
                        field,
                        comp_type_hint,
                        metadata.uuid,
                    )
                    composed_value = self._deserialize_composed_value(metadata, cached_types)
                    if composed_value is _PERM_FAILURE:
                        # The referenced component is permanently dead.
                        # If the field allows None we can silently use None
                        # and continue; otherwise this component is dead too.
                        if component_type and self._is_optional_field(component_type, field):
                            logger.trace(
                                "Field '{}' on {}: dead ref, field is optional — using None",
                                field,
                                comp_type_hint,
                            )
                            values[field] = None
                        else:
                            logger.trace(
                                "Field '{}' on {}: dead ref, field is required — cascading failure",
                                field,
                                comp_type_hint,
                            )
                            return _PERM_FAILURE
                    elif composed_value is None:
                        logger.trace(
                            "Field '{}' on {}: composed ref not yet available, deferring",
                            field,
                            comp_type_hint,
                        )
                        return None
                    else:
                        values[field] = composed_value
                elif isinstance(metadata, SerializedQuantityType):
                    quantity_type = cached_types.get_type(metadata)
                    values[field] = quantity_type(value=value["value"], units=value["units"])
                    logger.trace(
                        "Field '{}' on {}: deserialized quantity {}={} {}",
                        field,
                        comp_type_hint,
                        quantity_type.__name__,
                        value["value"],
                        value["units"],
                    )
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
                logger.trace(
                    "Field '{}' on {}: resolving composed list ({} items)", field, comp_type_hint, len(value)
                )
                composed_values = self._deserialize_composed_list(value, cached_types, partial=partial)
                if composed_values is _PERM_FAILURE:
                    # One or more items in the list are permanently dead.
                    # Optional list fields fall back to an empty list; required
                    # list fields cascade the permanent failure.
                    if component_type and self._is_optional_field(component_type, field):
                        logger.trace(
                            "Field '{}' on {}: dead list ref, field is optional — using []",
                            field,
                            comp_type_hint,
                        )
                        values[field] = []
                    else:
                        logger.trace(
                            "Field '{}' on {}: dead list ref, field is required — cascading failure",
                            field,
                            comp_type_hint,
                        )
                        return _PERM_FAILURE
                elif composed_values is None:
                    logger.trace(
                        "Field '{}' on {}: composed list not yet available, deferring", field, comp_type_hint
                    )
                    return None
                else:
                    values[field] = composed_values
            elif field != TYPE_METADATA:
                values[field] = value

        return values

    def _deserialize_composed_value(
        self, metadata: SerializedComponentReference, cached_types: CachedTypeHelper
    ) -> Any:
        # Fast-path: UUID is permanently dead — caller decides whether to use None
        # (optional field) or propagate the failure (required field).
        if metadata.uuid in self.perm_failed_uuids:
            logger.trace(
                "Composed ref permanently failed: uuid={} (in perm_failed_uuids)",
                metadata.uuid,
            )
            return _PERM_FAILURE
        component_type = cached_types.get_type(metadata)
        if cached_types.allowed_to_deserialize(component_type):
            try:
                resolved = self.system._components.get_by_uuid(metadata.uuid)
            except Exception:
                # The type is known but this specific instance isn't in the system yet
                # (another instance of the same type succeeded first-pass, marking the type
                # as allowed, while this UUID is still pending in skipped_types).
                logger.trace(
                    "Composed ref deferred: {} uuid={} (type allowed but UUID not yet in system)",
                    component_type.__name__,
                    metadata.uuid,
                )
                return None
            logger.trace("Resolved composed ref: {} uuid={}", component_type.__name__, metadata.uuid)
            return resolved
        logger.trace(
            "Composed ref deferred: {} uuid={} (type not yet deserialized)",
            component_type.__name__,
            metadata.uuid,
        )
        return None

    def _deserialize_composed_list(
        self, components: list[dict[str, Any]], cached_types: CachedTypeHelper, partial: bool = False
    ) -> list[Any] | _PermFailure | None:
        deserialized_components: list[Any] = []
        for component in components:
            metadata = SerializedTypeMetadata.validate_python(component[TYPE_METADATA])
            assert isinstance(metadata, SerializedComponentReference)

            # Permanently-dead UUID: skip in partial/cycle-breaking mode; otherwise
            # signal failure so the caller can decide (optional list → [] or cascade).
            if metadata.uuid in self.perm_failed_uuids:
                if partial:
                    logger.trace(
                        "Composed list partial: {} uuid={} permanently failed, skipping item",
                        metadata.uuid,
                    )
                    continue
                logger.trace(
                    "Composed list dead ref: {} uuid={} permanently failed",
                    metadata.uuid,
                )
                return _PERM_FAILURE

            component_type = cached_types.get_type(metadata)
            if cached_types.allowed_to_deserialize(component_type):
                try:
                    deserialized_components.append(self.system._components.get_by_uuid(metadata.uuid))
                except Exception:
                    # The type is known but this specific UUID is still pending
                    # (another instance of the same type succeeded earlier).
                    if partial:
                        logger.trace(
                            "Composed list partial: {} uuid={} not yet in system, skipping item",
                            component_type.__name__,
                            metadata.uuid,
                        )
                        continue
                    logger.trace(
                        "Composed list deferred: {} uuid={} (type allowed but UUID not yet in system)",
                        component_type.__name__,
                        metadata.uuid,
                    )
                    return None
            else:
                if partial:
                    # Type not yet deserialized; skip item in cycle-breaking mode
                    logger.trace(
                        "Composed list partial: {} uuid={} type not yet deserialized, skipping item",
                        component_type.__name__,
                        metadata.uuid,
                    )
                    continue
                logger.trace(
                    "Composed list deferred: {} uuid={} not yet available",
                    component_type.__name__,
                    metadata.uuid,
                )
                return None
        logger.trace(
            "Resolved composed list: {} items{}",
            len(deserialized_components),
            " (partial)" if partial else "",
        )
        return deserialized_components

    def _h5_manager(self) -> None:
        """Load HDF5 time series data."""
        try:
            if "time_series_storage_file" not in self.data_information:
                logger.debug("No time_series_storage_file in data_information, skipping HDF5 loading")
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
                logger.warning("Time series file not found: {}. Skipping HDF5 loading.", h5_path)
                return

            file_size_mb = h5_path.stat().st_size / (1024 * 1024)
            logger.info("Loading HDF5 time series from {} ({:.1f} MB)", h5_path, file_size_mb)
            t0 = time.perf_counter()
            storage = create_temporary_h5_storage(h5_path)
            conn = storage.get_metadata_store()
            metadata_store = TimeSeriesMetadataStore(con=conn, initialize=False)
            conn.commit()
            metadata_store._load_metadata_into_memory()
            mgr = TimeSeriesManager(con=conn, storage=storage, metadata_store=metadata_store)
            self.system._time_series_mgr = mgr
            logger.info("HDF5 time series loaded in {:.2f}s", time.perf_counter() - t0)

        except Exception as e:
            logger.error("Failed to load time series data: {}", e)


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
    logger.trace("Copying HDF5 from {} to temp {}", source_h5_path, dest_h5_path)
    t0 = time.perf_counter()
    with h5py.File(source_h5_path, "r") as src_file:
        with h5py.File(dest_h5_path, "w") as dest_file:
            for key in src_file.keys():
                src_file.copy(key, dest_file)
            logger.trace("Copied {} HDF5 groups to temp storage", len(list(src_file.keys())))

    logger.debug("Created temporary HDF5 storage at {} in {:.2f}s", temp_dir, time.perf_counter() - t0)
    storage = HDF5TimeSeriesStorage(directory=temp_dir)
    return storage
