# Units Reference

`r2x-sienna` unit types are defined in `r2x_sienna.units` and built on the shared `pint` registry (`ureg`).

## Available Quantity Types

- `Distance` (base unit: `meter`)
- `Voltage` (`kilovolt`)
- `Current` (`ampere`)
- `Angle` (`degree`)
- `ActivePower` (`megawatt`)
- `ApparentPower` (`volt_ampere`)
- `Time` (`minute`)
- `Resistance` (`ohm`)
- `HeatRate` (`Btu/kWh`)
- `FuelPrice` (`usd/Btu`)
- `VOMPrice` (`usd/kWh`)
- `Energy` (`watthour`)
- `Percentage` (`percent`)
- `EmissionRate` (`kg/MWh`)
- `PowerRate` (`MW/min`)
- `Currency` (`usd`)

A custom currency unit is registered:

```python
ureg.define("usd = []")
```

## Utility Helpers

### `get_magnitude(field)`

Returns plain numeric value from either:

- raw number
- `pint.Quantity`

This is used by getters/serializers to support code paths that accept both quantity objects and scalar values.

## Typical Usage in Models/Scripts

```python
from r2x_sienna.units import ureg
from r2x_sienna.models import ACBus

bus = ACBus(name="Bus1", number=1, base_voltage=138 * ureg.kV)
```

## Per-unit Considerations

Model base classes integrate with per-unit support from `r2x-core` mixins.

- System base power (`system_base_power`) influences per-unit conversions.
- Component fields can store physical units while still supporting per-unit workflows.
- Export paths normalize values into PSY-compatible serialized structures.
