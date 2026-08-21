import uuid
from typing import Any

from infrasys.value_curves import LinearCurve
from loguru import logger
from r2x_core import UpgradeType

from r2x_sienna.models import HydroReservoirCost, ReservoirDataType
from r2x_sienna.models.enums import PrimeMoversType

from .data_upgrader import SiennaUpgrader


def _patch_ac_branch(comp: dict[str, Any]) -> None:
    """Fill in missing rating_b and rating_c fields on an AC branch component in place."""
    comp_name = comp.get("name", "<unknown>")
    comp_type = comp.get("__metadata__", {}).get("type", "<unknown>")
    rating = comp.get("rating") or 0.0
    for field in ("rating_b", "rating_c"):
        if comp.get(field) is None:
            logger.warning(
                "Component {} ({}) has no {} defined. Assuming {} = rating = {}.",
                comp_name,
                comp_type,
                field,
                field,
                rating,
            )
            comp[field] = rating


def _get_ref_uuid(ref: Any) -> str | None:
    """Extract a UUID string from a component reference dict.

    Handles both the ``{"value": "uuid"}`` format (PSY4/infrasys composed refs)
    and the ``{"__metadata__": {"uuid": "..."}}`` format (PSY5 serialization).
    """
    if not isinstance(ref, dict):
        return None
    if "value" in ref:
        return ref["value"]
    return ref.get("__metadata__", {}).get("uuid")


def _build_bus_voltage_map(components: list[dict[str, Any]]) -> dict[str, float]:
    """Return {uuid: base_voltage} for every ACBus in *components*."""
    return {
        comp["internal"]["uuid"]["value"]: comp.get("base_voltage", 0.0)
        for comp in components
        if comp.get("__metadata__", {}).get("type") == "ACBus" and "internal" in comp
    }


def _build_arc_to_bus_map(
    components: list[dict[str, Any]],
) -> dict[str, tuple[str | None, str | None]]:
    """Return {arc_uuid: (from_bus_uuid, to_bus_uuid)} for every Arc in *components*."""
    arc_map: dict[str, tuple[str | None, str | None]] = {}
    for comp in components:
        if comp.get("__metadata__", {}).get("type") != "Arc":
            continue
        arc_uuid = _get_ref_uuid(comp.get("internal", {}).get("uuid", {}))
        if arc_uuid:
            arc_map[arc_uuid] = (
                _get_ref_uuid(comp.get("from", {})),
                _get_ref_uuid(comp.get("to", {})),
            )
    return arc_map


def _patch_two_winding_transformer(
    comp: dict[str, Any],
    bus_voltage_map: dict[str, float],
    arc_to_bus_map: dict[str, tuple[str | None, str | None]],
    system_base_power: float,
) -> None:
    """Apply common two-winding transformer field fixes in place."""
    comp_name = comp.get("name", "<unknown>")
    comp_type = comp.get("__metadata__", {}).get("type", "<unknown>")

    # primary_shunt: float to Complex dict upgrade
    if isinstance(comp.get("primary_shunt"), float):
        comp["primary_shunt"] = {"real": comp["primary_shunt"], "imag": 0.0}

    # Resolve primary/secondary voltages from the connected buses via the Arc object
    primary_voltage = 0.0
    secondary_voltage = 0.0
    arc_uuid = _get_ref_uuid(comp.get("arc", {}))
    if arc_uuid:
        from_uuid, to_uuid = arc_to_bus_map.get(arc_uuid, (None, None))
        primary_voltage = bus_voltage_map.get(from_uuid or "", 0.0)
        secondary_voltage = bus_voltage_map.get(to_uuid or "", 0.0)

    # Set rating_b and rating_c to rating if they are missing
    rating = comp.get("rating") or 0.0
    defaults: dict[str, Any] = {
        "rating_b": rating,
        "rating_c": rating,
        "base_power": system_base_power,
        "base_voltage_primary": primary_voltage,
        "base_voltage_secondary": secondary_voltage,
    }
    for field, default in defaults.items():
        if not comp.get(field):
            logger.warning(
                "Component {} ({}) has no {} defined. Assuming {} = {}.",
                comp_name,
                comp_type,
                field,
                field,
                default,
            )
            comp[field] = default


