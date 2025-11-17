"""Models for generator devices."""

from typing import Annotated

from infrasys.value_curves import InputOutputCurve, LinearCurve
from pydantic import Field
from r2x_core import Unit

from r2x_sienna.models.load import InterruptiblePowerLoad, PowerLoad
from r2x_sienna.units import ActivePower, ApparentPower

from .core import Device
from .costs import (
    HydroGenerationCost,
    HydroReservoirCost,
    MarketBidCost,
    RenewableGenerationCost,
    StorageCost,
    ThermalGenerationCost,
)
from .enums import (
    HydroTurbineType,
    PrimeMoversType,
    PumpHydroStatus,
    ReservoirDataType,
    ReservoirLocation,
    StorageTechs,
    ThermalFuels,
)
from .named_tuples import InputOutput, MinMax, StartShut, StartUpStages, TurbinePump, UpDown
from .topology import ACBus


class ThermalStandard(Device):
    """Thermal Standard device per PSY."""

    bus: Annotated[ACBus, Field(description="Bus where the generator is connected.")] | None = None
    active_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(
            description=(
                "Initial active power set point of the unit in MW. For power flow, this is the steady "
                "state operating point of the system."
            ),
        ),
    ]
    reactive_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(
            description=(
                "Reactive power set point of the unit in MVAr. For power flow, this is the steady "
                "state operating point of the system."
            ),
        ),
    ]
    rating: Annotated[
        float,
        Unit("MVA", base="base_power"),
        Field(ge=0, description="Maximum output power rating of the unit (MVA)."),
    ]
    base_power: Annotated[
        float,
        Unit("MVA"),
        Field(
            ge=0,
            description="Base power of the unit (MVA) for per unitization.",
        ),
    ]
    active_power_limits: Annotated[MinMax, Field(description="Active power limits of the unit (MW).")]
    reactive_power_limits: Annotated[
        MinMax | None,
        Field(description="Reactive power limits of the unit (MVAr)."),
    ] = None
    must_run: Annotated[bool, Field(description="If we need to force the dispatch of the device.")]
    prime_mover_type: Annotated[
        PrimeMoversType, Field(description="Prime mover technology according to EIA 923.")
    ]
    ramp_limits: Annotated[
        UpDown | None,
        Unit("pu/min", base="base_power"),
        Field(description="ramp up and ramp down limits in MW/min"),
    ] = None
    status: Annotated[
        bool,
        Field(
            description="Initial commitment condition at the start of a simulation (`true` = on or `false` = off)"
        ),
    ]
    time_at_status: Annotated[
        float,
        Unit("hour"),
        Field(description="Time the generator has been on or off, as indicated by status."),
    ]
    time_limits: Annotated[
        UpDown | None, Unit("hour"), Field(description="Minimum up and Minimum down time limits in hours")
    ] = None
    operation_cost: Annotated[ThermalGenerationCost, Field(description="Operational cosst.")]
    fuel: Annotated[ThermalFuels, Field(description="Prime mover fuel according to EIA 923.")]

    @classmethod
    def example(cls) -> "ThermalStandard":
        return ThermalStandard(
            name="thermal-standard-test",
            must_run=False,
            bus=ACBus.example(),
            status=False,
            base_power=100.0,
            rating=200.0,
            active_power=0.0,
            reactive_power=0.0,
            active_power_limits=MinMax(min=0, max=1),
            prime_mover_type=PrimeMoversType.CC,
            fuel=ThermalFuels.NATURAL_GAS,
            operation_cost=ThermalGenerationCost.example(),
            time_at_status=1_000,
        )


class ThermalMultiStart(Device):
    """A thermal generator, such as a fossil fuel or nuclear generator, that can start-up again from a *hot*, *warm*, or *cold* state.

    ThermalMultiStart has a detailed representation of the start-up process based on the time elapsed since the last shut down, as well as a detailed shut-down process. The model is based on "Tight and Compact MILP Formulation for the Thermal Unit Commitment Problem." For a simplified representation of the start-up and shut-down processes, see ThermalStandard.

    Components of the same type (e.g., PowerLoad) must have unique names, but components of
    different types (e.g., PowerLoad and ACBus) can have the same name.
    """

    bus: Annotated[ACBus, Field(description="Bus that this component is connected to.")] | None = None
    status: Annotated[
        bool,
        Field(
            description="Initial commitment condition at the start of a simulation (True = on or False = off)."
        ),
    ]
    active_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(
            description="Initial active power set point of the unit in MW. For power flow, this is the steady state operating point of the system. For production cost modeling, this may or may not be used as the initial starting point for the solver, depending on the solver used."
        ),
    ]
    reactive_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(description="Initial reactive power set point of the unit (MVAR)."),
    ]
    rating: Annotated[
        float,
        Unit("MVA", base="base_power"),
        Field(ge=0, description="Maximum output power rating of the unit (MVA)."),
    ]
    prime_mover_type: Annotated[
        PrimeMoversType, Field(description="Prime mover technology according to EIA 923.")
    ]
    fuel: Annotated[ThermalFuels, Field(description="Prime mover fuel according to EIA 923.")]
    active_power_limits: Annotated[
        MinMax, Field(description="Minimum and maximum stable active power levels (MW).")
    ]
    reactive_power_limits: Annotated[
        MinMax | None,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum reactive power limits. Set to None if not applicable."),
    ] = None
    ramp_limits: Annotated[
        UpDown | None,
        Unit("pu/min", base="base_power"),
        Field(description="Ramp up and ramp down limits in MW/min."),
    ] = None
    power_trajectory: Annotated[
        StartShut | None,
        Unit("pu", base="base_power"),
        Field(
            description="Power trajectory the unit will take during the start-up and shut-down ramp process."
        ),
    ] = None
    time_limits: Annotated[
        UpDown | None,
        Unit("hour"),
        Field(description="Minimum up and Minimum down time limits in hours."),
    ] = None
    start_time_limits: Annotated[
        StartUpStages | None,
        Unit("hour"),
        Field(description="Time limits for start-up based on turbine temperature in hours."),
    ] = None
    start_types: Annotated[
        int,
        Field(
            ge=1,
            le=3,
            description="Number of start-up based on turbine temperature, where 1 = hot, 2 = warm, and 3 = cold.",
        ),
    ]
    operation_cost: Annotated[
        ThermalGenerationCost | MarketBidCost,
        Field(description="Operational cost of generation."),
    ]
    base_power: Annotated[
        float,
        Unit("MVA"),
        Field(
            ge=0,
            description="Base power of the unit (MVA) for per unitization.",
        ),
    ]
    time_at_status: Annotated[
        float,
        Unit("hour"),
        Field(description="Time the generator has been on or off, as indicated by status."),
    ] = float("inf")
    must_run: Annotated[
        bool,
        Field(description="Set to true if the unit is must run."),
    ] = False

    @classmethod
    def example(cls) -> "ThermalMultiStart":
        return ThermalMultiStart(
            name="thermal-multistart-test",
            available=True,
            bus=ACBus.example(),
            status=False,
            active_power=0.0,
            reactive_power=0.0,
            rating=100.0,
            prime_mover_type=PrimeMoversType.CC,
            fuel=ThermalFuels.NATURAL_GAS,
            active_power_limits=MinMax(min=10.0, max=100.0),
            reactive_power_limits=MinMax(min=-30.0, max=30.0),
            ramp_limits=UpDown(up=5.0, down=5.0),
            power_trajectory=StartShut(startup=50.0, shutdown=25.0),
            time_limits=UpDown(up=4.0, down=2.0),
            start_time_limits=StartUpStages(hot=1.0, warm=4.0, cold=8.0),
            start_types=3,
            operation_cost=ThermalGenerationCost.example(),
            base_power=100.0,
            time_at_status=float("inf"),
            must_run=False,
        )


