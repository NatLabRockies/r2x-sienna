import json
from unittest.mock import Mock

import pytest
from infrasys import System
from infrasys.cost_curves import FuelCurve, UnitSystem
from infrasys.function_data import XYCoords
from infrasys.value_curves import LinearCurve
from pydantic import ValidationError

from r2x_sienna.exporter import to_psy
from r2x_sienna.models import (
    ACBus,
    Arc,
    Complex,
    FromTo_ToFrom,
    InputOutput,
    Line,
    MinMax,
    PrimeMoversType,
    StartUpStages,
    ThermalFuels,
    ThermalGenerationCost,
    ThermalStandard,
    UpDown,
)
from r2x_sienna.models.branch import PhaseShiftingTransformer, PhaseShiftingTransformer3W
from r2x_sienna.plugin_config import SiennaConfig
from r2x_sienna.serialization import _serialize_parametric_object, serialize_component_to_psy, serialize_value


def create_thermal_standard(name="test_generator", base_power=100.0, **kwargs):
    """Helper function to create ThermalStandard with default values."""
    defaults = {
        "must_run": False,
        "bus": ACBus.example(),
        "status": False,
        "rating": 200.0,
        "active_power": 0.0,
        "reactive_power": 0.0,
        "active_power_limits": MinMax(min=0, max=1),
        "prime_mover_type": PrimeMoversType.CC,
        "fuel": ThermalFuels.NATURAL_GAS,
        "operation_cost": ThermalGenerationCost.example(),
        "time_at_status": 1_000,
    }
    defaults.update(kwargs)

    return ThermalStandard(name=name, base_power=base_power, **defaults)


@pytest.fixture
def sienna_config(data_folder, tmp_path):
    return SiennaConfig(
        model_year=2010,
        system_name="Test System",
        scenario="test_scenario",
        system_base_power=100.0,
        skip_validation=False,
        json_path=str(data_folder / "test.json"),
    )


@pytest.fixture
def infrasys_test_system():
    """Create a test system with basic components for testing."""
    system = System()
    system.name = "test_system"

    # Add a test bus
    bus = ACBus(name="test_bus", number=1)
    system.add_component(bus)

    # Add a test generator with complete parameters
    gen = create_thermal_standard(
        name="test_gen",
        bus=bus,
        rating=150.0,
    )
    system.add_component(gen)

    return system


def test_serialize_component_to_psy(infrasys_test_system):
    """Test that components can be serialized to PSY format."""
    components = list(infrasys_test_system._component_mgr.iter_all())
    if components:
        component = components[0]
        serialized = serialize_component_to_psy(component)
        assert serialized is not None
        assert "__metadata__" in serialized
        assert "internal" in serialized


def test_get_component_output_fields():
    """Test that component output fields can be retrieved."""
    fields = set(ThermalStandard.model_fields.keys())
    assert isinstance(fields, set)
    assert len(fields) > 0


@pytest.mark.parametrize("angle", [-1.571, 1.571])
def test_acbus_rejects_angles_at_validation_bounds(angle):
    """AC bus angles must be strictly inside the valid +/- pi/2 bounds."""
    with pytest.raises(ValueError):
        ACBus(name="boundary_angle_bus", number=1, angle=angle)


@pytest.mark.parametrize(
    "transformer_type, angle_fields",
    [
        (PhaseShiftingTransformer, ["α"]),
        (PhaseShiftingTransformer3W, ["α_primary", "α_secondary", "α_tertiary"]),
    ],
)
def test_phase_shifting_transformer_warns_for_out_of_range_angles(
    monkeypatch, transformer_type, angle_fields
):
    """Phase-shifting transformer angles are retained while warning when out of range."""
    transformer = transformer_type.example()
    values = transformer.model_dump(exclude_computed_fields=True)
    for field in angle_fields:
        values[field] = 2.0

    warning = Mock()
    monkeypatch.setattr("r2x_sienna.models.branch.logger.warning", warning)
    validated = transformer_type.model_validate(values)

    assert all(getattr(validated, field) == 2.0 for field in angle_fields)
    assert warning.call_count == len(angle_fields)
    assert all("outside the valid range" in call.args[0] for call in warning.call_args_list)


