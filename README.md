# R2X-Sienna

> A plugin for the R2X framework that enables translation from Sienna (PowerSystems.jl) data formats to PLEXOS models.
>
> [![image](https://img.shields.io/pypi/v/r2x.svg)](https://pypi.python.org/pypi/r2x-sienna)
> [![image](https://img.shields.io/pypi/l/r2x.svg)](https://pypi.python.org/pypi/r2x-sienna)
> [![CI](https://github.com/NREL/r2x/actions/workflows/CI.yaml/badge.svg)](https://github.nrel.gov/PCM/r2x-sienna/actions/workflows/CI.yaml)
> [![codecov](https://codecov.io/gh/NREL/r2x/branch/main/graph/badge.svg)](https://codecov.io/gh/PCM/r2x-sienna)
> [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
> [![Documentation](https://github.com/NREL/R2X/actions/workflows/docs-build.yaml/badge.svg?branch=main)](https://github.nrel.gov/PCM/r2x-sienna/)

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
  - [1. Create a configuration file](#1-create-a-configuration-file)
  - [2. Run the translation](#2-run-the-translation)
- [Supported Components](#supported-components)
  - [Generation Components](#generation-components)
  - [Storage Components](#storage-components)
  - [Battery Components](#battery-components)
  - [Network Components](#network-components)
  - [System Components](#system-components)
- [Plugin Architecture](#plugin-architecture)
- [Advanced Usage](#advanced-usage)
  - [Custom Component Limits](#custom-component-limits)
  - [Direct Script Usage (Legacy)](#direct-script-usage-legacy)
- [File Structure](#file-structure)
- [Configuration Files](#configuration-files)
  - [System Mapping](#system-mapping-sienna_mapping_extjson)
  - [Input Configuration](#input-configuration-sienna_input_extjson)
  - [Plugin Configuration](#plugin-configuration-plugins_config_extjson)
- [Development](#development)
  - [Running Tests](#running-tests)
- [Contributing](#contributing)
- [License](#license)


## Overview

R2X-Sienna provides seamless integration between Sienna and PLEXOS through the R2X translation framework. This plugin allows users to:

- Parse Sienna JSON/h5 system files
- Convert Sienna components to PLEXOS format
- Export complete PLEXOS XML databases
- Maintain data integrity during translation

## Quick Start

```bash
pip install r2x-sienna
```

## License

This project is licensed under a BSD 3-Clause License.
