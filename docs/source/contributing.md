# Contributing

We welcome contributions to R2X-Sienna! This guide will help you get started with contributing to the project.

## Development Setup

### How to set up a development environment

Set up a development environment for contributing to R2X-Sienna:

```console
# Clone the repository
git clone https://github.nrel.gov/PCM/r2x-sienna.git
cd r2x-sienna

# Install with development dependencies
uv sync --dev

# Install pre-commit hooks
uv run pre-commit install
```

### How to run tests

Execute the test suite:

```console
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov --cov-report=xml

# Run tests with verbose output
uv run pytest -vvl

# Run specific test categories
uv run pytest tests/test_translation.py  # Translation tests
uv run pytest tests/test_parser.py       # Parser tests
```

### How to run code quality checks

Ensure code quality and consistency:

```console
# Run pre-commit checks on all files
uv run pre-commit run --all-files

# Run type checking
uv run mypy --config-file=pyproject.toml src/

# Run linting and formatting
uv run ruff check src/
uv run ruff format src/
```

## Documentation

### How to build documentation locally

Build and preview the documentation:

```console
# Navigate to docs directory
cd docs

# Build HTML documentation
make html

# Serve documentation locally for live editing
make livehtml
```

### How to add new documentation

Add new content to the documentation:

1. Create or edit markdown files in `docs/source/`
2. Update `docs/source/index.md` if adding new sections
3. Build and preview locally:
   ```console
   make html
   ```
4. Check that links and references work correctly

## Contributing Guidelines

### How to contribute to R2X-Sienna

Follow these steps to contribute:

1. **Fork the repository** on GitHub Enterprise
2. **Create a feature branch**:
   ```console
   git switch -c feature/my-new-feature
   ```
3. **Make your changes** following the coding standards
4. **Run tests and checks**:
   ```console
   uv run pytest
   uv run pre-commit run --all-files
   ```
5. **Commit your changes** using conventional commit format:
   ```console
   git commit -m "feat(translation): add support for new component type"
   ```
6. **Push to your fork** and create a pull request

### How to report issues

Report bugs or request features:

1. Check existing issues on GitHub Enterprise
2. Create a new issue with:
   - Clear description of the problem/feature
   - Steps to reproduce (for bugs)
   - Expected vs actual behavior
   - Environment details (Python version, R2X version, etc.)
   - Sample Sienna data files (if applicable)

### Component Translation Development

When adding support for new Sienna components:

1. **Add component mapping** in `src/r2x_sienna/translation.py`
2. **Update component types** in plugin configuration
3. **Add validation logic** for the new component
4. **Include tests** with sample component data
5. **Update documentation** with component details

### Testing Guidelines

- **Unit tests**: Test individual translation functions
- **Integration tests**: Test complete translation workflows
- **Component tests**: Test specific component type translations
- **Validation tests**: Test error handling and data validation

```python
# Example component test
def test_thermal_standard_translation():
    sienna_component = create_test_thermal_standard()
    plexos_component = translate_thermal_standard(sienna_component)
    assert plexos_component.name == sienna_component.name
    assert plexos_component.max_capacity == sienna_component.base_power
```

## Git Conventions

### Branch Naming

Use descriptive branch names following this pattern:

```
<type>/<scope>
```

**Types:**
- `feature/` - New component support or features
- `fix/` - Bug fixes in translation logic
- `docs/` - Documentation improvements
- `test/` - Test additions or improvements
- `refactor/` - Code improvements without feature changes

**Examples:**
- `feature/battery-storage-support`
- `fix/thermal-ramp-limits`
- `docs/component-mapping-guide`

### Commit Message Format

Follow the [Angular/Karma](https://karma-runner.github.io/6.4/dev/git-commit-msg.html) convention:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**R2X-Sienna specific scopes:**
- `translation`: Component translation logic
- `parser`: Sienna file parsing
- `plugin`: Plugin integration
- `config`: Configuration handling
- `validation`: Data validation

**Examples:**
```
feat(translation): add support for PhaseShiftingTransformer
fix(parser): handle missing time series data gracefully
docs(components): add battery storage mapping details
test(translation): add comprehensive thermal unit tests
```

## Development Practices

### Translation Logic Guidelines

- **Preserve data integrity**: Ensure no critical component data is lost
- **Handle missing data**: Gracefully handle optional component properties
- **Validate conversions**: Check unit conversions and data ranges
- **Maintain mappings**: Keep clear mappings between Sienna and PLEXOS properties

### Code Organization

```
src/r2x_sienna/
├── plugin.py           # Plugin registration and components
├── parser.py           # Sienna file parsing logic
├── translation.py      # Component translation functions
├── models.py           # Data models and validation
├── system_utils.py     # System-level utilities
└── defaults/           # Default configuration files
```

### Testing Structure

```
tests/
├── test_parser.py           # Parser functionality tests
├── test_translation.py     # Translation logic tests
├── test_plugin.py          # Plugin integration tests
├── test_components/        # Component-specific tests
│   ├── test_thermal.py
│   ├── test_hydro.py
│   └── test_renewables.py
├── fixtures/               # Test data files
└── conftest.py            # Test configuration
```

### Configuration Management

When modifying configuration:

1. **Update default files** in `src/r2x_sienna/defaults/`
2. **Validate JSON schemas** for configuration files
3. **Test configuration loading** with unit tests
4. **Update documentation** with new parameters

### Performance Considerations

- **Memory usage**: Consider memory impact for large systems
- **Component limits**: Support `max_components` for testing
- **Progress reporting**: Provide feedback for long translations
- **Parallel processing**: Consider parallelization for independent components

## Useful References

- [R2X Framework Documentation](https://nrel.github.io/R2X/)
- [Sienna PowerSystems.jl Documentation](https://nrel-sienna.github.io/PowerSystems.jl/)
- [PLEXOS Model Reference](https://wiki.energyexemplar.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
