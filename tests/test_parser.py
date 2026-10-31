"""Basic Sienna parser tests using r2x-core Plugin API.

These tests verify basic parser instantiation and configuration using
a minimal test data set.
"""

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID, uuid4

import numpy as np
import pytest
from infrasys import Deterministic, SingleTimeSeries
from infrasys.exceptions import ISNotStored
from r2x_core import DataStore, PluginContext, System

from r2x_sienna.models import ACBus, HydroReservoir, PowerLoad, Source, VariableReserve
from r2x_sienna.parser import SiennaParser, create_temporary_h5_storage
from r2x_sienna.plugin_config import SiennaConfig


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


def test_parser_adds_default_hydro_reservoir_inflow_series(
    sienna_config: SiennaConfig, mock_data_store: Mock
):
    """Reservoirs created during PSY4-to-PSY5 upgrades get a default inflow series."""
    ctx = PluginContext(config=sienna_config, store=mock_data_store)
    parser = SiennaParser.from_context(ctx)
    system = System(name="hydro-test")
    reservoir = HydroReservoir.example()
    system.add_component(reservoir)
    parser.ctx.system = system

    parser._ensure_hydro_reservoir_inflow_time_series()

    time_series = system.get_time_series(reservoir, "inflow")
    assert time_series.name == "inflow"
    assert len(time_series.data) == 8760
    assert all(value == 0.0 for value in time_series.data)


def test_parser_preserves_existing_hydro_reservoir_time_series(
    sienna_config: SiennaConfig, mock_data_store: Mock
):
    """Existing reservoir series are not replaced by the default series."""
    ctx = PluginContext(config=sienna_config, store=mock_data_store)
    parser = SiennaParser.from_context(ctx)
    system = System(name="hydro-test")
    reservoir = HydroReservoir.example()
    system.add_component(reservoir)
    existing_series = SingleTimeSeries.from_array(
        data=[1.0] * 8760,
        name="existing_inflow",
        resolution=timedelta(hours=1),
        initial_timestamp=datetime(year=2029, month=1, day=1, tzinfo=UTC),
    )
    system.add_time_series(existing_series, reservoir)
    parser.ctx.system = system

    parser._ensure_hydro_reservoir_inflow_time_series()

    existing = system.get_time_series(reservoir, "existing_inflow")
    inflow = system.get_time_series(reservoir, "inflow")
    assert existing.name == "existing_inflow"
    assert inflow.name == "inflow"


def test_parser_filters_hydro_reservoir_max_active_power(sienna_config: SiennaConfig, mock_data_store: Mock):
    """Reservoirs do not retain the unsupported max_active_power series."""
    ctx = PluginContext(config=sienna_config, store=mock_data_store)
    parser = SiennaParser.from_context(ctx)
    system = System(name="hydro-test")
    reservoir = HydroReservoir.example()
    system.add_component(reservoir)
    system.add_time_series(
        SingleTimeSeries.from_array(
            data=[1.0] * 8760,
            name="max_active_power",
            resolution=timedelta(hours=1),
            initial_timestamp=datetime(year=2029, month=1, day=1, tzinfo=UTC),
        ),
        reservoir,
    )
    system.add_time_series(
        SingleTimeSeries.from_array(
            data=[2.0] * 8760,
            name="inflow",
            resolution=timedelta(hours=1),
            initial_timestamp=datetime(year=2029, month=1, day=1, tzinfo=UTC),
        ),
        reservoir,
    )
    parser.ctx.system = system

    parser._filter_hydro_reservoir_max_active_power()

    with pytest.raises(ISNotStored):
        system.get_time_series(reservoir, "max_active_power")
    assert system.get_time_series(reservoir, "inflow").name == "inflow"


