import json

import pytest
from r2x_core import DataStore, PluginContext

from r2x_sienna import (
    SiennaConfig,
    SiennaExporter,
    SiennaParser,
)
from r2x_sienna.models import (
    ACBus,
    MinMax,
    PrimeMoversType,
    ThermalFuels,
    ThermalGenerationCost,
    ThermalStandard,
    Transformer2W,
)
from r2x_sienna.serialization import serialize_component_to_psy, serialize_value


@pytest.fixture
def data_store():
    """Create a DataStore instance for tests."""
    return DataStore()


@pytest.fixture
def sienna_config_rts(data_folder):
    """Configuration for RTS GMLC test case."""
    return SiennaConfig(
        model_year=2010,
        system_name="RTS GMLC Test System",
        scenario="test_scenario",
        system_base_power=100.0,
        skip_validation=False,
        json_path=str(data_folder / "case_rts_gmlc" / "rts_gmlc_da_sys.json"),
    )


@pytest.fixture
def sienna_config_pjm(data_folder):
    """Configuration for PJM 5-bus test case."""
    return SiennaConfig(
        model_year=2010,
        system_name="PJM 5-Bus Test System",
        scenario="test_scenario",
        system_base_power=100.0,
        skip_validation=False,
        json_path=str(data_folder / "case5_pjm_rt" / "c_sys5_pjm_rt.json"),
    )


@pytest.fixture
def rts_system(sienna_config_rts, data_store):
    """Load RTS GMLC system from test data."""
    ctx = PluginContext(
        config=sienna_config_rts,
        store=data_store,
        skip_validation=sienna_config_rts.skip_validation,
    )
    parser = SiennaParser.from_context(ctx)
    result_ctx = parser.run()
    return result_ctx.system


@pytest.fixture
def pjm_system(sienna_config_pjm, data_store):
    """Load PJM 5-bus system from test data."""
    ctx = PluginContext(
        config=sienna_config_pjm,
        store=data_store,
        skip_validation=sienna_config_pjm.skip_validation,
    )
    parser = SiennaParser.from_context(ctx)
    result_ctx = parser.run()
    return result_ctx.system


@pytest.fixture
def simple_test_system():
    """Create a minimal test system for basic functionality tests."""
    from infrasys import System

    system = System()
    system.name = "simple_test_system"

    bus = ACBus(name="test_bus", number=1)
    system.add_component(bus)

    gen = ThermalStandard(
        name="thermal-standard-test",
        must_run=False,
        bus=bus,
        status=False,
        base_power=100.0,
        rating=200.0,
        active_power=0.0,
        reactive_power=0.0,
        active_power_limits=MinMax(min=0, max=1),
        prime_mover_type=PrimeMoversType.CC,
        fuel=ThermalFuels.NATURAL_GAS,
        operation_cost=ThermalGenerationCost.example(),
        time_at_status=1_000,
    )
    system.add_component(gen)

    return system


@pytest.fixture
def single_bus_system_with_geoinfo():
    """Create a minimal system with one bus (GeographicInfo SA), one generator (GeometricDistributionForcedOutage SA),
    and one transformer (ImpedanceCorrectionData SA)."""
    from infrasys import System
    from r2x_sienna.models import (
        ACBus,
        Arc,
        Area,
        LoadZone,
        GeographicInfo,
        GeometricDistributionForcedOutage,
        ImpedanceCorrectionData,
        Transformer2W,
    )
    from r2x_sienna.models.named_tuples import Complex, MinMax
    from r2x_sienna.models.enums import ACBusTypes
    from infrasys.base_quantity import ureg

    system = System()
    system.name = "single_bus_geo_system"
    area = Area(name="TestArea")
    load_zone = LoadZone(name="TestLoadZone")
    system.add_component(area)
    system.add_component(load_zone)

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
    system.add_component(bus)

    bus2 = ACBus(
        name="Bus2",
        number=2,
        bustype=ACBusTypes.PQ,
        base_voltage=138 * ureg.kV,
        area=area,
        load_zone=load_zone,
        magnitude=1.0,
        angle=0.0,
        voltage_limits=MinMax(min=0.95, max=1.05),
    )
    system.add_component(bus2)

    geo = GeographicInfo.example()
    geo.geo_json.coordinates = [1.0, 2.0]
    system.add_supplemental_attribute(bus, geo)

    gen = ThermalStandard(
        name="TestGen",
        must_run=False,
        bus=bus,
        status=False,
        base_power=100.0,
        rating=200.0,
        active_power=0.0,
        reactive_power=0.0,
        active_power_limits=MinMax(min=0, max=1),
        prime_mover_type=PrimeMoversType.CC,
        fuel=ThermalFuels.NATURAL_GAS,
        operation_cost=ThermalGenerationCost.example(),
        time_at_status=1_000,
    )
    system.add_component(gen)

    outage = GeometricDistributionForcedOutage.example()
    system.add_supplemental_attribute(gen, outage)

    arc1 = Arc(from_to=bus, to_from=bus2)
    system.add_component(arc1)
    transformer = Transformer2W(
        name="tr2w-bus1-bus2",
        rating=100,
        arc=arc1,
        active_power_flow=100,
        reactive_power_flow=100,
        primary_shunt=Complex(real=0.0, imag=0.0),
    )
    system.add_component(transformer)

    impedance = ImpedanceCorrectionData.example()
    system.add_supplemental_attribute(transformer, impedance)

    return system, bus.name, [1.0, 2.0], gen.name, outage, transformer.name, impedance


