"""Model related to branches."""

from typing import Annotated, Any

from infrasys.value_curves import InputOutputCurve, LinearCurve
from pint import Quantity
from pydantic import Field, NonNegativeFloat, NonPositiveFloat, field_serializer

from r2x_sienna.models.enums import (
    DiscreteControlledBranchStatus,
    DiscreteControlledBranchType,
    TransformerControlObjective,
    WindingGroupNumber,
)
from r2x_sienna.models.core import Device
from r2x_sienna.models.named_tuples import FromTo_ToFrom, MinMax, Complex
from r2x_sienna.models.topology import ACBus, Arc, Area, DCBus
from r2x_sienna.units import ActivePower, Percentage


class Branch(Device):
    """Class representing a connection between components."""

    @classmethod
    def example(cls) -> "Branch":
        return Branch(name="ExampleBranch")


class ACBranch(Branch):
    """Class representing an AC connection between components."""

    arc: Annotated[Arc | None, Field(description="The branch's connections.")] = None
    from_bus: Annotated[ACBus, Field(description="Bus connected upstream from the arc.")]
    to_bus: Annotated[ACBus, Field(description="Bus connected downstream from the arc.")]
    r: Annotated[float | None, Field(description=("Resistance of the branch"))] = None
    x: Annotated[float | None, Field(description=("Reactance of the branch"))] = None
    rating: Annotated[ActivePower, Field(ge=0, description="Thermal rating of the line.")] | None = None


class MonitoredLine(ACBranch):
    """Class representing an AC transmission line."""

    b: Annotated[FromTo_ToFrom | None, Field(description="Shunt susceptance in pu")] = None
    g: Annotated[FromTo_ToFrom | None, Field(description="Shunt conductance in pu")] = None
    active_power_flow: Annotated[
        NonNegativeFloat, Field(description="Initial condition of active power flow on the line (MW)")
    ] = 0.0
    reactive_power_flow: Annotated[
        NonNegativeFloat, Field(description="Initial condition of reactive power flow on the line (MVAR)")
    ] = 0.0
    flow_limits: Annotated[
        FromTo_ToFrom | None,
        Field(
            description="Minimum and maximum permissable flow on the line (MVA), "
            "if different from the thermal rating defined in `rating`"
        ),
    ] = None
    angle_limits: MinMax | None = None
    losses: Annotated[Percentage, Field(description="Power losses on the line.")] | None = None

    @field_serializer("flow_limits")
    def serialize_flow_limits(self, fromto_tofrom: FromTo_ToFrom | dict | None) -> dict[str, Any] | None:
        if fromto_tofrom is None:
            return None
        if not isinstance(fromto_tofrom, FromTo_ToFrom):
            fromto_tofrom = FromTo_ToFrom(**fromto_tofrom)
        if fromto_tofrom is not None:
            return {
                "from_to": fromto_tofrom.from_to.magnitude
                if isinstance(fromto_tofrom.from_to, Quantity)
                else fromto_tofrom.from_to,
                "to_from": fromto_tofrom.to_from.magnitude
                if isinstance(fromto_tofrom.to_from, Quantity)
                else fromto_tofrom.to_from,
            }

    @classmethod
    def example(cls) -> "MonitoredLine":
        return MonitoredLine(
            name="ExampleMonitoredLine",
            from_bus=ACBus.example(),
            to_bus=ACBus.example(),
            active_power_flow=100.0,
            reactive_power_flow=0.0,
            losses=Percentage(10, "%"),
        )


class Line(ACBranch):
    """Class representing an AC transmission line."""

    b: Annotated[FromTo_ToFrom | None, Field(description="Shunt susceptance in pu")] = None
    g: Annotated[FromTo_ToFrom | None, Field(description="Shunt conductance in pu")] = None
    active_power_flow: NonNegativeFloat
    reactive_power_flow: NonNegativeFloat
    angle_limits: MinMax

    @classmethod
    def example(cls) -> "Line":
        return Line(
            name="ExampleLine",
            from_bus=ACBus.example(),
            to_bus=ACBus.example(),
            rating=ActivePower(100, "MW"),
            active_power_flow=100,
            reactive_power_flow=100,
            angle_limits=MinMax(min=-0.03, max=0.03),
        )


