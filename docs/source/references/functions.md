# Functions Reference

These helpers are useful when integrating Sienna parsing and exporting into an
existing application. Parser and exporter plugins remain the preferred API for
new `r2x-core` integrations.

## Export Helpers

### `to_psy(config, system, system_data, filename, *, write_year=None, **kwargs)`

Legacy compatibility function for exporting an `infrasys.System` to PSY JSON.
It creates a `SiennaExporterConfig`, validates the output directory, writes JSON,
and exports HDF5 time-series data when the exporter has it enabled. New code
should construct `SiennaExporter` with a `PluginContext` instead.

### `default_system_information()`

Returns the default PSY system-information dictionary used when the source
system has no preserved system metadata. It includes units settings, frequency,
run-check settings, metadata, and the PSY data-format version.

### `serialize_component_to_psy(component)`

Converts a supported Sienna component and its fields into the PSY-compatible
serialized representation. Unsupported components return `None` and are
skipped by `SiennaExporter`.

### `serialize_supplemental_attributes(system)`

Serializes supported supplemental attributes and their component associations
into an `attributes`/`associations` dictionary suitable for the PSY data section.

### `set_time_series_scaling_factor_multiplier(system, owner, name, function_name)`

Associates a PowerSystems scaling function with an existing time series. The
function raises `ValueError` when the function name is empty or the named series
is not attached to the owner.

### `get_magnitude(field)`

Returns the numeric magnitude of either a scalar or a `pint.Quantity`, which is
used by model getters and serializers.

## Upgrade Helpers

### `run_sienna_upgrades(*, json_path=None, store=None, ctx)`

Runs registered system upgrade steps using a parser context. `json_path` takes
precedence over `store`; one of them must be supplied. The helper also upgrades
referenced HDF5 time-series metadata when the JSON points to a storage file.

### `SiennaVersionDetector.read_version(path)`

Reads the data version from `data_format_version` or the legacy
`data.version_info.version` location.

### `SiennaUpgrader.upgrade(*, current_version=None, target_version=None, strategy=None, upgrade_type=...)`

Applies registered upgrade steps in version order. It supports file and system
upgrade modes and returns a `rust_ok.Result` containing the upgraded path or an
error string.

## Model Getters

### `get_value(value, component)`

Returns a value normalized for the component's system base power. It supports
plain numbers, `MinMax`, and `pint.Quantity` values.

### `get_max_active_power(component)`

Returns the component's maximum active-power limit, applying the component's
per-unit multiplier when available.

### `get_ramp_limits(component)`

Returns the component's up/down ramp limits, applying the same per-unit handling
used by active-power getters.
