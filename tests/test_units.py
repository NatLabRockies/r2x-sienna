"""Tests for per-unit functionality in Sienna components."""

import pytest

from r2x_core.units import set_unit_system, get_unit_system
from r2x_core.system import System
from r2x_sienna.models.branch import Transformer3W
from r2x_sienna.models.topology import ACBus, Area, LoadZone
from r2x_sienna.models.generators import ThermalStandard
from r2x_sienna.models.enums import ACBusTypes, ThermalFuels, PrimeMoversType
from r2x_sienna.models.named_tuples import MinMax, UpDown
from r2x_sienna.models.costs import ThermalGenerationCost
from r2x_sienna.units import ureg


class TestSiennaComponent:
    """Test the SiennaComponent base class using Sienna components."""

    def test_acbus_creation(self):
        """Test ACBus component creation."""
        area = Area(name="TestArea")
        load_zone = LoadZone(name="TestLoadZone")

        bus = ACBus(
            name="Bus1",
            number=1,
            bustype=ACBusTypes.PQ,
            base_voltage=138 * ureg.kV,
            area=area,
            load_zone=load_zone,
            magnitude=1.0,
            angle=0.0,
            voltage_limits=MinMax(min=0.95, max=1.05),
        )

        assert bus.name == "Bus1"
        assert bus.number == 1
        assert bus.bustype == ACBusTypes.PQ
        assert bus.magnitude == 1.0
        assert bus.angle == 0.0
        assert bus.area == area
        assert bus.load_zone == load_zone
        assert bus.available is True

    def test_zero_base_voltage_is_missing(self):
        bus = ACBus(name="zero_voltage_bus", number=1, base_voltage=0.0)

        assert bus.base_voltage is None

    def test_zero_transformer_base_voltages_are_missing(self):
        values = Transformer3W.example().model_dump()

        def remove_computed_fields(value):
            if isinstance(value, dict):
                value.pop("class_type", None)
                for nested_value in value.values():
                    remove_computed_fields(nested_value)
            elif isinstance(value, list):
                for nested_value in value:
                    remove_computed_fields(nested_value)

        remove_computed_fields(values)
        values.update(
            base_voltage_primary=0.0,
            base_voltage_secondary=0.0,
            base_voltage_tertiary=0.0,
        )

        transformer = Transformer3W.model_validate(values)

        assert transformer.base_voltage_primary is None
        assert transformer.base_voltage_secondary is None
        assert transformer.base_voltage_tertiary is None

    def test_thermal_generator_creation(self):
        """Test ThermalStandard generator creation."""
        area = Area(name="TestArea")
        load_zone = LoadZone(name="TestLoadZone")
        bus = ACBus(
            name="Bus1",
            number=1,
            bustype=ACBusTypes.PQ,
            base_voltage=138.0,
            area=area,
            load_zone=load_zone,
            magnitude=1.0,
        )

        gen = ThermalStandard(
            name="thermal-standard-1",
            must_run=False,
            bus=bus,
            status=False,
            base_power=100.0,
            rating=100.0,
            active_power=0.0,
            reactive_power=0.0,
            active_power_limits=MinMax(min=0.0, max=100.0),
            prime_mover_type=PrimeMoversType.CC,
            fuel=ThermalFuels.NATURAL_GAS,
            operation_cost=ThermalGenerationCost.example(),
            time_at_status=1000.0,
        )

        assert gen.name == "thermal-standard-1"
        assert gen.bus == bus
        assert gen.fuel == ThermalFuels.NATURAL_GAS
        assert gen.prime_mover_type == PrimeMoversType.CC
        assert gen.available is True

    def test_class_type_computed_field(self):
        """Test that class_type returns the correct class name."""
        area = Area(name="TestArea")
        load_zone = LoadZone(name="TestLoadZone")

        bus = ACBus(
            name="Bus1",
            number=1,
            bustype=ACBusTypes.PQ,
            base_voltage=138.0,
            area=area,
            load_zone=load_zone,
            magnitude=1.0,
        )

        gen = ThermalStandard(
            name="gen-1",
            must_run=False,
            bus=bus,
            status=False,
            base_power=100.0,
            rating=100.0,
            active_power=0.0,
            operation_cost=ThermalGenerationCost.example(),
            reactive_power=0.0,
            active_power_limits=MinMax(min=0.0, max=100.0),
            prime_mover_type=PrimeMoversType.CC,
            fuel=ThermalFuels.NATURAL_GAS,
            time_at_status=1000.0,
        )

        assert bus.class_type == "ACBus"
        assert gen.class_type == "ThermalStandard"
        assert area.class_type == "Area"
        assert load_zone.class_type == "LoadZone"

    def test_ext_field_with_quantities(self):
        """Test ext field with Pint Quantity objects."""
        area = Area(name="TestArea")
        load_zone = LoadZone(name="TestLoadZone")
        bus = ACBus(
            name="Bus1",
            number=1,
            bustype=ACBusTypes.PQ,
            base_voltage=138.0,
            area=area,
            load_zone=load_zone,
            magnitude=1.0,
        )

        gen = ThermalStandard(
            name="gen-x",
            must_run=False,
            bus=bus,
            status=False,
            base_power=100.0,
            rating=100.0,
            active_power=0.0,
            operation_cost=ThermalGenerationCost.example(),
            reactive_power=0.0,
            active_power_limits=MinMax(min=0.0, max=100.0),
            prime_mover_type=PrimeMoversType.CC,
            fuel=ThermalFuels.NATURAL_GAS,
            time_at_status=1000.0,
        )

        gen.ext["efficiency"] = 0.45 * ureg.dimensionless
        gen.ext["fuel_cost"] = 25.0 * ureg.usd / ureg.MWh
        gen.ext["string_data"] = "natural_gas"
        gen.ext["numeric_data"] = 42.0

        assert isinstance(gen.ext["efficiency"], ureg.Quantity)
        assert isinstance(gen.ext["fuel_cost"], ureg.Quantity)
        assert gen.ext["string_data"] == "natural_gas"
        assert gen.ext["numeric_data"] == 42.0

    def test_ext_serialization(self):
        """Test that ext field serializes Quantity objects correctly."""
        area = Area(name="TestArea")
        load_zone = LoadZone(name="TestLoadZone")
        bus = ACBus(
            name="Bus1",
            number=1,
            bustype=ACBusTypes.PQ,
            base_voltage=138.0,
            area=area,
            load_zone=load_zone,
            magnitude=1.0,
        )

        gen = ThermalStandard(
            name="Gen1",
            fuel=ThermalFuels.NATURAL_GAS,
            prime_mover_type=PrimeMoversType.CC,
            must_run=False,
            bus=bus,
            status=False,
            base_power=100.0,
            rating=100.0,
            active_power=0.0,
            reactive_power=0.0,
            active_power_limits=MinMax(min=0.0, max=100.0),
            operation_cost=ThermalGenerationCost.example(),
            time_at_status=1000.0,
        )

        gen.ext["efficiency"] = 0.45 * ureg.dimensionless
        gen.ext["fuel_cost"] = 25.0 * ureg.usd / ureg.MWh
        gen.ext["string_data"] = "natural_gas"

        # Test serialization
        serialized = gen.model_dump(mode="json")

        # Quantities should be converted to magnitudes
        assert serialized["ext"]["efficiency"] == 0.45
        assert serialized["ext"]["fuel_cost"] == 25.0
        assert serialized["ext"]["string_data"] == "natural_gas"

    def test_per_unit_system_integration(self):
        """Test that components work with r2x-core System."""
        # Create system with 100 MVA base
        system = System(name="TestSystem", system_base=100.0)

        # Create topology components
        area = Area(name="TestArea")
        load_zone = LoadZone(name="TestLoadZone")
        bus = ACBus(
            name="Bus1",
            number=1,
            bustype=ACBusTypes.PQ,
            base_voltage=138.0,
            area=area,
            load_zone=load_zone,
            magnitude=1.0,
        )

        gen = ThermalStandard(
            name="gen-7",
            must_run=False,
            bus=bus,
            status=False,
            base_power=100.0,
            rating=100.0,
            active_power=0.0,
            ramp_limits=UpDown(up=5.0, down=5.0),
            time_limits=UpDown(up=4.0, down=2.0),
            operation_cost=ThermalGenerationCost.example(),
            reactive_power=0.0,
            active_power_limits=MinMax(min=0.0, max=100.0),
            prime_mover_type=PrimeMoversType.CC,
            fuel=ThermalFuels.NATURAL_GAS,
            time_at_status=1000.0,
        )

        # Add components to system in correct order (dependencies first)
        system.add_component(area)
        system.add_component(load_zone)
        system.add_component(bus)
        system.add_component(gen)

        # Retrieve components from system
        retrieved_gen = system.get_component(ThermalStandard, "gen-7")
        retrieved_bus = system.get_component(ACBus, "Bus1")

        assert retrieved_gen.name == "gen-7"
        assert retrieved_bus.name == "Bus1"

        # Test that components are properly integrated with system
        components = list(system._component_mgr.iter_all())
        assert len(components) == 4  # area, load_zone, bus, gen

    def test_system_base_handling(self):
        """Test system base power handling."""
        # Create systems with different base powers
        system1 = System(name="System1", system_base=100.0)
        system2 = System(name="System2", system_base=200.0)

        area = Area(name="TestArea")
        load_zone = LoadZone(name="TestLoadZone")
        bus = ACBus(
            name="Bus1",
            number=1,
            bustype=ACBusTypes.PQ,
            base_voltage=138.0,
            area=area,
            load_zone=load_zone,
            magnitude=1.0,
        )

        gen = ThermalStandard(
            name="Gen1",
            fuel=ThermalFuels.NATURAL_GAS,
            prime_mover_type=PrimeMoversType.CC,
            must_run=False,
            bus=bus,
            status=False,
            base_power=100.0,
            rating=100.0,
            active_power=0.0,
            reactive_power=0.0,
            active_power_limits=MinMax(min=0.0, max=100.0),
            operation_cost=ThermalGenerationCost.example(),
            time_at_status=1000.0,
        )

        # Add to first system
        system1.add_component(area)
        system1.add_component(load_zone)
        system1.add_component(bus)
        system1.add_component(gen)

        # Test that system has the correct base power
        assert system1.base_power == 100.0
        assert system2.base_power == 200.0

        # Component should be retrievable from system
        retrieved_gen = system1.get_component(ThermalStandard, "Gen1")
        assert retrieved_gen.name == "Gen1"

    def test_multiple_component_types(self):
        """Test that different component types work correctly."""
        area = Area(name="TestArea")
        load_zone = LoadZone(name="TestLoadZone")
        bus = ACBus(
            name="Bus1",
            number=1,
            bustype=ACBusTypes.PQ,
            base_voltage=138.0,
            area=area,
            load_zone=load_zone,
            magnitude=1.0,
        )

        gen = ThermalStandard(
            name="gen-4",
            must_run=False,
            bus=bus,
            status=False,
            base_power=100.0,
            rating=100.0,
            active_power=0.0,
            ramp_limits=UpDown(up=5.0, down=5.0),
            time_limits=UpDown(up=4.0, down=2.0),
            operation_cost=ThermalGenerationCost.example(),
            reactive_power=0.0,
            active_power_limits=MinMax(min=0.0, max=100.0),
            prime_mover_type=PrimeMoversType.CC,
            fuel=ThermalFuels.NATURAL_GAS,
            time_at_status=1000.0,
        )

        system = System(name="TestSystem", system_base=100.0)
        system.add_component(area)
        system.add_component(load_zone)
        system.add_component(bus)
        system.add_component(gen)

        # Test that all components are in the system
        components = list(system._component_mgr.iter_all())
        assert len(components) == 4

        # Test that we can retrieve all components
        retrieved_area = system.get_component(Area, "TestArea")
        retrieved_load_zone = system.get_component(LoadZone, "TestLoadZone")
        retrieved_bus = system.get_component(ACBus, "Bus1")
        retrieved_gen = system.get_component(ThermalStandard, "gen-4")

        assert retrieved_area.name == "TestArea"
        assert retrieved_load_zone.name == "TestLoadZone"
        assert retrieved_bus.name == "Bus1"
        assert retrieved_gen.name == "gen-4"

        # Class types should be correct
        assert area.class_type == "Area"
        assert load_zone.class_type == "LoadZone"
        assert bus.class_type == "ACBus"
        assert gen.class_type == "ThermalStandard"

    def test_unit_specs_integration(self):
        """Test that UnitSpec integration works correctly if available."""
        area = Area(name="TestArea")
        load_zone = LoadZone(name="TestLoadZone")
        bus = ACBus(
            name="Bus1",
            number=1,
            bustype=ACBusTypes.PQ,
            base_voltage=138.0,
            area=area,
            load_zone=load_zone,
            magnitude=1.0,
        )

        gen = ThermalStandard(
            name="Gen1",
            fuel=ThermalFuels.NATURAL_GAS,
            prime_mover_type=PrimeMoversType.CC,
            must_run=False,
            bus=bus,
            status=False,
            base_power=100.0,
            rating=100.0,
            active_power=0.0,
            reactive_power=0.0,
            active_power_limits=MinMax(min=0.0, max=100.0),
            operation_cost=ThermalGenerationCost.example(),
            time_at_status=1000.0,
        )

        # Get unit specs map if method exists
        if hasattr(gen, "_get_unit_specs_map"):
            specs_map = gen._get_unit_specs_map()
            # Test that we can access unit specs
            assert isinstance(specs_map, dict)
        else:
            # Skip test if method doesn't exist
            pytest.skip("_get_unit_specs_map method not implemented")

    def test_repr_with_units(self):
        """Test that __repr__ shows component information correctly."""
        area = Area(name="TestArea")
        load_zone = LoadZone(name="TestLoadZone")
        bus = ACBus(
            name="Bus1",
            number=1,
            bustype=ACBusTypes.PQ,
            base_voltage=138.0,
            area=area,
            load_zone=load_zone,
            magnitude=1.0,
        )

        gen = ThermalStandard(
            name="Gen1",
            fuel=ThermalFuels.NATURAL_GAS,
            prime_mover_type=PrimeMoversType.CC,
            must_run=False,
            bus=bus,
            status=False,
            base_power=100.0,
            rating=100.0,
            active_power=0.0,
            reactive_power=0.0,
            active_power_limits=MinMax(min=0.0, max=100.0),
            operation_cost=ThermalGenerationCost.example(),
            time_at_status=1000.0,
        )

        # Get repr string
        repr_str = repr(gen)

        # Should contain the component name and some field values
        assert "ThermalStandard" in repr_str
        assert "name='Gen1'" in repr_str

    def test_json_serialization_roundtrip(self):
        """Test JSON serialization and deserialization."""
        area = Area(name="TestArea")
        load_zone = LoadZone(name="TestLoadZone")
        bus = ACBus(
            name="Bus1",
            number=1,
            bustype=ACBusTypes.PQ,
            base_voltage=138.0,
            area=area,
            load_zone=load_zone,
            magnitude=1.0,
        )

        gen = ThermalStandard(
            name="thermal-standard-ser-rt",
            must_run=False,
            bus=bus,
            status=False,
            base_power=100.0,
            rating=100.0,
            active_power=0.0,
            ramp_limits=UpDown(up=5.0, down=5.0),
            time_limits=UpDown(up=4.0, down=2.0),
            operation_cost=ThermalGenerationCost.example(),
            reactive_power=0.0,
            active_power_limits=MinMax(min=0.0, max=100.0),
            prime_mover_type=PrimeMoversType.CC,
            fuel=ThermalFuels.NATURAL_GAS,
            time_at_status=1000.0,
        )

        gen.ext["efficiency"] = 0.45 * ureg.dimensionless
        json_data = gen.model_dump(mode="json", exclude={"bus", "class_type"})
        json_data["operation_cost"] = ThermalGenerationCost.example().model_dump(
            mode="json", exclude={"class_type", "variable_type", "value_curve_type", "function_data_type"}
        )
        gen2 = ThermalStandard.model_validate(json_data)

        assert gen2.name == gen.name
        assert gen2.fuel == gen.fuel
        assert gen2.prime_mover_type == gen.prime_mover_type
        assert gen2.ext["efficiency"] == 0.45

    def test_component_uuid_uniqueness(self):
        """Test that components have unique UUIDs."""
        area = Area(name="TestArea")
        load_zone = LoadZone(name="TestLoadZone")
        bus1 = ACBus(
            name="Bus1",
            number=1,
            bustype=ACBusTypes.PQ,
            base_voltage=138.0,
            area=area,
            load_zone=load_zone,
            magnitude=1.0,
        )
        bus2 = ACBus(
            name="Bus2",
            number=2,
            bustype=ACBusTypes.PQ,
            base_voltage=138.0,
            area=area,
            load_zone=load_zone,
            magnitude=1.0,
        )

        gen1 = ThermalStandard(
            name="thermal-standard-example",
            must_run=False,
            bus=bus1,
            status=False,
            base_power=100.0,
            rating=100.0,
            active_power=0.0,
            ramp_limits=UpDown(up=10.0, down=10.0),
            time_limits=UpDown(up=4.0, down=2.0),
            operation_cost=ThermalGenerationCost.example(),
            reactive_power=0.0,
            active_power_limits=MinMax(min=0.0, max=100.0),
            prime_mover_type=PrimeMoversType.CC,
            fuel=ThermalFuels.NATURAL_GAS,
            time_at_status=1000.0,
        )
        gen2 = ThermalStandard(
            name="thermal-standard-2",
            must_run=False,
            bus=bus2,
            status=False,
            base_power=100.0,
            rating=100.0,
            active_power=0.0,
            ramp_limits=UpDown(up=5.0, down=5.0),
            time_limits=UpDown(up=4.0, down=2.0),
            operation_cost=ThermalGenerationCost.example(),
            reactive_power=0.0,
            active_power_limits=MinMax(min=0.0, max=100.0),
            prime_mover_type=PrimeMoversType.CC,
            fuel=ThermalFuels.NATURAL_GAS,
            time_at_status=1000.0,
        )

        assert gen1.uuid != gen2.uuid
        assert str(gen1.uuid) != str(gen2.uuid)

    def test_example_methods(self):
        """Test that example class methods work correctly."""
        bus_example = ACBus.example()
        assert isinstance(bus_example, ACBus)
        assert bus_example.name == "ExampleBus"

        gen_example = ThermalStandard.example()
        assert isinstance(gen_example, ThermalStandard)
        assert gen_example.name == "thermal-standard-test"

    def test_minimal_component_creation(self):
        """Test creating components with minimal required fields."""
        area = Area(name="MinimalArea")
        load_zone = LoadZone(name="MinimalLoadZone")

        bus = ACBus(
            name="MinimalBus",
            number=1,
            bustype=ACBusTypes.PQ,
            base_voltage=138.0,
            area=area,
            load_zone=load_zone,
        )

        assert bus.name == "MinimalBus"
        assert bus.available is True

        gen = ThermalStandard(
            name="minimal-thermal-standard",
            must_run=False,
            bus=bus,
            status=False,
            base_power=100.0,
            rating=100.0,
            active_power=0.0,
            ramp_limits=UpDown(up=5.0, down=5.0),
            time_limits=UpDown(up=4.0, down=2.0),
            operation_cost=ThermalGenerationCost.example(),
            reactive_power=0.0,
            active_power_limits=MinMax(min=0.0, max=100.0),
            prime_mover_type=PrimeMoversType.CC,
            fuel=ThermalFuels.NATURAL_GAS,
            time_at_status=1000.0,
        )

        assert gen.name == "minimal-thermal-standard"
        assert gen.fuel == ThermalFuels.NATURAL_GAS
        assert gen.available is True
        assert gen.ramp_limits.up * gen.base_power == 5.0
        assert gen.time_limits.up == 4.0

    @pytest.fixture(autouse=True)
    def reset_unit_system(self):
        """Reset unit system before each test."""
        original_system = get_unit_system()
        yield
        set_unit_system(original_system)
