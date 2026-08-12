import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from r2x_core import UpgradeStep, UpgradeType
from rust_ok import Err, Ok

from r2x_sienna import plugins
from r2x_sienna.logger import timeit
from r2x_sienna.upgrader import data_upgrader, upgrade_steps
from r2x_sienna.upgrader.data_upgrader import SiennaUpgrader, SiennaVersionDetector, run_sienna_upgrades
from r2x_sienna.upgrader.data_upgrader import (
    SiennaUpgrader,
    SiennaVersionDetector,
    _normalize_initial_timestamp,
    run_sienna_upgrades,
)
from r2x_sienna.upgrader.upgrade_steps import (
    _sanitize_geojson_coordinates,
    upgrade_geographic_info,
    upgrade_psy5_schema_fields,
)


def test_normalize_initial_timestamp_adds_fractional_seconds() -> None:
    assert _normalize_initial_timestamp("2023-01-01T00:00:00") == "2023-01-01T00:00:00.0"
    assert _normalize_initial_timestamp("2023-01-01 00:00:00") == "2023-01-01T00:00:00.0"
    assert _normalize_initial_timestamp("2023-01-01T00:00:00.123") == "2023-01-01T00:00:00.123"


def test_system_upgrade_preserves_trailing_newline(tmp_path: Path) -> None:
    """System upgrades should not remove trailing newline from JSON fixture files."""

    json_path = tmp_path / "system.json"
    system_data = {
        "data_format_version": "1.0.0",
        "data": {
            "components": [],
        },
    }
    json_path.write_text(f"{json.dumps(system_data)}\n", encoding="utf-8")

    def noop_upgrade(data: dict[str, Any]) -> dict[str, Any]:
        return data

    upgrader = SiennaUpgrader(
        json_path,
        steps=[
            UpgradeStep(
                name="noop_upgrade",
                func=noop_upgrade,
                target_version="2.0.0",
                upgrade_type=UpgradeType.SYSTEM,
            )
        ],
    )

    result = upgrader.upgrade(current_version="1.0.0", upgrade_type=UpgradeType.SYSTEM)
    assert result.is_ok(), result.err()
    assert json_path.read_bytes().endswith(b"\n")


def test_upgrade_geographic_info_sanitizes_invalid_new_format_coordinates() -> None:
    system_data = {
        "data": {
            "components": [],
            "supplemental_attribute_manager": {
                "attributes": [
                    {
                        "name": "bad_geo",
                        "__metadata__": {"type": "GeographicInfo"},
                        "geo_json": {
                            "coordinates": ["Out of Service", None],
                            "type": "Point",
                        },
                    }
                ]
            },
        }
    }

    upgraded = upgrade_geographic_info(system_data)
    coords = upgraded["data"]["supplemental_attribute_manager"]["attributes"][0]["geo_json"]["coordinates"]
    assert coords == [0.0, 0.0]


def test_upgrade_geographic_info_sanitizes_invalid_legacy_coordinates() -> None:
    system_data = {
        "data": {
            "components": [],
            "supplemental_attribute_manager": {
                "attributes": [
                    {
                        "name": "legacy_geo",
                        "__metadata__": {"type": "GeographicInfo"},
                        "geo_json": {
                            "Longitude": "Out of Service",
                            "Latitude": None,
                        },
                    }
                ]
            },
        }
    }

    upgraded = upgrade_geographic_info(system_data)
    geo_json = upgraded["data"]["supplemental_attribute_manager"]["attributes"][0]["geo_json"]
    assert geo_json["type"] == "Point"
    assert geo_json["coordinates"] == [0.0, 0.0]


def test_upgrade_geographic_info_skips_when_no_data_section() -> None:
    system_data = {"foo": "bar"}

    upgraded = upgrade_geographic_info(system_data)

    assert upgraded == system_data


def test_upgrade_geographic_info_skips_when_no_supplemental_attributes() -> None:
    system_data = {
        "data": {
            "components": [],
        }
    }

    upgraded = upgrade_geographic_info(system_data)

    assert upgraded == system_data


