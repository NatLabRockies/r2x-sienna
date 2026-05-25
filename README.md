<div align="center">

# r2x-sienna

**Sienna PSY parser/exporter plugin for the `r2x-core` plugin framework.**

[![CI](https://img.shields.io/github/actions/workflow/status/NatLabRockies/r2x-sienna/ci.yaml?branch=main&label=CI)](https://github.com/NatLabRockies/r2x-sienna/actions/workflows/ci.yaml)
[![Actions Quality](https://img.shields.io/github/actions/workflow/status/NatLabRockies/r2x-sienna/workflow-quality.yaml?branch=main&label=actions-quality)](https://github.com/NatLabRockies/r2x-sienna/actions/workflows/workflow-quality.yaml)
[![Python](https://img.shields.io/badge/python-3.11%20to%203.13-blue)](https://pypi.org/project/r2x-sienna/)
[![PyPI](https://img.shields.io/pypi/v/r2x-sienna)](https://pypi.org/project/r2x-sienna/)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-green)](./LICENSE.txt)

</div>

> [!WARNING]
> This project is currently optimized for internal R2X workflows. You are welcome
> to use it, but APIs and behavior may continue to evolve as `r2x-core` evolves.

`r2x-sienna` integrates Sienna-style PSY data with `r2x-core` and `infrasys`.
It provides parser and exporter plugins, plus version-upgrade utilities for input
JSON, so Sienna data can be loaded into `System` objects and written back out in
PSY-compatible form.

<p align="center">
  <a href="#quickstart">Quickstart</a> ·
  <a href="#installation">Installation</a> ·
  <a href="#what-it-provides">What It Provides</a> ·
  <a href="#usage-with-r2x-core">Usage with r2x-core</a> ·
  <a href="#development">Development</a> ·
  <a href="#license">License</a>
</p>

## Quickstart

Install:

```bash
pip install r2x-sienna
```

Parse a Sienna JSON system into an `infrasys.System`, then export it back to
PSY JSON:

```python
from pathlib import Path

from r2x_core import DataStore, PluginContext
from r2x_sienna import (
    SiennaConfig,
    SiennaExporter,
    SiennaExporterConfig,
    SiennaParser,
)

data_path = Path("tests/data/case5_pjm_rt/c_sys5_pjm_rt.json")
out_path = Path("output/system.json")

# Parse
parse_cfg = SiennaConfig(
    model_year=2029,
    system_name="PJM-5",
    json_path=str(data_path),
)
parse_ctx = PluginContext(config=parse_cfg, store=DataStore(path=data_path.parent))
parsed_system = SiennaParser.from_context(parse_ctx).run().system

# Export
export_cfg = SiennaExporterConfig(output_path=str(out_path))
export_ctx = PluginContext(config=export_cfg, system=parsed_system, store=DataStore(path=out_path.parent))
SiennaExporter.from_context(export_ctx).run()
```

## Installation

### From PyPI

Python requirement: `>=3.11, <3.14`.

```bash
pip install r2x-sienna
```

Using `uv`:

```bash
uv add r2x-sienna
```

### From Source

```bash
git clone https://github.com/NatLabRockies/r2x-sienna.git
cd r2x-sienna
uv sync --all-groups
```

## What It Provides

- `SiennaParser`: reads Sienna PSY JSON and related time series metadata into
  `infrasys.System`.
- `SiennaExporter`: writes `infrasys.System` back to Sienna-compatible PSY JSON,
  including supplemental attributes and optional HDF5 time series export.
- `SiennaUpgrader` and `run_sienna_upgrades(...)`: version-detection and upgrade
  pipeline for legacy JSON data before parsing.
- Plugin entry points for `r2x-core` under the `r2x_plugin` group:
  - `sienna-parser = r2x_sienna:SiennaParser`
  - `sienna-exporter = r2x_sienna:SiennaExporter`

## Usage with r2x-core

`r2x-sienna` follows the `r2x-core` plugin lifecycle.

- Build parser/exporter instances with `PluginContext`.
- Run plugin hooks through `.run()`.
- Access parser/exporter configs through `SiennaConfig` and
  `SiennaExporterConfig`.

The parser `on_upgrade()` hook automatically runs Sienna data upgrades when
`json_path` is provided, then proceeds with deserialization into a `System`.

## Development

Install dev dependencies:

```bash
uv sync --all-groups
```

Run the same checks used in CI:

```bash
uv run prek run --all-files --hook-stage pre-push
```

Targeted commands:

```bash
uv run pytest -q -m "not slow" --maxfail=1 --disable-warnings
uv run ty check ./src/r2x_sienna/
```

## License

BSD 3-Clause. See `LICENSE.txt`.
