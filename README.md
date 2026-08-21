<h1 align="center">r2x-sienna</h1>

<p align="center">
  <strong>Translate Sienna PSY JSON models to and from the R2X ecosystem.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/r2x-sienna/"><img src="https://img.shields.io/pypi/v/r2x-sienna.svg" alt="PyPI version"></a>
  <a href="https://pypi.org/project/r2x-sienna/"><img src="https://img.shields.io/pypi/pyversions/r2x-sienna.svg" alt="Supported Python versions"></a>
  <a href="https://github.com/NatLabRockies/r2x-sienna/actions/workflows/ci.yaml"><img src="https://github.com/NatLabRockies/r2x-sienna/actions/workflows/ci.yaml/badge.svg" alt="CI status"></a>
  <a href="https://natlabrockies.github.io/r2x-sienna/"><img src="https://img.shields.io/badge/docs-latest-blue.svg" alt="Documentation"></a>
  <a href="https://github.com/NatLabRockies/r2x-sienna/actions/workflows/workflow-quality.yaml"><img src="https://github.com/NatLabRockies/r2x-sienna/actions/workflows/workflow-quality.yaml/badge.svg" alt="Workflow quality"></a>
</p>

`r2x-sienna` is an [R2X Core](https://github.com/NatLabRockies/r2x-core)
plugin for reading Sienna/PowerSystems JSON data into typed
`infrasys.System` objects and writing those systems back to PSY-compatible JSON.
It supports Python workflows and repeatable `r2x` CLI pipelines.

> [!WARNING]
> This project is currently optimized for internal R2X workflows. APIs and
> behavior may continue to evolve as `r2x-core` evolves.

## What it does

- **Parse Sienna models**: Read PSY JSON components, references, supplemental attributes, and time-series metadata.
- **Export R2X systems**: Write PSY-compatible JSON with supplemental attributes and optional HDF5 time-series storage.
- **Upgrade legacy data**: Apply ordered schema transformations and migrate legacy HDF5 metadata before parsing.
- **Round-trip models**: Parse, inspect or transform a system, then export it again in Sienna-compatible form.
- **Provide typed models**: Expose topology, branch, generation, load, service, cost, attribute, enum, and unit definitions.
- **Compose pipelines**: Connect the Sienna parser and exporter with other R2X plugins through YAML pipelines.

## Installation

Using [uv](https://docs.astral.sh/uv/):

```console
uv add r2x-sienna
```

Or using pip:

```console
python -m pip install r2x-sienna
```

The package supports Python 3.11, 3.12, and 3.13. To verify installation
and plugin discovery:

```console
python -c "import r2x_sienna; print(r2x_sienna.__version__)"
r2x list
```

The CLI executable is `r2x`. Its discovered plugin names include
`sienna-parser` and `sienna-exporter`.

## Python quick start

### Parse a Sienna JSON system

The parser is initialized with an R2X Core `PluginContext`. The parser runs
registered Sienna upgrades when `json_path` is provided.

```python
from pathlib import Path

from r2x_core import DataStore, PluginContext
from r2x_sienna import SiennaConfig, SiennaParser

json_path = Path("input/system.json")
config = SiennaConfig(
  json_path=str(json_path),
  model_year=2029,
  system_name="PJM-5",
)
context = PluginContext(config=config, store=DataStore(path=json_path.parent))

result_context = SiennaParser.from_context(context).run()
system = result_context.system
if system is None:
  raise RuntimeError("No system returned")
print(system.name)
```

### Export a system to Sienna PSY JSON

Pass the parsed or transformed system to the exporter through a context. HDF5
time-series storage is exported alongside the JSON by default.

```python
from pathlib import Path

from r2x_core import DataStore, PluginContext
from r2x_sienna import SiennaExporter, SiennaExporterConfig

output_path = Path("output/system.json")
config = SiennaExporterConfig(output_path=str(output_path))
context = PluginContext(
  config=config,
  system=system,
  store=DataStore(path=output_path.parent),
)

SiennaExporter.from_context(context).run()
```

Set `exporter.should_export_time_series = False` before `run()` when only JSON
output is needed.

### Upgrade a system independently

Use `SiennaUpgrader` when data must be upgraded before building a parser context:

```python
from pathlib import Path

from r2x_core import UpgradeType
from r2x_sienna import SiennaUpgrader

result = SiennaUpgrader(Path("input/system.json")).upgrade(
  upgrade_type=UpgradeType.SYSTEM,
)
if result.is_err():
  raise RuntimeError(result.err())
```

## R2X CLI pipelines

Use a pipeline when parsing, transformations, and exporting should run as one
reproducible workflow. Create a starter file with:

```console
r2x init sienna-pipeline.yaml
```

The following example parses a Sienna system and exports it again:

```yaml
variables:
  input_json: /data/input/system.json
  output_json: /data/output/system.json
  system_name: PJM-5
  model_year: 2029

pipelines:
  round_trip:
    - r2x-sienna.sienna-parser
    - r2x-sienna.sienna-exporter

config:
  r2x-sienna.sienna-parser:
    json_path: ${input_json}
    system_name: ${system_name}
    model_year: ${model_year}

  r2x-sienna.sienna-exporter:
    output_path: ${output_json}

output_folder: /data/output
```

Inspect and run the pipeline with:

```console
r2x list
r2x run sienna-pipeline.yaml round_trip --print
r2x run sienna-pipeline.yaml round_trip --dry-run
r2x run sienna-pipeline.yaml round_trip
```

Transformations from other R2X plugins can be inserted between the parser and
exporter. Use `r2x list` to find installed plugin references.

For direct plugin usage and schema-generated options:

```console
r2x run plugin sienna-parser --show-help
r2x run plugin sienna-exporter --show-help
```

## Documentation

The complete documentation includes tutorials, task-focused recipes,
architecture explanations, API details, model catalogs, upgrader behavior, and
pipeline examples:

- [Documentation site](https://natlabrockies.github.io/r2x-sienna/)
- [How-to guides](https://natlabrockies.github.io/r2x-sienna/how-tos/)
- [Architecture explanations](https://natlabrockies.github.io/r2x-sienna/explanations/)
- [API reference](https://natlabrockies.github.io/r2x-sienna/references/)
- [CLI guide](https://natlabrockies.github.io/r2x-sienna/how-tos/r2x-cli.html)
- [Upgrader design](https://natlabrockies.github.io/r2x-sienna/explanations/upgrader.html)

## Development

Install development dependencies from source:

```console
git clone https://github.com/NatLabRockies/r2x-sienna.git
cd r2x-sienna
uv sync --all-groups
```

Run the same checks used in CI:

```console
uv run prek run --all-files --hook-stage pre-push
```

Targeted commands:

```console
uv run pytest -q -m "not slow" --maxfail=1 --disable-warnings
uv run ty check ./src/r2x_sienna/
```

## Contributing

- [Issues](https://github.com/NatLabRockies/r2x-sienna/issues)
- [Pull requests](https://github.com/NatLabRockies/r2x-sienna/pulls)
- [Labels](https://github.com/NatLabRockies/r2x-sienna/labels)

## License

This project is distributed under the [BSD 3-Clause License](LICENSE.txt).