def test_upgrade_geographic_info_defaults_type_when_missing() -> None:
    system_data = {
        "data": {
            "components": [],
            "supplemental_attribute_manager": {
                "attributes": [
                    {
                        "name": "geo_missing_type",
                        "__metadata__": {"type": "GeographicInfo"},
                        "geo_json": {
                            "coordinates": ["-122.3", "47.6"],
                        },
                    }
                ]
            },
        }
    }

    upgraded = upgrade_geographic_info(system_data)
    geo_json = upgraded["data"]["supplemental_attribute_manager"]["attributes"][0]["geo_json"]

    assert geo_json["type"] == "Point"
    assert geo_json["coordinates"] == [-122.3, 47.6]


def test_sanitize_geojson_coordinates_nested_points() -> None:
    coordinates = [["1.5", "2.5"], [3, 4.0], [None, "bad"]]

    sanitized = _sanitize_geojson_coordinates(coordinates, "nested_geo")

    assert sanitized == [[1.5, 2.5], [3.0, 4.0], [0.0, 0.0]]


def test_sanitize_geojson_coordinates_mixed_nesting_defaults() -> None:
    coordinates = [[1.0, 2.0], 3.0]

    sanitized = _sanitize_geojson_coordinates(coordinates, "mixed_geo")

    assert sanitized == [0.0, 0.0]


def test_sanitize_geojson_coordinates_invalid_shape_defaults() -> None:
    sanitized_none = _sanitize_geojson_coordinates(None, "none_geo")
    sanitized_empty = _sanitize_geojson_coordinates([], "empty_geo")

    assert sanitized_none == [0.0, 0.0]
    assert sanitized_empty == [0.0, 0.0]


def test_timeit_logs_and_returns(monkeypatch) -> None:
    events: list[str] = []
    monkeypatch.setattr("r2x_sienna.logger.time.time", lambda: 100.0 if not events else 100.5)
    monkeypatch.setattr("r2x_sienna.logger.logger.debug", lambda message: events.append(message))

    @timeit
    def add(a: int, b: int) -> int:
        return a + b

    assert add(1, 2) == 3
    assert len(events) == 1
    assert "Function add executed in" in events[0]


def test_plugins_exports() -> None:
    assert plugins.parser.__name__ == "SiennaParser"
    assert plugins.exporter.__name__ == "SiennaExporter"
    assert plugins.config.__name__ == "SiennaConfig"
    assert "SiennaUpgrader" in plugins.__all__
    assert "SiennaVersionDetector" in plugins.__all__


def test_upgrade_step_helpers_for_refs_and_branches() -> None:
    comp = {
        "name": "line_a",
        "__metadata__": {"type": "Line"},
        "rating": 10.0,
        "rating_b": None,
        "rating_c": None,
    }
    upgrade_steps._patch_ac_branch(comp)
    assert comp["rating_b"] == 10.0
    assert comp["rating_c"] == 10.0

    assert upgrade_steps._get_ref_uuid({"value": "abc"}) == "abc"
    assert upgrade_steps._get_ref_uuid({"__metadata__": {"uuid": "def"}}) == "def"
    assert upgrade_steps._get_ref_uuid("bad") is None


