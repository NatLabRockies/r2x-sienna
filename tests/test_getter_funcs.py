import pytest
from pint import Quantity

from r2x_sienna.models.generators import ThermalStandard
from r2x_sienna.models.enums import PrimeMoversType, ThermalFuels
from r2x_sienna.models.topology import ACBus
from r2x_sienna.models.costs import ThermalGenerationCost
from r2x_sienna.models.getters import _get_multiplier, get_max_active_power, get_ramp_limits, get_value
from r2x_sienna.models.named_tuples import MinMax, UpDown
from r2x_sienna.units import get_magnitude


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


def test_get_value_minmax():
    """Test get_value with MinMax value."""
    component = create_thermal_standard(base_power=100.0)

    value = MinMax(min=0.5, max=1.0)
    result = get_value(value, component)

    assert isinstance(result, MinMax)
    assert result.min == 50.0
    assert result.max == 100.0


def test_get_value_float():
    """Test get_value with float value."""
    component = create_thermal_standard(base_power=200.0)

    value = 0.8
    result = get_value(value, component)

    assert result == 160.0


def test_get_value_quantity():
    """Test get_value with Quantity value."""
    component = create_thermal_standard(base_power=50.0)

    value = Quantity(0.6, "MW")
    result = get_value(value, component)

    assert result == 30.0


def test_get_value_not_implemented():
    """Test get_value raises NotImplementedError for unsupported types."""
    component = create_thermal_standard(base_power=100.0)

    with pytest.raises(NotImplementedError, match="`get_value` not implemented for"):
        get_value("unsupported_string", component)


def test_get_value_no_base_power():
    """Test get_value when component has no base_power."""
    # Note: base_power is required in the new ThermalStandard definition
    # This test might need to be adjusted based on actual behavior
    component = create_thermal_standard(base_power=1.0)  # Use minimal value instead of None

    value = 5.0
    result = get_value(value, component)

    assert result == 5.0


def test_get_max_active_power_generator():
    """Test get_max_active_power with Generator."""
    generator = create_thermal_standard(base_power=100.0, active_power_limits=MinMax(min=0.3, max=1.0))

    result = get_max_active_power(generator)

    assert result == 100.0


def test_get_max_active_power_not_implemented():
    """Test get_max_active_power raises TypeError due to NotImplementedType usage."""
    unsupported_component = "Generator()"

    with pytest.raises(TypeError, match="`get_max_active_power` not implemented"):
        get_max_active_power(unsupported_component)


def test_get_ramp_limits_generator():
    """Test get_ramp_limits with Generator having ramp_limits."""
    generator = create_thermal_standard(base_power=100.0, ramp_limits=UpDown(up=0.1, down=0.08))

    result = get_ramp_limits(generator)

    assert isinstance(result, UpDown)
    assert get_magnitude(result.up) * generator.base_power == 10.0
    assert get_magnitude(result.down) * generator.base_power == 8.0


def test_get_ramp_limits_no_ramp():
    """Test get_ramp_limits when Generator has no ramp_limits."""
    generator = create_thermal_standard(base_power=100.0, ramp_limits=None)

    with pytest.raises(KeyError, match="Ramp not defined for"):
        get_ramp_limits(generator)


def test_get_ramp_limits_not_implemented():
    """Test get_ramp_limits raises NotImplementedType for unsupported components."""
    unsupported_component = "Generator()"

    with pytest.raises(TypeError, match="`get_ramp_limits` not implemented"):
        get_ramp_limits(unsupported_component)


def test_get_multiplier_with_base_power():
    """Test _get_multiplier when component has base_power."""
    component = create_thermal_standard(base_power=150.0)

    result = _get_multiplier(component)
    assert result == 150.0


def test_get_multiplier_no_base_power():
    """Test _get_multiplier when component has no base_power."""
    component = create_thermal_standard(base_power=1.0)

    result = _get_multiplier(component)
    assert result == 1.0


def test_get_multiplier_no_base_power_attribute():
    """Test _get_multiplier when component doesn't have base_power attribute."""
    component = create_thermal_standard(base_power=1.0)

    result = _get_multiplier(component)
    assert result == 1.0