class DiscreteControlledACBranch(ACBranch):
    """Used to represent switches and breakers connecting AC Buses."""

    active_power_flow: Annotated[
        float, Field(description="Initial condition of active power flow on the line (MW)")
    ]
    reactive_power_flow: Annotated[
        float, Field(description="Initial condition of reactive power flow on the line (MVAR)")
    ]
    discrete_branch_type: Annotated[
        DiscreteControlledBranchType,
        Field(default=DiscreteControlledBranchType.OTHER, description="Type of discrete control"),
    ] = DiscreteControlledBranchType.OTHER

    branch_status: Annotated[
        DiscreteControlledBranchStatus,
        Field(default=DiscreteControlledBranchStatus.CLOSED, description="Open or Close status"),
    ] = DiscreteControlledBranchStatus.CLOSED

    @classmethod
    def example(cls) -> "DiscreteControlledACBranch":
        """Create an example DiscreteControlledACBranch instance."""
        from_bus = ACBus.example()
        from_bus.name = "Bus1"
        to_bus = ACBus.example()
        to_bus.name = "Bus2"

        return DiscreteControlledACBranch(
            name="ExampleDiscreteControlledACBranch",
            available=True,
            active_power_flow=0.0,
            reactive_power_flow=0.0,
            r=0.01,
            x=0.05,
            rating=ActivePower(100, "MVA"),
            discrete_branch_type=DiscreteControlledBranchType.BREAKER,
            branch_status=DiscreteControlledBranchStatus.CLOSED,
            from_bus=from_bus,
            to_bus=to_bus,
        )


class TwoWindingTransformer(ACBranch):
    """Base class for 2-winding transformers."""

    active_power_flow: NonNegativeFloat = 0.0
    reactive_power_flow: NonNegativeFloat = 0.0
    primary_shunt: Annotated[
        Complex | None, Field(description="Primary shunt admittance (complex number)")
    ] = None
    base_power: (
        Annotated[float | None, Field(ge=0, description="Thermal rating of the transformer.")] | None
    ) = None
    base_voltage_primary: float | None = None
    base_voltage_secondary: float | None = None
    rating_b: ActivePower | None = None
    rating_c: ActivePower | None = None
    winding_group_number: WindingGroupNumber = WindingGroupNumber.UNDEFINED
    control_objective: TransformerControlObjective = TransformerControlObjective.UNDEFINED


