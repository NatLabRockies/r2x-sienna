---
title: "Parse and export a Sienna model"
---

Complete a two-step round trip using the repository's public test fixture.
This checks the parser/exporter integration; it does not run an optimization or prove numerical equivalence.

## Prepare a working copy

Install [r2x-cli](/r2x-sienna/how-to/install/) and Git. Clone a disposable copy of this repository:

```bash
git clone https://github.com/NatLabRockies/r2x-sienna.git
cd r2x-sienna
r2x python install
r2x install r2x-sienna
r2x list r2x-sienna
```

Keep the fixture's companion files together. The parser may upgrade JSON and HDF5 metadata in place; use this disposable copy rather than your original study data.

## Create the pipeline

Save this as `round-trip.yaml` in the repository root:

```yaml
variables: {}
pipelines:
  round_trip:
    - r2x-sienna.sienna-parser
    - r2x-sienna.sienna-exporter
config:
  r2x-sienna.sienna-parser:
    json_path: tests/data/2area-5bus-system/test_system.json
    system_name: Two-area
    model_year: 2029
  r2x-sienna.sienna-exporter:
    output_path: output/system.json
output_folder: output
```

Preview the resolved configuration and execution order:

```bash
r2x run round-trip.yaml round_trip --print
r2x run round-trip.yaml round_trip --dry-run
```

Check the input and output paths in the preview. A dry run displays the plan; it does not validate all model data.

## Execute and verify

```bash
r2x run round-trip.yaml round_trip
```

Check that `output/system.json` exists and that any referenced HDF5 companion file is present. Keep the pair together when moving the model.

```bash
python -c "from pathlib import Path; files = list(Path('output').rglob('*.json')); assert files; print(*files, sep='\n')"
```

For data inspection before export, use the [Python workflow](/r2x-sienna/how-to/python/).
If a step fails, follow [troubleshooting](/r2x-sienna/troubleshooting/) before retrying with a different input.

## Verification environment

This pipeline was executed with r2x-cli 0.1.15 and Python 3.12, using r2x-sienna 0.5.0 with r2x-core 0.9.0.
Both parser and exporter completed. Use the CLI binary’s supported Python runtime when repeating the example.