def test_upgrade_psy5_schema_fields_normalizes_only_required_fields() -> None:
    system_data = {
        "data": {
            "components": [
                {
                    "__metadata__": {"type": "PowerLoad"},
                    "name": "pl1",
                    "comformity": "CONFORMING",
                },
                {
                    "__metadata__": {"type": "TransmissionInterface"},
                    "name": "if1",
                    "active_power_flow_limits": {"min": -100.0, "max": 100.0},
                    "direction_mapping": {},
                },
                {
                    "__metadata__": {"type": "TapTransformer"},
                    "name": "tap1",
                },
                {
                    "__metadata__": {"type": "TModelHVDCLine"},
                    "name": "dc1",
                    "rating_up": 300.0,
                    "rating_down": -250.0,
                    "resistance": 0.01,
                    "inductance": 0.02,
                    "capacitance": 0.03,
                },
                {
                    "__metadata__": {"type": "TwoTerminalVSCLine"},
                    "name": "vsc1",
                    "dc_voltage_control_from": True,
                    "dc_voltage_control_to": False,
                    "ac_voltage_control_from": False,
                    "ac_voltage_control_to": True,
                },
                {
                    "__metadata__": {"type": "InterconnectingConverter"},
                    "name": "ipc1",
                },
                {
                    "__metadata__": {"type": "SwitchedAdmittance"},
                    "name": "sa1",
                },
                {
                    "__metadata__": {"type": "EnergyReservoirStorage"},
                    "name": "st1",
                },
            ]
        }
    }

    upgraded = upgrade_psy5_schema_fields(system_data)
    comps = upgraded["data"]["components"]

    pl = next(c for c in comps if c.get("__metadata__", {}).get("type") == "PowerLoad")
    assert pl["conformity"] == "CONFORMING"

    iface = next(c for c in comps if c.get("__metadata__", {}).get("type") == "TransmissionInterface")
    assert iface["violation_penalty"] == 1e30

    tap = next(c for c in comps if c.get("__metadata__", {}).get("type") == "TapTransformer")
    assert "tap_limits" not in tap
    assert "number_of_tap_positions" not in tap
    assert "regulated_bus_number" not in tap
    assert "voltage_setpoint" not in tap

    tmodel = next(c for c in comps if c.get("__metadata__", {}).get("type") == "TModelHVDCLine")
    assert "r" not in tmodel
    assert "l" not in tmodel
    assert "c" not in tmodel
    assert "active_power_limits_from" not in tmodel
    assert "active_power_limits_to" not in tmodel

    vsc = next(c for c in comps if c.get("__metadata__", {}).get("type") == "TwoTerminalVSCLine")
    assert "dc_control_from" not in vsc
    assert "dc_control_to" not in vsc
    assert "ac_control_from" not in vsc
    assert "ac_control_to" not in vsc
    assert "rmpct_from" not in vsc
    assert "rmpct_to" not in vsc

    ipc = next(c for c in comps if c.get("__metadata__", {}).get("type") == "InterconnectingConverter")
    assert "max_dc_current" not in ipc
    assert "dc_control" not in ipc

    sa = next(c for c in comps if c.get("__metadata__", {}).get("type") == "SwitchedAdmittance")
    assert "control_mode" not in sa
    assert "regulated_bus_number" not in sa

    ers = next(c for c in comps if c.get("__metadata__", {}).get("type") == "EnergyReservoirStorage")
    assert "operation_cost" not in ers


