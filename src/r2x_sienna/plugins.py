"""Plugin exports for r2x-sienna package.

This module provides direct class exports for the r2x-sienna plugin system.
The new r2x-core 0.2.x pattern uses direct class exports instead of PluginManifest.
"""

from r2x_sienna import SiennaConfig, SiennaExporter, SiennaParser
from r2x_sienna.upgrader.data_upgrader import SiennaUpgrader, SiennaVersionDetector

# Main plugins - direct class references for entry points
parser = SiennaParser
exporter = SiennaExporter
config = SiennaConfig

__all__ = [
    # Classes
    "SiennaConfig",
    "SiennaExporter",
    "SiennaParser",
    "SiennaUpgrader",
    "SiennaVersionDetector",
    # Plugin references
    "config",
    "exporter",
    "parser",
]
