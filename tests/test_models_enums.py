"""Tests for Sienna model enumerations."""

from r2x_sienna.models.enums import (
    ACBusTypes,
    ReserveDirection,
    ReserveType,
    ReservoirDataType,
)


def test_reserve_type_spinning_exists():
    """Test that SPINNING reserve type exists."""
    assert ReserveType.SPINNING.value == "SPINNING"


def test_reserve_type_flexibility_exists():
    """Test that FLEXIBILITY reserve type exists."""
    assert ReserveType.FLEXIBILITY.value == "FLEXIBILITY"


def test_reserve_type_regulation_exists():
    """Test that REGULATION reserve type exists."""
    assert ReserveType.REGULATION.value == "REGULATION"


def test_reserve_direction_up_exists():
    """Test that UP reserve direction exists."""
    assert ReserveDirection.UP.value == "UP"


def test_reserve_direction_down_exists():
    """Test that DOWN reserve direction exists."""
    assert ReserveDirection.DOWN.value == "DOWN"


def test_reservoir_data_type_usable_volume_exists():
    """Test that USABLE_VOLUME reservoir data type exists."""
    assert ReservoirDataType.USABLE_VOLUME.value == "USABLE_VOLUME"


def test_reservoir_data_type_total_volume_exists():
    """Test that TOTAL_VOLUME reservoir data type exists."""
    assert ReservoirDataType.TOTAL_VOLUME.value == "TOTAL_VOLUME"


def test_reservoir_data_type_head_exists():
    """Test that HEAD reservoir data type exists."""
    assert ReservoirDataType.HEAD.value == "HEAD"


def test_reservoir_data_type_energy_exists():
    """Test that ENERGY reservoir data type exists."""
    assert ReservoirDataType.ENERGY.value == "ENERGY"


def test_acbus_types_pv_exists():
    """Test that PV bus type exists."""
    assert ACBusTypes.PV.value == "PV"


def test_acbus_types_pq_exists():
    """Test that PQ bus type exists."""
    assert ACBusTypes.PQ.value == "PQ"


def test_acbus_types_ref_exists():
    """Test that REF bus type exists."""
    assert ACBusTypes.REF.value == "REF"


def test_acbus_types_slack_exists():
    """Test that SLACK bus type exists."""
    assert ACBusTypes.SLACK.value == "SLACK"


def test_acbus_types_isolated_exists():
    """Test that ISOLATED bus type exists."""
    assert ACBusTypes.ISOLATED.value == "ISOLATED"


def test_all_reserve_types_are_valid():
    """Test that all ReserveType enum members have valid string values."""
    for reserve_type in ReserveType:
        assert isinstance(reserve_type.value, str)
        assert len(reserve_type.value) > 0


def test_all_reserve_directions_are_valid():
    """Test that all ReserveDirection enum members have valid string values."""
    for direction in ReserveDirection:
        assert isinstance(direction.value, str)
        assert len(direction.value) > 0


def test_all_reservoir_data_types_are_valid():
    """Test that all ReservoirDataType enum members have valid string values."""
    for dtype in ReservoirDataType:
        assert isinstance(dtype.value, str)
        assert len(dtype.value) > 0


def test_all_acbus_types_are_valid():
    """Test that all ACBusTypes enum members have valid string values."""
    for bus_type in ACBusTypes:
        assert isinstance(bus_type.value, str)
        assert len(bus_type.value) > 0
