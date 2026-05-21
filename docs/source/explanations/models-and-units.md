# Models and Units Design

`r2x-sienna` uses typed model classes under `r2x_sienna.models` and quantity classes under `r2x_sienna.units`.

## Model Philosophy

The model layer is designed to:

- Mirror Sienna/PowerSystems concepts with Python classes
- Keep component validation close to model definitions
- Preserve serialization metadata needed for PSY compatibility
- Support per-unit and physical-unit representations in the same component hierarchy

Most concrete components inherit from a Sienna base component that combines:

- `infrasys.Component`
- Per-unit conversion support through `r2x-core` unit mixins

## Model Families

Top-level families include:

- Topology: buses, areas, load zones, arcs
- Branches: AC lines, transformers, HVDC variants
- Generators and storage: thermal, hydro, renewable, storage, source/hybrid
- Loads and FACTS-related load components
- Services and reserve models
- Cost models for generation/load/storage/hydro
- Supplemental attributes (for extra geospatial/forced-outage/impedance-correction data)
- Enums and helper tuple-like structures

See the reference section for a complete catalog.

## Units Approach

Unit types are declared in `r2x_sienna.units` with `pint` + `infrasys.base_quantity.BaseQuantity`.

Examples:

- `Voltage` with base unit `kilovolt`
- `ActivePower` with base unit `megawatt`
- `Energy` with base unit `watthour`
- `FuelPrice` / `VOMPrice` / `Currency` with `usd`-based units

A custom `usd` unit is registered in the shared unit registry.

## Quantity Handling Rules

1. Model fields can hold typed quantities (for example, `Voltage`, `ActivePower`).
2. Serialization paths convert quantities to JSON-friendly values where required.
3. Helper utilities (like `get_magnitude`) normalize raw numbers and `pint.Quantity` values.
4. Per-unit conversions are supported through model base mixins and system base power.

## Practical Implications

- You can build components in scripts using explicit units (for example, `138 * ureg.kV`).
- Validation catches unit/type mismatches early in model construction.
- Export output remains aligned with PSY-style numeric payload expectations.