class RenewableGen(Device):
    """Abstract class for renewable generators."""


class RenewableDispatch(RenewableGen):
    """Curtailable renewable generator.

    This type of generator have a hourly capacity factor profile.
    """

    bus: Annotated[ACBus, Field(description="Bus where the generator is connected.")] | None = None
    active_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(
            description=(
                "Initial active power set point of the unit in MW. For power flow, this is the steady "
                "state operating point of the system."
            ),
        ),
    ]
    reactive_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(
            description=(
                "Reactive power set point of the unit in MVAr. For power flow, this is the steady "
                "state operating point of the system."
            ),
        ),
    ]
    rating: Annotated[
        float,
        Unit("MVA", base="base_power"),
        Field(ge=0, description="Maximum output power rating of the unit (MVA)."),
    ]
    prime_mover_type: Annotated[
        PrimeMoversType, Field(description="Prime mover technology according to EIA 923.")
    ]
    reactive_power_limits: Annotated[
        MinMax | None,
        Unit("pu", base="base_power"),
        Field(description="Reactive power limits of the unit (MVAr)."),
    ] = None
    power_factor: Annotated[
        float,
        Field(ge=0, le=1, description="Power factor between real and apparent power."),
    ] = 1.0
    operation_cost: Annotated[
        RenewableGenerationCost, Field(description="Operation cost for the renewable generator.")
    ]
    base_power: Annotated[
        float,
        Unit("MVA"),
        Field(
            ge=0,
            description="Base power of the unit (MVA) for per unitization.",
        ),
    ]

    @classmethod
    def example(cls) -> "RenewableDispatch":
        return RenewableDispatch(
            name="renewable-dispatch-test",
            bus=ACBus.example(),
            base_power=100,
            rating=1,
            active_power=0.8,
            reactive_power=0.0,
            prime_mover_type=PrimeMoversType.PVe,
            power_factor=1.0,
            operation_cost=RenewableGenerationCost(),
        )


class RenewableNonDispatch(RenewableGen):
    """Non-curtailable renewable generator.

    Renewable technologies w/o operational cost.
    """

    bus: Annotated[ACBus, Field(description="Bus where the generator is connected.")] | None = None
    active_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(
            description=(
                "Initial active power set point of the unit in MW. For power flow, this is the steady "
                "state operating point of the system."
            ),
        ),
    ]
    reactive_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(
            description=(
                "Reactive power set point of the unit in MVAr. For power flow, this is the steady "
                "state operating point of the system."
            ),
        ),
    ]
    rating: Annotated[
        float,
        Unit("MVA", base="base_power"),
        Field(ge=0, description="Maximum output power rating of the unit (MVA)."),
    ]
    prime_mover_type: Annotated[
        PrimeMoversType, Field(description="Prime mover technology according to EIA 923.")
    ]
    power_factor: Annotated[
        float,
        Field(ge=0, le=1, description="Power factor between real and apparent power."),
    ] = 1.0
    base_power: Annotated[
        float,
        Unit("MVA"),
        Field(
            ge=0,
            description="Base power of the unit (MVA) for per unitization.",
        ),
    ]

    @classmethod
    def example(cls) -> "RenewableNonDispatch":
        return RenewableNonDispatch(
            name="renewable-nondispatch-test",
            bus=ACBus.example(),
            base_power=100,
            rating=1,
            active_power=0.9,
            reactive_power=0.0,
            prime_mover_type=PrimeMoversType.WT,
            power_factor=1.0,
        )


class SynchronousCondenser(Device):
    """A Synchronous Machine connected to the system to provide inertia or reactive power support.

    Components of the same type (e.g., PowerLoad) must have unique names, but components of
    different types (e.g., PowerLoad and ACBus) can have the same name.
    """

    bus: Annotated[ACBus, Field(description="Bus that this component is connected to.")] | None = None
    reactive_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(description="Initial reactive power set point of the unit (MVAR)."),
    ]
    rating: Annotated[
        float,
        Unit("MVA", base="base_power"),
        Field(ge=0, description="Maximum output power rating of the unit (MVA)."),
    ]
    reactive_power_limits: Annotated[
        MinMax | None,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum reactive power limits. Set to None if not applicable."),
    ] = None
    base_power: Annotated[
        float,
        Unit("MVA"),
        Field(
            ge=0,
            description="Base power of the unit (MVA) for per unitization.",
        ),
    ]
    active_power_losses: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(ge=0, description="Active Power Loss incurred by having the unit online."),
    ] = 0.0

    @classmethod
    def example(cls) -> "SynchronousCondenser":
        return SynchronousCondenser(
            name="synchronoys-condenser-test",
            available=True,
            bus=ACBus.example(),
            reactive_power=0.0,
            rating=100.0,
            reactive_power_limits=MinMax(min=-100.0, max=100.0),
            base_power=100.0,
            active_power_losses=2.0,
        )


