import uuid
from copy import deepcopy

import h5py
import pytest
from _pytest.logging import LogCaptureFixture
from loguru import logger

from r2x_sienna.models import HydroGenerationCost
from tests.models.pjm import pjm_2area

DATA_FOLDER = "tests/data"
OUTPUT_FOLDER = "r2x_output"
DEFAULT_INFRASYS = "pjm_2area"


@pytest.fixture
def data_folder(pytestconfig):
    return pytestconfig.rootpath.joinpath(DATA_FOLDER)


@pytest.fixture
def caplog(caplog: LogCaptureFixture):
    handler_id = logger.add(
        caplog.handler,
        format="{message}",
        level=0,
        filter=lambda record: record["level"].no >= caplog.handler.level,
        enqueue=False,
    )
    yield caplog
    logger.remove(handler_id)


@pytest.fixture(scope="function")
def h5_without_index_names(tmp_path):
    fpath = tmp_path / "h5_no_index.h5"
    with h5py.File(fpath, "w") as f:
        f.create_dataset("index_0", data=[0])
        f.create_dataset("index_1", data=[0])
        f.create_dataset("columns", data=[0])
        f.create_dataset("index_names", data=[0])
        f.create_dataset("data", data=[0])
    return fpath


@pytest.fixture
def hydro_energy_reservoir_component():
    return {
        "__metadata__": {"type": "HydroEnergyReservoir", "module": "PowerSystems"},
        "name": "Reservoir1",
        "available": True,
        "inflow": 10.0,
        "rating": 1.0,
        "base_power": 20.0,
        "initial_energy": 5.0,
        "storage_capacity": 100.0,
        "min_storage_capacity": 10.0,
        "storage_target": 80.0,
        "ramp_limits": {"up": 5.0, "down": 5.0},
        "time_limits": {"min_up": 1, "min_down": 1},
        "bus": {"value": "bus-id-1"},
        "operation_cost": HydroGenerationCost.example().model_dump(round_trip=True, mode="json"),
        "internal": {"uuid": {"value": str(uuid.uuid4())}},
    }


@pytest.fixture
def hydro_pumped_storage_component():
    return {
        "__metadata__": {"type": "HydroPumpedStorage", "module": "PowerSystems"},
        "name": "PumpedStorage1",
        "available": True,
        "inflow": 20.0,
        "outflow": 5.0,
        "rating": 100.0,
        "rating_pump": 80.0,
        "base_power": 50.0,
        "initial_energy": 500.0,
        "storage_capacity": {"up": 1000.0, "down": 0.0},
        "storage_target": {"up": 800.0, "down": 0.0},
        "initial_storage": {"up": 500.0, "down": 500.0},
        "pump_efficiency": 0.85,
        "ramp_limits": {"up": 10.0, "down": 10.0},
        "time_limits": {"min_up": 1, "min_down": 1},
        "ramp_limits_pump": {"up": 5.0, "down": 5.0},
        "time_limits_pump": {"min_up": 1, "min_down": 1},
        "bus": {"value": "bus-id-2"},
        "operation_cost": HydroGenerationCost.example().model_dump(round_trip=True, mode="json"),
        "conversion_factor": 1.0,
        "initial_volume": 500.0,
        "pump_load": 100.0,
        "internal": {"uuid": {"value": str(uuid.uuid4())}},
    }


@pytest.fixture
def old_system_data(hydro_energy_reservoir_component, hydro_pumped_storage_component):
    """Return a system data dict containing both HydroEnergyReservoir and HydroPumpedStorage."""
    return {
        "data": {
            "components": [
                deepcopy(hydro_energy_reservoir_component),
                deepcopy(hydro_pumped_storage_component),
            ]
        }
    }


@pytest.fixture
def infrasys_test_system():
    return pjm_2area()
