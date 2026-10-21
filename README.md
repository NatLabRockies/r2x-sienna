<img src="./docs/src/assets/r2x-logo-full-square.svg" alt="R2X framework logo" align="left" width="220px" height="220px" hspace="10"/>
<img align="left" alt="" width="0" height="220px" hspace="10"/>

#### r2x-sienna
<p><small>Sienna models, parser, and exporter for the R2X ecosystem.</small></p>

[![PyPI](https://img.shields.io/pypi/v/r2x-sienna.svg)](https://pypi.org/project/r2x-sienna/) [![Docs](https://img.shields.io/badge/docs-guides-0079c2)](https://natlabrockies.github.io/r2x-sienna/)

<br clear="left">

`r2x-sienna` reads Sienna/PowerSystems JSON into typed R2X systems and exports systems back to Sienna.
Use [r2x-cli](https://github.com/NatLabRockies/r2x-cli) for repeatable pipelines and [R2X translation plugins](https://natlabrockies.github.io/R2X/) for cross-format mappings.

## Quick Start

Use Python 3.11, 3.12, or 3.13. In your active Python environment:

```bash
python -m pip install r2x-sienna
python -c "import r2x_sienna; print(r2x_sienna.__version__)"
```

The command prints the installed package version. For the separately installed CLI, install into its managed environment:

```bash
r2x python install
r2x install r2x-sienna
r2x list r2x-sienna
```

Confirm `sienna-parser` and `sienna-exporter` are discovered, then follow the [round-trip tutorial](https://natlabrockies.github.io/r2x-sienna/tutorials/round-trip/).

## Documentation

- [Getting started](https://natlabrockies.github.io/r2x-sienna/getting-started/installation/): installation, environment setup, and first-use checks.
- [Tutorials](https://natlabrockies.github.io/r2x-sienna/tutorials/round-trip/): parse and export a public test model.
- [How-to guides](https://natlabrockies.github.io/r2x-sienna/how-to/python/): Python contexts and CLI pipelines.
- [Reference / API](https://natlabrockies.github.io/r2x-sienna/reference/): exports, configuration, and source links.
- [Explanation](https://natlabrockies.github.io/r2x-sienna/explanation/): data flow and compatibility.
- [Troubleshooting](https://natlabrockies.github.io/r2x-sienna/troubleshooting/): discovery, inputs, and export failures.
- [Changelog](CHANGELOG.md): canonical release history.
- [Contributors](https://natlabrockies.github.io/r2x-sienna/contributors/): development and docs checks.

## Development

```bash
uv sync --all-groups
uv run prek run --all-files --hook-stage pre-push
```

See [docs/README.md](docs/README.md) for the documentation build.

## License

BSD-3-Clause. See [LICENSE.txt](LICENSE.txt).