class EnergyReservoirStorage(Device):
    """An energy storage device, modeled as a generic energy reservoir.

    This is suitable for modeling storage charging and discharging with average efficiency losses,
    ignoring the physical dynamics of the storage unit. A variety of energy storage types and
    chemistries can be modeled with this approach. For pumped hydro storage, alternatively see
    HydroPumpTurbine and HydroReservoir.

    Components of the same type (e.g., PowerLoad) must have unique names, but components of
    different types (e.g., PowerLoad and ACBus) can have the same name.
    """

    bus: Annotated[ACBus, Field(description="Bus that this component is connected to.")] | None = None
    prime_mover_type: Annotated[
        PrimeMoversType, Field(description="Prime mover technology according to EIA 923.")
    ]
    storage_technology_type: Annotated[
        StorageTechs, Field(description="Storage Technology Complementary to EIA 923.")
    ]
    storage_capacity: Annotated[
        float,
        Unit("MWh"),
        Field(
            ge=0,
            description="Maximum storage capacity (can be in units of, e.g., MWh for batteries or liters for hydrogen).",
        ),
    ]
    storage_level_limits: Annotated[
        MinMax,
        Field(
            description="Minimum and maximum allowable storage levels [0, 1], which can be used to model derates or other restrictions, such as state-of-charge restrictions on battery cycling."
        ),
    ]
    initial_storage_capacity_level: Annotated[
        float,
        Field(
            ge=0, le=1, description="Initial storage capacity level as a ratio [0, 1.0] of storage_capacity."
        ),
    ]
    rating: Annotated[
        float,
        Unit("MVA", base="base_power"),
        Field(ge=0, description="Maximum output power rating of the unit (MVA)."),
    ]
    active_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(
            description="Initial active power set point of the unit in MW. For power flow, this is the steady state operating point of the system. For production cost modeling, this may or may not be used as the initial starting point for the solver, depending on the solver used."
        ),
    ]
    input_active_power_limits: Annotated[
        MinMax,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum limits on the input active power (i.e., charging)."),
    ]
    output_active_power_limits: Annotated[
        MinMax,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum limits on the output active power (i.e., discharging)."),
    ]
    efficiency: Annotated[
        InputOutput,
        Field(
            description="Average efficiency [0, 1] in (charging/filling) and out (discharging/consuming) of the storage system."
        ),
    ]
    reactive_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(description="Initial reactive power set point of the unit (MVAR)."),
    ]
    reactive_power_limits: Annotated[
        MinMax | None,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum reactive power limits. Set to None if not applicable."),
    ] = None
    base_power: Annotated[
        float,
        Unit("MVA"),
        Field(
            ge=0,
            description="Base power of the unit (MVA) for per unitization.",
        ),
    ]
    conversion_factor: Annotated[
        float,
        Field(
            ge=0,
            description="Conversion factor of storage_capacity to MWh, if different than 1.0. For example, X MWh/liter hydrogen.",
        ),
    ] = 1.0
    storage_target: Annotated[
        float,
        Field(
            ge=0, le=1, description="Storage target at the end of simulation as ratio of storage capacity."
        ),
    ] = 0.0
    cycle_limits: Annotated[
        int,
        Field(ge=0, description="Storage Maximum number of cycles per year."),
    ] = 10000

    @classmethod
    def example(cls) -> "EnergyReservoirStorage":
        return EnergyReservoirStorage(
            name="energy-reservoir-storage-test",
            available=True,
            bus=ACBus.example(),
            prime_mover_type=PrimeMoversType.BA,
            storage_technology_type=StorageTechs.OTHER_CHEM,
            storage_capacity=1000.0,
            storage_level_limits=MinMax(min=0.1, max=0.9),
            initial_storage_capacity_level=0.5,
            rating=250.0,
            active_power=0.0,
            input_active_power_limits=MinMax(min=0.0, max=200.0),
            output_active_power_limits=MinMax(min=0.0, max=200.0),
            efficiency=InputOutput(input=0.95, output=0.95),
            reactive_power=0.0,
            reactive_power_limits=MinMax(min=-50.0, max=50.0),
            base_power=250.0,
            conversion_factor=1.0,
            storage_target=0.5,
            cycle_limits=5000,
        )


