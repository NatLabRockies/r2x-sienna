import uuid
from typing import Any

from infrasys.value_curves import LinearCurve
from loguru import logger
from r2x_core import UpgradeType

from r2x_sienna.models import HydroReservoirCost, ReservoirDataType

from .data_upgrader import SiennaUpgrader


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
            "travel_time": None,
            "intake_elevation": ext.get("intake_elevation", 0.0),
            "head_to_volume_factor": LinearCurve(0.0),
            "operation_cost": HydroReservoirCost().model_dump(round_trip=True),
            "level_data_type": str(ReservoirDataType.ENERGY),  # NOTE: Is this a good default?
            "internal": comp.get("internal", {}),
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
            "active_power_limits": comp.get(
                "active_power_limits", {"min": 0.0, "max": ext.get("rating", 0.0)}
            ),
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
            "reservoirs": [{"value": comp["internal"]["uuid"]["value"]}],
            "services": ext.get("services", []),
            "dynamic_injector": ext.get("dynamic_injector"),
            "ext": ext,
            "__metadata__": {"module": "PowerSystems", "type": "HydroTurbine"},
            "internal": {"uuid": {"value": str(uuid.uuid4())}},
        }

        new_components.extend([reservoir, turbine])

    system_data["data"]["components"] = new_components
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

        head_uuid = str(uuid.uuid4())
        tail_uuid = str(uuid.uuid4())
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
            "internal": comp.get("internal", {}),
            "ext": ext,
        }

        new_components.extend([head_reservoir, tail_reservoir, pump_turbine])

    system_data["data"]["components"] = new_components
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

        if comp["angle"] > 1.571 or comp["angle"] < -1.571:
            logger.warning(
                f"Bus {comp['name']} has an angle of {comp['angle']}, which is outside the valid range [-1.571, 1.571]. Setting angle to 0.0.",
            )
            comp["angle"] = 0.0

        new_components.extend([comp])

    system_data["data"]["components"] = new_components
    return system_data


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=100)
def upgrade_3w_transformer(system_data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade 3W Transformer components."""
    if not system_data_has_right_keys(system_data):
        logger.debug("No data found. Skipping step")
        return system_data

    new_components: list[dict[str, Any]] = []

    for comp in system_data["data"]["components"]:
        if comp["__metadata__"]["type"] != "Transformer3W":
            new_components.append(comp)
            continue

        if comp["x_secondary"] > 4 or comp["x_secondary"] < -2:
            logger.warning(
                f"Transformer {comp['name']} has an x_secondary of {comp['x_secondary']}, which is outside the valid range [-2, 4]. Setting x_secondary to 0.0.",
            )
            comp["x_secondary"] = 0.0
        if comp["x_tertiary"] > 4 or comp["x_tertiary"] < -2:
            logger.warning(
                f"Transformer {comp['name']} has an x_tertiary of {comp['x_tertiary']}, which is outside the valid range [-2, 4]. Setting x_tertiary to 0.0.",
            )
            comp["x_tertiary"] = 0.0
        if comp["x_23"] > 4 or comp["x_23"] < -2:
            logger.warning(
                f"Transformer {comp['name']} has an x_23 of {comp['x_23']}, which is outside the valid range [-2, 4]. Setting x_23 to 0.0.",
            )
            comp["x_23"] = 0.0
        if comp["x_13"] > 4 or comp["x_13"] < 0:
            logger.warning(
                f"Transformer {comp['name']} has an x_13 of {comp['x_13']}, which is outside the valid range [0, 4]. Setting x_13 to 0.0.",
            )
            comp["x_13"] = 0.0
        if comp["r_23"] > 4 or comp["r_23"] < 0:
            logger.warning(
                f"Transformer {comp['name']} has an r_23 of {comp['r_23']}, which is outside the valid range [0, 4]. Setting r_23 to 0.0.",
            )
            comp["r_23"] = 0.0
        if comp["r_13"] > 4 or comp["r_13"] < 0:
            logger.warning(
                f"Transformer {comp['name']} has an r_13 of {comp['r_13']}, which is outside the valid range [0, 4]. Setting r_13 to 0.0.",
            )
            comp["r_13"] = 0.0

        new_components.extend([comp])

    system_data["data"]["components"] = new_components
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

    return system_data


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=100)
def upgrade_2w_transformer(system_data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade Transformer2W components: convert primary_shunt from float to Complex dict if needed."""
    if not system_data_has_right_keys(system_data):
        logger.debug("No data found. Skipping step")
        return system_data

    for comp in system_data["data"]["components"]:
        if (
            comp.get("type") in ("Transformer2W", "PhaseShiftingTransformer", "TapTransformer")
            or comp.get("__metadata__", {}).get("type")
            in ("Transformer2W", "PhaseShiftingTransformer", "TapTransformer")
        ) and isinstance(comp.get("primary_shunt"), float):
            comp["primary_shunt"] = {"real": comp["primary_shunt"], "imag": 0.0}

    return system_data


@SiennaUpgrader.register_step(target_version="5.999", upgrade_type=UpgradeType.SYSTEM, priority=100)
def remove_time_series_container(system_data: dict[str, Any]) -> dict[str, Any]:
    if not system_data_has_right_keys(system_data):
        logger.debug("No data found. Skipping step")
        return system_data

    for comp in system_data["data"]["components"]:
        if "time_series_container" in comp:
            comp.pop("time_series_container")

    return system_data