def test_supplemental_attributes_roundtrip(single_bus_system_with_geoinfo, tmp_path):
    """Ensure GeographicInfo, GeometricDistributionForcedOutage, and ImpedanceCorrectionData
    supplemental attributes are preserved after export + parse."""
    from r2x_sienna.models import GeographicInfo, GeometricDistributionForcedOutage, ImpedanceCorrectionData

    system, bus_name, expected_coords, gen_name, expected_outage, transformer_name, expected_impedance = (
        single_bus_system_with_geoinfo
    )

    output_file = tmp_path / "single_bus_geo.json"

    export_cfg = SiennaConfig(
        model_year=2010,
        system_name="single_bus_geo_system",
        scenario="test",
        system_base_power=100.0,
        skip_validation=False,
        output_path=str(output_file),
    )
    export_ctx = PluginContext(config=export_cfg, system=system, store=DataStore(path=tmp_path))
    exporter = SiennaExporter.from_context(export_ctx)
    exporter.should_export_time_series = False
    _ = exporter.run()

    assert output_file.exists()
    assert output_file.stat().st_size > 0

    parse_cfg = SiennaConfig(
        model_year=2010,
        system_name="single_bus_geo_system",
        scenario="test",
        system_base_power=100.0,
        skip_validation=False,
        json_path=str(output_file),
    )
    parse_ctx = PluginContext(config=parse_cfg, store=DataStore(path=tmp_path), skip_validation=False)
    parser = SiennaParser.from_context(parse_ctx)
    parsed_system = parser.run().system

    # Verify Bus GeographicInfo attribute
    parsed_bus = next(
        c
        for c in parsed_system._component_mgr.iter_all()
        if isinstance(c, ACBus) and getattr(c, "name", None) == bus_name
    )
    assert parsed_system.has_supplemental_attribute(parsed_bus)
    assert parsed_system.has_supplemental_attribute(parsed_bus, supplemental_attribute_type=GeographicInfo)
    bus_attrs = parsed_system.get_supplemental_attributes_with_component(parsed_bus)
    assert len(bus_attrs) >= 1
    assert any(a.geo_json.coordinates == expected_coords for a in bus_attrs)

    # Verify Generator GeometricDistributionForcedOutage attribute
    parsed_gen = next(
        c
        for c in parsed_system._component_mgr.iter_all()
        if isinstance(c, ThermalStandard) and getattr(c, "name", None) == gen_name
    )
    assert parsed_system.has_supplemental_attribute(parsed_gen)
    assert parsed_system.has_supplemental_attribute(
        parsed_gen, supplemental_attribute_type=GeometricDistributionForcedOutage
    )
    gen_attrs = parsed_system.get_supplemental_attributes_with_component(parsed_gen)
    outage_attrs = [a for a in gen_attrs if isinstance(a, GeometricDistributionForcedOutage)]
    assert len(outage_attrs) >= 1
    parsed_outage = outage_attrs[0]
    assert parsed_outage.mean_time_to_recovery == expected_outage.mean_time_to_recovery
    assert parsed_outage.outage_transition_probability == expected_outage.outage_transition_probability

    # Verify Transformer ImpedanceCorrectionData attribute
    parsed_transformer = next(
        c
        for c in parsed_system._component_mgr.iter_all()
        if isinstance(c, Transformer2W) and getattr(c, "name", None) == transformer_name
    )
    assert parsed_system.has_supplemental_attribute(parsed_transformer)
    assert parsed_system.has_supplemental_attribute(
        parsed_transformer, supplemental_attribute_type=ImpedanceCorrectionData
    )
    transformer_attrs = parsed_system.get_supplemental_attributes_with_component(parsed_transformer)
    impedance_attrs = [a for a in transformer_attrs if isinstance(a, ImpedanceCorrectionData)]
    assert len(impedance_attrs) >= 1
    parsed_impedance = impedance_attrs[0]
    assert parsed_impedance.table_number == expected_impedance.table_number
    assert parsed_impedance.transformer_winding == expected_impedance.transformer_winding
    assert parsed_impedance.transformer_control_mode == expected_impedance.transformer_control_mode
    assert (
        parsed_impedance.impedance_correction_curve.points
        == expected_impedance.impedance_correction_curve.points
    )


