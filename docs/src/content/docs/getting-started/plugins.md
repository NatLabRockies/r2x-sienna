---
title: Plugins and workflow
---

`r2x-sienna` provides two registered plugins. Start with the
[pip installation](/r2x-sienna/getting-started/installation/) for Python applications,
or install the package in the separate [r2x-cli](https://natlabrockies.github.io/r2x-cli/) environment for pipelines.

| Registered name | Public class | Role |
| --- | --- | --- |
| `sienna-parser` | [`SiennaParser`](/r2x-sienna/reference/api/#r2x_sienna.SiennaParser) | Read native input and populate the context System. |
| `sienna-exporter` | [`SiennaExporter`](/r2x-sienna/reference/api/#r2x_sienna.SiennaExporter) | Consume a System and write native output. |

This is the complete [`r2x_plugin` registration table](https://github.com/NatLabRockies/r2x-sienna/blob/main/pyproject.toml).
There are no system modifiers registered by this package. Do not expect a model class
or an upgrade helper to appear as a CLI plugin.

The parser reads native PowerSystems.jl JSON and its HDF5 companion into Sienna components. The exporter writes native JSON and time-series storage. Input upgrades run inside parsing and can modify working files; retain originals and copy both companions before starting.

```mermaid
flowchart LR
  Input[Native input] --> Parser[sienna-parser]
  Parser --> System[Typed System]
  System --> Exporter[sienna-exporter]
  Exporter --> Output[Native output]
  System --> Archive[Portable archive for inspection]
```

## Choose your first task

Verify discovery in the runtime where you installed the package:

```bash
r2x list r2x-sienna
```

Expect both names in the table. Inspect their actual installed options before creating a pipeline:

```bash
r2x run sienna-parser --help
r2x run sienna-exporter --help
```

Use [the round-trip tutorial](/r2x-sienna/tutorials/round-trip/) to download pinned public inputs,
parse them, check component counts, export, and inspect an archive. Use
[Python contexts](/r2x-sienna/how-to/python/) when your application needs analysis between steps.
The [Core lifecycle](https://natlabrockies.github.io/r2x-core/references/api/) explains how contexts carry configuration and systems.

For cross-format workflows, use the separate [R2X translation plugins](https://natlabrockies.github.io/R2X/)
and the destination model package. [r2x-reeds](https://natlabrockies.github.io/r2x-reeds/) supplies ReEDS parsing and system modifiers;
those registrations are not part of `r2x-sienna`.
