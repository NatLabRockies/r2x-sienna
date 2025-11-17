```{toctree}
:maxdepth: 2
:hidden:

install
how-tos/index
references/index
contributing
CHANGELOG
```

# R2X-Sienna Documentation

R2X-Sienna is a plugin for the R2X framework that enables seamless translation from Sienna (PowerSystems.jl) data formats to PLEXOS models.

## About R2X-Sienna

R2X-Sienna provides a complete workflow for converting power system models from Sienna's JSON format to PLEXOS XML databases. It supports comprehensive component mapping, data validation, and maintains data integrity throughout the translation process.

### Key Features

R2X-Sienna offers the following capabilities:

- **Sienna System Parsing** - Read and validate Sienna JSON/HDF5 system files with comprehensive error handling
- **Component Translation** - Convert 19+ component types including generators, storage, transmission, and system components
- **PLEXOS Export** - Generate complete PLEXOS XML databases ready for optimization studies
- **Plugin Architecture** - Seamlessly integrates with R2X v2.0.0 plugin system for modular workflows
- **Configurable Translation** - YAML-based configuration for flexible translation parameters and component filtering

## Quick Start

## Supported Component Types

R2X-Sienna supports translation of these Sienna components:

### Generation
- **Thermal**: ThermalStandard, ThermalMultiStart
- **Hydro**: HydroDispatch, HydroEnergyReservoir
- **Renewable**: RenewableDispatch, RenewableNonDispatch

### Storage
- **Hydro Storage**: HydroPumpedStorage, HydroEnergyReservoir
- **Battery Storage**: EnergyReservoirStorage

### Network
- **Transmission**: Line, MonitoredLine, TwoTerminalHVDCLine
- **Transformers**: Transformer2W, TapTransformer, PhaseShiftingTransformer

### System
- **Topology**: ACBus, LoadZone, Area
- **Services**: VariableReserve, TransmissionInterface

## Indices and Tables

- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`
