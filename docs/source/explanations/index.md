# Explanations

```{toctree}
:maxdepth: 2
:hidden:

workflow
upgrader
models-and-units
```

This section explains how `r2x-sienna` works internally and how its key parts fit together.

## What the Package Does

`r2x-sienna` is focused on Sienna/PowerSystems data interoperability in the `r2x-core` plugin ecosystem:

- Parse JSON system data into an `infrasys.System`
- Export `infrasys.System` back to PSY-compatible JSON
- Run structured data upgrades for legacy formats
- Provide Sienna-specific model classes and enums used during serialization/deserialization
- Apply unit-aware modeling with per-unit support

## Read Next

- [Parser, Exporter, and Upgrader Workflow](workflow.md)
- [Upgrader Design](upgrader.md)
- [Models and Units Design](models-and-units.md)
