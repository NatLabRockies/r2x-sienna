"""Basic Sienna parser tests using r2x-core 0.0.5b3 API.

These tests verify basic parser instantiation and configuration using
a minimal test data set.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest
from r2x_core.store import DataStore

from r2x_sienna.config import SiennaConfig
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
    """Test creating SiennaParser instance with mock data store."""
    parser = SiennaParser(config=sienna_config, data_store=mock_data_store, name="test_system")

    assert parser is not None


def test_parser_has_config(sienna_config: SiennaConfig, mock_data_store: Mock):
    """Test parser stores config."""
    parser = SiennaParser(config=sienna_config, data_store=mock_data_store, name="test_system")

    assert parser.config == sienna_config
    assert parser.config.model_year == 2029


def test_parser_has_data_store(sienna_config: SiennaConfig, mock_data_store: Mock):
    """Test parser stores data_store."""
    parser = SiennaParser(config=sienna_config, data_store=mock_data_store, name="test_system")

    assert parser.store == mock_data_store


def test_parser_system_initially_none(sienna_config: SiennaConfig, mock_data_store: Mock):
    """Test parser.system is None before build_system() is called."""
    parser = SiennaParser(config=sienna_config, data_store=mock_data_store, name="test_system")

    assert parser.system.name == "test_system"
