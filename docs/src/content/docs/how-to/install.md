---
title: "Install and verify"
---

Use Python 3.11, 3.12, or 3.13, as required by [package metadata](https://github.com/NatLabRockies/r2x-sienna/blob/main/pyproject.toml).

## Python environment

In your activated project environment:

```bash
python -m pip install r2x-sienna
python -c "import r2x_sienna; print(r2x_sienna.__version__)"
```

The printed version confirms the package is importable in this interpreter.
Package releases are on [PyPI](https://pypi.org/project/r2x-sienna/).

## CLI environment

Install [r2x-cli](https://github.com/NatLabRockies/r2x-cli#quick-start) separately.
The CLI manages its own Python environment; installing with pip in a different environment does not install a CLI plugin.

```bash
r2x --version
r2x python install
r2x install r2x-sienna
r2x list r2x-sienna
```

Confirm that `sienna-parser` and `sienna-exporter` appear before running a pipeline.
Continue with the [tutorial](/r2x-sienna/tutorials/round-trip/) or inspect [CLI configuration](/r2x-sienna/how-to/pipeline/).
