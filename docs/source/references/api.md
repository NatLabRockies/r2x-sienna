# API Reference

## Package Exports

Top-level exports from `r2x_sienna`:

- `SiennaConfig`
- `SiennaExporterConfig`
- `SiennaParser`
- `SiennaExporter`
- `SiennaUpgrader`
- `SiennaVersionDetector`

Compatibility note:

- The packaged `r2x_sienna.models` definitions are maintained to match current
	`PowerSystems.jl` schemas for overlapping model names, with backward-compatible aliases used where
	practical to avoid breaking existing inputs.

## Parser

### `SiennaConfig`

Main parse configuration fields:

- `model_year`: int or list of ints
- `system_name`: optional system label
- `json_path`: input JSON path
- `system_base_power`: base MVA for per-unit calculations
- `scenario`: scenario label
- `skip_validation`: parsing validation toggle
- `models`: model module tuple (default includes `r2x_sienna.models`)

### `SiennaParser`

Primary usage:

```python
parser = SiennaParser.from_context(ctx)
result_ctx = parser.run()
system = result_ctx.system
```

Responsibilities:

- Runs upgrades before build
- Parses components and references
- Restores supplemental attributes and associations
- Connects time series storage metadata when present

## Exporter

### `SiennaExporterConfig`

Main export configuration fields:

- `output_path`: required output JSON path
- `system_base_power`: base MVA
- `scenario`: scenario label
- `models`: model module tuple

### `SiennaExporter`

Primary usage:

```python
exporter = SiennaExporter.from_context(export_ctx)
exporter.run()
```

Runtime behavior:

- Serializes supported components to PSY-compatible dictionaries
- Serializes supported supplemental attributes and associations
- Writes JSON to `output_path`
- Writes HDF5 time series output unless disabled (`should_export_time_series = False`)

## Upgrader

### `SiennaVersionDetector`

Reads version from:

- Top-level `data_format_version`
- Legacy `data.version_info.version`

### `SiennaUpgrader`

Standalone API:

```python
from r2x_core import UpgradeType

upgrader = SiennaUpgrader(path)
result = upgrader.upgrade(upgrade_type=UpgradeType.SYSTEM)
```

Step registration uses class decorators in upgrade-step modules and semantic version strategy from `r2x-core`.

### `run_sienna_upgrades(...)`

Parser-facing helper that:

- Resolves file/folder input from `json_path` or `DataStore`
- Detects/uses current and target versions from context
- Runs system upgrades
- Migrates legacy HDF5 time series metadata when needed
