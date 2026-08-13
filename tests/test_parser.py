"""Basic Sienna parser tests using r2x-core Plugin API.

These tests verify basic parser instantiation and configuration using
a minimal test data set.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
from infrasys import Deterministic, SingleTimeSeries
from infrasys.exceptions import ISNotStored
from r2x_core import DataStore, PluginContext, System

from r2x_sienna.models import HydroReservoir, Source
from r2x_sienna.parser import SiennaParser
from r2x_sienna.plugin_config import SiennaConfig


@pytest.fixture
def sienna_config() -> SiennaConfig:
    """Create basic Sienna configuration."""
    return SiennaConfig(model_year=2029, system_name="test_case")


@pytest.fixture
def mock_data_store() -> Mock:
    """Create a mock DataStore for testing parser instantiation."""
    mock_store = Mock(spec=DataStore)
    mock_store.folder = Path("/fake/path")
    # Make __contains__ return False so load_data registration is skipped
    mock_store.__contains__ = Mock(return_value=False)
    return mock_store


def test_parser_creation_with_mock(sienna_config: SiennaConfig, mock_data_store: Mock):
    """Test creating SiennaParser instance with plugin context."""
    ctx = PluginContext(config=sienna_config, store=mock_data_store)
    parser = SiennaParser.from_context(ctx)

    assert parser is not None


def test_parser_has_config(sienna_config: SiennaConfig, mock_data_store: Mock):
    """Test parser stores config."""
    ctx = PluginContext(config=sienna_config, store=mock_data_store)
    parser = SiennaParser.from_context(ctx)

    assert parser.config == sienna_config
    assert parser.config.model_year == 2029


def test_parser_has_data_store(sienna_config: SiennaConfig, mock_data_store: Mock):
    """Test parser stores data_store."""
    ctx = PluginContext(config=sienna_config, store=mock_data_store)
    parser = SiennaParser.from_context(ctx)

    assert parser.store == mock_data_store


def test_parser_system_access(sienna_config: SiennaConfig, mock_data_store: Mock):
    """Test parser.system raises error before context has system."""
    from r2x_core import PluginError

    ctx = PluginContext(config=sienna_config, store=mock_data_store)
    parser = SiennaParser.from_context(ctx)

    # System should raise PluginError when not set in context
    with pytest.raises(PluginError, match="System not provided"):
        _ = parser.system


def test_parser_adds_default_hydro_reservoir_inflow_series(
    sienna_config: SiennaConfig, mock_data_store: Mock
):
    """Reservoirs created during PSY4-to-PSY5 upgrades get a default inflow series."""
    ctx = PluginContext(config=sienna_config, store=mock_data_store)
    parser = SiennaParser.from_context(ctx)
    system = System(name="hydro-test")
    reservoir = HydroReservoir.example()
    system.add_component(reservoir)
    parser._ctx.system = system

    parser._ensure_hydro_reservoir_inflow_time_series()

    time_series = system.get_time_series(reservoir, "inflow")
    assert time_series.name == "inflow"
    assert len(time_series.data) == 8760
    assert all(value == 0.0 for value in time_series.data)


def test_parser_preserves_existing_hydro_reservoir_time_series(
    sienna_config: SiennaConfig, mock_data_store: Mock
):
    """Existing reservoir series are not replaced by the default series."""
    ctx = PluginContext(config=sienna_config, store=mock_data_store)
    parser = SiennaParser.from_context(ctx)
    system = System(name="hydro-test")
    reservoir = HydroReservoir.example()
    system.add_component(reservoir)
    existing_series = SingleTimeSeries.from_array(
        data=[1.0] * 8760,
        name="existing_inflow",
        resolution=timedelta(hours=1),
        initial_timestamp=datetime(year=2029, month=1, day=1, tzinfo=UTC),
    )
    system.add_time_series(existing_series, reservoir)
    parser._ctx.system = system

    parser._ensure_hydro_reservoir_inflow_time_series()

    existing = system.get_time_series(reservoir, "existing_inflow")
    inflow = system.get_time_series(reservoir, "inflow")
    assert existing.name == "existing_inflow"
    assert inflow.name == "inflow"


def test_parser_filters_hydro_reservoir_max_active_power(
    sienna_config: SiennaConfig, mock_data_store: Mock
):
    """Reservoirs do not retain the unsupported max_active_power series."""
    ctx = PluginContext(config=sienna_config, store=mock_data_store)
    parser = SiennaParser.from_context(ctx)
    system = System(name="hydro-test")
    reservoir = HydroReservoir.example()
    system.add_component(reservoir)
    system.add_time_series(
        SingleTimeSeries.from_array(
            data=[1.0] * 8760,
            name="max_active_power",
            resolution=timedelta(hours=1),
            initial_timestamp=datetime(year=2029, month=1, day=1, tzinfo=UTC),
        ),
        reservoir,
    )
    system.add_time_series(
        SingleTimeSeries.from_array(
            data=[2.0] * 8760,
            name="inflow",
            resolution=timedelta(hours=1),
            initial_timestamp=datetime(year=2029, month=1, day=1, tzinfo=UTC),
        ),
        reservoir,
    )
    parser._ctx.system = system

    parser._filter_hydro_reservoir_max_active_power()

    with pytest.raises(ISNotStored):
        system.get_time_series(reservoir, "max_active_power")
    assert system.get_time_series(reservoir, "inflow").name == "inflow"


def test_parser_derives_inflow_timestamp_from_existing_series(mock_data_store: Mock):
    """Missing model_year uses an existing time-series timestamp."""
    config = SiennaConfig(model_year=None, system_name="test_case")
    ctx = PluginContext(config=config, store=mock_data_store)
    parser = SiennaParser.from_context(ctx)
    system = System(name="hydro-test")
    reservoir = HydroReservoir.example()
    system.add_component(reservoir)
    existing_series = SingleTimeSeries.from_array(
        data=[1.0] * 8760,
        name="hydro_budget",
        resolution=timedelta(hours=1),
        initial_timestamp=datetime(year=2023, month=1, day=1, tzinfo=UTC),
    )
    system.add_time_series(existing_series, reservoir)
    parser._ctx.system = system

    parser._ensure_hydro_reservoir_inflow_time_series()

    inflow = system.get_time_series(reservoir, "inflow")
    assert inflow.initial_timestamp == existing_series.initial_timestamp


def test_parser_adds_deterministic_inflow_when_system_has_deterministic_series(
    sienna_config: SiennaConfig, mock_data_store: Mock
):
    """Missing reservoir inflow gets both series types when forecasts are present."""
    ctx = PluginContext(config=sienna_config, store=mock_data_store)
    parser = SiennaParser.from_context(ctx)
    system = System(name="hydro-test")
    reservoir = HydroReservoir.example()
    system.add_component(reservoir)
    system.add_time_series(
        Deterministic.from_array(
            data=np.ones((365, 24)),
            name="hydro_budget",
            resolution=timedelta(hours=1),
            initial_timestamp=datetime(year=2029, month=1, day=1, tzinfo=UTC),
            horizon=timedelta(days=1),
            interval=timedelta(days=1),
            window_count=365,
        ),
        reservoir,
    )
    system._time_series_mgr._metadata_store._con.execute(
        "UPDATE time_series_associations SET time_series_type = 'DeterministicSingleTimeSeries'"
    )
    parser._ctx.system = system

    parser._ensure_hydro_reservoir_inflow_time_series()

    con = system._time_series_mgr._metadata_store._con
    rows = con.execute(
        """
        SELECT time_series_type
        FROM time_series_associations
        WHERE owner_uuid = ? AND name = 'inflow'
        ORDER BY time_series_type
        """,
        (str(reservoir.uuid),),
    ).fetchall()
    assert {row[0] for row in rows} == {
        "Deterministic",
        "SingleTimeSeries",
    }


def test_parser_builds_2area_5bus_with_source(data_folder: Path):
    """Parse the 2area-5bus test system and verify Source deserialization."""
    case_path = data_folder / "2area-5bus-system"
    config = SiennaConfig(
        model_year=2029,
        system_name="2area-5bus-system",
        scenario="test_source_parse",
        system_base_power=100.0,
        skip_validation=False,
        json_path=str(case_path / "test_system.json"),
    )

    ctx = PluginContext(
        config=config,
        store=DataStore(path=case_path),
        skip_validation=config.skip_validation,
    )
    parser = SiennaParser.from_context(ctx)
    result_ctx = parser.run()
    system = result_ctx.system

    sources = [component for component in system._component_mgr.iter_all() if isinstance(component, Source)]
    assert sources, "Expected at least one Source component in parsed system"

    source_names = {source.name for source in sources}
    assert "source_bus1" in source_names

    source_bus1 = next(source for source in sources if source.name == "source_bus1")
    assert source_bus1.operation_cost is not None
    assert source_bus1.operation_cost.ancillary_service_offers == []


class TestDeserializeComponentsNested:
    """Tests for _deserialize_components_nested assertion bug.

    The bug: When one component of a type deserializes successfully,
    the code assumes all other components of the same type will too.
    This is wrong because validation can fail for individual components.
    """

    def test_raises_valueerror_when_second_component_has_validation_error(self):
        """Test that ValueError is raised when a component fails validation.

        Scenario:
        - Two ACBus components of the same type
        - First has valid data
        - Second has invalid bus number (0, but must be > 0)
        - First pass: both skip because they reference Area (not yet deserialized)
        - Nested pass: first succeeds, second fails validation
        - With the fix: raises ValueError with clear message listing failed components
        """
        import json
        import tempfile
        from pathlib import Path

        from r2x_core import DataStore, PluginContext, System

        # Create minimal Sienna JSON with:
        # 1. Area component (no dependencies, deserialized first)
        # 2. Two ACBus components that reference Area
        #    - First ACBus: valid angle
        #    - Second ACBus: invalid bus number
        #
        # Note: Use {"value": "uuid"} format for references, which is how
        # actual Sienna JSON files represent component references.
        system_data = {
            "data_format_version": "3.0.0",
            "data": {
                "components": [
                    # Area - will be deserialized in first pass
                    {
                        "__metadata__": {"module": "PowerSystems", "type": "Area"},
                        "name": "Area1",
                        "internal": {
                            "uuid": {"value": "11111111-1111-1111-1111-111111111111"},
                            "ext": None,
                            "units_info": None,
                        },
                        "peak_active_power": 100.0,
                        "peak_reactive_power": 50.0,
                        "load_response": 0.0,
                    },
                    # LoadZone - will be deserialized in first pass
                    {
                        "__metadata__": {"module": "PowerSystems", "type": "LoadZone"},
                        "name": "Zone1",
                        "internal": {
                            "uuid": {"value": "22222222-2222-2222-2222-222222222222"},
                            "ext": None,
                            "units_info": None,
                        },
                        "peak_active_power": 100.0,
                        "peak_reactive_power": 50.0,
                    },
                    # ACBus 1 - valid angle, references Area (skipped first, succeeds in nested)
                    {
                        "__metadata__": {"module": "PowerSystems", "type": "ACBus"},
                        "name": "Bus1",
                        "number": 1,
                        "bustype": "PQ",
                        "angle": 0.1,  # Valid: within (-π/2, π/2)
                        "magnitude": 1.0,
                        "base_voltage": 230.0,
                        "available": True,
                        # Reference to Area using Sienna's {"value": "uuid"} format
                        "area": {"value": "11111111-1111-1111-1111-111111111111"},
                        "load_zone": {"value": "22222222-2222-2222-2222-222222222222"},
                        "internal": {
                            "uuid": {"value": "33333333-3333-3333-3333-333333333333"},
                            "ext": None,
                            "units_info": None,
                        },
                        "ext": {},
                    },
                    # ACBus 2 - INVALID bus number, references Area (skipped first, fails validation in nested)
                    {
                        "__metadata__": {"module": "PowerSystems", "type": "ACBus"},
                        "name": "Bus2_Invalid",
                        "number": 0,  # INVALID: must be > 0 (exclusiveMinimum: 0)
                        "bustype": "PQ",
                        "angle": 0.1,  # Valid angle
                        "magnitude": 1.0,
                        "base_voltage": 230.0,
                        "available": True,
                        "area": {"value": "11111111-1111-1111-1111-111111111111"},
                        "load_zone": {"value": "22222222-2222-2222-2222-222222222222"},
                        "internal": {
                            "uuid": {"value": "44444444-4444-4444-4444-444444444444"},
                            "ext": None,
                            "units_info": None,
                        },
                        "ext": {},
                    },
                ],
                "supplemental_attribute_associations": [],
                "supplemental_attributes": [],
            },
            "data_information": {
                "name": "test_system",
                "description": "Test system with invalid ACBus",
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "test_system.json"
            with open(json_path, "w") as f:
                json.dump(system_data, f)

            config = SiennaConfig(
                json_path=str(json_path),
                model_year=2029,
                system_name="test",
                skip_validation=False,
            )
            store = DataStore.from_data_files([], path=json_path.parent)
            ctx = PluginContext(config, store=store)
            parser = SiennaParser.from_context(ctx)
            parser.on_prepare()
            parser.on_upgrade()

            system = System(name="test")
            parser._ctx.system = system

            # With the fix, this should raise ValueError with a clear message
            # instead of the cryptic AssertionError
            with pytest.raises(ValueError, match="Failed to deserialize.*Bus2_Invalid"):
                parser._parse_components()
