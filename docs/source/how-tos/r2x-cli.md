# Use r2x-cli

`r2x-sienna` registers `sienna-parser` and `sienna-exporter` with the
`r2x-cli` plugin registry. Install the package in the environment used by the
CLI, then confirm discovery:

```bash
r2x list r2x-sienna
```

## Inspect Plugin Capabilities

The CLI generates plugin options from the Pydantic configuration classes:

```bash
r2x run plugin sienna-parser --show-help
r2x run plugin sienna-exporter --show-help
```

Parser options are:

- `--json-path`: input PSY JSON file
- `--model-year`: one year or a list of years
- `--system-name`: system name
- `--system-base-power`: base MVA used for per-unit calculations
- `--scenario`: scenario identifier
- `--skip-validation`: disable parser validation when needed for controlled debugging
- `--models`: module paths containing component classes
- `--output-path`: optional serialized output path supported by the core CLI

Exporter options are:

- `--output-path`: required PSY JSON output path
- `--system-base-power`: base MVA used for per-unit calculations
- `--scenario`: scenario identifier
- `--models`: module paths containing component classes

Options accept both hyphenated and underscore names. Configuration can also be
provided as `key=value` arguments or with the explicit `--set key=value` form.

## Parse With The CLI

The direct plugin mode reads a JSON system from the input file and writes the
resulting system to the requested output:

```bash
r2x run plugin sienna-parser \
  --input tests/data/case5_pjm_rt/c_sys5_pjm_rt.json \
  --output output/case5.infrasys.json \
  --json-path tests/data/case5_pjm_rt/c_sys5_pjm_rt.json \
  --model-year 2029 \
  --system-name PJM-5
```

When `json_path` is provided, the parser runs registered Sienna upgrades before
deserializing components, supplemental attributes, references, and time-series
metadata. The input may also be supplied through standard input using the core
CLI input behavior.

## Export With The CLI

Export an infrasys system supplied through the core CLI input mechanism:

```bash
r2x run plugin sienna-exporter \
  --input output/case5.infrasys.json \
  --output output/case5_psy.json \
  --output-path output/case5_psy.json
```

The exporter writes PSY-compatible JSON. Time series are exported to a sibling
`*_time_series_storage.h5` file by default. The JSON records that HDF5 file in
its time-series storage metadata.

## Pipelines And Utilities

The core CLI also provides capabilities around these plugins:

```bash
r2x init pipeline.yaml
r2x run pipeline.yaml <pipeline-name>
r2x run pipeline.yaml <pipeline-name> --dry-run
r2x run pipeline.yaml <pipeline-name> --list
r2x run pipeline.yaml <pipeline-name> --print
```

For quick inspection of a system, use the interactive reader:

```bash
r2x read output/case5_psy.json
r2x read output/case5_psy.json --exec inspect_system.py
```

Run `r2x --help` and `r2x run --help` for global logging, verbosity, plugin
repeat, and benchmark options.