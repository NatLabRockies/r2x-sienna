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
| `json_path` | Parser input JSON path; optional in schema, needed for ordinary disk input. |
| `model_year` | Optional integer or list of integers. |
| `system_name` | Optional label. |
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
