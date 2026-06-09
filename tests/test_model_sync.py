import pytest
from pydantic import ValidationError

from r2x_sienna.models import (
    ACBus,
    ConstantReserveNonSpinning,
    DCBus,
    HydroPumpTurbine,
    HydroReservoir,
    HydroTurbine,
    InterconnectingConverter,
    MinMax,
    PrimeMoversType,
    ReserveDemandCurve,
    VariableReserveNonSpinning,
)
from r2x_sienna.models.costs import HydroGenerationCost, HydroReservoirCost
from r2x_sienna.models.named_tuples import TurbinePump


def test_hydro_travel_time_is_turbine_field_only():
    assert "travel_time" not in HydroReservoir.model_fields
    assert "travel_time" in HydroTurbine.model_fields
    assert "travel_time" in HydroPumpTurbine.model_fields


def test_hydro_reservoir_rejects_legacy_travel_time_field():
    with pytest.raises(ValidationError):
        HydroReservoir(
            name="Reservoir1",
            available=True,
            initial_level=1.0,
            storage_level_limits={"min": 0.0, "max": 1.0},
            spillage_limits=None,
            inflow=0.0,
            outflow=0.0,
            level_targets=0.0,
            level_data_type="TOTAL_VOLUME",
            intake_elevation=0.0,
            operation_cost=HydroReservoirCost.example(),
            travel_time=0.0,
        )


def test_hydro_turbine_accepts_travel_time_and_round_trips_json():
    turbine = HydroTurbine(
        name="Turbine1",
        available=True,
        bus=None,
        active_power=0.0,
        reactive_power=0.0,
        rating=1.0,
        base_power=100.0,
        active_power_limits=MinMax(min=0.0, max=1.0),
        reactive_power_limits=MinMax(min=-1.0, max=1.0),
        outflow_limits=MinMax(min=0.0, max=1.0),
        powerhouse_elevation=0.0,
        ramp_limits={"up": 1.0, "down": 1.0},
        time_limits={"up": 1.0, "down": 1.0},
        operation_cost=HydroGenerationCost.example(),
        prime_mover_type=PrimeMoversType.OT,
        travel_time=0.25,
    )

    round_tripped = HydroTurbine.model_validate_json(turbine.model_dump_json(round_trip=True))

    assert round_tripped.travel_time == 0.25


def test_hydro_pump_turbine_accepts_travel_time_and_round_trips_json():
    turbine = HydroPumpTurbine(
        name="PumpTurbine1",
        available=True,
        bus=None,
        active_power=100.0,
        reactive_power=0.0,
        rating=100.0,
        active_power_limits=MinMax(min=0.0, max=100.0),
        reactive_power_limits=MinMax(min=-100.0, max=100.0),
        active_power_limits_pump=MinMax(min=0.0, max=100.0),
        outflow_limits=MinMax(min=0.0, max=100.0),
        powerhouse_elevation=100.0,
        base_power=100.0,
        active_power_pump=50.0,
        efficiency=TurbinePump(turbine=0.90, pump=0.85),
        conversion_factor=1.0,
        ramp_limits={"up": 1.0, "down": 1.0},
        time_limits={"up": 1.0, "down": 1.0},
        time_at_status=0.0,
        must_run=False,
        prime_mover_type=PrimeMoversType.PS,
        transition_time=TurbinePump(turbine=0.25, pump=0.25),
        operation_cost=HydroGenerationCost.example(),
        minimum_time=TurbinePump(turbine=1.0, pump=1.0),
        travel_time=0.5,
    )

    round_tripped = HydroPumpTurbine.model_validate_json(turbine.model_dump_json(round_trip=True))

    assert round_tripped.travel_time == 0.5


@pytest.mark.parametrize(
    "model_cls",
    [VariableReserveNonSpinning, ConstantReserveNonSpinning],
)
def test_non_spinning_reserve_models_import_construct_validate_and_round_trip_json(model_cls):
    reserve = model_cls(
        name="NonSpinningReserve",
        available=True,
        time_frame=300.0,
        requirement=10.0,
        sustained_time=3600.0,
        max_output_fraction=1.0,
        max_participation_factor=0.5,
        deployed_fraction=0.1,
    )

    round_tripped = model_cls.model_validate_json(reserve.model_dump_json(round_trip=True))

    assert round_tripped.requirement == 10.0


def test_reserve_demand_curve_import_construct_validate_and_round_trip_json():
    reserve = ReserveDemandCurve(
        name="ReserveDemandCurve1",
        available=True,
        time_frame=300.0,
        sustained_time=3600.0,
        max_participation_factor=0.5,
        deployed_fraction=0.1,
    )

    round_tripped = ReserveDemandCurve.model_validate_json(reserve.model_dump_json(round_trip=True))

    assert round_tripped.max_participation_factor == 0.5


def test_interconnecting_converter_import_construct_validate_and_round_trip_json():
    converter = InterconnectingConverter(
        name="Converter1",
        available=True,
        bus=ACBus(name="ACBus1", number=1),
        dc_bus=DCBus(name="DCBus1", number=2),
        active_power=0.0,
        rating=100.0,
        active_power_limits=MinMax(min=-100.0, max=100.0),
        base_power=100.0,
        reactive_power_limits=MinMax(min=-50.0, max=50.0),
        max_dc_current=1.0,
    )

    round_tripped = InterconnectingConverter.model_validate_json(converter.model_dump_json(round_trip=True))

    assert round_tripped.max_dc_current == 1.0


@pytest.mark.parametrize(
    "model_cls, kwargs",
    [
        (VariableReserveNonSpinning, {"requirement": 1.0}),
        (ConstantReserveNonSpinning, {"requirement": 1.0}),
        (ReserveDemandCurve, {}),
        (
            InterconnectingConverter,
            {
                "bus": ACBus(name="ACBusInvalid", number=3),
                "dc_bus": DCBus(name="DCBusInvalid", number=4),
                "active_power": 0.0,
                "rating": 100.0,
                "active_power_limits": MinMax(min=-100.0, max=100.0),
                "base_power": 100.0,
                "max_dc_current": 1.0,
            },
        ),
    ],
)
def test_new_models_reject_invalid_extra_fields(model_cls, kwargs):
    with pytest.raises(ValidationError):
        model_cls(name="InvalidExtraField", available=True, unexpected_field=1, **kwargs)
