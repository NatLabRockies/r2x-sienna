from pathlib import Path
from typing import Any

from r2x_core.upgrader import PluginUpgrader
from r2x_core.upgrader_utils import UpgradeStep
from r2x_core.versioning import VersionReader


class SiennaVersionDetector(VersionReader):
    """Detect version from Sienna JSON files by reading the `data_format_version` field.

    Supports both single JSON files and directories containing JSON files.
    """

    def read_version(self, path: Path) -> str | None:
        """Detect Sienna version from JSON file or directory.

        Parameters
        ----------
        path : Path
            Path to JSON file or directory containing JSON files.

        Returns
        -------
        str | None
            Version string from data_format_version field, or None if not found.
        """
        import json

        path = Path(path)
        if path.is_file():
            json_path = path
        else:
            p1 = path / "system.json"
            if p1.exists():
                json_path = p1
            else:
                candidates = list(path.glob("*.json"))
                if not candidates:
                    return None
                json_path = candidates[0]

        try:
            with open(json_path) as f:
                data = json.load(f)
                return data.get("data_format_version") or data.get("data", {}).get("version_info", {}).get(
                    "version"
                )
        except (json.JSONDecodeError, OSError):
            return None


class SiennaUpgrader(PluginUpgrader):
    """Plugin upgrader for Sienna model data."""

    def __init__(
        self,
        path: Path | str,
        steps: list[UpgradeStep] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Sienna upgrader.

        Parameters
        ----------
        path : Path | str
            Path to JSON file or directory containing JSON files.
        steps : list | None
            Optional list of upgrade steps. If None, uses class-level steps.
        **kwargs
            Additional keyword arguments (unused, for compatibility).
        """
        self.path = Path(path)
        if steps is not None:
            # Override the class-level registry for this upgrader instance when provided.
            type(self).steps = steps
