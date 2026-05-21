"""Cost related functions."""

from operator import attrgetter
from typing import Annotated

from infrasys.cost_curves import CostCurve, FuelCurve, UnitSystem
from infrasys.function_data import PiecewiseStepData
from infrasys.models import InfraSysBaseModel
from infrasys.time_series_models import TimeSeriesKey
from infrasys.value_curves import LinearCurve, IncrementalCurve
from pydantic import Field, NonNegativeFloat, computed_field, model_validator

from .core import Service
from .named_tuples import StartUpStages


class OperationalCost(InfraSysBaseModel):
    @computed_field  # type: ignore[prop-decorator]
    @property
    def class_type(self) -> str:
        """Create attribute that holds the class name."""
        return type(self).__name__

    @computed_field  # type: ignore[prop-decorator]
    @property
    def variable_type(self) -> str | None:
        """Create attribute that holds the class name."""
        if not getattr(self, "variable", None):
            return None
        return type(getattr(self, "variable")).__name__

    @computed_field  # type: ignore[prop-decorator]
    @property
    def value_curve_type(self) -> str | None:
        """Create attribute that holds the class name."""
        try:
            return type(attrgetter("variable.value_curve")(self)).__name__
        except AttributeError:
            return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def function_data_type(self) -> str | None:
        """Create attribute that holds the class name."""
        try:
            return type(attrgetter("variable.value_curve.function_data")(self)).__name__
        except AttributeError:
            return None


class OfferCurveCost(OperationalCost):
    """Abstract base type for market offer-curve operational costs."""


class RenewableGenerationCost(OperationalCost):
    fixed: Annotated[float, Field(default=0.0, description="Fixed cost component")] = 0.0
    curtailment_cost: CostCurve | None = None
    variable: CostCurve = CostCurve(value_curve=LinearCurve(0), power_units=UnitSystem.NATURAL_UNITS)


class HydroGenerationCost(OperationalCost):
    fixed: Annotated[
        NonNegativeFloat | None,
        Field(
            description=(
                "Fixed cost of keeping the unit online. "
                "For some cost representations this field can be duplicative"
            )
        ),
    ] = 0.0
    variable: CostCurve | None = None

    @classmethod
    def example(cls) -> "HydroGenerationCost":
        return HydroGenerationCost(
            fixed=0.0,
            variable=CostCurve(
                value_curve=LinearCurve(10), power_units=UnitSystem.NATURAL_UNITS, vom_cost=LinearCurve(5.0)
            ),
        )


class ThermalGenerationCost(OperationalCost):
    """An operational cost for thermal generators.

    It includes fixed cost, variable cost, shut-down cost, and multiple options for start up costs.

    References
    ----------
    .. [1] National Renewable Energy Laboratory. "Thermal Generation Cost Model Library."
       Available: https://github.com/Sienna-Platform/PowerSystems.jl/blob/main/docs/src/model_library/thermal_generation_cost.md
    """

    fixed: Annotated[NonNegativeFloat, Field(description="Cost of using fuel in $ or $/hr.")] = 0.0
    shut_down: Annotated[NonNegativeFloat, Field(description="Cost to turn the unit off")] = 0.0
    start_up: Annotated[NonNegativeFloat, Field(description="Cost to start the unit.")] = 0.0
    variable: Annotated[CostCurve | FuelCurve | None, Field(description="Variable production cost")] = None

    @classmethod
    def example(cls) -> "ThermalGenerationCost":
        return ThermalGenerationCost(
            fixed=0.0,
            shut_down=100.0,
            start_up=100.0,
            variable=FuelCurve(value_curve=LinearCurve(10), power_units=UnitSystem.NATURAL_UNITS),
        )


class StorageCost(OperationalCost):
    charge_variable_cost: CostCurve | None = None
    discharge_variable_cost: CostCurve | None = None
    energy_shortage_cost: Annotated[
        NonNegativeFloat, Field(description="Cost incurred by the model for being short of the energy target")
    ] = 0.0
    energy_surplus_cost: Annotated[NonNegativeFloat, Field(description="Cost of using fuel in $/MWh.")] = 0.0
    fixed: Annotated[NonNegativeFloat, Field(description=" Fixed cost of operating the storage system")] = 0.0
    shut_down: Annotated[NonNegativeFloat | None, Field(description="Cost to turn the unit off")] = 0.0
    start_up: Annotated[NonNegativeFloat | None, Field(description="Cost to start the unit.")] = 0.0


class LoadCost(OperationalCost):
    """An operational cost for controllable loads.

    Includes a required variable cost curve and an optional fixed-cost component.
    """

    variable: Annotated[
        CostCurve,
        Field(description="Variable cost represented as a CostCurve."),
    ]
    fixed: Annotated[
        float,
        Field(
            description=("Fixed cost component. For some cost representations this field can be duplicative.")
        ),
    ] = 0.0

    @classmethod
    def example(cls) -> "LoadCost":
        return LoadCost(
            variable=CostCurve(value_curve=LinearCurve(0), power_units=UnitSystem.NATURAL_UNITS),
            fixed=0.0,
        )

    def get_variable(self) -> CostCurve:
        """Get LoadCost variable."""
        return self.variable

    def get_fixed(self) -> float:
        """Get LoadCost fixed value."""
        return self.fixed

    def set_variable(self, value: CostCurve) -> None:
        """Set LoadCost variable."""
        self.variable = value

    def set_fixed(self, value: float) -> None:
        """Set LoadCost fixed value."""
        self.fixed = value


