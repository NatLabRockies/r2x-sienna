"""Script that creates simple 2-area pjm systems for testing."""

import json
import pathlib
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

from infrasys.cost_curves import CostCurve, UnitSystem
from infrasys.time_series_models import SingleTimeSeries
from infrasys.value_curves import LinearCurve
from r2x_core.system import System

from r2x_sienna.exporter import to_psy
from r2x_sienna.models import (
    ACBus,
    Arc,
    Area,
    AreaInterchange,
    FromTo_ToFrom,
    Line,
    LoadZone,
    MinMax,
    MonitoredLine,
    PowerLoad,
    RenewableDispatch,
    Reserve,
    ReserveMap,
    ThermalStandard,
    UpDown,
)
from r2x_sienna.models.costs import RenewableGenerationCost, ThermalGenerationCost
from r2x_sienna.models.enums import ACBusTypes, PrimeMoversType, ReserveDirection, ReserveType, ThermalFuels
from r2x_sienna.plugin_config import SiennaConfig

T = TypeVar("T")


def get_enum_from_string(value: str, enum_class: type[T]) -> T:
    """Get enum value from string, case-insensitive."""
    for enum_value in enum_class:
        if enum_value.value.lower() == value.lower():
            return enum_value
    raise ValueError(f"No {enum_class.__name__} found for value: {value}")


def read_json(filepath: str) -> dict[str, Any]:
    """Read JSON file and return parsed data."""
    with open(filepath, "r") as f:
        return json.load(f)


def create_thermal_standard_pjm(name, bus, gen_data, **kwargs):
    """Helper function to create ThermalStandard with complete required fields."""
    defaults = {
        "must_run": False,
        "status": False,
        "base_power": 100.0,
        "rating": 200.0,
        "active_power": 0.0,
        "reactive_power": 0.0,
        "active_power_limits": MinMax(min=0, max=1),
        "prime_mover_type": PrimeMoversType.ST,
        "fuel": ThermalFuels.NATURAL_GAS,
        "time_at_status": 1000.0,
        "operation_cost": ThermalGenerationCost(
            shut_down=gen_data.get("ShutDnCost", 0.0),
            start_up=gen_data.get("StartupCost", 0.0),
            variable=CostCurve(
                value_curve=LinearCurve(14.0),
                power_units=UnitSystem.NATURAL_UNITS,
                vom_cost=LinearCurve(gen_data.get("VOM", 0.0)),
            ),
        ),
    }

    # Override with data from gen_data
    if "fuel" in gen_data:
        defaults["fuel"] = get_enum_from_string(gen_data["fuel"].lower(), ThermalFuels)

    if "RampLimitsUp" in gen_data and "RampLimitsDn" in gen_data:
        defaults["ramp_limits"] = UpDown(up=gen_data["RampLimitsUp"], down=gen_data["RampLimitsDn"])

    # Store the min up/down times in ext field since they're not part of the main model
    ext_data = {}
    if "MinTimeDn" in gen_data:
        ext_data["min_down_time"] = gen_data["MinTimeDn"]
    if "MinTimeUp" in gen_data:
        ext_data["min_up_time"] = gen_data["MinTimeUp"]
    ext_data["mean_time_to_repair"] = 10.0
    ext_data["forced_outage_rate"] = 0.0
    ext_data["planned_outage_rate"] = 0.0

    defaults.update(kwargs)

    thermal_gen = ThermalStandard(name=name, bus=bus, **defaults)

    # Add the extra data to ext field
    thermal_gen.ext.update(ext_data)

    return thermal_gen