class HybridSystem(Device):
    """A Hybrid System that includes a combination of renewable generation, load, thermal
    generation and/or energy storage.

    Components of the same type (e.g., PowerLoad) must have unique names, but components of
    different types (e.g., PowerLoad and ACBus) can have the same name.
    """

    status: Annotated[
        bool,
        Field(
            description="Initial commitment condition at the start of a simulation (True = on or False = off)."
        ),
    ]
    bus: Annotated[ACBus, Field(description="Bus that this component is connected to.")] | None = None
    active_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(
            description="Initial active power set point of the unit in MW. For power flow, this is the steady state operating point of the system. For production cost modeling, this may or may not be used as the initial starting point for the solver, depending on the solver used."
        ),
    ]
    reactive_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(description="Initial reactive power set point of the unit (MVAR)."),
    ]
    base_power: Annotated[
        float,
        Unit("MVA"),
        Field(
            ge=0,
            description="Base power of the unit (MVA) for per unitization, which is commonly the same as rating.",
        ),
    ]
    operation_cost: Annotated[
        "MarketBidCost",
        Field(description="Market bid cost to operate the hybrid system."),
    ]

    thermal_unit: Annotated[
        "ThermalStandard | None",
        Field(description="A thermal generator component."),
    ] = None
    electric_load: Annotated[
        "PowerLoad | InterruptiblePowerLoad | None",
        Field(description="An electric load component."),
    ] = None
    storage: Annotated[
        "EnergyReservoirStorage | None",
        Field(description="An energy storage system component."),
    ] = None
    renewable_unit: Annotated[
        "RenewableDispatch | RenewableNonDispatch | None",
        Field(description="A renewable generator component."),
    ] = None
    interconnection_impedance: Annotated[
        complex,
        Field(
            description="Impedance (typically in p.u.) between the hybrid system and the grid interconnection."
        ),
    ] = 0.0 + 0.0j
    interconnection_rating: Annotated[
        float | None,
        Unit("MVA", base="base_power"),
        Field(
            description="Maximum rating of the hybrid system's interconnection with the transmission network (MVA)."
        ),
    ] = None
    input_active_power_limits: Annotated[
        MinMax | None,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum stable input active power levels (MW)."),
    ] = None
    output_active_power_limits: Annotated[
        MinMax | None,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum stable output active power levels (MW)."),
    ] = None
    reactive_power_limits: Annotated[
        MinMax | None,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum reactive power limits (MVAR). Set to None if not applicable."),
    ] = None
    interconnection_efficiency: Annotated[
        InputOutput | None,
        Field(
            description="Efficiency [0, 1.0] at the grid interconnection to model losses in and out of the common DC-side conversion."
        ),
    ] = None

    @classmethod
    def example(cls) -> "HybridSystem":
        thermal_gen = ThermalStandard(
            name="thermal-standard-test",
            fuel=ThermalFuels.NATURAL_GAS,
            prime_mover_type=PrimeMoversType.CC,
            active_power=50.0,
            reactive_power=4.0,
            rating=100.0,
            base_power=100.0,
            must_run=False,
            status=True,
            time_at_status=0.0,
            active_power_limits=MinMax(min=10.0, max=100.0),
            operation_cost=ThermalGenerationCost.example(),
            category="thermal",
        )
        renewable_gen = RenewableDispatch(
            name="renewable-dispatch-test",
            prime_mover_type=PrimeMoversType.PVe,
            active_power=30.0,
            reactive_power=10.0,
            rating=50.0,
            base_power=50.0,
            operation_cost=RenewableGenerationCost(),
            category="renewable",
        )
        storage_unit = EnergyReservoirStorage(
            name="energy-reservoir-storage-test",
            prime_mover_type=PrimeMoversType.BA,
            storage_technology_type=StorageTechs.OTHER_CHEM,
            storage_capacity=200.0,  # MWh
            storage_level_limits=MinMax(min=0.1, max=0.9),
            initial_storage_capacity_level=0.5,
            rating=50.0,
            active_power=0.0,
            input_active_power_limits=MinMax(min=0.0, max=50.0),
            output_active_power_limits=MinMax(min=0.0, max=50.0),
            efficiency=InputOutput(input=0.95, output=0.95),
            reactive_power=0.0,
            base_power=50.0,
            category="storage",
        )
        electric_load_unit = PowerLoad(
            name="power-load",
            bus=ACBus.example(),
            active_power=ActivePower(25.0),
            reactive_power=5.0,
            max_active_power=ActivePower(30.0),
            max_reactive_power=ActivePower(8.0),
            base_power=ApparentPower(50.0),
            operation_cost=0.0,
            category="load",
        )

        hybrid_bid_cost = MarketBidCost.example()

        return HybridSystem(
            name="hybrid-system-test",
            available=True,
            status=True,
            bus=ACBus.example(),
            active_power=55.0,
            reactive_power=0.0,
            base_power=200.0,
            operation_cost=hybrid_bid_cost,
            thermal_unit=thermal_gen,
            renewable_unit=renewable_gen,
            storage=storage_unit,
            electric_load=electric_load_unit,
            interconnection_impedance=0.01 + 0.1j,
            interconnection_rating=200.0,
            input_active_power_limits=MinMax(min=0.0, max=150.0),
            output_active_power_limits=MinMax(min=0.0, max=200.0),
            reactive_power_limits=MinMax(min=-50.0, max=50.0),
            interconnection_efficiency=InputOutput(input=0.98, output=0.98),
            category="hybrid",
        )


class HydroGen(Device):
    """Abstract class for Hydro generators"""


class HydroDispatch(HydroGen):
    """A hydropower generator without a reservoir, suitable for modeling run-of-river hydropower.

    For hydro generators with an upper reservoir, see HydroReservoir.

    Components of the same type (e.g., PowerLoad) must have unique names, but components of
    different types (e.g., PowerLoad and ACBus) can have the same name.
    """

    bus: Annotated[ACBus, Field(description="Bus that this component is connected to.")] | None = None
    active_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(
            description="Initial active power set point of the unit in MW. For power flow, this is the steady state operating point of the system. For production cost modeling, this may or may not be used as the initial starting point for the solver, depending on the solver used."
        ),
    ]
    reactive_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(description="Initial reactive power set point of the unit (MVAR)."),
    ]
    rating: Annotated[
        float,
        Unit("MVA", base="base_power"),
        Field(ge=0, description="Maximum output power rating of the unit (MVA)."),
    ]
    prime_mover_type: Annotated[
        PrimeMoversType, Field(description="Prime mover technology according to EIA 923.")
    ]
    active_power_limits: Annotated[
        MinMax,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum stable active power levels (MW)."),
    ]
    reactive_power_limits: Annotated[
        MinMax | None,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum reactive power limits. Set to None if not applicable."),
    ] = None
    ramp_limits: Annotated[
        UpDown | None,
        Unit("pu/min", base="base_power"),
        Field(description="Ramp up and ramp down limits in MW/min."),
    ] = None
    time_limits: Annotated[
        UpDown | None,
        Unit("hour"),
        Field(description="Minimum up and Minimum down time limits in hours."),
    ] = None
    base_power: Annotated[
        float,
        Unit("MVA"),
        Field(
            ge=0,
            description="Base power of the unit (MVA) for per unitization.",
        ),
    ]
    status: Annotated[
        bool,
        Field(
            description="Initial commitment condition at the start of a simulation (True = on or False = off)."
        ),
    ] = False
    time_at_status: Annotated[
        float,
        Unit("hour"),
        Field(description="Time the generator has been on or off, as indicated by status."),
    ] = float("inf")
    operation_cost: Annotated[
        "HydroGenerationCost | MarketBidCost",
        Field(description="Operational cost of generation."),
    ]

    @classmethod
    def example(cls) -> "HydroDispatch":
        """Create an example HydroDispatch instance for demo purposes."""
        # Import here to avoid circular imports
        from .costs import HydroGenerationCost

        return HydroDispatch(
            name="hydro-dispatch-test",
            available=True,
            bus=ACBus.example(),
            active_power=80.0,
            reactive_power=0.0,
            rating=100.0,
            prime_mover_type=PrimeMoversType.HY,
            active_power_limits=MinMax(min=10.0, max=100.0),
            reactive_power_limits=MinMax(min=-30.0, max=30.0),
            ramp_limits=UpDown(up=5.0, down=5.0),
            time_limits=UpDown(up=1.0, down=1.0),
            base_power=100.0,
            status=True,
            time_at_status=24.0,
            operation_cost=HydroGenerationCost.example(),
            category="hydro",
        )