def test_serialize_component_to_psy_rts(rts_system):
    """Test that RTS components can be serialized to PSY format."""
    components = list(rts_system._component_mgr.iter_all())
    assert len(components) > 0, "RTS system should have components"

    component = components[0]
    serialized = serialize_component_to_psy(component)
    assert serialized is not None
    assert "__metadata__" in serialized
    assert "internal" in serialized


def test_serialize_component_to_psy_pjm(pjm_system):
    """Test that PJM components can be serialized to PSY format."""
    components = list(pjm_system._component_mgr.iter_all())
    assert len(components) > 0, "PJM system should have components"

    component = components[0]
    serialized = serialize_component_to_psy(component)
    assert serialized is not None
    assert "__metadata__" in serialized
    assert "internal" in serialized


def test_get_component_output_fields():
    """Test that component output fields can be retrieved."""
    fields = set(ThermalStandard.model_fields.keys())
    assert isinstance(fields, set)
    assert len(fields) > 0


def test_to_psy_serialization_rts(sienna_config_rts, rts_system, tmp_path):
    """Test full PSY serialization with RTS system."""
    output_file = tmp_path / "rts_system.json"

    # Update config with output path
    config = SiennaConfig(**{**sienna_config_rts.model_dump(), "output_path": str(output_file)})

    ctx = PluginContext(config=config, system=rts_system)
    exporter = SiennaExporter.from_context(ctx)
    _ = exporter.run()

    assert output_file.exists()

    with open(output_file, "rb") as f:
        data = json.load(f)

    assert "data" in data
    assert "components" in data["data"]
    assert isinstance(data["data"]["components"], list)
    assert len(data["data"]["components"]) > 0, "Should have serialized components"

    h5_file = output_file.parent / f"{output_file.stem}_time_series_storage.h5"
    if h5_file.exists():
        file_size = h5_file.stat().st_size / (1024 * 1024)
        print(f"Time series data exported to {h5_file} ({file_size:.2f} MB)")


def test_to_psy_serialization_pjm(sienna_config_pjm, pjm_system, tmp_path):
    """Test full PSY serialization with PJM system."""
    output_file = tmp_path / "pjm_system.json"

    # Update config with output path
    config = SiennaConfig(**{**sienna_config_pjm.model_dump(), "output_path": str(output_file)})

    ctx = PluginContext(config=config, system=pjm_system)
    exporter = SiennaExporter.from_context(ctx)
    _ = exporter.run()

    assert output_file.exists()

    with open(output_file, "rb") as f:
        data = json.load(f)

    assert "data" in data
    assert "components" in data["data"]
    assert isinstance(data["data"]["components"], list)
    assert len(data["data"]["components"]) > 0, "Should have serialized components"

    h5_file = output_file.parent / f"{output_file.stem}_time_series_storage.h5"
    if h5_file.exists():
        file_size = h5_file.stat().st_size / (1024 * 1024)
        print(f"Time series data exported to {h5_file} ({file_size:.2f} MB)")


def test_to_psy_serialization_simple(simple_test_system, tmp_path):
    """Test PSY serialization with simple mock system to avoid time series issues."""

    output_file = tmp_path / "simple_system.json"

    config = SiennaConfig(
        model_year=2010,
        system_name="Simple Test System",
        scenario="test",
        system_base_power=100.0,
        skip_validation=False,
        output_path=str(output_file),
    )

    ctx = PluginContext(config=config, system=simple_test_system)
    exporter = SiennaExporter.from_context(ctx)
    exporter.should_export_time_series = False

    # Set system_data for export
    exporter.system_data = {
        "system_information": {
            "internal": {
                "uuid": {"value": "test-uuid"},
                "ext": {},
                "units_info": None,
            },
            "name": "Simple Test System",
            "description": "Simple test system for PSY serialization",
        },
        "data_information": {"version": "1.0", "base_power": 100.0},
    }

    _ = exporter.run()

    assert output_file.exists()

    with open(output_file, "rb") as f:
        data = json.load(f)

    assert "data" in data
    assert "components" in data["data"]
    assert isinstance(data["data"]["components"], list)


def test_psy_serialization_with_quantity():
    """Test PSY serialization with Quantity objects."""

    component = ThermalStandard(
        name="thermal-standard-test",
        must_run=False,
        bus=ACBus.example(),
        status=False,
        base_power=100.0,
        rating=200.0,
        active_power=0.0,
        reactive_power=0.0,
        active_power_limits=MinMax(min=0, max=1),
        prime_mover_type=PrimeMoversType.CC,
        fuel=ThermalFuels.NATURAL_GAS,
        operation_cost=ThermalGenerationCost.example(),
        time_at_status=1_000,
    )

    result = serialize_value(component.rating, "rating")
    assert result is not None


