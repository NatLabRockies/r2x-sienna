"""R2X Sienna Plugin.
A plugin for parsing Sienna model data into the R2X framework using infrasys components.
"""

from importlib.metadata import version

from loguru import logger

from .plugin_config import SiennaConfig, SiennaExporterConfig
from .exporter import SiennaExporter
from .parser import SiennaParser
from .upgrader.data_upgrader import SiennaUpgrader, SiennaVersionDetector

__version__ = version("r2x_sienna")


# Disable default loguru handler for library usage
# Applications using this library should configure their own handlers
logger.disable("r2x_sienna")


__all__ = [
    "SiennaConfig",
    "SiennaExporterConfig",
    "SiennaParser",
    "SiennaExporter",
    "SiennaUpgrader",
    "SiennaVersionDetector",
    "__version__",
]