class HydroEnergyReservoir(HydroGen):
    """A hydropower generator with an upper reservoir, offering some energy storage and operational flexibility.

    For hydro generators with pumped storage, see HydroPumpedStorage.

    Note: This class was used in PowerSystems.jl v4. In PowerSystems.jl v5, this functionality
    has been split into separate HydroReservoir and HydroTurbine components for more detailed
    modeling of hydro systems.

    Components of the same type (e.g., PowerLoad) must have unique names, but components of
    different types (e.g., PowerLoad and ACBus) can have the same name.
    """

    bus: Annotated[ACBus, Field(description="Bus that this component is connected to.")] | None = None
    active_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(
            description="Initial active power set point of the unit in MW. For power flow, this is the steady state operating point of the system. For production cost modeling, this may or may not be used as the initial starting point for the solver, depending on the solver used."
        ),
    ]
    reactive_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(description="Initial reactive power set point of the unit (MVAR)."),
    ]
    rating: Annotated[
        float,
        Unit("MVA", base="base_power"),
        Field(ge=0, description="Maximum output power rating of the unit (MVA)."),
    ]
    prime_mover_type: Annotated[
        PrimeMoversType, Field(description="Prime mover technology according to EIA 923.")
    ]
    active_power_limits: Annotated[
        MinMax,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum stable active power levels (MW)."),
    ]
    reactive_power_limits: Annotated[
        MinMax | None,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum reactive power limits. Set to None if not applicable."),
    ] = None
    ramp_limits: Annotated[
        UpDown | None,
        Unit("pu/min", base="base_power"),
        Field(description="Ramp up and ramp down limits in MW/min."),
    ] = None
    time_limits: Annotated[
        UpDown | None,
        Unit("hour"),
        Field(description="Minimum up and Minimum down time limits in hours."),
    ] = None
    base_power: Annotated[
        float,
        Unit("MVA"),
        Field(
            ge=0,
            description="Base power of the unit (MVA) for per unitization.",
        ),
    ]
    storage_capacity: Annotated[
        float,
        Unit("pu-hour", base="base_power"),
        Field(ge=0, description="Maximum storage capacity in the reservoir (units can be p.u-hr or m^3)."),
    ]
    inflow: Annotated[
        float,
        Unit("pu/hour", base="base_power"),
        Field(ge=0, description="Baseline inflow into the reservoir (units can be p.u. or m^3/hr)."),
    ]
    initial_storage: Annotated[
        float,
        Unit("pu-hour", base="base_power"),
        Field(ge=0, description="Initial storage capacity in the reservoir (units can be p.u-hr or m^3)."),
    ]
    operation_cost: Annotated[
        "HydroGenerationCost | StorageCost | MarketBidCost",
        Field(description="Operational cost of generation."),
    ]
    storage_target: Annotated[
        float,
        Field(
            ge=0,
            le=1,
            description="Storage target at the end of simulation as a fraction of storage capacity.",
        ),
    ] = 1.0
    conversion_factor: Annotated[
        float,
        Field(ge=0, description="Conversion factor from flow/volume to energy: m^3 -> p.u-hr."),
    ] = 1.0
    status: Annotated[
        bool,
        Field(
            description="Initial commitment condition at the start of a simulation (True = on or False = off)."
        ),
    ] = False
    time_at_status: Annotated[
        float,
        Unit("hour"),
        Field(description="Time the generator has been on or off, as indicated by status."),
    ] = float("inf")

    @classmethod
    def example(cls) -> "HydroEnergyReservoir":
        return HydroEnergyReservoir(
            name="hydro-energy-reservoir-test",
            available=True,
            bus=ACBus.example(),
            active_power=150.0,
            reactive_power=0.0,
            rating=200.0,
            prime_mover_type=PrimeMoversType.HY,
            active_power_limits=MinMax(min=20.0, max=200.0),
            reactive_power_limits=MinMax(min=-50.0, max=50.0),
            ramp_limits=UpDown(up=10.0, down=10.0),
            time_limits=UpDown(up=2.0, down=2.0),
            base_power=200.0,
            storage_capacity=5000.0,
            inflow=50.0,
            initial_storage=2500.0,
            operation_cost=HydroGenerationCost.example(),
            storage_target=0.8,
            conversion_factor=1.0,
            status=True,
            time_at_status=12.0,
            category="hydro_reservoir",
        )


