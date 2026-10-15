---
title: "Diagnose input, runtime, and export problems"
---

Use the failing lifecycle stage and a small inspection before changing data.
Commands below use the [tutorial workspace](/r2x-sienna/tutorials/round-trip/).
Keep the original inputs and complete error/log path when reporting a failure.

## Plugin is missing

**Symptom:** the pipeline cannot resolve `sienna-parser` or `sienna-exporter`.
The package may be installed in a project environment but absent from the CLI runtime.

```bash
r2x python show
```

```bash
r2x list r2x-sienna
```

If either entry point is absent, install through the same CLI:

```bash
r2x install r2x-sienna
```

Repeat `list` and check generated help before executing:

```bash
r2x run sienna-parser --help
```

**Runtime startup instead mentions Python ABI:** compare `r2x --version` and
`r2x python show` with the runtime required by that binary. The tested CLI 0.1.15
binary here used Python 3.12. Changing a project's Python does not change the ABI
against which a CLI binary was built. See [CLI development/runtime guidance](https://github.com/NatLabRockies/r2x-cli/blob/main/docs/development.md).

## Execution fails after a successful dry run

**Symptom:** `--dry-run` succeeds but parsing or export fails.
The preview did not open or validate all model files. Verify the expanded paths:

```bash
r2x run pipeline.yaml round_trip --print
```

Confirm the working directory and input contents separately:

```bash
pwd
```

```bash
ls -lh inputs
```

Run verbose execution only after checking the failing setting:

```bash
r2x run pipeline.yaml round_trip -v
```

Use the printed log path to identify parser, upgrade, build or export failure.
For missing native storage, keep `inputs/test_system.json` and `inputs/test_system_time_series_storage.h5` together. Check the storage filename recorded in JSON rather than renaming a different HDF5 file to match.

## Upgrade or HDF5 metadata fails

**Symptom:** the upgrade phase reports an unsupported schema, missing storage, or an HDF5 locking/migration error. Work on a fresh copy of the JSON/HDF5 pair, confirm both files are writable, and close other processes using that same HDF5 file before retrying. Do not run concurrent upgrades against one working copy. Review detected version and the registered step in [upgrader design](/r2x-sienna/explanation/upgrader/). A newer package does not imply every historical or future schema is supported.

## Archive loading fails

**Symptom:** `r2x read` reports invalid ZIP, wrong JSON structure, missing module, or
SQLite/storage metadata errors. Confirm which artifact you supplied:

| Input | Correct reader |
| --- | --- |
| Native PSY JSON and companion HDF5 | `sienna-parser` |
| `outputs/system.zip` from `--zip -o` | `r2x read ... --zip` or Infrasys `System.load` |
| Infrasys JSON from `to_json` | `System.from_json`, with its sibling storage directory |

The supported inspection command is:

```bash
r2x read outputs/system.zip --zip --exec inspect_system.py
```

Use the [tutorial inspection script](/r2x-sienna/tutorials/round-trip/#5-inspect-the-graph-not-just-the-filenames).
The reader environment must import `r2x_sienna` model classes and compatible
Infrasys/Core versions. A successful import in another interpreter is not enough.

If only `sys.info()` or interactive startup fails with
`no such table: supplemental_attribute_associations`, use the scripted component
queries without `sys.info()` or `--interactive`. This is an observed ecosystem
[serialization-summary issue](https://natlabrockies.github.io/R2X/troubleshooting/#summary-fails-with-supplemental_attribute_associations),
not proof that every component is absent. Preserve the archive and report the
metadata failure; the workaround does not repair supplemental associations.

## Python construction or configuration fails

**Symptom:** positional parser construction, `build_system()`, or `.is_err()` on
`run()` fails. Use `Parser.from_context(ctx).run()` and inspect its returned
`PluginContext.system`; failed hooks raise `PluginError`.
See [Python workflow](/r2x-sienna/how-to/python/) for complete setup.

**Symptom:** `DataStore(path=...)` raises `FileNotFoundError`. Create that directory
before creating a store. The exporter's own parent-directory handling does not
change this separate constructor requirement.

## Report the failure with evidence

Include CLI and package versions, exact command, expanded configuration with
private paths/data removed, failing lifecycle stage, complete error and a minimal
shareable fixture in a [GitHub issue](https://github.com/NatLabRockies/r2x-sienna/issues).
Record component counts before/after and the intended PowerSystems.jl/InfrastructureSystems.jl versions
when diagnosing consumer compatibility. Do not modify runtime source or silently
replace missing profiles merely to make a documentation example pass.