class ThreeWindingTransformer(Branch):
    """Base class for 3-winding transformers.

    The model uses an equivalent star model with a star (hidden) bus.
    """

    star_bus: Annotated[ACBus, Field(description="Star (hidden) Bus that this component is connected to")]
    primary_star_arc: Annotated[
        Arc, Field(description="Arc defining transformer from primary bus to star bus")
    ]
    secondary_star_arc: Annotated[
        Arc, Field(description="Arc defining transformer from secondary bus to star bus")
    ]
    tertiary_star_arc: Annotated[
        Arc, Field(description="Arc defining transformer from tertiary bus to star bus")
    ]
    active_power_flow_primary: Annotated[
        float,
        Field(
            description="Initial condition of active power flow through transformer primary side to star bus (MW)"
        ),
    ]
    reactive_power_flow_primary: Annotated[
        float,
        Field(
            description="Initial condition of reactive power flow through transformer primary side to star bus (MVAR)"
        ),
    ]
    active_power_flow_secondary: Annotated[
        float,
        Field(
            description="Initial condition of active power flow through transformer secondary side to star bus (MW)"
        ),
    ]
    reactive_power_flow_secondary: Annotated[
        float,
        Field(
            description="Initial condition of reactive power flow through transformer secondary side to star bus (MVAR)"
        ),
    ]
    active_power_flow_tertiary: Annotated[
        float,
        Field(
            description="Initial condition of active power flow through transformer tertiary side to star bus (MW)"
        ),
    ]
    reactive_power_flow_tertiary: Annotated[
        float,
        Field(
            description="Initial condition of reactive power flow through transformer tertiary side to star bus (MVAR)"
        ),
    ]
    r_primary: Annotated[
        float,
        Field(
            ge=-2,
            le=4,
            description="Equivalent resistance in pu from primary to star bus, validation range: (-2, 4)",
        ),
    ]
    x_primary: Annotated[
        float,
        Field(
            ge=-2,
            le=4,
            description="Equivalent reactance in pu from primary to star bus, validation range: (-2, 4)",
        ),
    ]
    r_secondary: Annotated[
        float,
        Field(
            ge=-2,
            le=4,
            description="Equivalent resistance in pu from secondary to star bus, validation range: (-2, 4)",
        ),
    ]
    x_secondary: Annotated[
        float,
        Field(
            ge=-2,
            le=4,
            description="Equivalent reactance in pu from secondary to star bus, validation range: (-2, 4)",
        ),
    ]
    r_tertiary: Annotated[
        float,
        Field(
            ge=-2,
            le=4,
            description="Equivalent resistance in pu from tertiary to star bus, validation range: (-2, 4)",
        ),
    ]
    x_tertiary: Annotated[
        float,
        Field(
            ge=-2,
            le=4,
            description="Equivalent reactance in pu from tertiary to star bus, validation range: (-2, 4)",
        ),
    ]
    r_12: Annotated[
        float, Field(ge=0, le=4, description="Measured resistance from primary to secondary windings")
    ]
    x_12: Annotated[
        float, Field(ge=0, le=4, description="Measured reactance from primary to secondary windings")
    ]
    r_23: Annotated[
        float, Field(ge=0, le=4, description="Measured resistance from secondary to tertiary windings")
    ]
    x_23: Annotated[
        float, Field(ge=0, le=4, description="Measured reactance from secondary to tertiary windings")
    ]
    r_13: Annotated[
        float, Field(ge=0, le=4, description="Measured resistance from primary to tertiary windings")
    ]
    x_13: Annotated[
        float, Field(ge=0, le=4, description="Measured reactance from primary to tertiary windings")
    ]
    base_power_12: Annotated[
        float, Field(gt=0, description="Base power (MVA) for primary-secondary windings")
    ]
    base_power_23: Annotated[
        float, Field(gt=0, description="Base power (MVA) for secondary-tertiary windings")
    ]
    base_power_13: Annotated[float, Field(gt=0, description="Base power (MVA) for primary-tertiary windings")]
    base_voltage_primary: Annotated[float | None, Field(gt=0, description="Primary base voltage in kV")] = (
        None
    )
    base_voltage_secondary: Annotated[
        float | None, Field(gt=0, description="Secondary base voltage in kV")
    ] = None
    base_voltage_tertiary: Annotated[float | None, Field(gt=0, description="Tertiary base voltage in kV")] = (
        None
    )
    g: Annotated[
        float, Field(description="Shunt conductance in pu from star bus to ground (MAG1 in PSS/E)")
    ] = 0.0
    b: Annotated[
        float, Field(description="Shunt susceptance in pu from star bus to ground (MAG2 in PSS/E)")
    ] = 0.0
    primary_turns_ratio: Annotated[
        float, Field(description="Primary side off-nominal turns ratio in p.u. (WINDV1 in PSS/E)")
    ] = 1.0
    secondary_turns_ratio: Annotated[
        float, Field(description="Secondary side off-nominal turns ratio in p.u. (WINDV2 in PSS/E)")
    ] = 1.0
    tertiary_turns_ratio: Annotated[
        float, Field(description="Tertiary side off-nominal turns ratio in p.u. (WINDV3 in PSS/E)")
    ] = 1.0
    available_primary: Annotated[bool, Field(description="Status if primary winding is available")] = True
    available_secondary: Annotated[bool, Field(description="Status if secondary winding is available")] = True
    available_tertiary: Annotated[bool, Field(description="Status if tertiary winding is available")] = True
    rating: (
        Annotated[ActivePower, Field(ge=0, description="Thermal rating of the generic Transformer 3W.")]
        | None
    ) = None
    rating_primary: (
        Annotated[ActivePower | None, Field(ge=0, description="Rating (in MVA) for primary winding")] | None
    ) = None
    rating_secondary: (
        Annotated[ActivePower | None, Field(ge=0, description="Rating (in MVA) for secondary winding")] | None
    ) = None
    rating_tertiary: (
        Annotated[ActivePower | None, Field(ge=0, description="Rating (in MVA) for tertiary winding")] | None
    ) = None