def test_to_psy_serialization(sienna_config, infrasys_test_system, tmp_path):
    """Test full PSY serialization."""
    output_file = tmp_path / "test_system.json"

    system_data = {
        "system_information": {"name": "Test System", "description": "Test system for PSY serialization"},
        "data_information": {"version": "1.0", "base_power": 100.0},
        "component_fields": {},
    }

    to_psy(sienna_config, infrasys_test_system, system_data, output_file, write_year=2010)

    assert output_file.exists()

    with open(output_file, "rb") as f:
        data = json.load(f)

    assert "data" in data
    assert "components" in data["data"]
    assert isinstance(data["data"]["components"], list)


def test_psy_serialization_with_quantity():
    """Test PSY serialization with Quantity objects."""
    component = create_thermal_standard(
        rating=100.0,
    )

    result = serialize_value(component.rating, "rating")
    assert result == 100.0


def test_psy_serialization_with_minmax():
    """Test PSY serialization with MinMax objects."""
    limits = MinMax(min=10.0, max=100.0)
    component = create_thermal_standard(
        active_power_limits=limits,
    )

    result = serialize_value(component.active_power_limits, "active_power_limits")
    assert result == {"min": 10.0, "max": 100.0}


def test_psy_serialization_with_updown():
    """Test PSY serialization with UpDown objects."""
    updown = UpDown(up=50.0, down=30.0)
    result = serialize_value(updown, "test_field")
    assert result == {"up": 50.0, "down": 30.0}


def test_psy_serialization_with_inputoutput():
    """Test PSY serialization with InputOutput objects."""
    inputoutput = InputOutput(input=25.0, output=75.0)
    result = serialize_value(inputoutput, "test_field")
    assert result == {"in": 25.0, "out": 75.0}


def test_psy_serialization_with_complex():
    """Test PSY serialization with Complex objects."""
    complex_val = Complex(real=10.0, imag=5.0)
    result = serialize_value(complex_val, "test_field")
    assert result == {"real": 10.0, "imag": 5.0}


def test_psy_serialization_with_from_to_special_fields():
    """Test serialization of FromTo_ToFrom with special and default field handling."""
    values = FromTo_ToFrom(from_to=1.5, to_from=-2.5)

    assert serialize_value(values, "b") == {"from": 1.5, "to": -2.5}
    assert serialize_value(values, "x") == {"from_to": 1.5, "to_from": -2.5}


def test_psy_serialization_with_xycoords():
    """Test PSY serialization for XYCoords values."""
    xy = XYCoords(x=3.0, y=4.0)
    result = serialize_value(xy, "xy")
    assert result == {"x": 3.0, "y": 4.0}


def test_psy_serialization_with_operational_cost():
    """Test PSY serialization with operational cost objects."""
    cost = ThermalGenerationCost(
        variable=FuelCurve(
            value_curve=LinearCurve(10.0, 12),
            vom_cost=LinearCurve(10.0),
            fuel_cost=0.05,
            power_units=UnitSystem.NATURAL_UNITS,
        )
    )

    component = create_thermal_standard(
        operation_cost=cost,
    )

    result = serialize_value(component.operation_cost, "operation_cost")
    assert result is not None
    assert isinstance(result, dict)
    assert "__metadata__" in result


def test_psy_serialization_none_value():
    """Test that PSY serialization returns string values as-is."""
    component = create_thermal_standard()

    result = serialize_value(component.name, "name")
    assert result == "test_generator"