def _patch_three_winding_transformer(
    comp: dict[str, Any],
    bus_voltage_map: dict[str, float],
    arc_to_bus_map: dict[str, tuple[str | None, str | None]],
    system_base_power: float,
) -> None:
    """Apply common three-winding transformer field fixes in place."""
    comp_name = comp.get("name", "<unknown>")
    comp_type = comp.get("__metadata__", {}).get("type", "<unknown>")

    # Validate known field ranges and warn if out of bounds
    field_ranges: dict[str, tuple[float, float]] = {
        "x_secondary": (-2, 4),
        "x_tertiary": (-2, 4),
        "x_23": (-2, 4),
        "x_13": (0, 4),
        "r_23": (0, 4),
        "r_13": (0, 4),
    }
    for field, (min_val, max_val) in field_ranges.items():
        value = comp.get(field)
        if value is not None and (value < min_val or value > max_val):
            logger.warning(
                "Component {} ({}) has a {} of {}, which is outside the valid range [{}, {}].",
                comp_name,
                comp_type,
                field,
                value,
                min_val,
                max_val,
            )

    def _voltage_from_arc(arc_key: str) -> float:
        arc_uuid = _get_ref_uuid(comp.get(arc_key, {}))
        if arc_uuid:
            from_uuid, _ = arc_to_bus_map.get(arc_uuid, (None, None))
            return bus_voltage_map.get(from_uuid or "", 0.0)
        return 0.0

    defaults: dict[str, Any] = {
        "base_power_12": system_base_power,
        "base_power_23": system_base_power,
        "base_power_13": system_base_power,
        "base_voltage_primary": _voltage_from_arc("primary_star_arc"),
        "base_voltage_secondary": _voltage_from_arc("secondary_star_arc"),
        "base_voltage_tertiary": _voltage_from_arc("tertiary_star_arc"),
    }
    for field, default in defaults.items():
        if comp.get(field) is None:
            logger.warning(
                "Component {} ({}) has no {} defined. Assuming {} = {}.",
                comp_name,
                comp_type,
                field,
                field,
                default,
            )
            comp[field] = default


def _coerce_coordinate_value(value: Any, component_name: str) -> float:
    """Return a valid float coordinate, coercing invalid values to 0.0."""
    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            try:
                return float(stripped)
            except ValueError:
                pass

    logger.warning(
        "GeographicInfo component '{}' has invalid coordinate value '{}'. Defaulting to 0.0.",
        component_name,
        value,
    )
    return 0.0


def _sanitize_geojson_coordinates(
    raw_coordinates: Any, component_name: str
) -> list[float] | list[list[float]]:
    """Normalize GeoJSON coordinates into a Pydantic-compatible list shape."""
    if not isinstance(raw_coordinates, list) or not raw_coordinates:
        logger.warning(
            "GeographicInfo component '{}' has invalid coordinates '{}'. Defaulting to [0.0, 0.0].",
            component_name,
            raw_coordinates,
        )
        return [0.0, 0.0]

    if all(not isinstance(item, list) for item in raw_coordinates):
        longitude = _coerce_coordinate_value(
            raw_coordinates[0] if len(raw_coordinates) > 0 else None, component_name
        )
        latitude = _coerce_coordinate_value(
            raw_coordinates[1] if len(raw_coordinates) > 1 else None, component_name
        )
        return [longitude, latitude]

    if all(isinstance(item, list) for item in raw_coordinates):
        sanitized_nested: list[list[float]] = []
        for point in raw_coordinates:
            if not point:
                sanitized_nested.append([0.0, 0.0])
                continue
            longitude = _coerce_coordinate_value(point[0] if len(point) > 0 else None, component_name)
            latitude = _coerce_coordinate_value(point[1] if len(point) > 1 else None, component_name)
            sanitized_nested.append([longitude, latitude])
        return sanitized_nested

    logger.warning(
        "GeographicInfo component '{}' has mixed coordinate nesting '{}'. Defaulting to [0.0, 0.0].",
        component_name,
        raw_coordinates,
    )
    return [0.0, 0.0]


