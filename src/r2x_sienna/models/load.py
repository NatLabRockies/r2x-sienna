"""Electric load related models."""

from typing import Annotated

from infrasys.value_curves import InputOutputCurve, LinearCurve
from pydantic import Field, NonNegativeFloat
from r2x_core import Unit

from r2x_sienna.models.core import DynamicInjection, StaticInjection
from r2x_sienna.models.costs import LoadCost, MarketBidCost
from r2x_sienna.models.enums import FACTSOperationModes, LoadConformity, MotorLoadTechnology
from r2x_sienna.models.named_tuples import Complex, MinMax
from r2x_sienna.models.topology import ACBus, Bus, DCBus
from r2x_sienna.units import ActivePower, ApparentPower


class ElectricLoad(StaticInjection):
    """Supertype for all electric loads."""

    bus: Bus = Field(description="Point of injection.")


class FACTSControlDevice(StaticInjection):
    """FACTS control devices. Used in AC power flow studies as a control of voltage and,
    active and reactive power.
    """

    bus: Annotated[ACBus, Field(description="Sending end bus number")]
    control_mode: Annotated[
        FACTSOperationModes | None,
        Field(
            default=None,
            description=(
                "Control mode. Used to describe the behavior of the control device. "
                "Options: OOS (out-of-service), NML (normal mode), BYP (bypass mode)"
            ),
        ),
    ] = None
    voltage_setpoint: Annotated[
        float,
        Field(
            description=(
                "Voltage setpoint at the sending end bus, it has to be a PV bus, in p.u. (SYSTEM_BASE)"
            )
        ),
    ] = 1.0
    max_shunt_current: Annotated[
        float,
        Field(
            ge=0, description="Maximum shunt current at the sending end bus; entered in MVA at unity voltage"
        ),
    ] = 9999.0
    max_reactive_power: Annotated[
        float,
        Field(ge=0, description="Maximum reactive power ceiling (MVA)."),
    ] = 9999.0
    shunt_control_type: Annotated[
        str,
        Field(description="FACTS shunt control type (e.g., STATCOM or SVC)."),
    ] = "STATCOM"
    regulated_bus_number: Annotated[
        int,
        Field(description="Bus number whose voltage this device regulates; 0 means local bus."),
    ] = 0
    reactive_power_required: Annotated[
        float, Field(description="Total MVAr required to hold voltage at sending bus, in %")
    ] = 100.0

    @classmethod
    def example(cls) -> "FACTSControlDevice":
        """Create an example FACTSControlDevice instance."""
        return FACTSControlDevice(
            name="FACTS_Device_1",
            available=True,
            bus=ACBus.example(),
            control_mode=FACTSOperationModes.NML,
            voltage_setpoint=1.05,
            max_shunt_current=100.0,
            reactive_power_required=50.0,
        )


class StaticLoad(ElectricLoad):
    """Supertype for static loads."""


class InterconnectingConverter(StaticInjection):
    """Converter connecting an AC bus to a DC bus."""

    bus: Annotated[ACBus, Field(description="AC bus connected to the converter.")]
    dc_bus: Annotated[DCBus, Field(description="DC bus connected to the converter.")]
    active_power: Annotated[
        float,
        Unit("pu", base="base_power"),
        Field(description="Initial active power set point of the converter."),
    ]
    rating: Annotated[
        float,
        Unit("MVA", base="base_power"),
        Field(ge=0, description="Maximum output power rating of the converter."),
    ]
    active_power_limits: Annotated[
        MinMax,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum active power limits for the converter."),
    ]
    base_power: Annotated[
        float,
        Unit("MVA"),
        Field(gt=0, description="Base power of the converter for per-unitization."),
    ]
    reactive_power_limits: Annotated[
        MinMax | None,
        Unit("pu", base="base_power"),
        Field(description="Minimum and maximum reactive power limits. Set to None if not applicable."),
    ] = None
    dc_current: Annotated[float, Unit("A"), Field(ge=0, description="DC current (A) on the converter.")] = 0.0
    max_dc_current: Annotated[
        float,
        Unit("A"),
        Field(ge=0, description="Maximum stable DC current limit."),
    ] = 1e8
    loss_function: Annotated[
        InputOutputCurve,
        Field(description="Converter loss model coefficients. PSY accepts linear or quadratic curves."),
    ] = LinearCurve(0.0)
    dc_control: Annotated[str, Field(description="DC-side control mode.")] = "DC_VOLTAGE"
    ac_control: Annotated[str, Field(description="AC-side control mode.")] = "AC_REACTIVE_POWER"
    dc_setpoint: Annotated[float, Field(description="Converter DC setpoint in per-unit.")] = 0.0
    ac_setpoint: Annotated[float, Field(description="Converter AC setpoint in per-unit.")] = 1.0
    dc_voltage_droop: Annotated[float, Field(description="DC-voltage droop gain.")] = 0.0
    dynamic_injector: Annotated[
        DynamicInjection | None,
        Field(description="Dynamic injection model attached to this converter."),
    ] = None

    @classmethod
    def example(cls) -> "InterconnectingConverter":
        return InterconnectingConverter(
            name="InterconnectingConverter_1",
            available=True,
            bus=ACBus.example(),
            dc_bus=DCBus.example(),
            active_power=0.0,
            rating=100.0,
            active_power_limits=MinMax(min=-100.0, max=100.0),
            base_power=100.0,
            reactive_power_limits=MinMax(min=-50.0, max=50.0),
            max_dc_current=1.0,
            loss_function=LinearCurve(0.0),
        )