def test_parser_clears_hydro_reservoir_scaling_multipliers(
    sienna_config: SiennaConfig, mock_data_store: Mock
):
    """Clear inherited generator scaling without changing unrelated metadata."""
    ctx = PluginContext(config=sienna_config, store=mock_data_store)
    parser = SiennaParser.from_context(ctx)
    system = System(name="hydro-test")
    reservoir = HydroReservoir.example()
    system.add_component(reservoir)
    parser.ctx.system = system
    timestamp = datetime(year=2029, month=1, day=1, tzinfo=UTC)
    for name in ("hydro_budget", "inflow"):
        system.add_time_series(
            SingleTimeSeries.from_array(
                data=[1.0] * 8760,
                name=name,
                resolution=timedelta(hours=1),
                initial_timestamp=timestamp,
            ),
            reservoir,
        )

    connection = system._time_series_mgr._metadata_store._con
    invalid = '{"__metadata__":{"module":"PowerSystems","function":"get_max_active_power"}}'
    valid = '{"__metadata__":{"module":"PowerSystems","function":"get_inflow"}}'
    connection.execute(
        """
        UPDATE time_series_associations
        SET scaling_factor_multiplier = ?
        WHERE owner_uuid = ? AND name = 'hydro_budget'
        """,
        (invalid, str(reservoir.uuid)),
    )
    connection.execute(
        """
        UPDATE time_series_associations
        SET scaling_factor_multiplier = ?
        WHERE owner_uuid = ? AND name = 'inflow'
        """,
        (valid, str(reservoir.uuid)),
    )
    unrelated_owner = str(uuid4())
    connection.execute(
        """
        INSERT INTO time_series_associations (
            time_series_uuid, time_series_type, initial_timestamp, resolution,
            length, name, owner_uuid, owner_type, owner_category, features,
            scaling_factor_multiplier, metadata_uuid
        ) VALUES (?, 'SingleTimeSeries', ?, '1 hour', 8760, 'hydro_budget', ?,
                  'HydroDispatch', 'Component', '[]', ?, ?)
        """,
        (str(uuid4()), timestamp.isoformat(), unrelated_owner, invalid, str(uuid4())),
    )
    connection.commit()

    parser._clear_hydro_reservoir_scaling_multipliers(connection)

    rows = connection.execute(
        """
        SELECT owner_uuid, name, scaling_factor_multiplier
        FROM time_series_associations
        WHERE (owner_uuid = ? AND name IN ('hydro_budget', 'inflow'))
           OR owner_uuid = ?
        ORDER BY owner_uuid, name
        """,
        (str(reservoir.uuid), unrelated_owner),
    ).fetchall()
    assert {
        (owner_uuid, name): scaling_factor_multiplier for owner_uuid, name, scaling_factor_multiplier in rows
    } == {
        (str(reservoir.uuid), "hydro_budget"): None,
        (str(reservoir.uuid), "inflow"): valid,
        (unrelated_owner, "hydro_budget"): invalid,
    }


def test_parser_derives_inflow_timestamp_from_existing_series(mock_data_store: Mock):
    """Missing model_year uses an existing time-series timestamp."""
    config = SiennaConfig(model_year=None, system_name="test_case")
    ctx = PluginContext(config=config, store=mock_data_store)
    parser = SiennaParser.from_context(ctx)
    system = System(name="hydro-test")
    reservoir = HydroReservoir.example()
    system.add_component(reservoir)
    existing_series = SingleTimeSeries.from_array(
        data=[1.0] * 8760,
        name="hydro_budget",
        resolution=timedelta(hours=1),
        initial_timestamp=datetime(year=2023, month=1, day=1, tzinfo=UTC),
    )
    system.add_time_series(existing_series, reservoir)
    parser.ctx.system = system

    parser._ensure_hydro_reservoir_inflow_time_series()

    inflow = system.get_time_series(reservoir, "inflow")
    assert inflow.initial_timestamp == existing_series.initial_timestamp