def system_data_has_right_keys(system_data: dict[str, Any]) -> bool:
    return bool(system_data.get("data", {}).get("components"))


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=100)
def upgrade_hydro_energy_reservoir(system_data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade HydroEnergyReservoir components into HydroReservoir and HydroTurbine components.

    This mutates system_data in place by replacing each HydroEnergyReservoir entry with
    a pair of new components: one HydroReservoir and one HydroTurbine.
    """
    if not system_data_has_right_keys(system_data):
        logger.debug("No data found. Skipping step")
        return system_data

    new_components: list[dict[str, Any]] = []

    for comp in system_data["data"]["components"]:
        if comp["__metadata__"]["type"] != "HydroEnergyReservoir":
            new_components.append(comp)
            continue

        logger.debug("Upgrading component = {} to PSY5.", comp["name"])

        ext = comp.get("ext", {})

        # Time-series ownership is keyed by UUID, so reusing the legacy
        # HydroEnergyReservoir's UUID here would make the new HydroReservoir
        # inherit that component's entire time-series association graph,
        # including series scaled for a generator (invalid for a reservoir).
        reservoir_uuid = str(uuid.uuid4())

        reservoir = {
            "__metadata__": {"type": "HydroReservoir", "module": "PowerSystems"},
            "name": f"{comp['name']}_Reservoir",
            "available": comp.get("available", True),
            "storage_level_limits": {
                "min": comp.get("min_storage_capacity", 0.0),
                "max": comp.get("storage_capacity", 0.0),
            },
            "initial_level": comp.get("initial_energy", 0.0),
            "spillage_limits": None,
            "inflow": comp.get("inflow", 0.0),
            "outflow": 0.0,
            "level_targets": comp.get("storage_target"),
            "intake_elevation": ext.get("intake_elevation", 0.0),
            "head_to_volume_factor": LinearCurve(0.0).model_dump(round_trip=True),
            "operation_cost": HydroReservoirCost().model_dump(round_trip=True),
            "level_data_type": str(ReservoirDataType.ENERGY),  # NOTE: Is this a good default?
            "internal": {"uuid": {"value": reservoir_uuid}},
            "ext": ext,
        }

        turbine = {
            "type": "HydroTurbine",
            "name": f"{comp['name']}_Turbine",
            "available": comp.get("available", True),
            "bus": comp.get("bus"),
            "active_power": comp.get("active_power", 0.0),
            "reactive_power": comp.get("reactive_power", 0.0),
            "rating": comp.get("rating", 0.0),
            "active_power_limits": comp.get("active_power_limits"),
            "reactive_power_limits": comp.get("reactive_power_limits"),
            "outflow_limits": None,
            "powerhouse_elevation": ext.get("powerhouse_elevation", 0.0),
            "ramp_limits": comp.get("ramp_limits"),
            "time_limits": comp.get("time_limits"),
            "base_power": comp.get("base_power", 0.0),
            "operation_cost": comp.get("operation_cost"),
            "efficiency": ext.get("efficiency", 1.0),
            "turbine_type": ext.get("turbine_type"),
            "conversion_factor": ext.get("conversion_factor", 1.0),
            "travel_time": comp.get("travel_time"),
            "reservoirs": [{"value": reservoir_uuid}],
            "prime_mover_type": str(PrimeMoversType.HY),
            "services": ext.get("services", []),
            "dynamic_injector": ext.get("dynamic_injector"),
            "ext": ext,
            "__metadata__": {"module": "PowerSystems", "type": "HydroTurbine"},
            "internal": {"uuid": {"value": str(uuid.uuid4())}},
        }

        new_components.extend([reservoir, turbine])

    system_data["data"]["components"] = new_components
    logger.debug("Completed HydroEnergyReservoir upgrade step.")
    return system_data


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=99)
def upgrade_hydro_turbine_prime_mover_type(system_data: dict[str, Any]) -> dict[str, Any]:
    """Fill in missing prime_mover_type on HydroTurbine / HydroPumpTurbine components.

    PSY5-format JSONs do not include prime_mover_type on these types, but the r2x_sienna
    models require it.
    """
    if not system_data_has_right_keys(system_data):
        logger.debug("No data found. Skipping step")
        return system_data

    default_prime_mover = {
        "HydroTurbine": PrimeMoversType.HY,
        "HydroPumpTurbine": PrimeMoversType.PS,
    }
    for comp in system_data["data"]["components"]:
        comp_type = comp.get("__metadata__", {}).get("type")
        if comp_type not in default_prime_mover:
            continue

        default = default_prime_mover[comp_type]
        logger.warning(
            "Component {} ({}) has no prime_mover_type defined. Assuming prime_mover_type = {}.",
            comp.get("name", "<unknown>"),
            comp_type,
            default,
        )
        comp["prime_mover_type"] = str(default)

    logger.debug("Completed hydro turbine prime_mover_type upgrade step.")
    return system_data


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=100)
def upgrade_hydro_pumped_storage(system_data: dict[str, Any]) -> dict[str, Any]:
    """
    Upgrade HydroPumpedStorage components into HydroPumpTurbine with head and tail HydroReservoirs.

    This mutates system_data in place by replacing each HydroPumpedStorage entry with
    a HydroPumpTurbine component and two HydroReservoir components.
    """
    if not system_data_has_right_keys(system_data):
        logger.debug("No data found. Skipping step")
        return system_data

    new_components: list[dict[str, Any]] = []

    for comp in system_data["data"]["components"]:
        if comp["__metadata__"]["type"] != "HydroPumpedStorage":
            new_components.append(comp)
            continue

        ext = comp.get("ext", {})

        head_uuid = comp["internal"]["uuid"]["value"]
        tail_uuid = str(uuid.uuid4())
        pump_turbine_uuid = str(uuid.uuid4())
        head_reservoir = {
            "__metadata__": {"type": "HydroReservoir", "module": "PowerSystems"},
            "name": f"{comp['name']}_HeadReservoir",
            "available": comp.get("available", True),
            "storage_level_limits": {
                "min": comp.get("storage_capacity", {}).get("down", 0.0),
                "max": comp.get("storage_capacity", {}).get("up", 0.0),
            },
            "initial_level": comp.get("initial_volume", 0.0),
            "inflow": comp.get("inflow", 0.0),
            "outflow": 0.0,
            "level_targets": comp.get("storage_target", {}).get("up"),
            "ext": ext,
            "internal": {"uuid": {"value": head_uuid}},
        }

        tail_reservoir = {
            "__metadata__": {"type": "HydroReservoir", "module": "PowerSystems"},
            "name": f"{comp['name']}_TailReservoir",
            "available": comp.get("available", True),
            "storage_level_limits": {
                "min": 0.0,
                "max": comp.get("storage_capacity", {}).get("down", 0.0),
            },
            "initial_level": comp.get("initial_volume", 0.0),
            "inflow": 0.0,
            "outflow": comp.get("outflow", 0.0),
            "level_targets": comp.get("storage_target", {}).get("down"),
            "ext": ext,
            "internal": {"uuid": {"value": tail_uuid}},
        }

        pump_turbine = {
            "__metadata__": {"type": "HydroPumpTurbine", "module": "PowerSystems"},
            "name": f"{comp['name']}_PumpTurbine",
            "available": comp.get("available", True),
            "bus": comp.get("bus"),
            "active_power": comp.get("active_power", 0.0),
            "rating": comp.get("rating", 0.0),
            "rating_pump": comp.get("rating_pump", 0.0),
            "active_power_limits": comp.get("active_power_limits"),
            "active_power_limits_pump": comp.get("active_power_limits_pump"),
            "ramp_limits": comp.get("ramp_limits"),
            "ramp_limits_pump": comp.get("ramp_limits_pump"),
            "time_limits": comp.get("time_limits"),
            "time_limits_pump": comp.get("time_limits_pump"),
            "reactive_power_limits": comp.get("reactive_power_limits"),
            "reactive_power_limits_pump": comp.get("reactive_power_limits_pump"),
            "head_reservoir": {"value": head_uuid},
            "tail_reservoir": {"value": tail_uuid},
            "powerhouse_elevation": ext.get("powerhouse_elevation", 0.0),
            "base_power": comp.get("base_power"),
            "operation_cost": comp.get("operation_cost"),
            "active_power_pump": comp.get("pump_load", 0.0),
            "efficiency": {
                "turbine": ext.get("efficiency", 1.0),
                "pump": comp.get("pump_efficiency", 0.85),
            },
            "conversion_factor": comp.get("conversion_factor", 1.0),
            "storage_duration": comp.get("storage_duration"),
            "initial_storage": comp.get("initial_storage"),
            "must_run": ext.get("must_run", False),
            "prime_mover_type": comp.get("prime_mover_type"),
            "services": ext.get("services", []),
            "dynamic_injector": ext.get("dynamic_injector"),
            "internal": {"uuid": {"value": pump_turbine_uuid}},
            "ext": ext,
        }

        new_components.extend([head_reservoir, tail_reservoir, pump_turbine])

    system_data["data"]["components"] = new_components
    logger.debug("Completed HydroPumpedStorage upgrade step.")
    return system_data


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=100)
def upgrade_ac_bus(system_data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade AC Bus components into DC Bus components."""

    if not system_data_has_right_keys(system_data):
        logger.debug("No data found. Skipping step")
        return system_data

    new_components: list[dict[str, Any]] = []

    for comp in system_data["data"]["components"]:
        if comp["__metadata__"]["type"] != "ACBus":
            new_components.append(comp)
            continue

        if comp["angle"] >= 1.571 or comp["angle"] <= -1.571:
            logger.warning(
                f"Bus {comp['name']} has an angle of {comp['angle']}, which is outside the valid range [-1.571, 1.571]. Setting angle to 0.0.",
            )
            comp["angle"] = 0.0

        new_components.extend([comp])

    system_data["data"]["components"] = new_components
    logger.debug("Completed ACBus upgrade step.")
    return system_data


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=100)
def upgrade_3w_transformer(system_data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade Transformer3W components: validate field ranges and fill in missing base fields."""
    if not system_data_has_right_keys(system_data):
        logger.debug("No data found. Skipping step")
        return system_data

    bus_voltage_map, arc_to_bus_map, system_base_power = _prepare_transformer_context(system_data)
    for comp in system_data["data"]["components"]:
        if comp.get("__metadata__", {}).get("type") == "Transformer3W":
            _patch_three_winding_transformer(comp, bus_voltage_map, arc_to_bus_map, system_base_power)

    logger.debug("Completed Transformer3W upgrade step.")
    return system_data


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=100)
def upgrade_phase_shifting_3w_transformer(system_data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade PhaseShiftingTransformer3W components: validate field ranges and fill in missing base fields."""
    if not system_data_has_right_keys(system_data):
        logger.debug("No data found. Skipping step")
        return system_data

    bus_voltage_map, arc_to_bus_map, system_base_power = _prepare_transformer_context(system_data)
    for comp in system_data["data"]["components"]:
        if comp.get("__metadata__", {}).get("type") == "PhaseShiftingTransformer3W":
            _patch_three_winding_transformer(comp, bus_voltage_map, arc_to_bus_map, system_base_power)

    logger.debug("Completed PhaseShiftingTransformer3W upgrade step.")
    return system_data


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=100)
def upgrade_line(system_data: dict[str, Any]) -> dict[str, Any]:
    """Fill in missing rating_b and rating_c fields for Line components."""
    if not system_data_has_right_keys(system_data):
        logger.debug("No data found. Skipping step")
        return system_data

    for comp in system_data["data"]["components"]:
        if comp.get("__metadata__", {}).get("type") == "Line":
            _patch_ac_branch(comp)

    logger.debug("Completed Line upgrade step.")
    return system_data


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=100)
def upgrade_monitored_line(system_data: dict[str, Any]) -> dict[str, Any]:
    """Fill in missing rating_b and rating_c fields for MonitoredLine components."""
    if not system_data_has_right_keys(system_data):
        logger.debug("No data found. Skipping step")
        return system_data

    for comp in system_data["data"]["components"]:
        if comp.get("__metadata__", {}).get("type") == "MonitoredLine":
            _patch_ac_branch(comp)

    logger.debug("Completed MonitoredLine upgrade step.")
    return system_data