class Transformer3W(ThreeWindingTransformer):
    """A 3-winding transformer."""

    @classmethod
    def example(cls) -> "Transformer3W":
        """Create an example Transformer3W instance."""
        return Transformer3W(
            name="Example3WTransformer",
            available=True,
            star_bus=ACBus.example(),
            primary_star_arc=Arc(
                name="PrimaryToStar",
                from_to=ACBus.example(),
                to_from=ACBus.example(),
            ),
            secondary_star_arc=Arc(
                name="SecondaryToStar",
                from_to=ACBus.example(),
                to_from=ACBus.example(),
            ),
            tertiary_star_arc=Arc(
                name="TertiaryToStar",
                from_to=ACBus.example(),
                to_from=ACBus.example(),
            ),
            active_power_flow_primary=100.0,
            reactive_power_flow_primary=20.0,
            active_power_flow_secondary=-50.0,
            reactive_power_flow_secondary=-10.0,
            active_power_flow_tertiary=-50.0,
            reactive_power_flow_tertiary=-10.0,
            r_primary=0.01,
            x_primary=0.08,
            r_secondary=0.015,
            x_secondary=0.09,
            r_tertiary=0.012,
            x_tertiary=0.085,
            r_12=0.02,
            x_12=0.15,
            r_23=0.025,
            x_23=0.16,
            r_13=0.022,
            x_13=0.155,
            base_power_12=100.0,
            base_power_23=100.0,
            base_power_13=100.0,
            base_voltage_primary=138.0,
            base_voltage_secondary=69.0,
            base_voltage_tertiary=13.8,
        )


class PhaseShiftingTransformer3W(ThreeWindingTransformer):
    """A 3-winding phase-shifting transformer."""

    α_primary: Annotated[
        float, Field(ge=-1.571, le=1.571, description="Initial condition of primary phase shift (radians)")
    ]
    α_secondary: Annotated[
        float, Field(ge=-1.571, le=1.571, description="Initial condition of secondary phase shift (radians)")
    ]
    α_tertiary: Annotated[
        float, Field(ge=-1.571, le=1.571, description="Initial condition of tertiary phase shift (radians)")
    ]
    phase_angle_limits: Annotated[
        MinMax, Field(description="Minimum and maximum phase angle limits (radians)")
    ] = MinMax(min=-3.1416, max=3.1416)

    @classmethod
    def example(cls) -> "PhaseShiftingTransformer3W":
        """Create an example PhaseShiftingTransformer3W instance."""
        return PhaseShiftingTransformer3W(
            name="ExamplePhaseShifting3WTransformer",
            available=True,
            star_bus=ACBus.example(),
            primary_star_arc=Arc(
                name="PrimaryToStar",
                from_to=ACBus.example(),
                to_from=ACBus.example(),
            ),
            secondary_star_arc=Arc(
                name="SecondaryToStar",
                from_to=ACBus.example(),
                to_from=ACBus.example(),
            ),
            tertiary_star_arc=Arc(
                name="TertiaryToStar",
                from_to=ACBus.example(),
                to_from=ACBus.example(),
            ),
            active_power_flow_primary=100.0,
            reactive_power_flow_primary=20.0,
            active_power_flow_secondary=-50.0,
            reactive_power_flow_secondary=-10.0,
            active_power_flow_tertiary=-50.0,
            reactive_power_flow_tertiary=-10.0,
            r_primary=0.01,
            x_primary=0.08,
            r_secondary=0.015,
            x_secondary=0.09,
            r_tertiary=0.012,
            x_tertiary=0.085,
            r_12=0.02,
            x_12=0.15,
            r_23=0.025,
            x_23=0.16,
            r_13=0.022,
            x_13=0.155,
            base_power_12=100.0,
            base_power_23=100.0,
            base_power_13=100.0,
            base_voltage_primary=138.0,
            base_voltage_secondary=69.0,
            base_voltage_tertiary=13.8,
            α_primary=0.0,
            α_secondary=0.1745,
            α_tertiary=-0.0873,
            phase_angle_limits=MinMax(min=-0.5236, max=0.5236),
        )


class Transformer2W(TwoWindingTransformer):
    """Class representing a 2-winding transformer."""

    @classmethod
    def example(cls) -> "Transformer2W":
        return Transformer2W(
            name="Example2WTransformer",
            rating=ActivePower(100, "MW"),
            from_bus=ACBus.example(),
            to_bus=ACBus.example(),
            active_power_flow=100,
            reactive_power_flow=100,
            primary_shunt=Complex(real=0.0, imag=0.0),
        )


class TapTransformer(TwoWindingTransformer):
    """Class representing a tap-changing transformer."""

    tap: Annotated[
        NonNegativeFloat,
        Field(
            ge=0,
            le=2.0,
            description=(
                "Normalized tap changer position for voltage control, varying between 0 and 2, with 1 "
                "centered at the nominal voltage"
            ),
        ),
    ]

    @classmethod
    def example(cls) -> "TapTransformer":
        return TapTransformer(
            name="ExampleTapTransformer",
            from_bus=ACBus.example(),
            to_bus=ACBus.example(),
            rating=ActivePower(100, "MW"),
            active_power_flow=50.0,
            reactive_power_flow=10.0,
            primary_shunt=Complex(real=0.0, imag=0.0),
            tap=1.0,
        )


