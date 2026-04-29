import pytest
from infrasys.cost_curves import CostCurve, FuelCurve, UnitSystem
from infrasys.value_curves import LinearCurve
from r2x_sienna.models.costs import (
    HydroGenerationCost,
    LoadCost,
    OperationalCost,
    RenewableGenerationCost,
    StorageCost,
    ThermalGenerationCost,
)


def test_properties():
    cost = OperationalCost()
    assert isinstance(cost, OperationalCost)


def test_computed_fields():
    variable = FuelCurve(value_curve=LinearCurve(0), power_units=UnitSystem.NATURAL_UNITS)
    cost = ThermalGenerationCost(variable=variable)

    assert isinstance(cost, OperationalCost)
    assert isinstance(cost, ThermalGenerationCost)
    assert cost.variable_type == "FuelCurve"
    assert cost.value_curve_type == "InputOutputCurve"

    cost = ThermalGenerationCost()
    assert isinstance(cost, OperationalCost)
    assert isinstance(cost, ThermalGenerationCost)
    assert cost.variable_type is None
    assert cost.value_curve_type is None


def test_default_fields():
    cost = ThermalGenerationCost()
    assert isinstance(cost, OperationalCost)
    assert isinstance(cost, ThermalGenerationCost)
    assert cost.fixed == 0.0
    assert cost.shut_down == 0.0
    assert cost.start_up == 0.0

    cost = HydroGenerationCost()
    assert isinstance(cost, OperationalCost)
    assert isinstance(cost, HydroGenerationCost)
    assert cost.fixed == 0.0

    cost = RenewableGenerationCost()
    assert isinstance(cost, OperationalCost)
    assert isinstance(cost, RenewableGenerationCost)
    assert cost.curtailment_cost is None

    cost = StorageCost()
    assert isinstance(cost, OperationalCost)
    assert isinstance(cost, StorageCost)
    assert cost.energy_surplus_cost == 0.0
    assert cost.fixed == 0.0
    assert cost.shut_down == 0.0
    assert cost.start_up == 0.0

    cost = LoadCost(variable=CostCurve(value_curve=LinearCurve(0), power_units=UnitSystem.NATURAL_UNITS))
    assert isinstance(cost, OperationalCost)
    assert isinstance(cost, LoadCost)
    assert cost.fixed == 0.0


def test_load_cost_requires_variable():
    with pytest.raises(Exception):
        LoadCost()  # type: ignore[call-arg]


def test_load_cost_getters_setters():
    initial_curve = CostCurve(value_curve=LinearCurve(0), power_units=UnitSystem.NATURAL_UNITS)
    updated_curve = CostCurve(value_curve=LinearCurve(5), power_units=UnitSystem.NATURAL_UNITS)
    cost = LoadCost(variable=initial_curve)

    assert cost.get_variable() == initial_curve
    assert cost.get_fixed() == 0.0

    cost.set_variable(updated_curve)
    cost.set_fixed(12.5)

    assert cost.get_variable() == updated_curve
    assert cost.get_fixed() == 12.5
