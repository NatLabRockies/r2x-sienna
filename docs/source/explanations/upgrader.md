# Upgrader Design

The Sienna upgrader keeps older PowerSystems.jl and InfrastructureSystems data
readable by the current parser. It runs before component deserialization, so
the parser only needs to handle the current model and metadata schema.

## Upgrade Flow

When `SiennaParser` is run with a disk-backed `json_path`, the flow is:

1. Resolve the input path. A path may be a JSON file or a directory containing
   `system.json` or another JSON system file.
2. Detect the source version from top-level `data_format_version`. Legacy files
   are also checked at `data.version_info.version`.
3. Determine the target version from the plugin context. If no target is set,
   the registered latest upgrade target is used.
4. Select registered steps with `r2x-core` semantic-version comparisons.
5. Run each applicable step in priority and target-version order against the
   in-memory JSON document.
6. Write the JSON document back only when at least one step changed it.
7. Inspect the JSON for a referenced HDF5 time-series file and migrate its
  embedded metadata when the file exists and the legacy layout is detected.
8. Continue with parser deserialization.

The parser calls this flow from `SiennaParser.on_upgrade()`. Automatic upgrades
are therefore file-backed: provide `json_path` in `SiennaConfig`. A stdin
payload has no source file to rewrite and should be upgraded separately before
it is passed to a parser context when compatibility transformations are needed.

## Step Registration And Ordering

Steps are registered with the `SiennaUpgrader.register_step` decorator:

```python
@SiennaUpgrader.register_step(
    target_version="5.999",
    upgrade_type=UpgradeType.SYSTEM,
    priority=100,
)
def upgrade_example(system_data):
    return system_data
```

Each step declares:

- `target_version`: the schema version produced by the step
- `upgrade_type`: `SYSTEM` for a JSON system transformation or `FILE` for a
  `r2x-core` path-based upgrade
- `priority`: higher values run first when several steps share a target version

All currently registered Sienna schema transformations target `5.999`. The
upgrader compares every step with the original detected version, allowing all
steps targeting the same version to run during one upgrade. A step that does
not apply is skipped; an already-current file is left unchanged.

## Current JSON Transformations

The registered system steps currently handle these compatibility cases:

- **Hydro model split:** converts `HydroEnergyReservoir` into a
  `HydroReservoir` and `HydroTurbine`, and converts `HydroPumpedStorage` into a
  `HydroPumpTurbine` with head and tail reservoirs. New UUIDs and references are
  created where required by time-series ownership.
- **Hydro prime movers:** fills missing `prime_mover_type` values for hydro
  turbine and pump-turbine components.
- **Bus validation:** resets out-of-range AC bus angles to a valid default.
- **Transformer fields:** repairs two-winding, tap, phase-shifting, three-
  winding, and phase-shifting three-winding transformer fields using connected
  bus voltages, arc relationships, and system base power.
- **AC branch limits:** fills missing `rating_b` and `rating_c` values for
  `Line` and `MonitoredLine` components.
- **HVDC naming:** renames legacy `TwoTerminalHVDCLine` metadata to
  `TwoTerminalGenericHVDCLine`.
- **Removed containers:** removes obsolete `time_series_container` fields from
  components.
- **Geographic attributes:** normalizes legacy geographic coordinate layouts to
  GeoJSON-style `{coordinates, type}` data and sanitizes malformed coordinates.
- **PSY5 fields:** copies the legacy `comformity` load field to canonical
  `conformity` and supplies the default `TransmissionInterface.violation_penalty`
  when it is absent.

Steps generally mutate the loaded dictionary in place and return it. Missing or
irrelevant data is skipped, while malformed data that prevents a step from
completing returns an error from the upgrader and stops parsing.

## HDF5 Metadata Migration

If the JSON references a time-series storage file, the upgrader can update the
embedded SQLite metadata database inside the HDF5 file. The migration handles:

- Legacy `time_series_associations` layouts using `resolution_ms` or missing
  `metadata_uuid` columns
- Millisecond resolutions converted to ISO-8601 durations
- Strict initial timestamp normalization for InfrastructureSystems readers
- Missing or stale metadata UUID references
- Deterministic-series periods and association metadata
- PowerSystems scaling-factor multiplier payloads

The HDF5 file is rewritten only when migration is needed. If the referenced
storage file is absent, the JSON upgrade can still complete; no HDF5 migration
is attempted.

## Standalone Usage

Use `SiennaUpgrader` directly when an application needs to upgrade data before
constructing a parser context:

```python
from pathlib import Path

from r2x_core import UpgradeType
from r2x_sienna import SiennaUpgrader

upgrader = SiennaUpgrader(Path("input/system.json"))
result = upgrader.upgrade(upgrade_type=UpgradeType.SYSTEM)

if result.is_err():
    raise RuntimeError(result.err())
```

`current_version`, `target_version`, `strategy`, and a custom step list can be
provided when an application needs controlled or partial upgrades. The result
is a `rust_ok.Result`: successful upgrades contain the resolved path, while
failures contain a descriptive error string.