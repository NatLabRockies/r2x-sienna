---
title: "Installation"
---

Install the published `r2x-sienna` package for your workflow. It supports
Python 3.11, 3.12, and 3.13 according to [package metadata](https://github.com/NatLabRockies/r2x-sienna/blob/main/pyproject.toml).
Use [environment setup](/r2x-sienna/getting-started/environment/) first if you need a
Python environment or the `r2x` executable.

## Use the Python library

With your supported Python environment activated:

```bash
python -m pip install r2x-sienna
```

This installs the format package and its dependencies, including
[R2X Core](https://github.com/NatLabRockies/r2x-core) and
[Infrasys](https://github.com/NatLabRockies/infrasys).
A Julia installation is not required for parsing and exporting the tutorial fixture in Python.
Published distributions and their Python requirements are on
[PyPI](https://pypi.org/project/r2x-sienna/).

## Use the CLI plugin

After installing [r2x-cli](https://github.com/NatLabRockies/r2x-cli#quick-start)
and preparing its managed runtime:

```bash
r2x install r2x-sienna
```

The CLI installs into its own managed environment. A package installed with pip
in another environment is not automatically available to the CLI. You only need
to follow both installation routes when using both environments.

Continue with [verify installation and first use](/r2x-sienna/getting-started/verify/).
For an existing artifact, compare its writer's package versions with
[release source](/r2x-sienna/reference/versions/) before changing dependencies.

## Develop the package

Source checkouts, `uv sync`, tests and documentation authoring belong to the
separate [contributor guide](/r2x-sienna/contributors/). A source checkout is not
required for normal package installation or the downloaded-fixture tutorial.