class PhaseShiftingTransformer(TwoWindingTransformer):
    """Class representing a phase-shifting transformer."""

    tap: Annotated[
        NonNegativeFloat,
        Field(
            ge=0,
            le=2.0,
            description=(
                "Normalized tap changer position for voltage control, varying between 0 and 2, with 1 "
                "centered at the nominal voltage"
            ),
        ),
    ]
    α: Annotated[float, Field(ge=-1.571, le=1.571, description="Phase angle in radians")]
    phase_angle_limits: MinMax

    @classmethod
    def example(cls) -> "PhaseShiftingTransformer":
        return PhaseShiftingTransformer(
            name="ExamplePhaseShiftingTransformer",
            from_bus=ACBus.example(),
            to_bus=ACBus.example(),
            rating=ActivePower(100, "MW"),
            active_power_flow=50.0,
            reactive_power_flow=10.0,
            primary_shunt=Complex(real=0.0, imag=0.0),
            tap=1.0,
            α=0.0,
            phase_angle_limits=MinMax(min=-0.5, max=0.5),
        )


class DCBranch(Branch):
    """Class representing a DC connection between components."""

    from_bus: Annotated[DCBus, Field(description="Bus connected upstream from the arc.")]
    to_bus: Annotated[DCBus, Field(description="Bus connected downstream from the arc.")]


class AreaInterchange(Branch):
    """Collection of branches that make up an interfece or corridor for the transfer of power."""

    active_power_flow: NonNegativeFloat
    flow_limits: FromTo_ToFrom
    from_area: Annotated[Area, Field(description="Area containing the bus.")] | None = None
    to_area: Annotated[Area, Field(description="Area containing the bus.")] | None = None

    @classmethod
    def example(cls) -> "AreaInterchange":
        return AreaInterchange(
            name="ExampleAreaInterchange",
            active_power_flow=10.0,
            flow_limits=FromTo_ToFrom(from_to=100, to_from=-100),
            from_area=Area.example(),
            to_area=Area.example(),
        )


class TModelHVDCLine(DCBranch):
    """Class representing a DC transmission line."""

    rating_up: Annotated[NonNegativeFloat, Field(description="Forward rating of the line.")] | None = None
    rating_down: Annotated[NonPositiveFloat, Field(description="Reverse rating of the line.")] | None = None
    losses: Annotated[NonNegativeFloat, Field(description="Power losses on the line.")] = 0
    resistance: Annotated[NonNegativeFloat, Field(description="Resistance of the line in p.u.")] | None = 0
    inductance: Annotated[NonNegativeFloat, Field(description="Inductance of the line in p.u.")] | None = 0
    capacitance: Annotated[NonNegativeFloat, Field(description="Capacitance of the line in p.u.")] | None = 0

    @classmethod
    def example(cls) -> "TModelHVDCLine":
        return TModelHVDCLine(
            name="ExampleDCLine",
            from_bus=DCBus.example(),
            to_bus=DCBus.example(),
            rating_up=100,
            rating_down=80,
        )


class TwoTerminalHVDCLine(ACBranch):
    """Class representing a DC transmission line."""

    active_power_flow: NonNegativeFloat
    active_power_limits_from: MinMax
    active_power_limits_to: MinMax
    reactive_power_limits_from: MinMax
    reactive_power_limits_to: MinMax
    loss: InputOutputCurve


class TwoTerminalGenericHVDCLine(TwoTerminalHVDCLine):
    """A High Voltage DC line"""

    active_power_flow: NonNegativeFloat
    active_power_limits_from: MinMax
    active_power_limits_to: MinMax
    reactive_power_limits_from: MinMax
    reactive_power_limits_to: MinMax
    loss: InputOutputCurve


