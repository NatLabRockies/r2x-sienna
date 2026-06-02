# Models Catalog

`r2x_sienna.models` provides the component classes used for parse and export.

## Topology

- `Area`, `LoadZone`
- `Bus`, `ACBus`, `DCBus`
- `Arc`

## Branch and Network Equipment

- `Branch`, `ACBranch`, `DCBranch`
- `Line`, `MonitoredLine`
- `Transformer2W`, `TapTransformer`, `PhaseShiftingTransformer`
- `Transformer3W`, `ThreeWindingTransformer`, `PhaseShiftingTransformer3W`
- `TwoTerminalHVDCLine`, `TwoTerminalGenericHVDCLine`, `TwoTerminalLCCLine`, `TwoTerminalVSCLine`, `TModelHVDCLine`
- `AreaInterchange`, `DiscreteControlledACBranch`

## Generation and Storage

- `Generator`, `Source`, `SynchronousCondenser`, `HybridSystem`
- Thermal: `ThermalGen`, `ThermalStandard`, `ThermalMultiStart`
- Hydro: `HydroGen`, `HydroDispatch`, `HydroReservoir`, `HydroEnergyReservoir`, `HydroPumpedStorage`, `HydroPumpTurbine`, `HydroTurbine`
- Renewable: `RenewableGen`, `RenewableDispatch`, `RenewableNonDispatch`
- Storage: `Storage`, `EnergyReservoirStorage`

## Load and FACTS-adjacent Load Models

- `PowerLoad`, `StandardLoad`, `InterruptiblePowerLoad`, `InterruptibleStandardLoad`
- `ShiftablePowerLoad`
- `MotorLoad`, `ExponentialLoad`
- `ActiveConstantPowerLoad`
- `FixedAdmittance`, `SwitchedAdmittance`, `FACTSControlDevice`

## Services and Core Mappings

- `Service`
- `Reserve`, `VariableReserve`, `TransmissionInterface`
- `ReserveMap`, `TransmissionInterfaceMap`

## Cost Models

- `ThermalGenerationCost`
- `HydroGenerationCost`, `HydroReservoirCost`
- `RenewableGenerationCost`
- `StorageCost`
- `LoadCost`

## Supplemental Attributes

- `GeographicInfo`
- `GeometricDistributionForcedOutage`
- `ImpedanceCorrectionData`
- `EmissionsData` — emission rate (as a [`ValueCurve`](api.md)) for a single pollutant;
  attach to any component via `add_supplemental_attribute`. Supports `FUEL_INPUT` or
  `POWER_OUTPUT` basis with validated `energy_unit` pairing. Scalar `float` rates are
  automatically wrapped in a constant-rate `LinearCurve`.

## Emissions Enums

| Enum | Members |
|------|---------|
| `PollutantType` | `CO2`, `CO2E`, `CH4`, `N2O`, `NOX`, `SO2`, `PM25`, `PM10`, `HG`, `HAP`, `CUSTOM` |
| `EmissionBasis` | `FUEL_INPUT`, `POWER_OUTPUT` |
| `MassUnit` | `KG`, `LB`, `SHORT_TON`, `METRIC_TON` |
| `EnergyUnit` | `MMBTU`, `GJ`, `MWH` |

## Helper Types and Enums

- Named tuples/helpers: `MinMax`, `UpDown`, `StartShut`, `StartUpStages`, `StartTimeLimits`, `InputOutput`, `FromTo_ToFrom`, `Complex`, `GeoLocation`
- Enums include fuel, reserve, transformer, hydro, bus-type, and related classification values

## Notes

- Models are strongly typed and validated via `pydantic`.
- Base component classes include per-unit-aware behavior and shared serialization patterns.
- The parser relies on model metadata to resolve component references and deserialize polymorphic types.
