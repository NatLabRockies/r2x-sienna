---
title: "Inspect an archive before using the export"
---

Start from `outputs/system.zip` in the [round-trip tutorial](/r2x-sienna/tutorials/round-trip/).
This is an **Infrasys archive**, not native Sienna JSON.
Keep `r2x-sienna` installed in the environment that reads it; serialized components
refer to Python model modules and class names.

## Repeat component and relationship checks

Save the following as `inspect_details.py` and run it from the tutorial directory:

```python
from r2x_sienna.models import ACBus, PowerLoad

buses = list(sys.get_components(ACBus))
print("Bus names:", [bus.name for bus in buses])
loads = list(sys.get_components(PowerLoad))
if loads:
    load = loads[0]
    print("Name:", load.name)
    print("Values:", load.model_dump(exclude={"internal"}))
    series_list = sys.list_time_series(load)
    print("Matching single series:", len(series_list))
    for series in series_list:
        print(series.name, series.initial_timestamp, series.resolution)
        print(series.data[:3])
```

```bash
r2x read outputs/system.zip --zip --exec inspect_details.py
```

The fixture has ten ACBus instances. The observed first load is `Load-nodeD2`, with `active_power` of `4.0 megawatt`; its default single-series query returns zero. That empty query does not establish that all HDF5 storage is empty. Review actual load values, units, timestamps and profile names rather than assuming that a successful export proves a study is valid.
`list_time_series` queries single time series by default. An empty result means
no matching series is attached to that component, not that every series in the
system is absent. Other time-series types need their corresponding API argument.
See [Infrasys System source](https://github.com/NatLabRockies/infrasys/blob/main/src/infrasys/system.py)
for supported filters and serialization behavior.

## Load the same archive from Python

Use the Python executable shown by `r2x python show`, or a separate environment
with compatible `r2x-sienna` and Infrasys versions. Save this as `load_archive.py`:

```python
from infrasys import Component, System

system = System.load("outputs/system.zip")
print("Components:", len(list(system.get_components(Component))))
```

Run it with that interpreter. For example, in an activated compatible environment:

```bash
python load_archive.py
```

Expect 53 components for the pinned tutorial fixture.
`System.load` extracts and restores the archive's storage. An Infrasys JSON created
with `system.to_json(...)` instead uses `System.from_json(...)` and needs its
sibling storage directory. A filename extension alone does not identify the schema.

## Decide whether the result is usable

Check names/counts against the input, component fields against schema/unit
expectations, and profiles against intended length and resolution.
Load the native JSON/HDF5 pair in your target PowerSystems.jl environment before running a study; Python serialization does not establish Julia-version compatibility.
For a translation, compare mappings with the relevant [R2X property reference](https://natlabrockies.github.io/R2X/reference/python-api/).
For import/schema/storage errors, follow [troubleshooting](/r2x-sienna/troubleshooting/).