def test_psy_parametric_serialization():
    """Test parametric serialization functionality."""
    cost = ThermalGenerationCost(
        variable=FuelCurve(
            value_curve=LinearCurve(10.0, 12),
            vom_cost=LinearCurve(10.0),
            fuel_cost=0.05,
            power_units=UnitSystem.NATURAL_UNITS,
        )
    )

    result = _serialize_parametric_object(cost)
    assert isinstance(result, dict)
    assert "__metadata__" in result
    assert result["__metadata__"]["module"] == "PowerSystems"
    assert result["__metadata__"]["type"] == "ThermalGenerationCost"


def test_psy_serialization_with_staged_startup_cost():
    """ThermalGenerationCost.start_up can be serialized as hot/warm/cold staging."""
    cost = ThermalGenerationCost(
        start_up=StartUpStages(hot=100.0, warm=150.0, cold=250.0),
        shut_down=50.0,
        fixed=0.0,
    )

    result = serialize_value(cost, "operation_cost")
    assert result is not None
    assert isinstance(result, dict)
    assert result["start_up"] == {"hot": 100.0, "warm": 150.0, "cold": 250.0}


def test_line_accepts_signed_flow_values():
    """PSY Line uses Float64 for flows, so signed values must be accepted."""
    bus_1 = ACBus(name="line_test_bus_1", number=1001)
    bus_2 = ACBus(name="line_test_bus_2", number=1002)
    line = Line(
        name="line_signed_flow",
        arc=Arc(from_to=bus_1, to_from=bus_2),
        r=0.01,
        x=0.10,
        rating=100.0,
        active_power_flow=-20.0,
        reactive_power_flow=-5.0,
        angle_limits=MinMax(min=-0.5, max=0.5),
    )

    assert line.active_power_flow == -20.0
    assert line.reactive_power_flow == -5.0


def test_line_requires_impedance_and_rating_fields():
    """Line should require PSY mandatory electrical fields."""
    bus_1 = ACBus(name="line_required_bus_1", number=1003)
    bus_2 = ACBus(name="line_required_bus_2", number=1004)

    with pytest.raises(ValidationError):
        Line(
            name="line_missing_fields",
            arc=Arc(from_to=bus_1, to_from=bus_2),
            active_power_flow=0.0,
            reactive_power_flow=0.0,
            angle_limits=MinMax(min=-0.5, max=0.5),
        )


def test_serialize_nested_component():
    """Test nested component serialization."""

    component = ACBus.example()
    result = serialize_value(component, "test_field")
    assert isinstance(result, dict)
    assert "value" in result
    assert result["value"] == str(component.uuid)


def test_serialize_arc_component_remaps_aliases():
    """Test Arc serialization remaps from_to/to_from keys to from/to aliases."""
    from_bus = ACBus(name="from_bus", number=101)
    to_bus = ACBus(name="to_bus", number=102)
    arc = Arc(name="arc_1", **{"from": from_bus, "to": to_bus})

    serialized = serialize_component_to_psy(arc)
    assert serialized is not None
    assert "from" in serialized
    assert "to" in serialized
    assert "from_to" not in serialized
    assert "to_from" not in serialized


def test_sienna_config_creation():
    """Test SiennaConfig creation."""
    config = SiennaConfig(
        model_year=2030,
        system_name="Test System",
        scenario="test",
        system_base_power=100.0,
        skip_validation=True,
    )
    assert config.model_year == 2030
    assert config.system_name == "Test System"
    assert config.scenario == "test"
    assert config.system_base_power == 100.0
    assert config.skip_validation is True


def test_sienna_config_multiple_years():
    """Test SiennaConfig with multiple years."""
    config = SiennaConfig(
        model_year=[2030, 2040, 2050],
        system_name="Multi Year System",
    )
    assert config.model_year == [2030, 2040, 2050]


def test_system_data_structure():
    """Test that the system data structure is properly formatted."""
    system_data = {
        "system_information": {"name": "Test System", "description": "Test description"},
        "data_information": {"version": "1.0", "base_power": 100.0, "components": []},
    }

    assert "system_information" in system_data
    assert "data_information" in system_data
    assert isinstance(system_data["system_information"], dict)
    assert isinstance(system_data["data_information"], dict)
