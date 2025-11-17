"""Electric load related models."""

from typing import Annotated

from pydantic import Field, NonNegativeFloat

from r2x_sienna.models.core import StaticInjection
from r2x_sienna.models.enums import FACTSOperationModes
from r2x_sienna.models.named_tuples import Complex, MinMax
from r2x_sienna.models.topology import ACBus, Bus
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
    operation_cost: float | None = None

    @classmethod
    def example(cls) -> "PowerLoad":
        return PowerLoad(name="ExampleLoad", bus=ACBus.example(), active_power=ActivePower(1000, "MW"))


class StandardLoad(StaticLoad):
    base_power: NonNegativeFloat
    constant_active_power: float
    constant_reactive_power: float
    impedance_active_power: float
    impedance_reactive_power: float
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
    operation_cost: float | None = None


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
