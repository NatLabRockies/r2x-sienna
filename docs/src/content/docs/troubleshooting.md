---
title: Troubleshooting
---

Use the error text or the incorrect result below. The commands use the
[public-fixture tutorial](/r2x-sienna/tutorials/round-trip/) directory; replace only
its paths when diagnosing a study. Preserve original inputs and diagnose a working
copy. `PluginError` adds the lifecycle stage to underlying errors; the stage alone
does not identify their cause.

## Plugin is missing

If the CLI cannot resolve `sienna-parser`, or Python cannot import `r2x_sienna`, first
identify **which interpreter** failed. A project installation and the CLI runtime
are separate. These checks do not install or modify packages:

```bash
r2x python show
```

```bash
r2x list r2x-sienna
```

The list must include `sienna-parser` and `sienna-exporter`. If absent, follow the
[CLI installation path](/r2x-sienna/getting-started/installation/#use-the-cli-plugin)
in that same runtime, then repeat `list`. If Python scripts fail instead, check:

```bash
python -c "import sys; print(sys.executable)"
```

```bash
python -c "from importlib.metadata import version; print(version('r2x-sienna'))"
```

A version printed by one interpreter does not establish availability in another.
Select the environment from [environment setup](/r2x-sienna/getting-started/environment/)
and rerun the exact import that failed.

For `Python ABI ... is incompatible with this r2x binary`, use the runtime required
by that binary; the tested CLI 0.1.15 binary required Python 3.12. Do not change a
project's Python and assume the executable ABI changed. Verify with `r2x python show`
and the [CLI runtime guidance](https://github.com/NatLabRockies/r2x-cli/blob/main/docs/development.md).

For `option '--show-help' requires a value`, use the tested current help command:

```bash
r2x run sienna-parser --help
```

Success prints the plugin's actual configuration flags. Use those flags for the
installed release rather than copying legacy Core CLI options.

## `No such file or directory`, JSON decoding error, or `Failed to build system: 'data'`

A missing path, malformed JSON, and the wrong JSON format need different fixes.
Run these checks in the same directory from which the pipeline failed:

```bash
python -m json.tool inputs/test_system.json > /dev/null
```

A zero exit status establishes JSON syntax only. A filename error means the path
is wrong; a decoding error means the file is truncated/malformed. Restore a fresh
copy from the producer or the pinned tutorial download before parsing it again.
For Windows PowerShell, omit `> /dev/null` if that shell does not provide it.

To identify the format, save this as `check_native.py`:

```python doctest
>>> import json
>>> from pathlib import Path
>>> path = Path("inputs/test_system.json")
>>> data = json.loads(path.read_text())
>>> print("Top-level keys:", sorted(data))
Top-level keys: ['data', 'data_format_version', 'frequency', 'internal', 'metadata', 'runchecks', 'units_settings']
>>> print("Data version:", data.get("data_format_version"))
Data version: 5.0.0
>>> native = data.get("data")
>>> print("Has native components:", isinstance(native, dict) and isinstance(native.get("components"), list))
Has native components: True
```

```bash
python check_native.py
```

For the pinned fixture, expect data version `5.0.0` and `Has native components:
True`. The parser expects native components under `data.components`; an Infrasys
JSON serialization uses a different schema. The wrong-schema failure `'data'` was
reproduced with a JSON document lacking that native envelope.

**Fix:** point `json_path` at the original native PSY file. Use `r2x read` for the
separate Infrasys archive, as described below. Renaming a file does not convert
formats. **Verify:** run the checker again, then rerun the tutorial pipeline and
its ten-bus component check. See [native input reader](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/parser.py).

## `Time series file not found: ... Skipping HDF5 loading` or `Failed to load time series data`

The current parser may log these messages and still return a System. A successful
parse is therefore not a complete time-series verification. Diagnose the filename
recorded in the native JSON with this read-only check:

```python doctest
>>> import json
>>> from pathlib import Path
>>> path = Path("inputs/test_system.json").resolve()
>>> data = json.loads(path.read_text())["data"]
>>> name = data.get("time_series_storage_file")
>>> print("Recorded storage:", name)
Recorded storage: test_system_time_series_storage.h5
>>> if name:
...     recorded = Path(name)
...     resolved = recorded if recorded.is_absolute() else path.parent / recorded.name
...     print("Resolved storage:", resolved.name)
...     print("Exists:", resolved.is_file())
...
Resolved storage: test_system_time_series_storage.h5
Exists: True
```

For the fixture, expect `test_system_time_series_storage.h5` and `Exists: True`.
The parser resolves relative recorded names beside the JSON, using the basename
when a relative path contains directories. An absolute recorded path stays
absolute. A missing `time_series_storage_file` field means this JSON does not
request a companion through that field; it does not prove that the study should
have no time series.

**Fix for missing storage:** restore the producer's matching HDF5 companion beside
the JSON with its original name. Do not copy an unrelated HDF5 file into its place.
The docs reproduction confirmed that JSON-only parsing can return a System;
restoring the original companion made the same pair readable again.

**If the file exists but HDF5 cannot open it**, check file access independently:

```python doctest
>>> import h5py
>>> with h5py.File(resolved, "r") as storage:
...     print("HDF5 groups:", list(storage))
...
HDF5 groups: ['time_series', 'time_series_metadata']
```

Run this after the resolution block above. An HDF5 open error narrows the problem
to file access, corruption, locking or unsupported storage. `unable to lock file`
was observed when two validation processes touched one working copy. Close the
other process or use separate complete copies; do not disable HDF5 locking as a
generic fix. A metadata-layout error after a successful open needs the exact
reader/writer versions and full log, not hand-edited SQLite/HDF5 metadata.

**Verify:** rerun parsing on one writable working copy, check that the HDF5 warning
is gone, and query the expected owner/name/type with the
[inspection guide](/r2x-sienna/how-to/inspect-system/). A default single-series query
returning zero does not establish that deterministic or other series are absent.
See [storage loading](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/parser.py) and [metadata migration](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/upgrader/data_upgrader.py).

## `Failed to deserialize ... component(s)` or a quantity validation error

The error names the rejected components; the preceding log identifies the field.
Recognizable validation text includes `Input should be greater than 0` for bus
numbers and `Unit must be compatible with kilovolt` for voltage quantities.
For example, `ACBus.number` is a positive integer, and `base_voltage` requires
units compatible with kilovolt. Both invalid bus number 0 and a voltage expressed
in MW were reproduced through the public model constructor.

Check the installed schema rather than guessing defaults:

```python doctest
>>> from r2x_sienna.models import ACBus
>>> assert "number" in ACBus.model_fields
>>> assert "base_voltage" in ACBus.model_fields
```

To validate a proposed corrected bus in application code:

```python doctest
>>> from r2x_sienna.models import ACBus
>>> from r2x_sienna.units import ureg
>>> bus = ACBus(name="CheckedBus", number=1, base_voltage=230 * ureg.kV)
>>> assert bus.number == 1
>>> assert bus.base_voltage.to("kilovolt").magnitude == 230
```

Expect `1` and a voltage quantity in kV. This tests the field contract; it is not a
replacement for the rejected network bus or its UUID relationships.

**Fix:** correct the source model/export that produced the invalid field, or use
an explicitly supported schema migration for its actual source version. Keep
validation enabled while diagnosing it. `skip_validation=True` does not fix bad
references, units or missing required fields.

**Verify:** regenerate a working JSON/HDF5 pair, rerun the parser, and compare
component counts and the named failed components with the source. The
[invalid-second-bus regression](https://github.com/NatLabRockies/r2x-sienna/blob/main/tests/test_parser.py) verifies that
one valid bus must not hide a later invalid bus. Historical schema mismatches are
recorded in [closed issue #11](https://github.com/NatLabRockies/r2x-sienna/issues/11) and [closed issue #13](https://github.com/NatLabRockies/r2x-sienna/issues/13);
compare your installed model definitions with the intended PowerSystems.jl release,
not just those issue titles. See [model catalog](/r2x-sienna/reference/models/) and
[units](/r2x-sienna/reference/units/).

## `Could not determine Sienna version` or `Failed <upgrade step>: ...`

The standalone upgrader returns `Err` when it cannot detect a version. Detection
may also return `None` for malformed JSON or a directory with no JSON files.
That result alone does not distinguish those cases. After the syntax/schema
check above, inspect the actual detector result:

```python doctest
>>> from pathlib import Path
>>> from r2x_sienna import SiennaVersionDetector
>>> print(SiennaVersionDetector().read_version(Path("inputs/test_system.json")))
5.0.0
```

For the pinned fixture this prints `5.0.0`. The detector checks top-level
`data_format_version`, then legacy `data.version_info.version`.

**Fix:** use the complete original producer export with its version information.
If a valid historical file lacks it, establish the version from the producer's
records before choosing the upgrader's documented `current_version` argument.
Do not invent a version or edit JSON metadata to force a transition.
A named failed step needs its source/target versions and component data; there is
no general command that repairs every schema. Parsing may skip unknown-version
upgrades and later fail during build, whereas standalone upgrade reports the
detection error directly.

**Verify:** rerun the detector, run upgrades only on a copy as shown in
[Python usage](/r2x-sienna/how-to/python/#upgrade-a-copy-independently), then parse and
inspect the result. `Err` handling and supported arguments are in the
[API reference](/r2x-sienna/reference/#standalone-version-and-upgrade-api).
Tests cover [unknown version and malformed JSON paths](https://github.com/NatLabRockies/r2x-sienna/blob/main/tests/test_data_upgrader.py).

## `Cannot create HydroReservoir inflow series: model_year is not configured ...`

The parser could not derive the timestamp needed by its compatibility time-series
step: no configured `model_year` and no existing series timestamp were available.
This exact failure reproduced on a minimal native JSON system with no storage;
setting `model_year=2029` allowed the same minimal input to build.

Check the parser's configuration, not just the exporter's year:

```bash
r2x run pipeline.yaml round_trip --print
```

In Python, inspect the same value with `print(config.model_year)`. A list uses its
first year for this step. **Fix:** configure the intended study year on
`sienna-parser`, or restore the source storage that should supply the timestamp.
Do not choose an arbitrary year merely to silence the error.

**Verify:** rerun and inspect timestamps, resolution and length on the intended
hydro components using `system.list_time_series(component)`. The current
[compatibility helper](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/parser.py) creates an hourly 8,760-point zero-inflow
series when needed; that is a fallback, not recovered source inflow. In a leap-year
study, do not infer full calendar coverage from a successful parse—compare with
your expected timestamp grid and actual source profiles. No production hydro-data
recovery or Julia solve was performed for this documentation.

## `output_path Field required`, `Path does not exist`, or export cannot be read by Julia

`SiennaExporterConfig` requires `output_path`. Separately, constructing a Core
`DataStore` requires its directory to exist. These are different setup failures;
the exporter's parent-directory hook cannot run before a failing store constructor.
Use the public setup pattern:

```python doctest
>>> from pathlib import Path
>>> from r2x_core import DataStore
>>> from r2x_sienna import SiennaExporterConfig
>>> output = Path("outputs/recovered.json")
>>> _ = output.parent.mkdir(parents=True, exist_ok=True)
>>> config = SiennaExporterConfig(output_path=str(output))
>>> store = DataStore(path=output.parent)
>>> assert Path(store.folder).is_dir()
```

**Verify:** run the complete [Python exporter example](/r2x-sienna/how-to/python/), then
check both the JSON and its recorded HDF5 companion with the storage diagnostic
above, substituting the output path. `should_export_time_series=False` is appropriate
only for a consumer intentionally accepting component-only output.

A Julia field/type rejection after successful Python export is a separate
compatibility boundary. Record the PowerSystems.jl and InfrastructureSystems.jl
versions and rejected component/field. Compare [model source](https://github.com/NatLabRockies/r2x-sienna/tree/main/src/r2x_sienna/models)
and [registered upgrades](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/upgrader/upgrade_steps.py) with that consumer.
Use a supported package/schema combination; do not remove fields or rewrite class
metadata by hand. **Verification requires loading the native JSON/HDF5 pair in
that Julia environment.** Python checks alone cannot establish that recovery.

## Archive loading fails

Native PSY JSON is not the Infrasys archive produced for Python inspection.
Choose the reader according to the actual artifact:

| Artifact | Reader |
| --- | --- |
| Native PSY JSON and HDF5 | `sienna-parser` |
| Portable `system.zip` from the tutorial | `r2x read ... --zip` or `System.load` |
| Infrasys JSON from `to_json` | `System.from_json`, retaining sibling storage |

Verify the tutorial archive with its supplied script:

```bash
r2x read outputs/system.zip --zip --exec inspect_system.py
```

Expect ten ACBus instances and six PowerLoad instances for that pinned fixture.
Module import or schema errors need compatible reader/writer packages; use
[environment checks](#plugin-is-missing) and [release/source matching](/r2x-sienna/reference/versions/).
If only `sys.info()` fails with `no such table: supplemental_attribute_associations`,
run scripted component queries without `sys.info()` or `--interactive`, preserve
the archive, and report the metadata failure. This known
[ecosystem summary issue](https://natlabrockies.github.io/R2X/troubleshooting/#summary-fails-with-supplemental_attribute_associations)
does not prove the graph is empty. The workaround does not repair associations.

## Report a reproducible failure

Include these items in a [package issue](https://github.com/NatLabRockies/r2x-sienna/issues):

- Exact command or small public-API script, working directory, and failing lifecycle stage.
- `r2x --version`, `r2x python show`, and package versions from the interpreter that failed.
- Complete error and the log path printed by the CLI; remove confidential data/paths before sharing.
- Minimal native input plus required companion files, or the complete failing archive and its writer's versions.
- Expected versus observed names/counts, timestamp range, resolution and units; target PowerSystems.jl/InfrastructureSystems.jl versions when relevant.
- Which diagnostic above passed or failed, the one change tried, and the verification result.

During this docs update, failures were reproduced on disposable fixture copies and
small synthetic inputs, and 4 focused package regressions passed. Native-file
parse/export and archive inspection were verified. No Julia consumer or production study data was available for cross-version recovery testing.
