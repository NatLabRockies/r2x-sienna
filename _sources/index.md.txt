```{toctree}
:maxdepth: 2
:hidden:

install
explanations/index
how-tos/index
references/index
contributing
CHANGELOG
```

# R2X-Sienna Documentation

`r2x-sienna` is an `r2x-core` plugin package for reading and writing Sienna/PowerSystems-style
system data.

It provides:

- A parser plugin (`SiennaParser`) that builds an `infrasys.System` from PSY-style JSON (+ optional HDF5 time series metadata)
- An exporter plugin (`SiennaExporter`) that serializes an `infrasys.System` back to PSY-compatible JSON (+ optional HDF5 time series)
- A version upgrader pipeline (`SiennaUpgrader` and `run_sienna_upgrades`) that normalizes legacy files before parse
- A typed model library (`r2x_sienna.models`) with topology, generation, branch, load, services, costs, attributes, and enum types
- A unit system (`r2x_sienna.units`) built on `pint`/`infrasys` base quantities, including per-unit support through model mixins

## Documentation Map

- [Installation](install.md)
- [Explanations](explanations/index.md): architecture, parser/exporter/upgrader lifecycle, models, and units
- [How-To Guides](how-tos/index.md): script-based workflows and practical examples
- [Reference](references/index.md): API summary, model catalog, and units reference
- [Contributing](contributing.md)

## Core Workflow

1. Create parser configuration (`SiennaConfig`) pointing to an input JSON.
2. Build a `PluginContext` and run `SiennaParser.from_context(ctx).run()`.
3. Work with the resulting `infrasys.System` in your script.
4. Create exporter configuration (`SiennaExporterConfig` or compatible config with `output_path`).
5. Run `SiennaExporter.from_context(export_ctx).run()` to emit PSY JSON (+ HDF5 when enabled).

The parser automatically invokes upgrade steps before deserialization when `json_path` is provided,
which helps keep old datasets compatible with current model definitions.

## Quick Example

```python
from pathlib import Path

from r2x_core import DataStore, PluginContext
from r2x_sienna import SiennaConfig, SiennaExporter, SiennaExporterConfig, SiennaParser

input_json = Path("tests/data/case5_pjm_rt/c_sys5_pjm_rt.json")
output_json = Path("output/system.json")

# Parse
parse_cfg = SiennaConfig(model_year=2029, system_name="PJM-5", json_path=str(input_json))
parse_ctx = PluginContext(config=parse_cfg, store=DataStore(path=input_json.parent))
system = SiennaParser.from_context(parse_ctx).run().system

# Export
export_cfg = SiennaExporterConfig(output_path=str(output_json))
export_ctx = PluginContext(config=export_cfg, system=system, store=DataStore(path=output_json.parent))
SiennaExporter.from_context(export_ctx).run()
```

## Indices and Tables

- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`