def test_upgrade_step_helpers_for_transformers() -> None:
    components = [
        {
            "__metadata__": {"type": "ACBus"},
            "internal": {"uuid": {"value": "bus_1"}},
            "base_voltage": 230.0,
        },
        {
            "__metadata__": {"type": "ACBus"},
            "internal": {"uuid": {"value": "bus_2"}},
            "base_voltage": 115.0,
        },
        {
            "__metadata__": {"type": "Arc"},
            "internal": {"uuid": {"value": "arc_12"}},
            "from": {"value": "bus_1"},
            "to": {"value": "bus_2"},
        },
    ]

    bus_map = upgrade_steps._build_bus_voltage_map(components)
    arc_map = upgrade_steps._build_arc_to_bus_map(components)
    assert bus_map == {"bus_1": 230.0, "bus_2": 115.0}
    assert arc_map == {"arc_12": ("bus_1", "bus_2")}

    two_w = {
        "name": "t2",
        "__metadata__": {"type": "Transformer2W"},
        "primary_shunt": 1.2,
        "rating": 99.0,
        "arc": {"value": "arc_12"},
        "rating_b": None,
        "rating_c": None,
        "base_power": None,
        "base_voltage_primary": None,
        "base_voltage_secondary": None,
    }
    upgrade_steps._patch_two_winding_transformer(two_w, bus_map, arc_map, 100.0)
    assert two_w["primary_shunt"] == {"real": 1.2, "imag": 0.0}
    assert two_w["rating_b"] == 99.0
    assert two_w["rating_c"] == 99.0
    assert two_w["base_power"] == 100.0
    assert two_w["base_voltage_primary"] == 230.0
    assert two_w["base_voltage_secondary"] == 115.0

    arc_map.update({"a": ("bus_1", "bus_2"), "b": ("bus_2", "bus_1"), "c": ("bus_1", "bus_2")})
    three_w = {
        "name": "t3",
        "__metadata__": {"type": "Transformer3W"},
        "x_secondary": 5.0,
        "x_tertiary": -3.0,
        "x_23": 0.1,
        "x_13": 0.2,
        "r_23": 0.3,
        "r_13": 0.4,
        "primary_star_arc": {"value": "a"},
        "secondary_star_arc": {"value": "b"},
        "tertiary_star_arc": {"value": "c"},
        "base_power_12": None,
        "base_power_23": None,
        "base_power_13": None,
        "base_voltage_primary": None,
        "base_voltage_secondary": None,
        "base_voltage_tertiary": None,
    }
    upgrade_steps._patch_three_winding_transformer(three_w, bus_map, arc_map, 150.0)
    assert three_w["base_power_12"] == 150.0
    assert three_w["base_power_23"] == 150.0
    assert three_w["base_power_13"] == 150.0
    assert three_w["base_voltage_primary"] == 230.0
    assert three_w["base_voltage_secondary"] == 115.0
    assert three_w["base_voltage_tertiary"] == 230.0


def test_data_upgrader_feature_and_duration_helpers() -> None:
    assert data_upgrader._iso_8601_duration_from_milliseconds(None) is None
    assert data_upgrader._iso_8601_duration_from_milliseconds("") is None
    assert data_upgrader._iso_8601_duration_from_milliseconds("P0DT1.000S") == "P0DT1.000S"
    assert data_upgrader._iso_8601_duration_from_milliseconds("1000") == "P0DT1.000S"
    assert data_upgrader._iso_8601_duration_from_milliseconds("bad") == "bad"

    assert data_upgrader._parse_features_dict(None) == {}
    assert data_upgrader._parse_features_dict({"a": 1}) == {"a": 1}
    assert data_upgrader._parse_features_dict('{"b": 2}') == {"b": 2}
    assert data_upgrader._parse_features_dict('[{"x": 1}, {"y": 2}]') == {"x": 1, "y": 2}
    assert data_upgrader._parse_features_dict("not-json") == {}

    assert data_upgrader._duration_to_milliseconds(None) == 0.0
    assert data_upgrader._duration_to_milliseconds(1234) == 1234.0
    assert data_upgrader._duration_to_milliseconds("PT1H30M5.5S") == 5405500.0
    assert data_upgrader._duration_to_milliseconds("01:02:03") == 3723000.0
    assert data_upgrader._duration_to_milliseconds("42.0") == 42.0
    assert data_upgrader._duration_to_milliseconds("n/a") == 0.0