def test_psy_serialization_with_minmax():
    """Test PSY serialization with MinMax objects."""
    from r2x_sienna.models import MinMax

    limits = MinMax(min=10.0, max=100.0)
    component = ThermalStandard(
        name="thermal-standard-test",
        must_run=False,
        bus=ACBus.example(),
        status=False,
        base_power=100,
        rating=1,
        active_power=0.0,
        reactive_power=0.0,
        active_power_limits=limits,
        prime_mover_type=PrimeMoversType.CC,
        fuel=ThermalFuels.NATURAL_GAS,
        operation_cost=ThermalGenerationCost.example(),
        time_at_status=1_000,
    )

    result = serialize_value(component.active_power_limits, "active_power_limits")
    assert result == {"min": 10.0, "max": 100.0}


def test_psy_serialization_with_operational_cost():
    """Test PSY serialization with operational cost objects."""
    from infrasys.cost_curves import FuelCurve, UnitSystem
    from infrasys.value_curves import LinearCurve

    cost = ThermalGenerationCost(
        variable=FuelCurve(
            value_curve=LinearCurve(10.0, 12),
            vom_cost=LinearCurve(10.0),
            fuel_cost=0.05,
            power_units=UnitSystem.NATURAL_UNITS,
        )
    )

    component = ThermalStandard(
        name="test_gen",
        must_run=False,
        bus=ACBus.example(),
        status=False,
        base_power=100,
        rating=1,
        active_power=0.0,
        reactive_power=0.0,
        active_power_limits=MinMax(min=0, max=1),
        prime_mover_type=PrimeMoversType.CC,
        fuel=ThermalFuels.NATURAL_GAS,
        operation_cost=cost,
        time_at_status=1_000,
    )

    result = serialize_value(component.operation_cost, "operation_cost")
    assert result is not None
    assert isinstance(result, dict)
    assert "__metadata__" in result


def test_psy_serialization_none_value():
    """Test that PSY serialization returns string values as-is."""
    component = ThermalStandard(
        name="test-gen",
        must_run=False,
        bus=ACBus.example(),
        status=False,
        base_power=100,
        rating=1,
        active_power=0.0,
        reactive_power=0.0,
        active_power_limits=MinMax(min=0, max=1),
        prime_mover_type=PrimeMoversType.CC,
        fuel=ThermalFuels.NATURAL_GAS,
        operation_cost=ThermalGenerationCost.example(),
        time_at_status=1_000,
    )

    result = serialize_value(component.name, "name")
    assert result == "test-gen"


def test_system_data_structure():
    """Test that the system data structure is properly formatted."""
    system_data = {
        "system_information": {"name": "Test System", "description": "Test description"},
        "data_information": {"version": "1.0", "base_power": 100.0, "components": []},
    }

    assert "system_information" in system_data
    assert "data_information" in system_data
    assert isinstance(system_data["system_information"], dict)
    assert isinstance(system_data["data_information"], dict)


def test_rts_system_properties(rts_system):
    """Test that RTS system loads correctly and has expected properties."""
    assert rts_system is not None
    assert rts_system.name is not None

    components = list(rts_system._component_mgr.iter_all())
    assert len(components) > 0

    assert hasattr(rts_system, "_time_series_mgr")


def test_pjm_system_properties(pjm_system):
    """Test that PJM system loads correctly and has expected properties."""
    assert pjm_system is not None
    assert pjm_system.name is not None

    components = list(pjm_system._component_mgr.iter_all())
    assert len(components) > 0

    assert hasattr(pjm_system, "_time_series_mgr")


def test_rts_time_series_files_exist(data_folder):
    """Test that RTS time series files exist."""
    rts_path = data_folder / "case_rts_gmlc"
    json_file = rts_path / "rts_gmlc_da_sys.json"
    h5_file = rts_path / "rts_gmlc_da_sys_time_series_storage.h5"

    assert json_file.exists(), f"RTS JSON file not found: {json_file}"
    assert h5_file.exists(), f"RTS H5 file not found: {h5_file}"


def test_pjm_time_series_files_exist(data_folder):
    """Test that PJM time series files exist."""
    pjm_path = data_folder / "case5_pjm_rt"
    json_file = pjm_path / "c_sys5_pjm_rt.json"
    h5_file = pjm_path / "c_sys5_pjm_rt_time_series_storage.h5"

    assert json_file.exists(), f"PJM JSON file not found: {json_file}"
    assert h5_file.exists(), f"PJM H5 file not found: {h5_file}"