class HydroPumpedStorage(HydroGen):
    """A hydropower generator with pumped storage and upper and lower reservoirs.

    Note: This class was used in PowerSystems.jl v4. In PowerSystems.jl v5, this functionality
    has been split into separate HydroReservoir and HydroPumpTurbine components for more detailed
    modeling of hydro systems.

    Components of the same type (e.g., PowerLoad) must have unique names, but components of
    different types (e.g., PowerLoad and ACBus) can have the same name.
    """

    bus: Annotated[ACBus, Field(description="Bus that this component is connected to.")] | None = None
    active_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(
            description="Initial active power set point of the unit in MW. For power flow, this is the steady state operating point of the system. For production cost modeling, this may or may not be used as the initial starting point for the solver, depending on the solver used."
        ),
    ]
    reactive_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(description="Initial reactive power set point of the unit (MVAR)."),
    ]
    rating: Annotated[
        float,
        Unit("MVA", base="base_power"),
        Field(ge=0, description="Maximum output power rating of the unit (MVA)."),
    ]
    base_power: Annotated[
        float,
        Unit("MVA"),
        Field(
            ge=0,
            description="Base power of the unit (MVA) for per unitization.",
        ),
    ]
    prime_mover_type: Annotated[
        PrimeMoversType, Field(description="Prime mover technology according to EIA 923.")
    ]
    active_power_limits: Annotated[
        MinMax,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum stable active power levels (MW)."),
    ]
    reactive_power_limits: Annotated[
        MinMax | None,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum reactive power limits. Set to None if not applicable."),
    ] = None
    ramp_limits: Annotated[
        UpDown | None,
        Unit("pu/min", base="base_power"),
        Field(description="Ramp up and ramp down limits in MW/min."),
    ] = None
    time_limits: Annotated[
        UpDown | None,
        Unit("hour"),
        Field(description="Minimum up and Minimum down time limits in hours."),
    ] = None
    rating_pump: Annotated[
        float,
        Unit("MVA", base="base_power"),
        Field(ge=0, description="Maximum power withdrawal (MVA) of the pump."),
    ]
    active_power_limits_pump: Annotated[
        MinMax,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum active power limits for pump operation (MW)."),
    ]
    reactive_power_limits_pump: Annotated[
        MinMax | None,
        Unit("pu", base="base_power"),
        Field(
            description="Minimum and maximum reactive power limits for pump operation. Set to None if not applicable."
        ),
    ] = None
    ramp_limits_pump: Annotated[
        UpDown | None,
        Unit("pu/min", base="base_power"),
        Field(description="Ramp up and ramp down limits in MW/min of pump."),
    ] = None
    time_limits_pump: Annotated[
        UpDown | None,
        Unit("hour"),
        Field(description="Minimum up and Minimum down time limits of pump in hours."),
    ] = None
    storage_capacity: Annotated[
        UpDown,
        Unit("pu-hour", base="base_power"),
        Field(
            description="Maximum storage capacity in the upper and lower reservoirs (units can be p.u-hr or m^3)."
        ),
    ]
    inflow: Annotated[
        float,
        Unit("pu/hour", base="base_power"),
        Field(ge=0, description="Baseline inflow into the upper reservoir (units can be p.u. or m^3/hr)."),
    ]
    outflow: Annotated[
        float,
        Unit("pu/hour", base="base_power"),
        Field(ge=0, description="Baseline outflow from the lower reservoir (units can be p.u. or m^3/hr)."),
    ]
    initial_storage: Annotated[
        UpDown,
        Unit("pu-hour", base="base_power"),
        Field(
            description="Initial storage capacity in the upper and lower reservoir (units can be p.u-hr or m^3)."
        ),
    ]
    storage_target: Annotated[
        UpDown,
        Field(
            description="Storage target of upper reservoir at the end of simulation as ratio of storage capacity."
        ),
    ] = UpDown(up=1.0, down=1.0)
    operation_cost: Annotated[
        "HydroGenerationCost | StorageCost | MarketBidCost",
        Field(description="Operational cost of generation."),
    ]
    pump_efficiency: Annotated[
        float,
        Field(ge=0, le=1, description="Pumping efficiency [0, 1.0]."),
    ] = 1.0
    conversion_factor: Annotated[
        float,
        Field(ge=0, description="Conversion factor from flow/volume to energy: m^3 -> p.u-hr."),
    ] = 1.0
    status: Annotated[
        "PumpHydroStatus",
        Field(description="Initial commitment condition at the start of a simulation (PUMP, GEN, or OFF)."),
    ] = PumpHydroStatus.OFF
    time_at_status: Annotated[
        float,
        Unit("hour"),
        Field(description="Time the generator has been generating, pumping, or off, as indicated by status."),
    ] = float("inf")

    @classmethod
    def example(cls) -> "HydroPumpedStorage":
        return HydroPumpedStorage(
            name="hydro-pumped-storage-test",
            available=True,
            bus=ACBus.example(),
            active_power=0.0,
            reactive_power=0.0,
            rating=400.0,
            base_power=400.0,
            prime_mover_type=PrimeMoversType.PS,
            active_power_limits=MinMax(min=50.0, max=400.0),
            reactive_power_limits=MinMax(min=-100.0, max=100.0),
            ramp_limits=UpDown(up=20.0, down=20.0),
            time_limits=UpDown(up=0.5, down=0.5),
            rating_pump=300.0,
            active_power_limits_pump=MinMax(min=30.0, max=300.0),
            reactive_power_limits_pump=MinMax(min=-75.0, max=75.0),
            ramp_limits_pump=UpDown(up=15.0, down=15.0),
            time_limits_pump=UpDown(up=0.5, down=0.5),
            storage_capacity=UpDown(up=8000.0, down=2000.0),
            inflow=20.0,
            outflow=5.0,
            initial_storage=UpDown(up=4000.0, down=1000.0),
            storage_target=UpDown(up=0.8, down=0.5),
            operation_cost=HydroGenerationCost.example(),
            pump_efficiency=0.85,
            conversion_factor=1.0,
            status=PumpHydroStatus.OFF,
            time_at_status=0.0,
            category="hydro_pumped_storage",
        )