def test_data_upgrader_path_resolution_helpers(tmp_path: Path) -> None:
    data_file = tmp_path / "file.json"
    data_file.write_text("{}", encoding="utf-8")
    assert data_upgrader._resolve_json_path(data_file) == data_file

    dir_with_system = tmp_path / "sysdir"
    dir_with_system.mkdir()
    system_json = dir_with_system / "system.json"
    system_json.write_text("{}", encoding="utf-8")
    assert data_upgrader._resolve_json_path(dir_with_system) == system_json

    no_system_dir = tmp_path / "nosystem"
    no_system_dir.mkdir()
    (no_system_dir / "a_metadata.json").write_text("{}", encoding="utf-8")
    other_json = no_system_dir / "data.json"
    other_json.write_text("{}", encoding="utf-8")
    assert data_upgrader._resolve_json_path(no_system_dir) == other_json

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert data_upgrader._resolve_json_path(empty_dir) is None

    absolute_h5 = tmp_path / "ts_absolute.h5"
    absolute_h5.write_bytes(b"x")
    json_path = tmp_path / "system_abs.json"
    json_path.write_text(
        json.dumps({"data": {"time_series_storage_file": str(absolute_h5)}}), encoding="utf-8"
    )
    assert data_upgrader._resolve_time_series_h5_path(json_path) == absolute_h5

    json_rel = tmp_path / "system_rel.json"
    json_rel.write_text(json.dumps({"data": {"time_series_storage_file": "local.h5"}}), encoding="utf-8")
    assert data_upgrader._resolve_time_series_h5_path(json_rel) == tmp_path / "local.h5"

    json_nested = tmp_path / "system_nested.json"
    json_nested.write_text(
        json.dumps({"data": {"time_series_storage_file": "nested/path/file.h5"}}),
        encoding="utf-8",
    )
    assert data_upgrader._resolve_time_series_h5_path(json_nested) == tmp_path / "file.h5"


def test_version_detector_and_run_sienna_upgrades_paths(tmp_path: Path, monkeypatch) -> None:
    detector = SiennaVersionDetector()

    no_json_dir = tmp_path / "no_json"
    no_json_dir.mkdir()
    assert detector.read_version(no_json_dir) is None

    invalid_json = tmp_path / "bad.json"
    invalid_json.write_text("{bad", encoding="utf-8")
    assert detector.read_version(invalid_json) is None

    version_json = tmp_path / "ok.json"
    version_json.write_text(json.dumps({"data_format_version": "5.0.0"}), encoding="utf-8")
    assert detector.read_version(version_json) == "5.0.0"

    nested_json = tmp_path / "nested.json"
    nested_json.write_text(json.dumps({"data": {"version_info": {"version": "4.2.1"}}}), encoding="utf-8")
    assert detector.read_version(nested_json) == "4.2.1"

    ctx = SimpleNamespace()
    result = run_sienna_upgrades(ctx=ctx)
    assert result.is_err()

    monkeypatch.setattr(
        data_upgrader.SiennaVersionDetector,
        "read_version",
        lambda self, path: (_ for _ in ()).throw(FileNotFoundError("missing")),
    )
    result_skip = run_sienna_upgrades(json_path=tmp_path / "missing.json", ctx=SimpleNamespace())
    assert result_skip.is_ok()

    monkeypatch.setattr(data_upgrader.SiennaVersionDetector, "read_version", lambda self, path: "5.0.0")
    monkeypatch.setattr(data_upgrader.SiennaUpgrader, "upgrade", lambda self, **kwargs: Ok(self.path))
    monkeypatch.setattr(data_upgrader, "_resolve_json_path", lambda path: None)
    result_ok = run_sienna_upgrades(json_path=tmp_path, ctx=SimpleNamespace())
    assert result_ok.is_ok()


def test_upgrader_upgrade_error_paths(tmp_path: Path, monkeypatch) -> None:
    upgrader = SiennaUpgrader(tmp_path)

    # current_version autodetection fails
    monkeypatch.setattr(upgrader.version_reader, "read_version", lambda _path: None)
    result = upgrader.upgrade(current_version=None)
    assert result.is_err()
    assert "Could not determine Sienna version" in str(result.err())

    # SYSTEM upgrade with no JSON files in directory
    empty_dir = tmp_path / "empty_system_dir"
    empty_dir.mkdir()
    empty_upgrader = SiennaUpgrader(empty_dir)
    result = empty_upgrader.upgrade(current_version="1.0.0", upgrade_type=UpgradeType.SYSTEM)
    assert result.is_err()
    assert "No JSON file found" in str(result.err())

    # SYSTEM upgrade with invalid JSON file
    bad_json = tmp_path / "bad_system.json"
    bad_json.write_text("{invalid", encoding="utf-8")
    bad_upgrader = SiennaUpgrader(bad_json)
    result = bad_upgrader.upgrade(current_version="1.0.0", upgrade_type=UpgradeType.SYSTEM)
    assert result.is_err()
    assert "Failed to load JSON" in str(result.err())