def test_parser_keeps_reservoir_inflow_source_only_when_system_has_forecasts(
    sienna_config: SiennaConfig, mock_data_store: Mock
):
    """Missing reservoir inflow remains a source series when forecasts are present."""
    ctx = PluginContext(config=sienna_config, store=mock_data_store)
    parser = SiennaParser.from_context(ctx)
    system = System(name="hydro-test")
    reservoir = HydroReservoir.example()
    system.add_component(reservoir)
    system.add_time_series(
        Deterministic.from_array(
            data=np.ones((365, 24)),
            name="hydro_budget",
            resolution=timedelta(hours=1),
            initial_timestamp=datetime(year=2029, month=1, day=1, tzinfo=UTC),
            horizon=timedelta(days=1),
            interval=timedelta(days=1),
            window_count=365,
        ),
        reservoir,
    )
    system._time_series_mgr._metadata_store._con.execute(
        "UPDATE time_series_associations SET time_series_type = 'DeterministicSingleTimeSeries'"
    )
    parser.ctx.system = system

    parser._ensure_hydro_reservoir_inflow_time_series()

    con = system._time_series_mgr._metadata_store._con
    rows = con.execute(
        """
        SELECT time_series_type
        FROM time_series_associations
        WHERE owner_uuid = ? AND name = 'inflow'
        ORDER BY time_series_type
        """,
        (str(reservoir.uuid),),
    ).fetchall()
    assert {row[0] for row in rows} == {"SingleTimeSeries"}


def test_parser_builds_2area_5bus_with_source(data_folder: Path, tmp_path: Path):
    """Parse the 2area-5bus test system and verify Source deserialization."""
    source_case_path = data_folder / "2area-5bus-system"
    case_path = tmp_path / source_case_path.name
    shutil.copytree(source_case_path, case_path)
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
    assert result_ctx.store is not None
    assert result_ctx.store["sienna_system"].reader.format == "json"
    assert str(result_ctx.store["sienna_system"].fpath) == "{sienna_json_path}"

    sources = [component for component in system._component_mgr.iter_all() if isinstance(component, Source)]
    assert sources, "Expected at least one Source component in parsed system"

    source_names = {source.name for source in sources}
    assert "source_bus1" in source_names

    source_bus1 = next(source for source in sources if source.name == "source_bus1")
    assert source_bus1.operation_cost is not None
    assert source_bus1.operation_cost.ancillary_service_offers == []


def test_parser_rules_preserve_rts_bus_references_and_uuids(data_folder: Path, tmp_path: Path):
    """Core-built buses retain the original UUID and canonical area and zone references."""
    case_path = tmp_path / "rts"
    shutil.copytree(data_folder / "case_rts_gmlc", case_path)
    json_path = case_path / "rts_gmlc_da_sys.json"
    components = json.loads(json_path.read_text())["data"]["components"]
    raw_bus = next(item for item in components if item.get("__metadata__", {}).get("type") == "ACBus")
    config = SiennaConfig(
        model_year=2010, system_name="rts", system_base_power=100.0, json_path=str(json_path)
    )
    parser = SiennaParser.from_context(PluginContext(config=config))
    system = parser.run().system
    assert system is not None
    assert {ACBus, PowerLoad} <= parser._configured_component_types
    raw_load = next(item for item in components if item.get("__metadata__", {}).get("type") == "PowerLoad")
    load = system.get_component(PowerLoad, raw_load["name"])
    assert load.uuid == UUID(raw_load["internal"]["uuid"]["value"])
    assert load.bus is system.get_component_by_uuid(UUID(raw_load["bus"]["value"]))
    bus = system.get_component(ACBus, raw_bus["name"])
    assert bus.uuid == UUID(raw_bus["internal"]["uuid"]["value"])
    assert bus.area is system.get_component_by_uuid(UUID(raw_bus["area"]["value"]))
    assert bus.load_zone is system.get_component_by_uuid(UUID(raw_bus["load_zone"]["value"]))

    output = tmp_path / "rts.json"
    system.to_json(output, overwrite=True)
    restored = System.from_json(output)
    restored_bus = restored.get_component(ACBus, raw_bus["name"])
    assert restored_bus.uuid == bus.uuid
    assert restored_bus.area is restored.get_component_by_uuid(bus.area.uuid)
    assert restored_bus.load_zone is restored.get_component_by_uuid(bus.load_zone.uuid)

    source_storage = create_temporary_h5_storage(case_path / "rts_gmlc_da_sys_time_series_storage.h5")
    source_connection = source_storage.get_metadata_store()
    query = (
        "SELECT owner_uuid, time_series_uuid, name, time_series_type "
        "FROM time_series_associations WHERE owner_type = 'Area' ORDER BY 1, 2, 3, 4"
    )
    source_associations = source_connection.execute(query).fetchall()
    assert source_associations
    assert system._time_series_mgr._metadata_store._con.execute(query).fetchall() == source_associations
    assert restored._time_series_mgr._metadata_store._con.execute(query).fetchall() == source_associations