class HydroReservoirCost(OperationalCost):
    """An operational cost for HydroReservoirs

    It includes fixed cost for level shortage, surplus and spillage.
    """

    level_shortage_cost: Annotated[
        float, Field(description=("Cost incurred by the model for being short of the reservoir level target"))
    ] = 0.0
    level_surplus_cost: Annotated[
        float, Field(description=("Cost incurred by the model for surplus of the reservoir"))
    ] = 0.0
    spillage_cost: Annotated[
        float, Field(description=("Cost incurred by the model for spillage of the reservoir"))
    ] = 0.0

    @classmethod
    def example(cls) -> "HydroReservoirCost":
        return HydroReservoirCost(level_shortage_cost=0.0, spillage_cost=0.0, level_surplus_cost=0.0)


class MarketBidCost(OfferCurveCost):
    """An operating cost for market bids of energy and ancillary services for any asset.

    Compatible with most US Market bidding mechanisms that support demand and generation side.
    """

    no_load_cost: Annotated[
        float | None,
        Field(description="No load cost"),
    ] = None
    start_up: Annotated[
        StartUpStages,
        Field(
            description=(
                "Start-up cost at different stages of the thermal cycle as the unit cools after a "
                "shutdown (e.g., hot, warm, or cold starts). Warm is also referred to as "
                "intermediate in some markets."
            )
        ),
    ]
    shut_down: Annotated[
        float,
        Field(description="Shut-down cost"),
    ] = 0.0
    incremental_offer_curves: Annotated[
        CostCurve | None,
        Field(
            description=(
                "Sell Offer Curves data, which can be a CostCurve with PiecewiseStepData or "
                "PiecewiseLinearData for market bidding"
            )
        ),
    ] = None
    decremental_offer_curves: Annotated[
        CostCurve | None,
        Field(
            description=(
                "Buy Offer Curves data, which can be a CostCurve with PiecewiseStepData or "
                "PiecewiseLinearData for market bidding"
            )
        ),
    ] = None
    incremental_initial_input: Annotated[
        float | None,
        Field(description=("Initial input for incremental offer curves if using time series data")),
    ] = None
    decremental_initial_input: Annotated[
        float | None,
        Field(description=("Initial input for decremental offer curves if using time series data")),
    ] = None

    @classmethod
    def example(cls) -> "MarketBidCost":
        return MarketBidCost(
            no_load_cost=100.0,
            start_up=StartUpStages(hot=500.0, warm=750.0, cold=1000.0),
            shut_down=200.0,
            incremental_offer_curves=CostCurve(
                value_curve=LinearCurve(35.0), power_units=UnitSystem.NATURAL_UNITS
            ),
            decremental_offer_curves=None,
            incremental_initial_input=10.0,
        )


class ImportExportCost(OfferCurveCost):
    """An operating cost for imports/exports and ancillary services from neighboring areas.
    The data model employs a CostCurve{PiecewiseIncrementalCurve} with an implied zero cost at zero power.
    """

    import_offer_curves: Annotated[
        TimeSeriesKey | CostCurve | None,
        Field(
            description=(
                "Buy Price Curves data to import power, which can be a time series of [PiecewiseStepData] or a CostCurve of PiecewiseIncrementalCurve"
            )
        ),
    ] = None

    export_offer_curves: Annotated[
        TimeSeriesKey | CostCurve | None,
        Field(
            description=(
                "Sell Price Curves data to export power, which can be a time series of PiecewiseStepData or a CostCurve of PiecewiseIncrementalCurve"
            )
        ),
    ] = None

    energy_import_weekly_limit: Annotated[
        float,
        Field(
            description="Weekly limit on the amount of energy that can be imported, defined in system base p.u-hours."
        ),
    ] = float("inf")

    energy_export_weekly_limit: Annotated[
        float,
        Field(
            description="Weekly limit on the amount of energy that can be exported, defined in system base p.u-hours."
        ),
    ] = float("inf")

    ancillary_service_offers: Annotated[
        list[Service],
        Field(description="Ancillary service offer data associated with import/export bidding."),
    ] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_offer_curves(self) -> "ImportExportCost":
        if isinstance(self.import_offer_curves, CostCurve) and not _is_import_export_curve(
            self.import_offer_curves
        ):
            msg = "import_offer_curves must be a CostCurve with IncrementalCurve backed by "
            msg += "PiecewiseStepData initial_input=0.0 input_at_zero=0.0 and first x=0.0"
            raise ValueError(msg)

        if isinstance(self.export_offer_curves, CostCurve) and not _is_import_export_curve(
            self.export_offer_curves
        ):
            msg = "export_offer_curves must be a CostCurve with IncrementalCurve backed by "
            msg += "PiecewiseStepData initial_input=0.0 input_at_zero=0.0 and first x=0.0"
            raise ValueError(msg)

        return self

    @classmethod
    def example(cls) -> "ImportExportCost":
        return ImportExportCost(
            import_offer_curves=CostCurve(
                value_curve=LinearCurve(35.0), power_units=UnitSystem.NATURAL_UNITS
            ),
            export_offer_curves=CostCurve(
                value_curve=LinearCurve(35.0), power_units=UnitSystem.NATURAL_UNITS
            ),
            energy_import_weekly_limit=1e6,
            energy_export_weekly_limit=1e6,
        )


def _is_import_export_curve(curve: CostCurve) -> bool:
    value_curve = curve.value_curve
    if not isinstance(value_curve, IncrementalCurve):
        return False

    data = value_curve.function_data
    if not isinstance(data, PiecewiseStepData):
        return False

    return value_curve.initial_input == 0.0 and value_curve.input_at_zero == 0.0 and data.x_coords[0] == 0.0
