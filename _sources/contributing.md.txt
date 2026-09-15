# Contributing

We welcome contributions to `r2x-sienna`. This guide covers the current development
workflow and conventions for this repository.

## Development Setup

Set up a local development environment:

```console
# Clone the repository
git clone https://github.com/NatLabRockies/r2x-sienna.git
cd r2x-sienna

# Install with development dependencies
uv sync --all-groups

# Optional: install local git hooks
uv run prek install
```

## Test and Quality Checks

Run the test suite:

```console
uv run pytest
```

Run targeted tests:

```console
uv run pytest tests/test_parser.py
uv run pytest tests/test_exporter.py
uv run pytest tests/test_data_upgrader.py
```

Run lint/type/format checks:

```console
uv run prek run --all-files --hook-stage pre-push
uv run ty check ./src/r2x_sienna/
```

## Documentation

```console
# Build docs locally
cd docs
make html
```

Main docs content lives under `docs/source/`.

When adding a new guide/reference page:

1. Add/edit the Markdown file in `docs/source/`
2. Include it in the proper `{toctree}`
3. Rebuild docs and verify there are no warnings/errors

## Contributing Guidelines

Typical contribution flow:

1. Create a feature branch (`git switch -c feature/my-change`)
2. Implement changes with tests
3. Run tests and quality checks
4. Update docs when behavior/API changes
5. Open a pull request with context and validation steps

## Reporting Issues

Report bugs or request features:

1. Check existing issues first
2. Create a new issue with:
   - Problem statement and expected behavior
   - Reproduction steps and sample input data when possible
   - Environment details (Python version, package versions)

## Git Conventions

Use descriptive branch names (`feature/...`, `fix/...`, `docs/...`, `test/...`, `refactor/...`).

Commit messages should follow conventional commits.

Follow the [Angular/Karma](https://karma-runner.github.io/6.4/dev/git-commit-msg.html) convention:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Useful scopes for this repository include: `parser`, `exporter`, `upgrader`,
`models`, `config`, `docs`, and `tests`.

Examples:

```
feat(models): add support for new component fields
fix(parser): handle missing time series data gracefully
docs(references): expand units documentation
test(upgrader): add coverage for version migration edge case
```

## Useful References

- [R2X Framework Documentation](https://github.com/NatLabRockies/R2X)
- [Sienna PowerSystems.jl Documentation](https://github.com/Sienna-Platform/PowerSystems.jl)
- [Pydantic Documentation](https://docs.pydantic.dev/)
