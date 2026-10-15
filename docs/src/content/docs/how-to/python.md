---
title: "Parse, inspect, and export with Python"
---

Run this example from a disposable repository checkout after installing `r2x-sienna` into your active Python environment.
The fixture and its companions are included under `tests/data/`.
Parsing may update legacy JSON/HDF5 data in place. Keep your original files separate.

```python
from pathlib import Path

from r2x_core import DataStore, PluginContext
from r2x_sienna import SiennaConfig, SiennaExporterConfig, SiennaParser, SiennaExporter

json_path = Path("tests/data/2area-5bus-system/test_system.json").resolve()
context = PluginContext(
    config=SiennaConfig(json_path=str(json_path), system_name="Two-area", model_year=2029),
    store=DataStore(path=json_path.parent),
)
context = SiennaParser.from_context(context).run()
system = context.system
if system is None:
    raise RuntimeError("Parser returned no system")
print(system.name)

output = Path("output/system.json")
output.parent.mkdir(parents=True, exist_ok=True)
export_context = PluginContext(
    config=SiennaExporterConfig(output_path=str(output)),
    system=system,
    store=DataStore(path=output.parent),
)
SiennaExporter.from_context(export_context).run()
assert output.is_file()
```

`from_context(ctx)` constructs a plugin bound to that context. `run()` returns the updated `PluginContext`; lifecycle failures raise `r2x_core.PluginError`.
Do not treat its return value as a `Result` or call individual lifecycle hooks to bypass normal ordering.
Confirm that the output exists before using it downstream.

## Export JSON without time series

When the receiving workflow needs only component JSON, set the exporter instance's flag before executing:

```python
exporter = SiennaExporter.from_context(export_context)
exporter.should_export_time_series = False
exporter.run()
```

The default is to export time series. Preserve the JSON and its referenced HDF5 file together for a complete transfer.

## Upgrade a copy independently

`SiennaUpgrader` can write the upgraded input. Copy JSON and companion HDF5 files to a working directory first.

```python
from pathlib import Path
from r2x_core import UpgradeType
from r2x_sienna import SiennaUpgrader

result = SiennaUpgrader(Path("working/system.json")).upgrade(
    upgrade_type=UpgradeType.SYSTEM,
)
if result.is_err():
    raise RuntimeError(result.err())
```

Read the [registered upgrade steps](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/upgrader/upgrade_steps.py) and [upgrader implementation](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/upgrader/data_upgrader.py) when diagnosing a schema transition.
The parser also invokes upgrades; independent upgrading is useful when inspecting a migration before parsing.
