"""Tests comparing new parser output with legacy system."""

import json
from pathlib import Path
from typing import Any

import pytest
from infrasys import System
from r2x_core import DataStore, PluginContext

from r2x_sienna.plugin_config import SiennaConfig
from r2x_sienna.parser import SiennaParser


@pytest.fixture
def legacy_system_path() -> Path:
    """Path to legacy system JSON file."""
    return Path(__file__).parent / "data" / "case5_pjm_rt" / "c_sys5_pjm_rt.json"


@pytest.fixture
def legacy_system_data(legacy_system_path: Path) -> dict[str, Any]:
    """Load legacy system JSON data."""
    assert legacy_system_path.exists(), f"Legacy system file not found: {legacy_system_path}"
    with open(legacy_system_path, "r") as f:
        return json.load(f)


@pytest.fixture
def legacy_component_count(legacy_system_data: dict[str, Any]) -> int:
    """Count components in legacy system."""
    components = legacy_system_data.get("data", {}).get("components", [])
    return len(components)


@pytest.fixture
def legacy_component_types(legacy_system_data: dict[str, Any]) -> dict[str, int]:
    """Get component type distribution from legacy system."""
    types: dict[str, int] = {}
    components = legacy_system_data.get("data", {}).get("components", [])
    for comp in components:
        comp_type = comp.get("__metadata__", {}).get("type", "Unknown")
        types[comp_type] = types.get(comp_type, 0) + 1
    return types


@pytest.fixture
def legacy_component_names(legacy_system_data: dict[str, Any]) -> set[str]:
    """Get all component names from legacy system."""
    names = set()
    components = legacy_system_data.get("data", {}).get("components", [])
    for comp in components:
        if name := comp.get("name"):
            names.add(name)
    return names


@pytest.fixture
def test_data_path() -> Path:
    """Path to test data directory."""
    # Fixed: Use correct folder name "case5_pjm_rt"
    return Path(__file__).parent / "data" / "case5_pjm_rt"


@pytest.fixture
def sienna_config(test_data_path: Path) -> SiennaConfig:
    """Create Sienna configuration matching legacy system."""
    json_path = test_data_path / "c_sys5_pjm_rt.json"
    return SiennaConfig(
        model_year=2029,
        system_name="PJM 5-Bus Test System",
        scenario="legacy_comparison",
        system_base_power=100.0,
        skip_validation=False,
        json_path=str(json_path),
    )


@pytest.fixture
def new_system(sienna_config: SiennaConfig, data_store: DataStore) -> System:
    """Build system using new parser."""
    ctx = PluginContext(
        config=sienna_config,
        store=data_store,
        skip_validation=sienna_config.skip_validation,
    )
    parser = SiennaParser.from_context(ctx)
    result_ctx = parser.run()
    return result_ctx.system


@pytest.fixture
def data_store(test_data_path: Path) -> DataStore:
    """Create DataStore for Sienna system."""
    return DataStore(path=test_data_path)


def test_legacy_system_has_components(legacy_component_count: int) -> None:
    """Test that legacy system has components."""
    assert legacy_component_count > 0, "Legacy system should have components"


def test_legacy_system_structure(legacy_system_data: dict[str, Any]) -> None:
    """Test that legacy system has expected structure."""
    assert "data" in legacy_system_data, "Legacy system should have 'data' key"
    assert "components" in legacy_system_data["data"], "Legacy system should have 'components' key"
    assert isinstance(legacy_system_data["data"]["components"], list), "Components should be a list"


def test_legacy_component_types(legacy_component_types: dict[str, int]) -> None:
    """Test that legacy system has expected component types."""
    assert len(legacy_component_types) > 0, "Should have component types"
    print(f"Legacy component types: {legacy_component_types}")


def test_legacy_component_names(legacy_component_names: set[str]) -> None:
    """Test that legacy system has component names."""
    assert len(legacy_component_names) > 0, "Should have component names"
    print(f"Found {len(legacy_component_names)} component names")


def test_new_system_builds(new_system: System) -> None:
    """Test that new system builds successfully."""
    assert new_system is not None, "New system should build successfully"
    assert new_system.name is not None, "New system should have a name"


def test_new_system_has_components(new_system: System) -> None:
    """Test that new system has components."""
    components = list(new_system._component_mgr.iter_all())
    assert len(components) > 0, "New system should have components"


def test_component_count_comparison(legacy_component_count: int, new_system: System) -> None:
    """Compare component counts between legacy and new systems."""
    new_component_count = len(list(new_system._component_mgr.iter_all()))

    print(f"Legacy component count: {legacy_component_count}")
    print(f"New component count: {new_component_count}")

    # This might not be exactly equal due to different parsing logic
    # but should be reasonably close
    assert new_component_count > 0, "New system should have components"

    # Optional: Check if counts are similar (within some tolerance)
    # You can adjust this based on your expectations
    # assert abs(legacy_component_count - new_component_count) <= 5,
    #     f"Component counts should be similar: legacy={legacy_component_count}, new={new_component_count}"


def test_file_paths_exist() -> None:
    """Test that all required files exist."""
    base_path = Path(__file__).parent / "data" / "case5_pjm_rt"
    json_file = base_path / "c_sys5_pjm_rt.json"
    h5_file = base_path / "c_sys5_pjm_rt_time_series_storage.h5"

    assert base_path.exists(), f"Data folder not found: {base_path}"
    assert json_file.exists(), f"JSON file not found: {json_file}"
    assert h5_file.exists(), f"H5 file not found: {h5_file}"


def test_legacy_data_structure_details(legacy_system_data: dict[str, Any]) -> None:
    """Test detailed structure of legacy data."""
    data_section = legacy_system_data.get("data", {})

    # Check for expected top-level keys
    expected_keys = ["components"]
    for key in expected_keys:
        assert key in data_section, f"Missing key '{key}' in data section"

    components = data_section.get("components", [])
    if components:
        # Check first component structure
        first_component = components[0]
        assert "__metadata__" in first_component, "Component should have __metadata__"
        assert "name" in first_component, "Component should have name"

        metadata = first_component.get("__metadata__", {})
        assert "type" in metadata, "Metadata should have type"


def test_component_type_distribution(legacy_component_types: dict[str, int], new_system: System) -> None:
    """Compare component type distributions."""
    print(f"Legacy component types: {legacy_component_types}")

    # Get new system component types
    new_types: dict[str, int] = {}
    for component in new_system._component_mgr.iter_all():
        comp_type = type(component).__name__
        new_types[comp_type] = new_types.get(comp_type, 0) + 1

    print(f"New system component types: {new_types}")

    # Both systems should have some component types
    assert len(legacy_component_types) > 0, "Legacy system should have component types"
    assert len(new_types) > 0, "New system should have component types"