def test_upgrader_upgrade_step_failure_and_file_mode_error(tmp_path: Path, monkeypatch) -> None:
    system_json = tmp_path / "system.json"
    system_json.write_text(json.dumps({"data": {"components": []}}), encoding="utf-8")

    def broken_upgrade(_data: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("step failed")

    failing_system_step = UpgradeStep(
        name="broken_upgrade",
        func=broken_upgrade,
        target_version="2.0.0",
        upgrade_type=UpgradeType.SYSTEM,
    )
    upgrader = SiennaUpgrader(system_json, steps=[failing_system_step])
    result = upgrader.upgrade(current_version="1.0.0", upgrade_type=UpgradeType.SYSTEM)
    assert result.is_err()
    assert "Failed broken_upgrade" in str(result.err())

    file_step = UpgradeStep(
        name="file_step",
        func=lambda path: path,
        target_version="2.0.0",
        upgrade_type=UpgradeType.FILE,
    )
    file_upgrader = SiennaUpgrader(system_json, steps=[file_step])
    monkeypatch.setattr(data_upgrader, "run_upgrade_step", lambda path, step: Err("file step failed"))
    result = file_upgrader.upgrade(current_version="1.0.0", upgrade_type=UpgradeType.FILE)
    assert result.is_err()
    assert "file step failed" in str(result.err())


def test_run_sienna_upgrades_store_and_h5_error_paths(tmp_path: Path, monkeypatch) -> None:
    system_json = tmp_path / "sys.json"
    system_json.write_text(
        json.dumps({"data_format_version": "5.0.0", "data": {"time_series_storage_file": "ts.h5"}}),
        encoding="utf-8",
    )
    h5_path = tmp_path / "ts.h5"
    h5_path.write_bytes(b"dummy")

    class Store:
        folder = tmp_path

    # Cover store.folder branch and "could not detect version" skip.
    monkeypatch.setattr(data_upgrader.SiennaUpgrader.version_reader, "read_version", lambda path: None)
    monkeypatch.setattr(data_upgrader, "_resolve_json_path", lambda path: None)
    result_skip = run_sienna_upgrades(store=Store(), ctx=SimpleNamespace())
    assert result_skip.is_ok()

    # Cover upgrade result error branch.
    monkeypatch.setattr(data_upgrader.SiennaUpgrader.version_reader, "read_version", lambda path: "5.0.0")
    monkeypatch.setattr(data_upgrader.SiennaUpgrader, "upgrade", lambda self, **kwargs: Err("upgrade failed"))
    result_upgrade_err = run_sienna_upgrades(store=Store(), ctx=SimpleNamespace())
    assert result_upgrade_err.is_err()
    assert "upgrade failed" in str(result_upgrade_err.err())

    # Cover JSON/H5 inspection error branch.
    monkeypatch.setattr(data_upgrader.SiennaUpgrader, "upgrade", lambda self, **kwargs: Ok(self.path))
    monkeypatch.setattr(data_upgrader, "_resolve_json_path", lambda path: system_json)
    monkeypatch.setattr(
        data_upgrader,
        "_resolve_time_series_h5_path",
        lambda path: (_ for _ in ()).throw(RuntimeError("inspect failed")),
    )
    result_inspect_err = run_sienna_upgrades(store=Store(), ctx=SimpleNamespace())
    assert result_inspect_err.is_err()
    assert "Failed to inspect JSON" in str(result_inspect_err.err())

    # Cover H5 upgrade error branch.
    monkeypatch.setattr(data_upgrader, "_resolve_time_series_h5_path", lambda path: h5_path)
    monkeypatch.setattr(
        data_upgrader, "_upgrade_h5_time_series_metadata", lambda path: Err("h5 upgrade failed")
    )
    result_h5_err = run_sienna_upgrades(store=Store(), ctx=SimpleNamespace())
    assert result_h5_err.is_err()
    assert "h5 upgrade failed" in str(result_h5_err.err())