class HydroReservoir(Device):
    """A hydropower reservoir that needs to be attached to HydroTurbine(s) or HydroPumpTurbine(s) to generate power.

    See How to Define Hydro Generators with Reservoirs for supported configurations.

    Components of the same type (e.g., PowerLoad) must have unique names, but components of
    different types (e.g., PowerLoad and ACBus) can have the same name.
    """

    storage_level_limits: Annotated[
        MinMax,
        Field(
            description="Storage level limits for the reservoir in m^3 (if data type is volume), m (if data type is head) or MWh (if data type is energy)."
        ),
    ]
    initial_level: Annotated[
        float,
        Field(description="Initial level of the reservoir relative to the storage_level_limits.max."),
    ]
    spillage_limits: Annotated[
        MinMax | None,
        Field(
            description="Amount of water allowed to be spilled from the reservoir. If nothing, infinite spillage is allowed."
        ),
    ] = None
    inflow: Annotated[
        float,
        Field(description="Amount of water refilling the reservoir in m^3/h or MW (if data type is energy)."),
    ]
    outflow: Annotated[
        float,
        Field(description="Amount of water going to the turbine(s) in m^3/h or MW (if data type is energy)."),
    ]
    level_targets: Annotated[
        float | None,
        Field(
            description="Reservoir level targets at the end of a simulation as a fraction of the storage_level_limits.max."
        ),
    ] = None
    travel_time: Annotated[
        float | None,
        Unit("hour"),
        Field(description="Downstream travel time in hours."),
    ] = None
    intake_elevation: Annotated[
        float,
        Unit("m"),
        Field(description="Height of the intake of the reservoir in meters above the sea level."),
    ]
    head_to_volume_factor: Annotated[
        InputOutputCurve,
        Field(description="Head to volume relationship for the reservoir."),
    ] = LinearCurve(0.0)
    reservoir_location: Annotated[
        ReservoirLocation,
        Field(description="Location of the reservoir relative to the turbine."),
    ] = ReservoirLocation.HEAD
    operation_cost: Annotated[
        HydroReservoirCost,
        Field(description="HydroReservoirCost of reservoir."),
    ]
    level_data_type: Annotated[
        ReservoirDataType,
        Field(description="Reservoir data type, which defines units for level parameters."),
    ] = ReservoirDataType.USABLE_VOLUME

    @classmethod
    def example(cls) -> "HydroReservoir":
        return HydroReservoir(
            name="hydro-reservoir-test",
            available=True,
            storage_level_limits=MinMax(min=0.0, max=1000.0),
            initial_level=0.5,
            spillage_limits=MinMax(min=0.0, max=100.0),
            inflow=50.0,
            outflow=30.0,
            level_targets=0.8,
            travel_time=2.0,
            intake_elevation=500.0,
            head_to_volume_factor=LinearCurve(1.0),
            reservoir_location=ReservoirLocation.HEAD,
            operation_cost=HydroReservoirCost(),
            level_data_type=ReservoirDataType.USABLE_VOLUME,
            category="hydro_reservoir",
        )


class HydroTurbine(HydroGen):
    """A hydropower generator that must have a HydroReservoir attached, suitable for modeling independent turbines and reservoirs.

    Components of the same type (e.g., PowerLoad) must have unique names, but components of
    different types (e.g., PowerLoad and ACBus) can have the same name.
    """

    bus: Annotated[ACBus, Field(description="Bus that this component is connected to.")] | None = None
    active_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(
            description="Initial active power set point of the unit in MW. For power flow, this is the steady state operating point of the system. For production cost modeling, this may or may not be used as the initial starting point for the solver, depending on the solver used."
        ),
    ]
    reactive_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(description="Initial reactive power set point of the unit (MVAR)."),
    ]
    rating: Annotated[
        float,
        Unit("MVA", base="base_power"),
        Field(ge=0, description="Maximum output power rating of the unit (MVA)."),
    ]
    active_power_limits: Annotated[
        MinMax,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum stable active power levels (MW)."),
    ]
    reactive_power_limits: Annotated[
        MinMax | None,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum reactive power limits. Set to None if not applicable."),
    ] = None
    base_power: Annotated[
        float,
        Unit("MVA"),
        Field(
            ge=0,
            description="Base power of the unit (MVA) for per unitization.",
        ),
    ]
    operation_cost: Annotated[
        "HydroGenerationCost | MarketBidCost",
        Field(description="Operational cost of generation."),
    ]
    powerhouse_elevation: Annotated[
        float,
        Unit("m"),
        Field(
            ge=0,
            description="Height level in meters above the sea level of the powerhouse on which the turbine is installed.",
        ),
    ] = 0.0
    ramp_limits: Annotated[
        UpDown | None,
        Unit("pu/min", base="base_power"),
        Field(description="Ramp up and ramp down limits in MW/min."),
    ] = None
    time_limits: Annotated[
        UpDown | None,
        Unit("hour"),
        Field(description="Minimum up and Minimum down time limits in hours."),
    ] = None
    outflow_limits: Annotated[
        MinMax | None,
        Unit("m3/s"),
        Field(description="Turbine outflow limits in m3/s. Set to None if not applicable."),
    ] = None
    efficiency: Annotated[
        float,
        Field(ge=0, le=1, description="Turbine efficiency [0, 1.0]."),
    ] = 1.0
    turbine_type: Annotated[
        "HydroTurbineType",
        Field(description="Type of the turbine."),
    ] = HydroTurbineType.UNKNOWN
    conversion_factor: Annotated[
        float,
        Field(ge=0, description="Conversion factor from flow/volume to energy: m^3 -> p.u-hr."),
    ] = 1.0
    reservoirs: Annotated[
        list[HydroReservoir],
        Field(description="HydroReservoir(s) that this component is connected to."),
    ] = []

    @classmethod
    def example(cls) -> "HydroTurbine":
        reservoir = HydroReservoir.example()
        return HydroTurbine(
            name="hydro-turbine-test",
            available=True,
            bus=ACBus.example(),
            active_power=120.0,
            reactive_power=0.0,
            rating=150.0,
            active_power_limits=MinMax(min=15.0, max=150.0),
            reactive_power_limits=MinMax(min=-45.0, max=45.0),
            base_power=150.0,
            operation_cost=HydroGenerationCost.example(),
            powerhouse_elevation=350.0,
            ramp_limits=UpDown(up=8.0, down=8.0),
            time_limits=UpDown(up=1.5, down=1.5),
            outflow_limits=MinMax(min=5.0, max=100.0),
            efficiency=0.92,
            turbine_type=HydroTurbineType.FRANCIS,
            conversion_factor=1.0,
            reservoirs=[reservoir],
            category="hydro_turbine",
        )


