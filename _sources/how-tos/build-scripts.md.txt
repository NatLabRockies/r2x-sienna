# Build scripts with parser/exporter/upgrader

This guide shows script patterns for end-to-end usage with `r2x-sienna`.

## Parse a JSON system file

```python
from pathlib import Path

from r2x_core import DataStore, PluginContext
from r2x_sienna import SiennaConfig, SiennaParser

input_json = Path("tests/data/case5_pjm_rt/c_sys5_pjm_rt.json")

cfg = SiennaConfig(
    model_year=2029,
    system_name="PJM-5",
    json_path=str(input_json),
    system_base_power=100.0,
    skip_validation=False,
)

ctx = PluginContext(
    config=cfg,
    store=DataStore(path=input_json.parent),
    skip_validation=cfg.skip_validation,
)

parser = SiennaParser.from_context(ctx)
system = parser.run().system
```

## Export a parsed system back to PSY JSON

```python
from pathlib import Path

from r2x_core import DataStore, PluginContext
from r2x_sienna import SiennaExporter, SiennaExporterConfig

output_json = Path("output/system.json")

export_cfg = SiennaExporterConfig(output_path=str(output_json))
export_ctx = PluginContext(
    config=export_cfg,
    system=system,
    store=DataStore(path=output_json.parent),
)

exporter = SiennaExporter.from_context(export_ctx)
exporter.run()
```

By default, exporter writes time series HDF5 when available.

- JSON output: `output/system.json`
- HDF5 output: `output/system_time_series_storage.h5`

## Disable time series export

```python
exporter = SiennaExporter.from_context(export_ctx)
exporter.should_export_time_series = False
exporter.run()
```

## Run upgrader standalone (outside parser hooks)

```python
from pathlib import Path

from r2x_core import UpgradeType
from r2x_sienna import SiennaUpgrader

path = Path("tests/data/case5_pjm_rt/c_sys5_pjm_rt.json")
upgrader = SiennaUpgrader(path)

result = upgrader.upgrade(upgrade_type=UpgradeType.SYSTEM)
if result.is_err():
    raise RuntimeError(result.err())
```

## Full round-trip script

```python
from pathlib import Path

from r2x_core import DataStore, PluginContext
from r2x_sienna import (
    SiennaConfig,
    SiennaExporter,
    SiennaExporterConfig,
    SiennaParser,
)

input_json = Path("tests/data/case_rts_gmlc/rts_gmlc_da_sys.json")
output_json = Path("output/rts_roundtrip.json")

# Parse
parse_cfg = SiennaConfig(model_year=2029, system_name="RTS", json_path=str(input_json))
parse_ctx = PluginContext(config=parse_cfg, store=DataStore(path=input_json.parent))
system = SiennaParser.from_context(parse_ctx).run().system

# Export
export_cfg = SiennaExporterConfig(output_path=str(output_json))
export_ctx = PluginContext(config=export_cfg, system=system, store=DataStore(path=output_json.parent))
SiennaExporter.from_context(export_ctx).run()
```

## Tips for robust scripts

- Keep `DataStore(path=...)` near your input/output folders for reliable file discovery.
- Provide `json_path` when parsing from disk so automatic upgrades can run.
- Use explicit `system_name` and `system_base_power` in configs for reproducibility.
- Set `skip_validation=True` only for controlled debugging scenarios.
