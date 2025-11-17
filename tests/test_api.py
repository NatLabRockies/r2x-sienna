import pytest
from r2x_core.system import System
from r2x_sienna.models import Area, ACBus, ThermalStandard
from r2x_sienna.models.enums import PrimeMoversType, ThermalFuels
from r2x_sienna.models.named_tuples import MinMax
from r2x_sienna.models.costs import ThermalGenerationCost


@pytest.fixture(scope="class")
def empty_system():
    return System(name="TestSystem")


def test_system_instance(empty_system):
    assert isinstance(empty_system, System)


def test_add_single_component(empty_system):
    area = Area.example()
    empty_system.add_component(area)
    assert isinstance(empty_system.get_component(Area, area.name), Area)


def test_add_composed_component():
    system = System(name="TestComposed", auto_add_composed_components=True)

    bus = ACBus.example()
    generator = ThermalStandard(
        name="TestGen",
        must_run=False,
        bus=bus,
        status=False,
        base_power=100.0,
        rating=120.0,
        active_power=0.0,
        reactive_power=0.0,
        active_power_limits=MinMax(min=0, max=1),
        prime_mover_type=PrimeMoversType.CC,
        fuel=ThermalFuels.NATURAL_GAS,
        operation_cost=ThermalGenerationCost.example(),
        time_at_status=1_000,
    )
    system.add_component(generator)

    assert system.get_component(ThermalStandard, "TestGen") == generator
    assert system.get_component(ThermalStandard, "TestGen").bus == bus
