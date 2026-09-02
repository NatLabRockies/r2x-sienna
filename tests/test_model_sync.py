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
from r2x_sienna.models.core import Device
from r2x_sienna.models.costs import HydroGenerationCost, HydroReservoirCost
from r2x_sienna.models.named_tuples import FromTo_ToFrom, InputOutput, TurbinePump


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


def test_hydro_pump_turbine_matches_current_sienna_fields():
    assert "head_reservoir" not in HydroPumpTurbine.model_fields
    assert "tail_reservoir" not in HydroPumpTurbine.model_fields
    assert HydroPumpTurbine.model_fields["active_power_pump"].default == 0.0
    assert HydroPumpTurbine.model_fields["powerhouse_elevation"].default == 0.0
    assert HydroPumpTurbine.model_fields["efficiency"].default == TurbinePump(turbine=1.0, pump=1.0)
    assert HydroPumpTurbine.model_fields["transition_time"].default == TurbinePump(turbine=0.0, pump=0.0)
    assert HydroPumpTurbine.model_fields["minimum_time"].default == TurbinePump(turbine=0.0, pump=0.0)
    assert HydroPumpTurbine.model_fields["conversion_factor"].default == 1.0
    assert HydroPumpTurbine.model_fields["must_run"].default is False
    assert HydroPumpTurbine.model_fields["prime_mover_type"].default is PrimeMoversType.PS


def test_current_psy_tuple_keys_are_accepted():
    assert InputOutput.model_validate({"in": 0.9, "out": 0.8}).input == 0.9
    assert FromTo_ToFrom.model_validate({"from": 0.01, "to": 0.02}).to_from == 0.02


def test_hydro_reservoir_matches_current_sienna_fields():
    assert "max_level" not in HydroReservoir.model_fields
    assert "reservoir_location" not in HydroReservoir.model_fields
    assert HydroReservoir.model_fields["operation_cost"].default is not None
    assert HydroReservoir.model_fields["upstream_reservoirs"].annotation == list[Device]


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
    assert round_tripped.variable is None


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