@pytest.mark.parametrize("skip_validation", [False, True])
def test_parser_preserves_uuid_references_in_component_lists(
    data_folder: Path, tmp_path: Path, skip_validation: bool
):
    """Resolve a Sienna service UUID and preserve the reference through serialization."""
    case_path = tmp_path / "case"
    shutil.copytree(data_folder / "2area-5bus-system", case_path)
    json_path = case_path / "test_system.json"
    payload = json.loads(json_path.read_text())
    components = payload["data"]["components"]
    source = next(item for item in components if item.get("name") == "source_bus1")
    reserve_uuid = uuid4()
    source["services"] = [{"value": str(reserve_uuid)}]
    components.append(
        {
            "__metadata__": {
                "module": "PowerSystems",
                "type": "VariableReserve",
                "parameters": ["ReserveUp"],
            },
            "name": "test_reserve",
            "requirement": 0.0,
            "internal": {"uuid": {"value": str(reserve_uuid)}},
        }
    )
    json_path.write_text(json.dumps(payload))
    config = SiennaConfig(
        model_year=2029, system_name="case", system_base_power=100.0, json_path=str(json_path)
    )
    system = SiennaParser.from_context(PluginContext(config=config)).run().system
    assert system is not None
    source_component = system.get_component(Source, "source_bus1")
    reserve = system.get_component(VariableReserve, "test_reserve")
    assert source_component.services == [reserve]
    assert source_component.services[0] is reserve
    assert reserve.uuid == reserve_uuid

    output = tmp_path / "system.json"
    system.to_json(output, overwrite=True)
    restored = System.from_json(output)
    restored_reserve = restored.get_component(VariableReserve, "test_reserve")
    assert restored_reserve.uuid == reserve_uuid
    restored_source = restored.get_component(Source, "source_bus1")
    assert restored_source.services == [restored_reserve]
    assert restored_source.services[0] is restored_reserve


