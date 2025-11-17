"""Script that creates simple systems for testing."""

import pathlib
from datetime import datetime, timedelta

from infrasys.cost_curves import FuelCurve, UnitSystem
from infrasys.function_data import LinearFunctionData
from infrasys.time_series_models import SingleTimeSeries
from infrasys.value_curves import InputOutputCurve

from r2x_core.system import System
from r2x_sienna.config import SiennaConfig
from r2x_sienna.exporter import to_psy
from r2x_sienna.models.enums import PrimeMoversType, StorageTechs, ThermalFuels
from r2x_sienna.models import (
    ACBus,
    Area,
    EnergyReservoirStorage,
    InputOutput,
    LoadZone,
    MinMax,
    MonitoredLine,
    RenewableDispatch,
    ThermalStandard,
)
from r2x_sienna.models.costs import ThermalGenerationCost
from r2x_sienna.units import Energy, Percentage, Time, ureg


def ieee5bus() -> System:
    """Return an instance of the IEEE 5-bus system."""
    system = System(
        name="IEEE 5-bus System",
        auto_add_composed_components=True,
        description="IEEE 5-bus test system",
        base_power=100.0,
    )

    area_1 = Area(name="region1")
    load_zone_1 = LoadZone(name="LoadZone1")
    system.add_component(area_1)
    system.add_component(load_zone_1)

    # Create buses
    bus_1 = ACBus(number=1, name="node_a", base_voltage=100 * ureg.volt, area=area_1, load_zone=load_zone_1)
    bus_2 = ACBus(number=2, name="node_b", base_voltage=100 * ureg.volt, area=area_1, load_zone=load_zone_1)
    bus_3 = ACBus(number=3, name="node_c", base_voltage=100 * ureg.volt, area=area_1, load_zone=load_zone_1)
    bus_4 = ACBus(number=4, name="node_d", base_voltage=100 * ureg.volt, area=area_1, load_zone=load_zone_1)
    bus_5 = ACBus(number=5, name="node_e", base_voltage=100 * ureg.volt, area=area_1, load_zone=load_zone_1)

    # Add buses to system
    for bus in [bus_1, bus_2, bus_3, bus_4, bus_5]:
        system.add_component(bus)

    # Solar generators
    initial_time = datetime(year=2012, month=1, day=1)
    ts = SingleTimeSeries.from_array(
        data=list(range(0, 8760)),
        initial_timestamp=initial_time,
        resolution=timedelta(hours=1),
        name="rated_capacity",
    )
    solar_pv_01 = RenewableDispatch(
        name="SolarPV1",
        bus=bus_3,
        prime_mover_type=PrimeMoversType.PVe,
        active_power=384 * ureg.MW,
        category="solar",
    )
    solar_pv_02 = RenewableDispatch(
        name="SolarPV2",
        bus=bus_4,
        prime_mover_type=PrimeMoversType.PVe,
        active_power=384 * ureg.MW,
        category="solar",
    )
    system.add_component(solar_pv_01)
    system.add_component(solar_pv_02)
    system.add_time_series(ts, solar_pv_01)
    system.add_time_series(ts, solar_pv_02)

    # Storage
    storage = EnergyReservoirStorage(
        name="Battery1",
        bus=bus_2,
        prime_mover_type=PrimeMoversType.BA,
        active_power=200 * ureg.MW,
        charge_efficiency=Percentage(85, "%"),
        storage_capacity=Energy(800, "MWh"),
        storage_duration=Time(4, "h"),
        category="storage",
        storage_technology_type=StorageTechs.OTHER_CHEM,
        initial_storage_capacity_level=0.5,
        input_active_power_limits=MinMax(min=0, max=200),
        output_active_power_limits=MinMax(min=0, max=200),
        efficiency=InputOutput(input=0.9, output=0.9),
    )
    system.add_component(storage)

    # Thermal generators
    alta = ThermalStandard(
        name="Alta",
        fuel=ThermalFuels.NATURAL_GAS,
        prime_mover_type=PrimeMoversType.CC,
        active_power=40 * ureg.MW,
        rating=40 * ureg.MW,
        bus=bus_1,
        category="thermal",
    )
    system.add_component(alta)

    brighton = ThermalStandard(
        name="Brighton",
        fuel=ThermalFuels.NATURAL_GAS,
        prime_mover_type=PrimeMoversType.CC,
        active_power=600 * ureg.MW,
        rating=600 * ureg.MW,
        bus=bus_5,
        category="thermal",
    )
    system.add_component(brighton)

    park_city = ThermalStandard(
        name="Park City",
        fuel=ThermalFuels.NATURAL_GAS,
        prime_mover_type=PrimeMoversType.CC,
        active_power=170 * ureg.MW,
        rating=170 * ureg.MW,
        operation_cost=ThermalGenerationCost(
            variable=FuelCurve(
                value_curve=InputOutputCurve(
                    function_data=LinearFunctionData(proportional_term=10, constant_term=0)
                ),
                fuel_cost=15,
                power_units=UnitSystem.NATURAL_UNITS,
            ),
        ),
        bus=bus_1,
        category="thermal",
    )
    system.add_component(park_city)

    solitude = ThermalStandard(
        name="Solitude",
        fuel=ThermalFuels.NATURAL_GAS,
        prime_mover_type=PrimeMoversType.CC,
        active_power=520 * ureg.MW,
        rating=520 * ureg.MW,
        operation_cost=ThermalGenerationCost(
            variable=FuelCurve(
                value_curve=InputOutputCurve(
                    function_data=LinearFunctionData(proportional_term=10, constant_term=0)
                ),
                fuel_cost=15,
                power_units=UnitSystem.NATURAL_UNITS,
            )
        ),
        bus=bus_3,
        category="thermal",
    )
    system.add_component(solitude)

    sundance = ThermalStandard(
        name="Sundance",
        fuel=ThermalFuels.NATURAL_GAS,
        prime_mover_type=PrimeMoversType.CC,
        active_power=400 * ureg.MW,
        rating=400 * ureg.MW,
        bus=bus_4,
        category="thermal",
    )
    system.add_component(sundance)

    # Branches
    branch_ab = MonitoredLine(
        name="line_ab",
        active_power_flow=0.0,
        reactive_power_flow=0.0,
        from_bus=bus_1,
        to_bus=bus_2,
        r=0.01,
        x=0.1,
    )
    system.add_component(branch_ab)

    branch_ad = MonitoredLine(
        name="line_ad",
        active_power_flow=0.0,
        reactive_power_flow=0.0,
        from_bus=bus_1,
        to_bus=bus_4,
        r=0.01,
        x=0.1,
    )
    system.add_component(branch_ad)

    branch_ae = MonitoredLine(
        name="line_ae",
        active_power_flow=0.0,
        reactive_power_flow=0.0,
        from_bus=bus_1,
        to_bus=bus_5,
        r=0.01,
        x=0.1,
    )
    system.add_component(branch_ae)

    branch_bc = MonitoredLine(
        name="line_bc",
        active_power_flow=0.0,
        reactive_power_flow=0.0,
        from_bus=bus_2,
        to_bus=bus_3,
        r=0.01,
        x=0.1,
    )
    system.add_component(branch_bc)

    branch_cd = MonitoredLine(
        name="line_cd",
        active_power_flow=0.0,
        reactive_power_flow=0.0,
        from_bus=bus_3,
        to_bus=bus_4,
        r=0.01,
        x=0.1,
    )
    system.add_component(branch_cd)

    branch_ed = MonitoredLine(
        name="line_ed",
        active_power_flow=0.0,
        reactive_power_flow=0.0,
        from_bus=bus_5,
        to_bus=bus_4,
        r=0.01,
        x=0.1,
    )
    system.add_component(branch_ed)

    return system


def ieee5bus_to_psy(output_folder: pathlib.Path, model_year: int = 2024):
    """Export IEEE 5-bus system to PowerSystems.jl format."""
    system = ieee5bus()

    # Create Sienna configuration
    config = SiennaConfig(
        model_year=model_year,
        system_name="IEEE_5Bus_System",
        scenario="base_case",
        system_base_power=100.0,
        skip_validation=False,
    )

    # Prepare system data for PSY export
    system_data = {
        "system_information": {
            "name": system.name,
            "description": system.description or "IEEE 5-bus test system for PowerSystems.jl",
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