class ControllableLoad(ElectricLoad):
    """Abstract class for controllable loads."""


class PowerLoad(StaticLoad):
    """Class representing a Load object."""

    active_power: (
        Annotated[
            ActivePower,
            Field(ge=0, description="Initial steady-state active power demand."),
        ]
        | None
    ) = None
    reactive_power: (
        Annotated[float, Field(ge=0, description="Reactive Power of Load at the bus in MW.")] | None
    ) = None
    max_active_power: Annotated[ActivePower, Field(ge=0, description="Max Load at the bus in MW.")] | None = (
        None
    )
    max_reactive_power: (
        Annotated[ActivePower, Field(ge=0, description=" Initial steady-state reactive power demand.")] | None
    ) = None
    base_power: Annotated[
        ApparentPower | None,
        Field(
            gt=0,
            description="Base power of the unit (MVA) for per unitization.",
        ),
    ] = None
    conformity: LoadConformity = Field(default=LoadConformity.UNDEFINED, validation_alias="comformity")

    @classmethod
    def example(cls) -> "PowerLoad":
        return PowerLoad(
            name="ExampleLoad",
            bus=ACBus.example(),
            conformity=LoadConformity.CONFORMING,
            active_power=ActivePower(1000, "MW"),
        )


class StandardLoad(StaticLoad):
    base_power: NonNegativeFloat
    constant_active_power: float
    constant_reactive_power: float
    impedance_active_power: float
    impedance_reactive_power: float
    conformity: LoadConformity = Field(default=LoadConformity.UNDEFINED, validation_alias="comformity")
    current_active_power: float
    current_reactive_power: float
    max_constant_active_power: float
    max_constant_reactive_power: float
    max_impedance_active_power: float
    max_impedance_reactive_power: float
    max_current_active_power: float
    max_current_reactive_power: float


class InterruptiblePowerLoad(ControllableLoad):
    """A static interruptible power load."""

    base_power: Annotated[
        ApparentPower | None,
        Field(
            gt=0,
            description="Base power of the unit (MVA) for per unitization.",
        ),
    ] = None
    active_power: (
        Annotated[
            ActivePower,
            Field(gt=0, description="Initial steady-state active power demand."),
        ]
        | None
    ) = None
    reactive_power: (
        Annotated[float, Field(gt=0, description="Reactive Power of Load at the bus in MW.")] | None
    ) = None
    max_active_power: Annotated[ActivePower, Field(ge=0, description="Max Load at the bus in MW.")] | None = (
        None
    )
    max_reactive_power: (
        Annotated[ActivePower, Field(gt=0, description=" Initial steady-state reactive power demand.")] | None
    ) = None
    operation_cost: LoadCost | None = None
    conformity: LoadConformity = Field(default=LoadConformity.UNDEFINED, validation_alias="comformity")


class InterruptibleStandardLoad(ControllableLoad):
    """A voltage-dependent ZIP interruptible load (Z=impedance, I=current, P=power)."""

    base_power: Annotated[
        ApparentPower,
        Field(gt=0, description="Base power of the load (MVA) for per unitization."),
    ]
    operation_cost: LoadCost | MarketBidCost | None = None
    conformity: LoadConformity = LoadConformity.UNDEFINED
    constant_active_power: Annotated[
        float, Field(default=0.0, description="Constant active power demand in MW (P_P).")
    ] = 0.0
    constant_reactive_power: Annotated[
        float, Field(default=0.0, description="Constant reactive power demand in MVAR (Q_P).")
    ] = 0.0
    impedance_active_power: Annotated[
        float,
        Field(default=0.0, description="Active power coefficient in MW for constant impedance load (P_Z)."),
    ] = 0.0
    impedance_reactive_power: Annotated[
        float,
        Field(
            default=0.0, description="Reactive power coefficient in MVAR for constant impedance load (Q_Z)."
        ),
    ] = 0.0
    current_active_power: Annotated[
        float,
        Field(default=0.0, description="Active power coefficient in MW for constant current load (P_I)."),
    ] = 0.0
    current_reactive_power: Annotated[
        float,
        Field(default=0.0, description="Reactive power coefficient in MVAR for constant current load (Q_I)."),
    ] = 0.0
    max_constant_active_power: Annotated[
        float, Field(default=0.0, description="Maximum active power (MW) drawn by constant power load.")
    ] = 0.0
    max_constant_reactive_power: Annotated[
        float, Field(default=0.0, description="Maximum reactive power (MVAR) drawn by constant power load.")
    ] = 0.0
    max_impedance_active_power: Annotated[
        float, Field(default=0.0, description="Maximum active power (MW) drawn by constant impedance load.")
    ] = 0.0
    max_impedance_reactive_power: Annotated[
        float,
        Field(default=0.0, description="Maximum reactive power (MVAR) drawn by constant impedance load."),
    ] = 0.0
    max_current_active_power: Annotated[
        float, Field(default=0.0, description="Maximum active power (MW) drawn by constant current load.")
    ] = 0.0
    max_current_reactive_power: Annotated[
        float, Field(default=0.0, description="Maximum reactive power (MVAR) drawn by constant current load.")
    ] = 0.0


