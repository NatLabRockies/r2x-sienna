"""Tests for HDF5 file parsing in Sienna."""

from pathlib import Path

import h5py
import pytest
from r2x_core.store import DataStore


@pytest.fixture
def h5_file_path() -> Path:
    """Path to test HDF5 file."""
    return Path(__file__).parent / "data" / "case5_pjm_rt" / "c_sys5_pjm_rt_time_series_storage.h5"


@pytest.fixture
def data_store(h5_file_path: Path) -> DataStore:
    """Create DataStore with HDF5 file."""
    return DataStore(path=h5_file_path.parent)


def test_h5_file_exists(h5_file_path: Path):
    """Test that the HDF5 file exists."""
    assert h5_file_path.exists(), f"File not found: {h5_file_path}"
    assert h5_file_path.suffix == ".h5"


def test_h5_file_can_be_opened(h5_file_path: Path):
    """Test that the HDF5 file can be opened and read."""
    with h5py.File(h5_file_path, "r") as h5file:
        assert isinstance(h5file, h5py.File)
        assert len(h5file.keys()) > 0


def test_h5_file_parsed_by_datastore(data_store: DataStore):
    """Test that DataStore can list and access HDF5 files."""
    h5_files = [f for f in data_store.folder.iterdir() if f.suffix == ".h5"]
    assert h5_files, "No HDF5 files found in data folder."


# Additional tests for both test cases
@pytest.fixture
def rts_h5_file_path() -> Path:
    """Path to RTS test HDF5 file."""
    return Path(__file__).parent / "data" / "case_rts_gmlc" / "rts_gmlc_da_sys_time_series_storage.h5"


@pytest.fixture
def rts_data_store(rts_h5_file_path: Path) -> DataStore:
    """Create DataStore with RTS HDF5 file."""
    return DataStore(path=rts_h5_file_path.parent)


def test_rts_h5_file_exists(rts_h5_file_path: Path):
    """Test that the RTS HDF5 file exists."""
    assert rts_h5_file_path.exists(), f"File not found: {rts_h5_file_path}"
    assert rts_h5_file_path.suffix == ".h5"


def test_rts_h5_file_can_be_opened(rts_h5_file_path: Path):
    """Test that the RTS HDF5 file can be opened and read."""
    with h5py.File(rts_h5_file_path, "r") as h5file:
        assert isinstance(h5file, h5py.File)
        assert len(h5file.keys()) > 0


def test_rts_h5_file_parsed_by_datastore(rts_data_store: DataStore):
    """Test that DataStore can list and access RTS HDF5 files."""
    h5_files = [f for f in rts_data_store.folder.iterdir() if f.suffix == ".h5"]
    assert h5_files, "No HDF5 files found in RTS data folder."


def test_both_data_folders_exist():
    """Test that both test data folders exist."""
    base_path = Path(__file__).parent / "data"

    rts_folder = base_path / "case_rts_gmlc"
    pjm_folder = base_path / "case5_pjm_rt"

    assert base_path.exists(), f"Data folder not found: {base_path}"
    assert rts_folder.exists(), f"RTS folder not found: {rts_folder}"
    assert pjm_folder.exists(), f"PJM folder not found: {pjm_folder}"


def test_all_required_files_exist():
    """Test that all required test files exist."""
    base_path = Path(__file__).parent / "data"

    # RTS files
    rts_json = base_path / "case_rts_gmlc" / "rts_gmlc_da_sys.json"
    rts_h5 = base_path / "case_rts_gmlc" / "rts_gmlc_da_sys_time_series_storage.h5"

    # PJM files
    pjm_json = base_path / "case5_pjm_rt" / "c_sys5_pjm_rt.json"
    pjm_h5 = base_path / "case5_pjm_rt" / "c_sys5_pjm_rt_time_series_storage.h5"

    assert rts_json.exists(), f"RTS JSON file not found: {rts_json}"
    assert rts_h5.exists(), f"RTS H5 file not found: {rts_h5}"
    assert pjm_json.exists(), f"PJM JSON file not found: {pjm_json}"
    assert pjm_h5.exists(), f"PJM H5 file not found: {pjm_h5}"
