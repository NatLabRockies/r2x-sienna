import json
from pathlib import Path
from typing import Any

from r2x_core import UpgradeStep, UpgradeType

from r2x_sienna.upgrader.data_upgrader import SiennaUpgrader
from r2x_sienna.upgrader.upgrade_steps import upgrade_geographic_info


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
