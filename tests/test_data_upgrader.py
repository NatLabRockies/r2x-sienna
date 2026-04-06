import json
from pathlib import Path
from typing import Any

from r2x_core import UpgradeStep, UpgradeType

from r2x_sienna.upgrader.data_upgrader import SiennaUpgrader


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
