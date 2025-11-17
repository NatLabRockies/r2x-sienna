"""Entry point for plugin system."""

from r2x_core import PluginManifest, PluginSpec, SemanticVersioningStrategy

from .config import SiennaConfig
from .exporter import SiennaExporter
from .parser import SiennaParser
from .upgrader.data_upgrader import SiennaUpgrader, SiennaVersionDetector

manifest = PluginManifest(package="r2x-sienna")

manifest.add(PluginSpec.parser(name="r2x-sienna.parser", entry=SiennaParser, config=SiennaConfig))
manifest.add(PluginSpec.parser(name="r2x-sienna.exporter", entry=SiennaExporter, config=SiennaConfig))
manifest.add(
    PluginSpec.upgrader(
        name="r2x-sienna.upgrader",
        entry=SiennaUpgrader,
        version_strategy=SemanticVersioningStrategy,
        version_reader=SiennaVersionDetector,
        steps=SiennaUpgrader.steps,
        description="Apply upgrades to Sienna system run folders.",
    )
)