class TestDeserializeComponentsNested:
    """Tests for _deserialize_components_nested assertion bug.

    The bug: When one component of a type deserializes successfully,
    the code assumes all other components of the same type will too.
    This is wrong because validation can fail for individual components.
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
        #    - Second ACBus: invalid bus number
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
                skip_validation=False,
            )
            store = DataStore(path=json_path.parent)
            ctx = PluginContext(config, store=store)
            parser = SiennaParser.from_context(ctx)
            parser.on_prepare()
            parser.on_upgrade()

            system = System(name="test")
            parser.ctx.system = system

            # With the fix, this should raise ValueError with a clear message
            # instead of the cryptic AssertionError
            with pytest.raises(ValueError, match="greater than 0"):
                parser._parse_components()


def test_parser_rules_optional_references_with_partial_config_override(tmp_path: Path):
    """Older overrides may omit new assets; all bus reference combinations remain valid."""
    area_id, zone_id = uuid4(), uuid4()
    rows = [
        {"__metadata__": {"type": "Area"}, "name": "area", "internal": {"uuid": {"value": str(area_id)}}},
        {"__metadata__": {"type": "LoadZone"}, "name": "zone", "internal": {"uuid": {"value": str(zone_id)}}},
    ]
    for index, (area, zone) in enumerate(((False, False), (True, False), (False, True), (True, True)), 1):
        rows.append(
            {
                "__metadata__": {"type": "DCBus" if index == 4 else "ACBus"},
                "name": f"bus-{index}",
                "number": index,
                "internal": {"uuid": {"value": str(uuid4())}},
                "area": {"value": str(area_id)} if area else None,
                "load_zone": {"value": str(zone_id)} if zone else None,
            }
        )
    path = tmp_path / "system.json"
    path.write_text(json.dumps({"data": {"components": rows}}))
    config_dir = tmp_path / "legacy-config"
    config_dir.mkdir()
    (config_dir / "file_mapping.json").write_text("[]")
    config = SiennaConfig(json_path=str(path), config_path_override=config_dir)
    parser = SiennaParser.from_context(PluginContext(config=config))
    assert parser.on_prepare().is_ok()
    parser.ctx.system = System(name="test")
    parser._parse_components()
    from r2x_sienna.models import Area, DCBus, LoadZone

    area = parser.system.get_component(Area, "area")
    zone = parser.system.get_component(LoadZone, "zone")
    assert parser.system.get_component(ACBus, "bus-1").area is None
    assert parser.system.get_component(ACBus, "bus-2").area is area
    assert parser.system.get_component(ACBus, "bus-3").load_zone is zone
    bus = parser.system.get_component(DCBus, "bus-4")
    assert bus.area is area and bus.load_zone is zone


def test_parser_rejects_injected_mapping_that_disagrees_with_upgrade_path(tmp_path: Path):
    """An injected store cannot silently make upgrades and parsing read different files."""
    from r2x_core import DataFile

    source, other = tmp_path / "source.json", tmp_path / "other.json"
    source.write_text("{}")
    other.write_text("{}")
    store = DataStore(tmp_path)
    store.add_data([DataFile(name="sienna_system", fpath=other)])
    parser = SiennaParser.from_context(PluginContext(config=SiennaConfig(json_path=str(source)), store=store))
    assert parser.on_prepare().is_ok()
    with pytest.raises(ValueError, match="mapping must resolve to config.json_path"):
        parser._parse_components()


@pytest.mark.parametrize("duplicate", [False, True])
def test_parser_rejects_missing_reference_or_duplicate_name(tmp_path: Path, duplicate: bool):
    """Invalid UUID references and ambiguous same-type names fail explicitly."""
    area_id = uuid4()
    area = {"__metadata__": {"type": "Area"}, "name": "area", "internal": {"uuid": {"value": str(area_id)}}}
    rows = [area]
    if duplicate:
        rows.append({**area, "internal": {"uuid": {"value": str(uuid4())}}})
    else:
        rows.append(
            {
                "__metadata__": {"type": "ACBus"},
                "name": "bus",
                "number": 1,
                "internal": {"uuid": {"value": str(uuid4())}},
                "area": {"value": str(uuid4())},
            }
        )
    path = tmp_path / "system.json"
    path.write_text(json.dumps({"data": {"components": rows}}))
    parser = SiennaParser.from_context(PluginContext(config=SiennaConfig(json_path=str(path))))
    assert parser.on_prepare().is_ok()
    parser.ctx.system = System(name="test")
    with pytest.raises(ValueError, match="Duplicate|Unknown area UUID"):
        parser._parse_components()


@pytest.mark.parametrize(
    "case_name,json_name",
    [("case_rts_gmlc", "rts_gmlc_da_sys.json"), ("2area-5bus-system", "test_system.json")],
)
def test_parser_rule_components_match_native_rts_deserialization(
    data_folder: Path, tmp_path: Path, monkeypatch, case_name: str, json_name: str
):
    """Mapped RTS component fields match native deserialization, including nested values."""
    source = data_folder / case_name
    mapped_path, native_path = tmp_path / "mapped", tmp_path / "native"
    shutil.copytree(source, mapped_path)
    shutil.copytree(source, native_path)

    def parse(folder: Path):
        config = SiennaConfig(model_year=2010, system_name="rts", json_path=str(folder / json_name))
        parser = SiennaParser.from_context(PluginContext(config=config))
        return parser, parser.run().system

    parser, mapped = parse(mapped_path)
    monkeypatch.setattr(SiennaParser, "_build_configured_components", lambda self, components: components)
    _, native = parse(native_path)
    assert mapped is not None and native is not None
    assert ACBus in parser._configured_component_types
    for component_type in parser._configured_component_types:
        for component in mapped.get_components(component_type):
            original = native.get_component_by_uuid(component.uuid)
            assert component.model_dump(mode="json") == original.model_dump(mode="json")
