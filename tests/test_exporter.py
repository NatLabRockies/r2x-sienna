import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from r2x_core import DataStore, PluginContext
from rust_ok import Err, Ok

import r2x_sienna.exporter as exporter_mod
from r2x_sienna import (
    SiennaConfig,
    SiennaExporter,
    SiennaParser,
)
from r2x_sienna.models import (
    ACBus,
    MinMax,
    PowerLoad,
    PrimeMoversType,
    RenewableDispatch,
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
    from infrasys.base_quantity import ureg

    from r2x_sienna.models import (
        ACBus,
        Arc,
        Area,
        GeographicInfo,
        GeometricDistributionForcedOutage,
        ImpedanceCorrectionData,
        LoadZone,
        Transformer2W,
    )
    from r2x_sienna.models.enums import ACBusTypes
    from r2x_sienna.models.named_tuples import Complex, MinMax

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


def test_set_time_series_scaling_factor_multiplier(infrasys_test_system):
    """Test assigning a PowerSystems scaling function to an existing time series."""
    solar = infrasys_test_system.get_component(RenewableDispatch, "PVBus5")
    load = next(iter(infrasys_test_system.get_components(PowerLoad)))
    connection = infrasys_test_system._time_series_mgr._metadata_store._con

    exporter_mod.set_time_series_scaling_factor_multiplier(
        infrasys_test_system,
        solar,
        "max_active_power",
        "get_max_active_power",
    )

    solar_scaling = connection.execute(
        """
        SELECT scaling_factor_multiplier
        FROM time_series_associations
        WHERE owner_uuid = ? AND name = 'max_active_power'
        """,
        (str(solar.uuid),),
    ).fetchone()[0]
    load_scaling = connection.execute(
        """
        SELECT scaling_factor_multiplier
        FROM time_series_associations
        WHERE owner_uuid = ? AND name = 'max_active_power'
        """,
        (str(load.uuid),),
    ).fetchone()[0]

    expected = {"__metadata__": {"module": "PowerSystems", "function": "get_max_active_power"}}
    assert json.loads(solar_scaling) == expected
    assert load_scaling is None


def test_export_preserves_missing_time_series_scaling_factor(infrasys_test_system, tmp_path):
    """Test that export does not assign a scaling function to raw load time series."""
    load = next(iter(infrasys_test_system.get_components(PowerLoad)))
    output_file = tmp_path / "system.json"
    config = SiennaConfig(
        model_year=2010,
        system_name="Test System",
        scenario="test",
        system_base_power=100.0,
        output_path=str(output_file),
    )

    SiennaExporter.from_context(PluginContext(config=config, system=infrasys_test_system)).run()

    connection = infrasys_test_system._time_series_mgr._metadata_store._con
    scaling = connection.execute(
        """
        SELECT scaling_factor_multiplier
        FROM time_series_associations
        WHERE owner_uuid = ? AND name = 'max_active_power'
        """,
        (str(load.uuid),),
    ).fetchone()[0]
    assert scaling is None


def test_set_time_series_scaling_factor_multiplier_requires_function(simple_test_system):
    """Test rejecting an empty PowerSystems scaling function name."""
    generator = simple_test_system.get_component(ThermalStandard, "thermal-standard-test")
    with pytest.raises(ValueError, match="function_name must not be empty"):
        exporter_mod.set_time_series_scaling_factor_multiplier(
            simple_test_system,
            generator,
            "max_active_power",
            "",
        )


def test_set_time_series_scaling_factor_multiplier_requires_series(simple_test_system):
    """Test requiring the selected time series to exist on the component."""
    generator = simple_test_system.get_component(ThermalStandard, "thermal-standard-test")
    with pytest.raises(ValueError, match="No SingleTimeSeries named 'max_active_power'"):
        exporter_mod.set_time_series_scaling_factor_multiplier(
            simple_test_system,
            generator,
            "max_active_power",
            "get_max_active_power",
        )


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


def test_iter_supplemental_attributes_fallback_and_empty():
    class WithMethod:
        def iter_supplemental_attributes(self):
            return [1, 2]

    class Empty:
        pass

    assert list(exporter_mod.iter_supplemental_attributes(WithMethod())) == [1, 2]
    assert tuple(exporter_mod.iter_supplemental_attributes(Empty())) == ()


def test_serialize_supplemental_attributes_skips_unsupported_type():
    class UnsupportedAttr:
        def __init__(self):
            self.uuid = uuid4()

    class Component:
        def __init__(self):
            self.uuid = uuid4()

    attr = UnsupportedAttr()
    component = Component()

    class ComponentMgr:
        def iter_all(self):
            return [component]

    class FakeSystem:
        _component_mgr = ComponentMgr()

        @staticmethod
        def iter_supplemental_attributes():
            return [attr]

        @staticmethod
        def has_supplemental_attribute(_component):
            return True

        @staticmethod
        def get_supplemental_attributes_with_component(_component):
            return [attr]

    assert exporter_mod.serialize_single_supplemental_attribute(attr) is None
    result = exporter_mod.serialize_supplemental_attributes(FakeSystem())
    assert result == {"attributes": [], "associations": []}


def test_exporter_on_validate_returns_err_when_mkdir_fails(simple_test_system, tmp_path, monkeypatch):
    cfg = SiennaConfig(output_path=str(tmp_path / "nested" / "out.json"), model_year=2010)
    ctx = PluginContext(config=cfg, system=simple_test_system, store=DataStore(path=tmp_path))
    exporter = SiennaExporter.from_context(ctx)

    def _raise_mkdir(self, parents=False, exist_ok=False):
        raise OSError("mkdir failed")

    monkeypatch.setattr(Path, "mkdir", _raise_mkdir)
    result = exporter.on_validate()
    assert result.is_err()
    assert "Failed to create output directory" in str(result.err())


def test_exporter_on_export_returns_err_when_component_serialization_raises(
    simple_test_system, tmp_path, monkeypatch
):
    cfg = SiennaConfig(output_path=str(tmp_path / "out.json"), model_year=2010)
    ctx = PluginContext(config=cfg, system=simple_test_system, store=DataStore(path=tmp_path))
    exporter = SiennaExporter.from_context(ctx)
    exporter.should_export_time_series = False
    exporter.system_data = {"data_information": {}, "system_information": {}}

    def _boom(_component):
        raise RuntimeError("serialize boom")

    monkeypatch.setattr(exporter_mod, "serialize_component_to_psy", _boom)
    result = exporter.on_export()
    assert result.is_err()
    assert "Export failed" in str(result.err())


def test_normalize_time_series_metadata_raises_on_upgrade_error(simple_test_system, tmp_path, monkeypatch):
    cfg = SiennaConfig(output_path=str(tmp_path / "out.json"), model_year=2010)
    ctx = PluginContext(config=cfg, system=simple_test_system, store=DataStore(path=tmp_path))
    exporter = SiennaExporter.from_context(ctx)

    import r2x_sienna.upgrader.data_upgrader as du

    monkeypatch.setattr(du, "_upgrade_h5_time_series_metadata", lambda _path: Err("bad metadata"))
    with pytest.raises(RuntimeError, match="bad metadata"):
        exporter._normalize_time_series_metadata(tmp_path / "dummy.h5")


def test_patch_time_series_owner_types_no_metadata_dataset(simple_test_system, tmp_path):
    import h5py

    cfg = SiennaConfig(output_path=str(tmp_path / "out.json"), model_year=2010)
    ctx = PluginContext(config=cfg, system=simple_test_system, store=DataStore(path=tmp_path))
    exporter = SiennaExporter.from_context(ctx)

    h5_path = tmp_path / "no_meta.h5"
    with h5py.File(h5_path, "w") as f:
        f.create_dataset("not_time_series_metadata", data=[1, 2, 3])

    exporter._patch_time_series_owner_types(h5_path)


def test_to_psy_raises_on_validate_and_export_errors(simple_test_system, tmp_path, monkeypatch):
    output_file = tmp_path / "legacy.json"
    config = SimpleNamespace(system_base_power=100.0, scenario="base")
    system_data = {"data_information": {}, "system_information": {}}

    monkeypatch.setattr(SiennaExporter, "on_validate", lambda self: Err("validation failed"))
    with pytest.raises(Exception, match="Validation failed"):
        exporter_mod.to_psy(config, simple_test_system, system_data, str(output_file))

    monkeypatch.setattr(SiennaExporter, "on_validate", lambda self: Ok(None))
    monkeypatch.setattr(SiennaExporter, "on_export", lambda self: Err("export failed"))
    with pytest.raises(Exception, match="Export failed"):
        exporter_mod.to_psy(config, simple_test_system, system_data, str(output_file))