class TwoTerminalLCCLine(TwoTerminalHVDCLine):
    """A Non-Capacitor Line Commutated Converter (LCC) - HVDC transmission line."""

    active_power_flow: Annotated[
        float, Field(description="Initial condition of active power flow on the line (MW)")
    ]
    r: Annotated[float, Field(description="Series resistance of the DC line in pu (SYSTEM_BASE)")]
    transfer_setpoint: Annotated[
        float,
        Field(
            description=(
                "Desired set-point of power. If power_mode = true this value is in MW units, "
                "and if power_mode = false is in Amperes units. This parameter must not be "
                "specified in per-unit. A positive value represents the desired consumed power "
                "at the rectifier bus, while a negative value represents the desired power at "
                "the inverter bus (i.e. the absolute value of transfer_setpoint is the generated "
                "power at the inverter bus)."
            )
        ),
    ]
    scheduled_dc_voltage: Annotated[
        float,
        Field(
            description=(
                "Scheduled compounded DC voltage in kV. By default this parameter is the "
                "scheduled DC voltage in the inverter bus This parameter must not be "
                "specified in per-unit."
            )
        ),
    ]
    rectifier_bridges: Annotated[int, Field(description="Number of bridges in series in the rectifier side")]
    rectifier_delay_angle_limits: Annotated[
        MinMax, Field(description="Minimum and maximum rectifier firing delay angle (α) (radians)")
    ]
    rectifier_rc: Annotated[
        float,
        Field(
            description="Rectifier commutating transformer resistance per bridge in system p.u. (SYSTEM_BASE)"
        ),
    ]
    rectifier_xc: Annotated[
        float,
        Field(
            description="Rectifier commutating transformer reactance per bridge in system p.u. (SYSTEM_BASE)"
        ),
    ]
    rectifier_base_voltage: Annotated[
        float, Field(description="Rectifier primary base AC voltage in kV, entered in kV")
    ]
    inverter_bridges: Annotated[int, Field(description="Number of bridges in series in the inverter side")]
    inverter_extinction_angle_limits: Annotated[
        MinMax, Field(description="Minimum and maximum inverter extinction angle (γ) (radians)")
    ]
    inverter_rc: Annotated[
        float,
        Field(
            description="Inverter commutating transformer resistance per bridge in system p.u. (SYSTEM_BASE)"
        ),
    ]
    inverter_xc: Annotated[
        float,
        Field(
            description="Inverter commutating transformer reactance per bridge in system p.u. (SYSTEM_BASE)"
        ),
    ]
    inverter_base_voltage: Annotated[
        float, Field(description="Inverter primary base AC voltage in kV, entered in kV")
    ]
    power_mode: Annotated[
        bool,
        Field(
            description=(
                "Boolean flag to identify if the LCC line is in power mode or current mode. "
                "If power_mode = true, setpoint values must be specified in MW, and if "
                "power_mode = false setpoint values must be specified in Amperes."
            )
        ),
    ] = True
    switch_mode_voltage: Annotated[
        float,
        Field(
            description=(
                "Mode switch DC voltage, in kV. This parameter must not be added in per-unit. "
                "If LCC line is in power mode control, and DC voltage falls below this value, "
                "the line switch to current mode control."
            )
        ),
    ] = 0.0
    compounding_resistance: Annotated[
        float,
        Field(
            description=(
                "Compounding Resistance, in ohms. This parameter is for control of the DC "
                "voltage in the rectifier or inverter end. For inverter DC voltage control, "
                "the paremeter is set to zero; for rectifier DC voltage control, the "
                "paremeter is set to the DC line resistance; otherwise, set to a fraction "
                "of the DC line resistance."
            )
        ),
    ] = 0.0
    min_compounding_voltage: Annotated[
        float,
        Field(
            description=(
                "Minimum compounded voltage, in kV. This parameter must not be added in "
                "per-unit. Only used in constant gamma operation (γ_min = γ_max), and the "
                "AC transformer is used to control the DC voltage."
            )
        ),
    ] = 0.0
    rectifier_transformer_ratio: Annotated[
        float,
        Field(description="Rectifier transformer ratio between the primary and secondary side AC voltages"),
    ] = 1.0
    rectifier_tap_setting: Annotated[float, Field(description="Rectifier transformer tap setting")] = 1.0
    rectifier_tap_limits: Annotated[
        MinMax,
        Field(
            description="Minimum and maximum rectifier tap limits as a ratio between the primary and secondary side AC voltages"
        ),
    ] = MinMax(min=0.51, max=1.5)
    rectifier_tap_step: Annotated[float, Field(description="Rectifier transformer tap step value")] = 0.00625
    rectifier_delay_angle: Annotated[float, Field(description="Rectifier firing delay angle (α)")] = 0.0
    rectifier_capacitor_reactance: Annotated[
        float,
        Field(
            description="Commutating rectifier capacitor reactance magnitude per bridge, in system p.u. (SYSTEM_BASE)"
        ),
    ] = 0.0
    inverter_transformer_ratio: Annotated[
        float,
        Field(description="Inverter transformer ratio between the primary and secondary side AC voltages"),
    ] = 1.0
    inverter_tap_setting: Annotated[float, Field(description="Inverter transformer tap setting")] = 1.0
    inverter_tap_limits: Annotated[
        MinMax,
        Field(
            description="Minimum and maximum inverter tap limits as a ratio between the primary and secondary side AC voltages"
        ),
    ] = MinMax(min=0.51, max=1.5)
    inverter_tap_step: Annotated[float, Field(description="Inverter transformer tap step value")] = 0.00625
    inverter_extinction_angle: Annotated[float, Field(description="Inverter extinction angle (γ)")] = 0.0
    inverter_capacitor_reactance: Annotated[
        float,
        Field(
            description="Commutating inverter capacitor reactance magnitude per bridge, in system p.u. (SYSTEM_BASE)"
        ),
    ] = 0.0

    @classmethod
    def example(cls) -> "TwoTerminalLCCLine":
        """Create an example TwoTerminalLCCLine instance."""
        return TwoTerminalLCCLine(
            name="ExampleLCCLine",
            available=True,
            from_bus=ACBus.example(),
            to_bus=ACBus.example(),
            active_power_flow=500.0,
            r=0.01,
            transfer_setpoint=500.0,
            scheduled_dc_voltage=400.0,
            rectifier_bridges=12,
            rectifier_delay_angle_limits=MinMax(min=0.1, max=0.35),
            rectifier_rc=0.001,
            rectifier_xc=0.15,
            rectifier_base_voltage=345.0,
            inverter_bridges=12,
            inverter_extinction_angle_limits=MinMax(min=0.3, max=0.5),
            inverter_rc=0.001,
            inverter_xc=0.15,
            inverter_base_voltage=230.0,
            active_power_limits_from=MinMax(min=0.0, max=600.0),
            active_power_limits_to=MinMax(min=-600.0, max=0.0),
            reactive_power_limits_from=MinMax(min=-200.0, max=200.0),
            reactive_power_limits_to=MinMax(min=-150.0, max=150.0),
            loss=LinearCurve(0.0),
        )


