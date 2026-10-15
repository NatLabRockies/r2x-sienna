---
title: "Public API and configuration"
---

The supported top-level imports are declared in [`r2x_sienna.__all__`](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/__init__.py).
Source links point to current `main`; for an installed release use [tagged source](/r2x-sienna/reference/versions/).

| Export | Contract and source |
| --- | --- |
| `SiennaConfig` | Parser settings; [fields](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/plugin_config.py). |
| `SiennaExporterConfig` | Export settings with required `output_path`; [fields](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/plugin_config.py). |
| `SiennaParser` | Context-bound PSY JSON parser; [implementation](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/parser.py). |
| `SiennaExporter` | JSON/HDF5 exporter; [implementation](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/exporter.py). |
| `SiennaUpgrader`, `SiennaVersionDetector` | Schema migration and version reading; [implementation](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/upgrader/data_upgrader.py). |

## Plugin lifecycle

Both parser and exporter use the core `Plugin.from_context(ctx)` class method and `run(*, ctx=None)` method.
`run()` returns the updated context and raises `PluginError` if a lifecycle hook returns an error.
The parser supplies `context.system`; the exporter consumes it and writes files.
[Core lifecycle source](https://github.com/NatLabRockies/r2x-core/blob/main/src/r2x_core/plugin_base.py) defines ordering and failure handling.

## Configuration fields

These are the package-specific settings. Inherited settings and validation are defined by [R2X Core](https://github.com/NatLabRockies/r2x-core/blob/main/src/r2x_core/plugin_config.py).

| Field | Meaning |
| --- | --- |
| `json_path` | `str \| None`, default `None`; needed for ordinary disk input. |
| `model_year` | `int \| list[int] \| None`, default `None`. |
| `system_name` | `str \| None`, default `None`; parsed system uses `Sienna` when unset. |
| `system_base_power` | Base MVA, defaults to 100.0 on parser and exporter. |
| `scenario` | Defaults to `base`. |
| `skip_validation` | Parser flag, defaults to false. |
| `models` | Module tuple, defaults to `("r2x_sienna.models",)`. |
| `output_path` | Optional on `SiennaConfig`; required string on `SiennaExporterConfig`. |

Inspect the installed schema rather than assuming current defaults apply to an older release:

```python
from r2x_sienna import SiennaConfig, SiennaExporterConfig

print(SiennaConfig.model_json_schema())
print(SiennaExporterConfig.model_json_schema())
```

## Model and helper modules

Component definitions live in [`r2x_sienna.models`](https://github.com/NatLabRockies/r2x-sienna/tree/main/src/r2x_sienna/models).
Topology, generation, branches, loads, services, costs, attributes, enums, and units describe the PSY serialization model. These definitions do not guarantee compatibility with every PowerSystems.jl release.
Follow [Python usage](/r2x-sienna/how-to/python/) for a complete context example.

## Construction and execution signatures

```python
SiennaParser.from_context(ctx: PluginContext[ConfigT]) -> Plugin[ConfigT]
SiennaExporter.from_context(ctx: PluginContext[ConfigT]) -> Plugin[ConfigT]
plugin.run(*, ctx: PluginContext[ConfigT] | None = None) -> PluginContext[ConfigT]
```

These parser/exporter classes inherit these methods from the [Core lifecycle](https://github.com/NatLabRockies/r2x-core/blob/main/src/r2x_core/plugin_base.py).
`from_context` binds configuration, system and store; `run` executes the normal
hook order. A parser produces `ctx.system`; an exporter requires an input System
and returns a context after writing files. A hook returning `Err` becomes a
`PluginError`, not an `Err` returned by `run`.

Configuration classes are Pydantic models. Invalid types or a missing required
field raise validation errors during construction, before plugin execution.
Inspect `model_json_schema()` from your installed package when generating a UI or
validating YAML. Package fields listed above do not replace inherited Core options.

## Standalone version and upgrade API

```python
SiennaVersionDetector().read_version(folder_path: Path) -> str | None
SiennaUpgrader(path: Path).upgrade(
    *,
    current_version: str | None = None,
    target_version: str | None = None,
    strategy: VersionStrategy | None = None,
    upgrade_type: UpgradeType = UpgradeType.FILE,
) -> Result[Path, str]
```

`read_version` returns a detected version or `None`. `upgrade` returns a path on
success or an error string in `Result`; it does not return PluginContext.
Use `UpgradeType.SYSTEM` for the JSON-system transformations shown in
[Python usage](/r2x-sienna/how-to/python/#upgrade-a-copy-independently).
This API can rewrite input files. The parser-facing upgrade path can also migrate
legacy metadata in referenced HDF5 storage. See [upgrader source](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/upgrader/data_upgrader.py).

## Export controls and limits

`SiennaExporter.output_path` resolves the required configuration string to a Path.
Its `on_validate` hook creates missing output parents. A separate `DataStore`
constructor still requires an existing directory; create it before the context.
`should_export_time_series` is an instance attribute defaulting to `True`; set it
before `run()` for JSON-only output. It is not an exporter configuration field.

Serialization skips unsupported component types when
`serialize_component_to_psy(component)` returns `None`. Successful file creation
therefore does not establish that every input object was exported. Inspect counts
and parser/exporter logs and load the result in the target Julia environment.
For model vocabulary use the [model catalog](/r2x-sienna/reference/models/); for units
and per-unit assumptions use [units](/r2x-sienna/reference/units/).