class HydroPumpTurbine(HydroGen):
    """A hydropower pumped turbine that needs to have two HydroReservoirs attached, suitable for modeling independent pumped hydro with reservoirs.

    Components of the same type (e.g., PowerLoad) must have unique names, but components of
    different types (e.g., PowerLoad and ACBus) can have the same name.
    """

    bus: Annotated[ACBus, Field(description="Bus that this component is connected to.")] | None = None
    active_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(
            description="Initial active power set point of the turbine unit in MW. For power flow, this is the steady state operating point of the system. For production cost modeling, this may or may not be used as the initial starting point for the solver, depending on the solver used."
        ),
    ]
    reactive_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(description="Initial reactive power set point of the unit (MVAR)."),
    ]
    rating: Annotated[
        float,
        Unit("MVA", base="base_power"),
        Field(ge=0, description="Maximum output power rating of the unit (MVA)."),
    ]
    active_power_limits: Annotated[
        MinMax,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum stable active power levels (MW) for the turbine."),
    ]
    reactive_power_limits: Annotated[
        MinMax | None,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum reactive power limits. Set to None if not applicable."),
    ] = None
    active_power_limits_pump: Annotated[
        MinMax,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum stable active power levels (MW) for the pump."),
    ]
    outflow_limits: Annotated[
        MinMax | None,
        Unit("m3/s"),
        Field(description="Turbine/Pump outflow limits in m3/s. Set to None if not applicable."),
    ] = None
    head_reservoir: Annotated[
        "HydroReservoir",
        Field(description="Head HydroReservoir that this component is connected to."),
    ]
    tail_reservoir: Annotated[
        "HydroReservoir",
        Field(description="Tail HydroReservoir that this component is connected to."),
    ]
    powerhouse_elevation: Annotated[
        float,
        Unit("m"),
        Field(
            ge=0,
            description="Height level in meters above the sea level of the powerhouse on which the turbine is installed.",
        ),
    ]
    ramp_limits: Annotated[
        UpDown | None,
        Unit("pu/min", base="base_power"),
        Field(description="Ramp up and ramp down limits in MW/min."),
    ] = None
    time_limits: Annotated[
        UpDown | None,
        Unit("hour"),
        Field(description="Minimum up and Minimum down time limits in hours."),
    ] = None
    base_power: Annotated[
        float,
        Unit("MVA"),
        Field(
            ge=0,
            description="Base power of the unit (MVA) for per unitization.",
        ),
    ]
    status: Annotated[
        PumpHydroStatus,
        Field(description="Initial Operating status of a pumped storage hydro unit."),
    ] = PumpHydroStatus.OFF
    time_at_status: Annotated[
        float,
        Unit("hour"),
        Field(description="Time the generator has been on or off, as indicated by status."),
    ] = float("inf")
    operation_cost: Annotated[
        HydroGenerationCost | MarketBidCost,
        Field(description="Operational cost of generation."),
    ]
    active_power_pump: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(
            description="Initial active power set point of the pump unit in MW. For power flow, this is the steady state operating point of the system. For production cost modeling, this may or may not be used as the initial starting point for the solver, depending on the solver used."
        ),
    ] = 0.0
    efficiency: Annotated[
        TurbinePump,
        Unit("%"),
        Field(description="Turbine/Pump efficiency [0, 1.0]."),
    ]
    transition_time: Annotated[
        TurbinePump,
        Unit("hour"),
        Field(description="Transition time in hours to switch into the specific mode."),
    ]
    minimum_time: Annotated[
        TurbinePump,
        Unit("hour"),
        Field(description="Minimum operating time in hours for the specific mode."),
    ]
    conversion_factor: Annotated[
        float,
        Field(ge=0, description="Conversion factor from flow/volume to energy: m^3 -> p.u-hr."),
    ] = 1.0
    must_run: Annotated[
        bool,
        Field(description="Whether the unit must run (i.e., cannot be curtailed)."),
    ] = False

    @classmethod
    def example(cls) -> "HydroPumpTurbine":
        head_reservoir = HydroReservoir(
            name="head_reservoir",
            available=True,
            storage_level_limits=MinMax(min=500.0, max=2000.0),
            initial_level=0.7,
            spillage_limits=MinMax(min=0.0, max=200.0),
            inflow=30.0,
            outflow=0.0,
            level_targets=0.8,
            travel_time=1.0,
            intake_elevation=800.0,
            head_to_volume_factor=LinearCurve(1.0),
            reservoir_location=ReservoirLocation.HEAD,
            operation_cost=HydroReservoirCost(),
            level_data_type=ReservoirDataType.USABLE_VOLUME,
            category="hydro_reservoir",
        )
        tail_reservoir = HydroReservoir(
            name="tail_reservoir",
            available=True,
            storage_level_limits=MinMax(min=100.0, max=800.0),
            initial_level=0.5,
            spillage_limits=MinMax(min=0.0, max=100.0),
            inflow=0.0,
            outflow=20.0,
            level_targets=0.5,
            travel_time=0.5,
            intake_elevation=400.0,
            head_to_volume_factor=LinearCurve(1.0),
            reservoir_location=ReservoirLocation.TAIL,
            operation_cost=HydroReservoirCost(),
            level_data_type=ReservoirDataType.USABLE_VOLUME,
            category="hydro_reservoir",
        )
        return HydroPumpTurbine(
            name="hydro-pump-turbine-test",
            available=True,
            bus=ACBus.example(),
            active_power=0.0,
            reactive_power=0.0,
            rating=500.0,
            active_power_limits=MinMax(min=50.0, max=500.0),
            reactive_power_limits=MinMax(min=-150.0, max=150.0),
            active_power_limits_pump=MinMax(min=50.0, max=400.0),
            outflow_limits=MinMax(min=10.0, max=200.0),
            head_reservoir=head_reservoir,
            tail_reservoir=tail_reservoir,
            powerhouse_elevation=600.0,
            ramp_limits=UpDown(up=25.0, down=25.0),
            time_limits=UpDown(up=1.0, down=1.0),
            base_power=500.0,
            status=PumpHydroStatus.OFF,
            time_at_status=0.0,
            operation_cost=HydroGenerationCost.example(),
            active_power_pump=0.0,
            efficiency=TurbinePump(turbine=0.90, pump=0.85),
            transition_time=TurbinePump(turbine=0.25, pump=0.25),
            minimum_time=TurbinePump(turbine=1.0, pump=1.0),
            conversion_factor=1.0,
            must_run=False,
            category="hydro_pump_turbine",
        )