class TwoTerminalVSCLine(TwoTerminalHVDCLine):
    """A Voltage-Source Converter (VSC) - HVDC transmission line.

    This model is appropriate for operational simulations with a linearized DC
    power flow approximation with losses using a voltage-current model. For
    modeling a DC network, see TModelHVDCLine.
    """

    active_power_flow: Annotated[
        float,
        Field(description="Initial condition of active power flowing from the from-bus to the to-bus in DC"),
    ]
    g: Annotated[float, Field(description="Series conductance of the DC line in pu (SYSTEM_BASE)")] = 0.0
    dc_current: Annotated[
        float,
        Field(description="DC current (A) on the converter flowing in the DC line, from from bus to to bus"),
    ] = 0.0
    reactive_power_from: Annotated[
        float, Field(description="Initial condition of reactive power flowing into the from-bus")
    ] = 0.0
    dc_voltage_control_from: Annotated[
        bool,
        Field(
            description=(
                "Converter control type in the from bus converter. Set true for DC Voltage Control "
                "(set DC voltage on the DC side of the converter), and false for power demand in the converter"
            )
        ),
    ] = True
    ac_voltage_control_from: Annotated[
        bool,
        Field(
            description=(
                "Converter control type in the from bus converter. Set true for AC Voltage Control "
                "(set AC voltage on the AC side of the converter), and false for fixed power AC factor"
            )
        ),
    ] = True
    dc_setpoint_from: Annotated[
        float,
        Field(
            description=(
                "Converter DC setpoint in the from bus converter. If voltage_control_from = true "
                "this number is the DC voltage on the DC side of the converter, entered in kV. "
                "If voltage_control_from = false, this value is the power demand in MW"
            )
        ),
    ] = 0.0
    ac_setpoint_from: Annotated[
        float,
        Field(
            description=(
                "Converter AC setpoint in the from bus converter. If voltage_control_from = true "
                "this number is the AC voltage on the AC side of the converter, entered in per unit. "
                "If voltage_control_from = false, this value is the power factor setpoint"
            )
        ),
    ] = 1.0
    converter_loss_from: Annotated[
        InputOutputCurve,
        Field(
            description="Loss model coefficients in the from bus converter. It accepts a linear model or quadratic"
        ),
    ] = LinearCurve(0.0)
    max_dc_current_from: (
        Annotated[float, Field(description="Maximum stable dc current limits (A)")] | None
    ) = None
    rating_from: (
        Annotated[ActivePower, Field(description="Converter rating in MVA in the from bus")] | None
    ) = None
    power_factor_weighting_fraction_from: Annotated[
        float,
        Field(
            ge=0,
            le=1,
            description=(
                "Power weighting factor fraction used in reducing the active power order and "
                "either the reactive power order when the converter rating is violated. "
                "When is 0.0, only the active power is reduced; when is 1.0, only the "
                "reactive power is reduced; otherwise, a weighted reduction of both active "
                "and reactive power is applied."
            ),
        ),
    ] = 1.0
    voltage_limits_from: (
        Annotated[MinMax, Field(description="Limits on the Voltage at the DC from Bus in per unit")] | None
    ) = None
    reactive_power_to: Annotated[
        float, Field(description="Initial condition of reactive power flowing into the to-bus")
    ] = 0.0
    dc_voltage_control_to: Annotated[
        bool,
        Field(
            description=(
                "Converter control type in the to bus converter. Set true for DC Voltage Control "
                "(set DC voltage on the DC side of the converter), and false for power demand in the converter"
            )
        ),
    ] = True
    ac_voltage_control_to: Annotated[
        bool,
        Field(
            description=(
                "Converter control type in the to bus converter. Set true for AC Voltage Control "
                "(set AC voltage on the AC side of the converter), and false for fixed power AC factor"
            )
        ),
    ] = True
    dc_setpoint_to: Annotated[
        float,
        Field(
            description=(
                "Converter DC setpoint in the to bus converter. If voltage_control_to = true "
                "this number is the DC voltage on the DC side of the converter, entered in kV. "
                "If voltage_control_to = false, this value is the power demand in MW"
            )
        ),
    ] = 0.0
    ac_setpoint_to: Annotated[
        float,
        Field(
            description=(
                "Converter AC setpoint in the to bus converter. If voltage_control_to = true "
                "this number is the AC voltage on the AC side of the converter, entered in per unit. "
                "If voltage_control_to = false, this value is the power factor setpoint"
            )
        ),
    ] = 1.0
    converter_loss_to: Annotated[
        InputOutputCurve,
        Field(
            description="Loss model coefficients in the to bus converter. It accepts a linear model or quadratic"
        ),
    ] = LinearCurve(0.0)
    max_dc_current_to: Annotated[float, Field(description="Maximum stable dc current limits (A)")] | None = (
        None
    )
    rating_to: Annotated[ActivePower, Field(description="Converter rating in MVA in the to bus")] | None = (
        None
    )
    power_factor_weighting_fraction_to: Annotated[
        float,
        Field(
            ge=0,
            le=1,
            description=(
                "Power weighting factor fraction used in reducing the active power order and "
                "either the reactive power order when the converter rating is violated"
            ),
        ),
    ] = 1.0
    voltage_limits_to: (
        Annotated[MinMax, Field(description="Limits on the Voltage at the DC to Bus")] | None
    ) = None

    @classmethod
    def example(cls) -> "TwoTerminalVSCLine":
        """Create an example TwoTerminalVSCLine instance."""
        return TwoTerminalVSCLine(
            name="ExampleVSCLine",
            available=True,
            from_bus=ACBus.example(),
            to_bus=ACBus.example(),
            active_power_flow=400.0,
            rating=ActivePower(500.0, "MW"),
            active_power_limits_from=MinMax(min=0.0, max=500.0),
            active_power_limits_to=MinMax(min=-500.0, max=0.0),
            g=0.001,
            dc_current=800.0,
            dc_setpoint_from=400.0,
            ac_setpoint_from=1.05,
            dc_setpoint_to=-400.0,
            ac_setpoint_to=1.0,
            rating_from=ActivePower(500.0, "MW"),
            rating_to=ActivePower(500.0, "MW"),
            reactive_power_limits_from=MinMax(min=-200.0, max=200.0),
            reactive_power_limits_to=MinMax(min=-200.0, max=200.0),
            loss=LinearCurve(0.0),
        )
