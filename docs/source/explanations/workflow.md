# Parser, Exporter, and Upgrader Workflow

`r2x-sienna` is implemented as two `r2x-core` plugins plus an upgrade engine.

## Plugin Lifecycle

The normal parse/export lifecycle in scripts is:

1. Build config (`SiennaConfig` for parsing, `SiennaExporterConfig` for exporting).
2. Create `PluginContext` with config and `DataStore`.
3. Instantiate plugin via `from_context(...)`.
4. Execute `.run()`.

For parsing, the lifecycle hooks are conceptually:

1. `on_prepare`: validate source options and read runtime flags.
2. `on_upgrade`: run data upgrades for JSON/HDF5 compatibility.
3. `on_build`: deserialize components, references, supplemental attributes, and time series metadata.

For exporting, the lifecycle hooks are conceptually:

1. `on_validate`: ensure output location is writable.
2. `on_export`: serialize components and supplemental attributes to JSON.
3. `_export_time_series` (optional): emit HDF5 and patch metadata for compatibility.

## Parsing Details

`SiennaParser` supports two input routes:

- `json_path` from `SiennaConfig` (standard script path)
- `_stdin_payload` when invoked by pipeline-style runtimes

During parse, the plugin:

- Normalizes metadata/module/type tags for model resolution
- Builds UUID maps for deferred reference resolution
- Deserializes components in staged passes to resolve nested/cross references
- Restores supplemental attributes and associations
- Reconnects HDF5 time series metadata through `infrasys`

## Exporting Details

`SiennaExporter` serializes a system by:

- Traversing all components and converting supported types with PSY metadata
- Serializing supplemental attributes and component associations
- Writing PSY JSON with `orjson`
- Optionally exporting time series to HDF5 and normalizing embedded metadata for downstream compatibility

When `should_export_time_series` is enabled (default), the exporter writes:

- `<output_stem>_time_series_storage.h5`
- JSON references to storage file and storage type

## Upgrade Engine

`SiennaUpgrader` is a standalone upgrader with version detection and ordered step execution.

- Version detection reads `data_format_version` (or legacy version fields)
- Steps are registered with `@SiennaUpgrader.register_step(...)`
- `run_sienna_upgrades(...)` is the parser-facing wrapper used in plugin hooks

The upgrader applies schema and data fixes before parse, and can also migrate legacy HDF5 time series metadata tables.
See [Upgrader Design](upgrader.md) for the full execution flow, registered
transformations, ordering rules, and HDF5 migration details.

## Why This Architecture

This split keeps responsibilities clear:

- Parser focuses on ingest and object reconstruction
- Exporter focuses on stable serialization output
- Upgrader isolates backward-compatibility logic from core parsing behavior
- Models/units provide strict typing and validation boundaries