class ShiftablePowerLoad(ControllableLoad):
    """A static power load that can be partially or fully shifted to later time periods."""

    active_power: Annotated[
        ActivePower,
        Field(description="Initial steady state active power demand (MW)."),
    ]
    active_power_limits: Annotated[
        MinMax,
        Field(description="Minimum and maximum stable active power levels (MW)."),
    ]
    reactive_power: Annotated[
        float,
        Field(description="Initial steady state reactive power demand (MVAR)."),
    ]
    max_active_power: Annotated[
        ActivePower,
        Field(description="Maximum active power (MW) that this load can demand."),
    ]
    max_reactive_power: Annotated[
        float,
        Field(description="Maximum reactive power (MVAR) that this load can demand."),
    ]
    base_power: Annotated[
        ApparentPower,
        Field(gt=0, description="Base power (MVA) for per unitization."),
    ]
    load_balance_time_horizon: Annotated[
        int,
        Field(ge=1, description="Number of time periods over which load must be balanced."),
    ]
    operation_cost: LoadCost | MarketBidCost | None = None


class MotorLoad(StaticLoad):
    """A static motor load."""

    active_power: Annotated[
        ActivePower,
        Field(
            description="Initial steady-state active power demand (MW). A positive value indicates power consumption."
        ),
    ]
    reactive_power: Annotated[
        float,
        Field(
            description="Initial steady-state reactive power demand (MVAR). A positive value indicates reactive power consumption."
        ),
    ]
    base_power: Annotated[
        ApparentPower,
        Field(gt=0, description="Base power (MVA) for per unitization."),
    ]
    rating: Annotated[
        float,
        Field(
            ge=0,
            description="Maximum AC side output power rating of the unit. Stored in per unit of the device.",
        ),
    ]
    max_active_power: Annotated[
        ActivePower,
        Field(description="Maximum active power (MW) that this load can demand."),
    ]
    reactive_power_limits: MinMax | None = None
    motor_technology: MotorLoadTechnology = MotorLoadTechnology.UNDETERMINED


class ExponentialLoad(StaticLoad):
    """A voltage-dependent exponential load.

    Models active power as P = P0 * V^α and reactive power as Q = Q0 * V^β.
    """

    active_power: Annotated[
        ActivePower,
        Field(description="Active power coefficient, P0 (MW)."),
    ]
    reactive_power: Annotated[
        float,
        Field(description="Reactive power coefficient, Q0 (MVAR)."),
    ]
    α: Annotated[
        float,
        Field(
            ge=0,
            description=(
                "Exponent relating voltage dependency for active power. "
                "0 = constant power only, 1 = constant current only, 2 = constant impedance only."
            ),
        ),
    ]
    β: Annotated[
        float,
        Field(
            ge=0,
            description=(
                "Exponent relating voltage dependency for reactive power. "
                "0 = constant power only, 1 = constant current only, 2 = constant impedance only."
            ),
        ),
    ]
    base_power: Annotated[
        ApparentPower,
        Field(gt=0, description="Base power (MVA) for per unitization."),
    ]
    max_active_power: Annotated[
        ActivePower,
        Field(description="Maximum active power (MW) that this load can demand."),
    ]
    max_reactive_power: Annotated[
        float,
        Field(description="Maximum reactive power (MVAR) that this load can demand."),
    ]
    conformity: LoadConformity = LoadConformity.UNDEFINED


class FixedAdmittance(ElectricLoad):
    """A fixed admittance."""

    Y: Annotated[Complex, Field(description="Fixed admittance in p.u. (SYSTEM_BASE)")]

    @classmethod
    def example(cls) -> "FixedAdmittance":
        """Create an example FixedAdmittance instance."""
        return FixedAdmittance(
            name="FixedAdmittance_1",
            available=True,
            bus=ACBus.example(),
            Y=Complex(real=0.0, imag=-0.1),
        )