def _prepare_transformer_context(
    system_data: dict[str, Any],
) -> tuple[dict[str, float], dict[str, tuple[str | None, str | None]], float]:
    """Build shared lookup maps and system base power for transformer upgrade steps."""
    components = system_data["data"]["components"]
    bus_voltage_map = _build_bus_voltage_map(components)
    arc_to_bus_map = _build_arc_to_bus_map(components)
    system_base_power = system_data.get("units_settings", {}).get("base_value", 100.0)
    return bus_voltage_map, arc_to_bus_map, system_base_power


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=100)
def upgrade_2w_transformer(system_data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade Transformer2W components: fix primary_shunt and fill in missing rated/voltage fields."""
    if not system_data_has_right_keys(system_data):
        logger.debug("No data found. Skipping step")
        return system_data

    bus_voltage_map, arc_to_bus_map, system_base_power = _prepare_transformer_context(system_data)
    for comp in system_data["data"]["components"]:
        if comp.get("__metadata__", {}).get("type") == "Transformer2W":
            _patch_two_winding_transformer(comp, bus_voltage_map, arc_to_bus_map, system_base_power)

    logger.debug("Completed Transformer2W upgrade step.")
    return system_data


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=100)
def upgrade_tap_transformer(system_data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade TapTransformer components: fix primary_shunt and fill in missing rated/voltage fields."""
    if not system_data_has_right_keys(system_data):
        logger.debug("No data found. Skipping step")
        return system_data

    bus_voltage_map, arc_to_bus_map, system_base_power = _prepare_transformer_context(system_data)
    for comp in system_data["data"]["components"]:
        if comp.get("__metadata__", {}).get("type") == "TapTransformer":
            _patch_two_winding_transformer(comp, bus_voltage_map, arc_to_bus_map, system_base_power)

    logger.debug("Completed TapTransformer upgrade step.")
    return system_data


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=100)
def upgrade_phase_shifting_transformer(system_data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade PhaseShiftingTransformer components: fix primary_shunt and fill in missing rated/voltage fields."""
    if not system_data_has_right_keys(system_data):
        logger.debug("No data found. Skipping step")
        return system_data

    bus_voltage_map, arc_to_bus_map, system_base_power = _prepare_transformer_context(system_data)
    for comp in system_data["data"]["components"]:
        if comp.get("__metadata__", {}).get("type") == "PhaseShiftingTransformer":
            _patch_two_winding_transformer(comp, bus_voltage_map, arc_to_bus_map, system_base_power)

    logger.debug("Completed PhaseShiftingTransformer upgrade step.")
    return system_data


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=100)
def upgrade_two_terminal_hvdc_line(system_data: dict[str, Any]) -> dict[str, Any]:
    """Rename TwoTerminalHVDCLine components to TwoTerminalGenericHVDCLine for PSY5 compatibility."""
    if not system_data_has_right_keys(system_data):
        logger.debug("No data found. Skipping step")
        return system_data

    for comp in system_data["data"]["components"]:
        if comp.get("type") == "TwoTerminalHVDCLine":
            comp["type"] = "TwoTerminalGenericHVDCLine"
        if "__metadata__" in comp and comp["__metadata__"].get("type") == "TwoTerminalHVDCLine":
            comp["__metadata__"]["type"] = "TwoTerminalGenericHVDCLine"

    logger.debug("Completed TwoTerminalHVDCLine to TwoTerminalGenericHVDCLine upgrade step.")
    return system_data


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=100)
def remove_time_series_container(system_data: dict[str, Any]) -> dict[str, Any]:
    if not system_data_has_right_keys(system_data):
        logger.debug("No data found. Skipping step")
        return system_data

    for comp in system_data["data"]["components"]:
        if "time_series_container" in comp:
            comp.pop("time_series_container")

    logger.debug("Completed removal of time_series_container from components.")
    return system_data


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=100)
def upgrade_geographic_info(system_data: dict[str, Any]) -> dict[str, Any]:
    data = system_data.get("data")
    if not isinstance(data, dict):
        logger.debug("No data section found. Skipping step")
        return system_data

    attr_mgr = data.get("supplemental_attribute_manager")
    if not attr_mgr or not attr_mgr.get("attributes"):
        logger.debug("No supplemental_attribute_manager or attributes found. Skipping step")
        return system_data

    for comp in attr_mgr["attributes"]:
        comp_name = comp.get("name", "<unknown>")
        comp_type = comp.get("__metadata__", {}).get("type", "")
        if comp_type != "GeographicInfo":
            continue

        geo_json = comp.get("geo_json")
        if geo_json is None:
            logger.warning(
                "GeographicInfo component '{}' has no geo_json field. Skipping.",
                comp_name,
            )
            continue

        if "coordinates" in geo_json:
            geo_type = geo_json.get("type") or "Point"
            coordinates = geo_json.get("coordinates")
        else:
            longitude = geo_json.get("Longitude")
            latitude = geo_json.get("Latitude")
            if longitude is None or latitude is None:
                missing = [k for k, v in (("Longitude", longitude), ("Latitude", latitude)) if v is None]
                logger.warning(
                    "GeographicInfo component '{}' geo_json is missing required key(s): {}. Defaulting missing values to 0.0.",
                    comp_name,
                    missing,
                )
            geo_type = "Point"
            coordinates = [longitude, latitude]

        comp["geo_json"] = {
            "coordinates": _sanitize_geojson_coordinates(coordinates, comp_name),
            "type": geo_type,
        }

    logger.debug("Successfully completed upgrading GeographicInfo in upgrade_geographic_info.")
    return system_data


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=100)
def upgrade_psy5_schema_fields(system_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize only required legacy fields to the current PSY5-aligned schema.

    This step intentionally avoids populating optional/default-backed fields and
    focuses only on canonical keys that are required by current models.
    """
    if not system_data_has_right_keys(system_data):
        logger.debug("No data found. Skipping step")
        return system_data

    for comp in system_data["data"]["components"]:
        comp_type = comp.get("__metadata__", {}).get("type")

        # Load conformity typo compatibility from older payloads.
        if (
            comp_type in {"PowerLoad", "StandardLoad", "InterruptiblePowerLoad"}
            and "conformity" not in comp
            and "comformity" in comp
        ):
            comp["conformity"] = comp.get("comformity")

        # Interface penalty introduced in newer PSY schema.
        if comp_type == "TransmissionInterface":
            comp.setdefault("violation_penalty", 1e30)

    logger.debug("Completed PSY5 schema field normalization step.")
    return system_data
