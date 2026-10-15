---
title: "Configure CLI pipelines"
---

Install the package into the [CLI environment](/r2x-sienna/how-to/install/) first.
Plugin references come from the `[project.entry-points."r2x_plugin"]` table in [pyproject.toml](https://github.com/NatLabRockies/r2x-sienna/blob/main/pyproject.toml).

```bash
r2x list r2x-sienna
r2x run plugin sienna-parser --show-help
r2x run plugin sienna-exporter --show-help
```

The generated help reflects the installed package's configuration schema.
Use fully qualified references (`r2x-sienna.sienna-parser`) when composing plugins from multiple packages.

## Share settings

Start from the [tested round-trip pipeline](/r2x-sienna/tutorials/round-trip/).
Move repeated values to `variables` and reference them with `${name}` in `config`.
Parser and exporter configurations are separate: set each plugin's input/output fields explicitly.
Run from the directory containing your relative data paths.

```bash
r2x init pipeline.yaml
r2x run pipeline.yaml --list
r2x run pipeline.yaml round_trip --print
r2x run pipeline.yaml round_trip --dry-run
```

`init` creates a starter file. Replace its example pipeline with your own before running it.
Compare `--print` with the [configuration source](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/plugin_config.py), then execute without preview flags.

For cross-format workflows, insert the appropriate [R2X translator](https://natlabrockies.github.io/R2X/how-to/) between parser and exporter.
These packages provide format ingestion and serialization; a parser/exporter round trip alone does not translate component types.