class SwitchedAdmittance(ElectricLoad):
    """A switched admittance, with discrete steps to adjust the admittance.
    Total admittance is calculated as: `Y` + `number_of_steps` * `Y_increase`
    """

    Y: Annotated[Complex, Field(description="Initial admittance at N = 0")]
    initial_status: Annotated[
        list[int],
        Field(
            default_factory=list,
            description=(
                "Vector of initial switched shunt status, one for in-service and zero "
                "for out-of-service for block i (1 through 8)"
            ),
        ),
    ]
    number_of_steps: Annotated[
        list[int],
        Field(
            default_factory=list,
            description=(
                "Vector with number of steps for each adjustable shunt block. "
                "For example, number_of_steps[2] are the number of available steps "
                "for admittance increment at block 2."
            ),
        ),
    ]
    Y_increase: Annotated[
        list[Complex],
        Field(
            default_factory=list,
            description=(
                "Vector with admittance increment step for each adjustable shunt block. "
                "For example, Y_increase[2] is the complex admittance increment for each "
                "step at block 2."
            ),
        ),
    ]
    admittance_limits: Annotated[
        MinMax, Field(description="Shunt admittance limits for switched shunt model")
    ] = MinMax(min=1.0, max=1.0)
    control_mode: Annotated[
        str,
        Field(description="Switched shunt control mode (e.g., FIXED)."),
    ] = "FIXED"
    regulated_bus_number: Annotated[
        int,
        Field(description="Bus number regulated by this switched shunt; 0 means local bus."),
    ] = 0

    @classmethod
    def example(cls) -> "SwitchedAdmittance":
        """Create an example SwitchedAdmittance instance."""
        return SwitchedAdmittance(
            name="SwitchedAdmittance_1",
            available=True,
            bus=ACBus.example(),
            Y=Complex(real=0.0, imag=-0.05),
            initial_status=[1, 0, 1],
            number_of_steps=[5, 3, 4],
            Y_increase=[
                Complex(real=0.0, imag=-0.01),
                Complex(real=0.0, imag=-0.015),
                Complex(real=0.0, imag=-0.008),
            ],
            admittance_limits=MinMax(min=0.0, max=0.2),
        )


class ActiveConstantPowerLoad(DynamicInjection):
    """Parameters of a 12-state active power load for dynamics modeling.

    Based on: 'Dynamic Stability of a Microgrid With an Active Load.'
    https://doi.org/10.1109/TPEL.2013.2241455
    """

    r_load: Annotated[float, Field(gt=0, description="DC-side resistor.")]
    c_dc: Annotated[float, Field(gt=0, description="DC-side capacitor.")]
    rf: Annotated[float, Field(gt=0, description="Converter side filter resistance.")]
    lf: Annotated[float, Field(gt=0, description="Converter side filter inductance.")]
    cf: Annotated[float, Field(gt=0, description="AC Converter filter capacitance.")]
    rg: Annotated[float, Field(gt=0, description="Network side filter resistance.")]
    lg: Annotated[float, Field(gt=0, description="Network side filter inductance.")]
    kp_pll: Annotated[float, Field(gt=0, description="Proportional constant for PI-PLL block.")]
    ki_pll: Annotated[float, Field(gt=0, description="Integral constant for PI-PLL block.")]
    kpv: Annotated[float, Field(gt=0, description="Proportional constant for Voltage Control block.")]
    kiv: Annotated[float, Field(gt=0, description="Integral constant for Voltage Control block.")]
    kpc: Annotated[float, Field(gt=0, description="Proportional constant for Current Control block.")]
    kic: Annotated[float, Field(gt=0, description="Integral constant for Current Control block.")]
    P_ref: Annotated[float, Field(description="Reference active power (pu).")] = 1.0
    Q_ref: Annotated[float, Field(description="Reference reactive power (pu).")] = 1.0
    V_ref: Annotated[float, Field(description="Reference voltage (pu).")] = 1.0
    ω_ref: Annotated[float, Field(description="Reference frequency (pu).")] = 1.0
    is_filter_differential: Annotated[
        int, Field(description="Boolean to decide if filter states are differential or algebraic.")
    ] = 1
    states: Annotated[
        list[str],
        Field(description="State names for the active constant power load model."),
    ] = [
        "θ_pll",
        "ϵ_pll",
        "η",
        "v_dc",
        "γd",
        "γq",
        "ir_cnv",
        "ii_cnv",
        "vr_filter",
        "vi_filter",
        "ir_filter",
        "ii_filter",
    ]
    n_states: Annotated[int, Field(description="Number of model states.")] = 12
