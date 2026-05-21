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

- `PowerLoad`, `StandardLoad`, `InterruptiblePowerLoad`
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

## Helper Types and Enums

- Named tuples/helpers: `MinMax`, `UpDown`, `StartShut`, `StartUpStages`, `StartTimeLimits`, `InputOutput`, `FromTo_ToFrom`, `Complex`, `GeoLocation`
- Enums include fuel, reserve, transformer, hydro, bus-type, and related classification values

## Notes

- Models are strongly typed and validated via `pydantic`.
- Base component classes include per-unit-aware behavior and shared serialization patterns.
- The parser relies on model metadata to resolve component references and deserialize polymorphic types.