def pjm_2area() -> System:
    """Return the PJM 2-area test system."""
    fpath = pathlib.Path(__file__).parent.parent
    fname = "data/pjm_2area_data.json"
    pjm_2area_components = read_json(str(fpath / fname))

    system = System(
        name="pjm 2-area system",
        auto_add_composed_components=True,
        description="Test system for PJM",
        base_power=100.0,
    )

    # Add topology elements
    system.add_component(Area(name="init"))
    system.add_component(Area(name="Area2"))
    system.add_component(LoadZone(name="init"))
    system.add_component(LoadZone(name="Area2"))

    for bus in pjm_2area_components["bus"]:
        system.add_component(
            ACBus(
                name=bus["name"],
                number=bus["number"],
                bustype=ACBusTypes(bus["bustype"]),
                base_voltage=bus["base_voltage"],  # Use float instead of Voltage with units
                area=system.get_component(Area, bus["area"]),
                load_zone=system.get_component(LoadZone, bus["area"]),
                magnitude=bus["magnitude"],
            )
        )

    # Add branches
    for branch in pjm_2area_components["branch"]:
        busf = system.get_component(ACBus, branch["FromBus"])
        bust = system.get_component(ACBus, branch["ToBus"])
        system.add_component(
            Line(
                name=branch["Name"],
                arc=Arc(from_to=busf, to_from=bust),
                x=branch["x"],
                r=branch["r"],
                rating=branch["MaxRating"],  # Use float instead of MW units
                active_power_flow=0.0,
                reactive_power_flow=0.0,
                angle_limits=MinMax(min=-0.7, max=0.7),
            )
        )
    # Add MonitoredLine
    busf = system.get_component(ACBus, "Bus_nodeC_1")
    bust = system.get_component(ACBus, "Bus_nodeC_2")
    branch_monitored = MonitoredLine(
        name="inter_area_line",
        arc=Arc(from_to=busf, to_from=bust),
        r=0.003,
        x=0.03,
        active_power_flow=0.0,
        reactive_power_flow=0.0,
        flow_limits=FromTo_ToFrom(from_to=-1000.0, to_from=1000.0),  # Use float instead of MW units
    )
    system.add_component(branch_monitored)

    # Add area interchange
    system.add_component(
        AreaInterchange(
            name="1_2",
            flow_limits=FromTo_ToFrom(from_to=-150, to_from=150),
            from_area=system.get_component(Area, "init"),
            to_area=system.get_component(Area, "Area2"),
            active_power_flow=0.0,
        )
    )

    # Add thermal generators - Updated section
    for gen in pjm_2area_components["thermal"]:
        thermal_gen = create_thermal_standard_pjm(
            name=gen["Name"],
            bus=system.get_component(ACBus, gen["BusName"]),
            gen_data=gen,
            active_power=100.0,  # Use float instead of ActivePower with units
        )
        system.add_component(thermal_gen)

    # Solar generators
    solar_pv_01 = RenewableDispatch(
        name="PVBus5",
        bus=system.get_component(ACBus, "Bus_nodeC_1"),
        prime_mover_type=PrimeMoversType.PVe,
        active_power=384.0,
        reactive_power=0.0,
        rating=400.0,
        base_power=400.0,
        operation_cost=RenewableGenerationCost(),
    )
    system.add_component(solar_pv_01)

    wind_01 = RenewableDispatch(
        name="WindBus1",
        bus=system.get_component(ACBus, "Bus_nodeA_2"),
        prime_mover_type=PrimeMoversType.WT,
        active_power=451.0,
        reactive_power=0.0,
        rating=500.0,
        base_power=500.0,
        operation_cost=RenewableGenerationCost(),
    )
    system.add_component(wind_01)

    # Add renewable profiles
    initial_timestamp = datetime(year=2024, month=1, day=1, tzinfo=UTC)
    solar_array = pjm_2area_components["solar_ts"]
    wind_array = pjm_2area_components["wind_ts"]
    solar_ts = SingleTimeSeries.from_array(
        data=solar_array,
        initial_timestamp=initial_timestamp,
        resolution=timedelta(hours=1),
        name="max_active_power",
    )
    wind_ts = SingleTimeSeries.from_array(
        data=wind_array,
        initial_timestamp=initial_timestamp,
        resolution=timedelta(hours=1),
        name="rated_capacity",
    )
    system.add_time_series(solar_ts, solar_pv_01)
    system.add_time_series(wind_ts, wind_01)

    initial_timestamp = datetime(year=2024, month=1, day=1, tzinfo=UTC)
    for load in pjm_2area_components["load"]:
        load_component = PowerLoad(
            name=load["BusName"],
            bus=system.get_component(ACBus, load["BusName"]),
            max_active_power=load["MaxLoad"],  # Use float instead of MW units
        )
        ld_ts = SingleTimeSeries.from_array(
            data=load["ts"],
            initial_timestamp=initial_timestamp,
            resolution=timedelta(hours=1),
            name="max_active_power",
        )
        system.add_component(load_component)
        system.add_time_series(ld_ts, load_component)

    # Create reserve
    reserve_map = ReserveMap(name="pjm_reserve_map")
    reserve = Reserve(
        name="SpinUp-pjm",
        region=system.get_component(LoadZone, "init"),
        reserve_type=ReserveType.SPINNING,
        vors=0.05,
        duration=3600.0,
        load_risk=0.5,
        time_frame=3600,
        direction=ReserveDirection.UP,
    )
    reserve_map.mapping[ReserveType.SPINNING.name].append(wind_01.name)
    reserve_map.mapping[ReserveType.SPINNING.name].append(solar_pv_01.name)
    system.add_components(reserve, reserve_map)

    return system


def pjm_2area_to_psy(output_folder: pathlib.Path, model_year: int = 2024):
    """Export PJM 2-area system to PowerSystems.jl format."""
    system = pjm_2area()

    config = SiennaConfig(
        model_year=model_year,
        system_name="PJM_2Area_System",
        scenario="base_case",
        system_base_power=100.0,
        skip_validation=False,
    )

    system_data = {
        "system_information": {
            "name": system.name,
            "description": system.description or "PJM 2-area test system for PowerSystems.jl",
            "base_power": config.system_base_power,
            "model_year": config.primary_model_year,
        },
        "data_information": {
            "version": "1.0.0",
            "base_power": config.system_base_power,
            "time_series_storage_type": "InfrastructureSystems.Hdf5TimeSeriesStorage",
        },
        "component_fields": {},
    }

    output_file = output_folder / f"{system.name.replace(' ', '_')}_psy.json"
    output_folder.mkdir(parents=True, exist_ok=True)

    to_psy(
        config=config,
        system=system,
        system_data=system_data,
        filename=output_file,
        write_year=config.primary_model_year,
    )

    h5_file = output_file.parent / f"{system.name}_time_series_storage.h5"
    if h5_file.exists():
        file_size = h5_file.stat().st_size / (1024 * 1024)
        print(f"Time series data exported to: {h5_file} ({file_size:.2f} MB)")

    return output_file
