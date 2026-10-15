---
title: "Common problems"
---

## Plugin is absent from the CLI

The CLI's managed environment is separate from your project environment.

```bash
r2x --version
r2x python show
r2x list r2x-sienna
```

If missing, install with `r2x install r2x-sienna` and repeat the list command.
If configuration differs from this site, compare the installed release with [tagged source](/r2x-sienna/reference/versions/).

## Old constructor or return-value examples fail

Use `Parser.from_context(ctx).run()` as shown in [Python usage](/r2x-sienna/how-to/python/).
`run()` returns `PluginContext`, and lifecycle errors raise `PluginError`.
Examples using positional parser constructors or treating the returned context as `Result` do not match the current core lifecycle.

## Upgrade or HDF5 failure

Restore a disposable copy of the original JSON/HDF5 pair before retrying a migration.
Check the version fields, referenced storage filename, and existence of the companion HDF5 file.
Use the upgrader source linked in [Python usage](../how-to/python/) to identify the failing step.

## Missing or unsupported components

Check component type metadata against the installed `r2x_sienna.models` definitions and `models` configuration.
Inspect parser logs for skipped components or unresolved references.
Confirm the expected system name and component types before exporting.

## Export cannot be read by Julia

Keep JSON and HDF5 companions together. Record the PowerSystems.jl and InfrastructureSystems.jl versions and the full load error.
A successful Python export is not a guarantee that an arbitrary Julia schema version accepts it.

## Report a reproducible failure

Include package/CLI versions, the failing command, lifecycle error, and a minimal shareable input in a [GitHub issue](https://github.com/NatLabRockies/r2x-sienna/issues).
Remove confidential model data before attaching files.
