---
title: "Parse, inspect, and export with Python"
---

Start from the downloaded inputs in the [round-trip tutorial](/r2x-sienna/tutorials/round-trip/).
Install `r2x-sienna` into your active Python environment with
`python -m pip install r2x-sienna`. The CLI's managed environment is separate;
use its printed interpreter if you want the exact same dependencies.

The example creates a parser context, runs it, inspects its returned System,
and sends that System to a separate exporter context. Export configuration does
not retroactively change parser settings. Keep JSON and HDF5 working copies together because upgrades can modify them.
Copy the console input below without `>>>`/`...` prompts into `python_roundtrip.py` in the tutorial workspace:

```python doctest
>>> from pathlib import Path
>>> from r2x_core import DataStore, PluginContext
>>> from r2x_sienna import SiennaConfig, SiennaExporterConfig, SiennaParser, SiennaExporter
>>> json_path = Path("inputs/test_system.json").resolve()
>>> context = PluginContext(
...     config=SiennaConfig(json_path=str(json_path), system_name="Two-area", model_year=2029),
...     store=DataStore(path=json_path.parent),
... )
>>> context = SiennaParser.from_context(context).run()
>>> system = context.system
>>> if system is None:
...     raise RuntimeError("Parser returned no system")
...
>>> print(system.name)
Two-area
>>> output = Path("output/system.json")
>>> _ = output.parent.mkdir(parents=True, exist_ok=True)
>>> export_context = PluginContext(
...     config=SiennaExporterConfig(output_path=str(output)),
...     system=system,
...     store=DataStore(path=output.parent),
... )
>>> _ = SiennaExporter.from_context(export_context).run()
>>> assert output.is_file()
```

Execute with the activated interpreter:

```bash
python python_roundtrip.py
```

The script prints the system name and asserts that the native output exists.
For component counts and archive inspection, follow the
[inspection guide](/r2x-sienna/how-to/inspect-system/). To distinguish schema validation
from hook failure, read the [lifecycle contract](/r2x-sienna/reference/#construction-and-execution-signatures).

`from_context(ctx)` constructs a plugin bound to that context. `run()` returns the updated `PluginContext`; lifecycle failures raise `r2x_core.PluginError`.
Do not treat its return value as a `Result` or call individual lifecycle hooks to bypass normal ordering.
Confirm that the output exists before using it downstream.

## Export JSON without time series

When the receiving workflow needs only component JSON, set the exporter instance's flag before executing:

```python doctest
>>> exporter = SiennaExporter.from_context(export_context)
>>> exporter.should_export_time_series = False
>>> _ = exporter.run()
```

The default is to export time series. Preserve the JSON and its referenced HDF5 file together for a complete transfer.

## Upgrade a copy independently

`SiennaUpgrader` can write the upgraded input. Copy JSON and companion HDF5 files to a working directory first.

```python doctest
>>> from pathlib import Path
>>> from r2x_core import UpgradeType
>>> from r2x_sienna import SiennaUpgrader
>>> result = SiennaUpgrader(Path("working/system.json")).upgrade(
...     upgrade_type=UpgradeType.SYSTEM,
... )
>>> if result.is_err():
...     raise RuntimeError(result.err())
...
```

Read the [registered upgrade steps](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/upgrader/upgrade_steps.py) and [upgrader implementation](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/upgrader/data_upgrader.py) when diagnosing a schema transition.
The parser also invokes upgrades; independent upgrading is useful when inspecting a migration before parsing.
