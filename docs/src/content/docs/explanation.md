---
title: "Data flow and compatibility"
---

The parser prepares configuration, runs registered upgrades, reconstructs typed components and their references, restores supplemental attributes, and connects time-series storage.
The exporter serializes PSY-compatible component dictionaries and supplemental attributes, then writes JSON and (by default) companion HDF5 data.
The upgrader isolates schema and legacy HDF5 metadata transitions from component reconstruction.

Upgrading can change files in place. Work on a copy and preserve the JSON/HDF5 pair.
Model classes encode schema assumptions; compatibility with a particular PowerSystems.jl version should be verified by loading the exported system in that Julia environment.
A Python round trip checks serialization behavior, not successful optimization or numerical equivalence.

## Package boundaries

`r2x-sienna` owns format-specific models, parser, and exporter.
[R2X Core](https://github.com/NatLabRockies/r2x-core) owns contexts, plugin lifecycle, and shared system behavior.
[r2x-cli](https://github.com/NatLabRockies/r2x-cli) owns managed Python environments, plugin discovery, and pipeline execution.
[R2X translators](https://natlabrockies.github.io/R2X/) map between formats.

See [parser source](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/parser.py), [exporter source](https://github.com/NatLabRockies/r2x-sienna/blob/main/src/r2x_sienna/exporter.py), and [configuration](/r2x-sienna/reference/) when evaluating behavior for a study.
