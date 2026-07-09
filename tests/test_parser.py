"""Basic Sienna parser tests using r2x-core Plugin API.

These tests verify basic parser instantiation and configuration using
a minimal test data set.
"""

from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from r2x_core import DataStore, PluginContext

from r2x_sienna.models import Source
from r2x_sienna.plugin_config import SiennaConfig
from r2x_sienna.parser import SiennaParser


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


def _write_minimal_json(tmpdir: str, components: list) -> "Path":
    """Write a minimal Sienna-format JSON file to *tmpdir* and return its path."""
    import json
    from pathlib import Path

    data = {
        "data_format_version": "3.0.0",
        "data": {
            "components": components,
            "supplemental_attribute_associations": [],
            "supplemental_attributes": [],
        },
    }
    p = Path(tmpdir) / "system.json"
    p.write_text(json.dumps(data))
    return p


def _make_parser(json_path: "Path") -> "tuple[SiennaParser, Any]":
    """Return a (parser, system) pair wired to *json_path*."""
    from r2x_core import DataStore, PluginContext, System

    config = SiennaConfig(json_path=str(json_path), model_year=2029, system_name="test")
    store = DataStore.from_data_files([], path=json_path.parent)
    ctx = PluginContext(config, store=store)
    parser = SiennaParser.from_context(ctx)
    parser.on_prepare()
    parser.on_upgrade()
    system = System(name="test")
    parser._ctx.system = system
    return parser, system


def test_all_components_deserialized_in_first_pass():
    """When every component has no composed-ref deps, the nested pass is skipped.

    Covers parser.py: the ``else`` branch (line ~374) of the ``if skipped_types``
    guard inside ``_deserialize_components``.
    """
    import tempfile

    components = [
        {
            "__metadata__": {"module": "PowerSystems", "type": "Area"},
            "name": "A1",
            "internal": {
                "uuid": {"value": "a1a1a1a1-0000-0000-0000-000000000001"},
                "ext": None,
                "units_info": None,
            },
            "peak_active_power": 10.0,
            "peak_reactive_power": 5.0,
            "load_response": 0.0,
        },
        {
            "__metadata__": {"module": "PowerSystems", "type": "LoadZone"},
            "name": "Z1",
            "internal": {
                "uuid": {"value": "a1a1a1a1-0000-0000-0000-000000000002"},
                "ext": None,
                "units_info": None,
            },
            "peak_active_power": 10.0,
            "peak_reactive_power": 5.0,
        },
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = _write_minimal_json(tmpdir, components)
        parser, system = _make_parser(json_path)
        parser._parse_components()  # must not raise — all resolved in first pass

    assert sum(1 for _ in system._component_mgr.iter_all()) == 2


def test_unknown_type_is_permanent_failure():
    """A component whose type does not exist in r2x_sienna.models is permanently failed.

    Covers parser.py:
    - The ``_PERM_FAILURE`` branch inside ``_deserialize_components_first_pass``
      (lines ~387-393).
    - The "Cannot resolve type" warning + ``return _PERM_FAILURE`` inside
      ``_try_deserialize_component`` (lines ~578-584).
    """
    import tempfile

    components = [
        # Area — valid, no deps, succeeds in first pass.
        {
            "__metadata__": {"module": "PowerSystems", "type": "Area"},
            "name": "A1",
            "internal": {
                "uuid": {"value": "b2b2b2b2-0000-0000-0000-000000000001"},
                "ext": None,
                "units_info": None,
            },
            "peak_active_power": 10.0,
            "peak_reactive_power": 5.0,
            "load_response": 0.0,
        },
        # Unknown type — triggers "Cannot resolve type" → _PERM_FAILURE in first pass.
        {
            "__metadata__": {"module": "PowerSystems", "type": "NonExistentPSYType"},
            "name": "ghost",
            "internal": {
                "uuid": {"value": "b2b2b2b2-0000-0000-0000-000000000002"},
                "ext": None,
                "units_info": None,
            },
        },
        # ACBus referencing Area — deferred in first pass, triggers the nested loop
        # so that perm_failed_components is checked and the ValueError is raised.
        {
            "__metadata__": {"module": "PowerSystems", "type": "ACBus"},
            "name": "Bus1",
            "number": 1,
            "bustype": "PQ",
            "angle": 0.0,
            "magnitude": 1.0,
            "base_voltage": 230.0,
            "available": True,
            "area": {"value": "b2b2b2b2-0000-0000-0000-000000000001"},
            "internal": {
                "uuid": {"value": "b2b2b2b2-0000-0000-0000-000000000003"},
                "ext": None,
                "units_info": None,
            },
            "ext": {},
        },
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = _write_minimal_json(tmpdir, components)
        parser, system = _make_parser(json_path)

        with pytest.raises(ValueError, match="Failed to deserialize.*ghost"):
            parser._parse_components()


class TestDeserializeComponentsNested:
    """Tests for _deserialize_components_nested assertion bug.

    The bug: When one component of a type deserializes successfully,
    the code assumes all other components of the same type will too.
    This is wrong because validation can fail for individual components.

    See: parser.py line 314 - `assert component is not None`
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
        #    - Second ACBus: invalid angle (outside -π/2 to π/2)
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
                skip_validation=True,  # Even with this, Pydantic still validates
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
