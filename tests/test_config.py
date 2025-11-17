"""Tests for Sienna configuration."""

import pytest

from r2x_sienna.config import SiennaConfig


def test_sienna_config_creation_single_year():
    """Test creating a Sienna config with single year parameter."""
    config = SiennaConfig(
        model_year=2030,
    )
    assert config.model_year == 2030
    assert config.primary_model_year == 2030
    assert config.system_name is None
    assert config.scenario == "base"


def test_sienna_config_creation_multiple_years():
    """Test creating a Sienna config with multiple years."""
    config = SiennaConfig(model_year=[2030, 2040, 2050], system_name="MultiYear", scenario="test_scenario")
    assert config.model_year == [2030, 2040, 2050]
    assert config.primary_model_year == 2030
    assert config.system_name == "MultiYear"
    assert config.scenario == "test_scenario"


def test_sienna_config_system_name():
    """Test system_name field."""
    config = SiennaConfig(
        model_year=2029,
        system_name="HighRenewable",
    )
    assert config.system_name == "HighRenewable"


def test_sienna_config_default_scenario():
    """Test default scenario."""
    config = SiennaConfig(
        model_year=2029,
    )
    assert config.scenario == "base"


def test_sienna_config_scenario_field():
    """Test scenario field."""
    config = SiennaConfig(
        model_year=2029,
        scenario="high_renewable",
    )
    assert config.scenario == "high_renewable"


def test_sienna_config_primary_model_year():
    """Test primary_model_year property returns first year."""
    config = SiennaConfig(
        model_year=[2029, 2035, 2040],
    )
    assert config.primary_model_year == 2029


def test_sienna_config_default_system_name():
    """Test default system_name."""
    config = SiennaConfig(
        model_year=2029,
    )
    assert config.system_name is None


def test_sienna_config_system_base_power():
    """Test system_base_power field."""
    config = SiennaConfig(model_year=2029, system_base_power=200.0)
    assert config.system_base_power == 200.0


def test_sienna_config_default_system_base_power():
    """Test default system_base_power."""
    config = SiennaConfig(
        model_year=2029,
    )
    assert config.system_base_power == 100.0


def test_sienna_config_load_defaults_file_not_found():
    """Test that load_defaults returns empty dict when file doesn't exist."""
    # The classmethod API returns an empty dict if defaults.json doesn't exist
    result = SiennaConfig.load_defaults(config_path="/nonexistent/path")
    assert result == {}


def test_sienna_config_with_defaults(tmp_path):
    """Test using custom defaults."""
    test_file = tmp_path / "defaults.json"
    test_file.write_text('{"excluded_techs": ["coal", "oil"]}')

    # Use classmethod with config_path (directory) not file
    defaults = SiennaConfig.load_defaults(config_path=tmp_path)
    assert defaults["excluded_techs"] == ["coal", "oil"]
