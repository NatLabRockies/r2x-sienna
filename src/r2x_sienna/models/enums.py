"""Enumerations for Sienna model components."""

from enum import StrEnum, Enum


class ReserveType(StrEnum):
    """Types of operating reserves."""

    SPINNING = "SPINNING"
    FLEXIBILITY = "FLEXIBILITY"
    REGULATION = "REGULATION"


class ReserveDirection(StrEnum):
    """Direction of reserve provision."""

    UP = "UP"
    DOWN = "DOWN"


class ReservoirDataType(StrEnum):
    """Valid data types for reservoir objects."""

    USABLE_VOLUME = "USABLE_VOLUME"
    TOTAL_VOLUME = "TOTAL_VOLUME"
    HEAD = "HEAD"
    ENERGY = "ENERGY"


class PrimeMoversType(StrEnum):
    """EIA prime mover codes."""

    BA = "BA"
    BT = "BT"
    CA = "CA"
    CC = "CC"
    CE = "CE"
    CP = "CP"
    CS = "CSV"
    CT = "CT"
    ES = "ES"
    FC = "FC"
    FW = "FW"
    GT = "GT"
    HA = "HA"
    HB = "HB"
    HK = "HK"
    HY = "HY"
    IC = "IC"
    PS = "PS"
    OT = "OT"
    ST = "ST"
    PVe = "PVe"
    WT = "WT"
    WS = "WS"
    RTPV = "RTPV"


class ACBusTypes(StrEnum):
    """Enum to define quantities for load flow calculation and categorize buses.

    For PCM translations, must of the buses are `PV`.
    """

    PV = "PV"
    PQ = "PQ"
    REF = "REF"
    SLACK = "SLACK"
    ISOLATED = "ISOLATED"


class ThermalFuels(StrEnum):
    """Thermal fuels that reflect options in the EIA annual energy review."""

    COAL = "COAL"
    WASTE_COAL = "WASTE_COAL"
    DISTILLATE_FUEL_OIL = "DISTILLATE_FUEL_OIL"
    WASTE_OIL = "WASTE_OIL"
    PETROLEUM_COKE = "PETROLEUM_COKE"
    RESIDUAL_FUEL_OIL = "RESIDUAL_FUEL_OIL"
    NATURAL_GAS = "NATURAL_GAS"
    OTHER_GAS = "OTHER_GAS"
    NUCLEAR = "NUCLEAR"
    AG_BIOPRODUCT = "AG_BIOPRODUCT"
    MUNICIPAL_WASTE = "MUNICIPAL_WASTE"
    WOOD_WASTE = "WOOD_WASTE"
    WOOD_WASTE_SOLIDS = "WOOD_WASTE_SOLIDS"
    WOOD_WASTE_LIQUIDS = "WOOD_WASTE_LIQUIDS"
    GEOTHERMAL = "GEOTHERMAL"
    WASTE_HEAT = "WASTE_HEAT"
    JET_FUEL = "JET_FUEL"
    OTHER = "OTHER"


class StorageTechs(StrEnum):
    """Valid Storage technologies."""

    PTES = "PTES"
    LIB = "LIB"
    LAB = "LAB"
    FLWB = "FLWB"
    SIB = "SIB"
    ZIB = "ZIB"
    HGS = "HGS"
    LAES = "LAES"
    OTHER_CHEM = "OTHER_CHEM"
    OTHER_MECH = "OTHER_MECH"
    OTHER_THERM = "OTHER_THERM"


class WindingGroupNumber(Enum):
    """Turbine types."""

    UNDEFINED = "UNDEFINED"  # -99
    GROUP_0 = "GROUP_0"  # 0       0 Degrees
    GROUP_1 = "GROUP_1"  # 1     -30 Degrees
    GROUP_5 = "GROUP_5"  # 5    -150 Degrees
    GROUP_6 = "GROUP_6"  # 6     180 Degrees
    GROUP_7 = "GROUP_7"  # 7     150 Degrees
    GROUP_11 = "GROUP_11"  # 11     30 Degrees


class TransformerControlObjective(StrEnum):
    """Transformer Control  types."""

    UNDEFINED = "UNDEFINED"
    VOLTAGE_DISABLED = "VOLTAGE_DISABLED"
    REACTIVE_POWER_FLOW_DISABLED = "REACTIVE_POWER_FLOW_DISABLED"
    ACTIVE_POWER_FLOW_DISABLED = "ACTIVE_POWER_FLOW_DISABLED"
    CONTROL_OF_DC_LINE_DISABLED = "CONTROL_OF_DC_LINE_DISABLED"
    ASYMMETRIC_ACTIVE_POWER_FLOW_DISABLED = "ASYMMETRIC_ACTIVE_POWER_FLOW_DISABLED"
    FIXED = "FIXED"
    VOLTAGE = "VOLTAGE"
    REACTIVE_POWER_FLOW = "REACTIVE_POWER_FLOW"
    ACTIVE_POWER_FLOW = "ACTIVE_POWER_FLOW"
    CONTROL_OF_DC_LINE = "CONTROL_OF_DC_LINE"
    ASYMMETRIC_ACTIVE_POWER_FLOW = "ASYMMETRIC_ACTIVE_POWER_FLOW"


class DiscreteControlledBranchType(StrEnum):
    """Discrete branch types."""

    SWITCH = "SWITCH"
    BREAKER = "BREAKER"
    OTHER = "OTHER"


class DiscreteControlledBranchStatus(StrEnum):
    """Branch status."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


class FACTSOperationModes(StrEnum):
    """FACTS operation modes."""

    OOS = "OOS"  # out-of-service
    NML = "NML"  # Normal mode of operation,
    BYP = "BYP"  # Series link is bypassed (i.e., like a zero impedance line) and Shunt link operates as a STATCOM


class ImpedanceCorrectionTransformerControlMode(StrEnum):
    """Transformer control modes for Impedance Correction Table (ICT)."""

    TAP_RATIO = "TAP_RATIO"  # 1
    PHASE_SHIFT_ANGLE = "PHASE_SHIFT_ANGLE"  # 2


class WindingCategory(StrEnum):
    """Transformer winding categories."""

    TR2W_WINDING = "TR2W_WINDING"  # 0
    PRIMARY_WINDING = "PRIMARY_WINDING"  # 1
    SECONDARY_WINDING = "SECONDARY_WINDING"  # 2
    TERTIARY_WINDING = "TERTIARY_WINDING"  # 3


class PumpHydroStatus(StrEnum):
    """Pump hydro unit status."""

    OFF = "OFF"  # 0
    GEN = "GEN"  # 1
    PUMP = "PUMP"  # -1


class ReservoirLocation(StrEnum):
    """Reservoir location types."""

    HEAD = "HEAD"  # 1
    TAIL = "TAIL"  # 2


class HydroTurbineType(str, Enum):
    """Hydro turbine types."""

    UNKNOWN = "UNKNOWN"  # Default / unspecified
    PELTON = "PELTON"  # Impulse turbine for high head
    FRANCIS = "FRANCIS"  # Reaction turbine for medium head
    KAPLAN = "KAPLAN"  # Propeller-type turbine for low head
    TURGO = "TURGO"  # Impulse turbine similar to Pelton
    CROSSFLOW = "CROSSFLOW"  # Banki-Michell (crossflow) turbine
    BULB = "BULB"  # Kaplan variation for very low head
    DERIAZ = "DERIAZ"  # Diagonal flow turbine
    PROPELLER = "PROPELLER"  # Simple propeller turbine
    OTHER = "OTHER"  # Catch-all for less common designs
