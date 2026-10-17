"""Execute documented Python console examples against isolated public fixtures."""

from __future__ import annotations

import doctest
import re
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "docs/src/content/docs"
BLOCK = re.compile(r"^```python doctest\n(.*?)^```", re.MULTILINE | re.DOTALL)
PAGES = sorted(path for path in CONTENT.rglob("*.md") if BLOCK.search(path.read_text()))


def prepare_workspace(folder: Path) -> object:
    """Copy native inputs and construct the archive used by CLI inspection examples."""
    from r2x_core import DataStore, PluginContext

    inputs = folder / "inputs"
    inputs.mkdir()
    outputs = folder / "outputs"
    outputs.mkdir()
    from r2x_sienna import SiennaConfig, SiennaParser

    source = ROOT / "tests/data/2area-5bus-system"
    for path in source.iterdir():
        if path.is_file():
            shutil.copy2(path, inputs / path.name)
    working = folder / "working"
    shutil.copytree(inputs, working)
    # Parsing may upgrade JSON/HDF5. Keep diagnostics on the original versioned copy.
    context = PluginContext(
        config=SiennaConfig(
            json_path=str(working / "test_system.json"), model_year=2029, system_name="Two-area"
        ),
        store=DataStore(path=working),
    )
    context = SiennaParser.from_context(context).run()
    shutil.copy2(inputs / "test_system.json", working / "system.json")
    assert context.system is not None
    context.system.save(outputs / "system", zip=True)
    return context.system


@pytest.mark.parametrize("page", PAGES, ids=lambda path: str(path.relative_to(CONTENT)))
def test_documented_examples(page: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run each page's successive blocks with checked output and shared page state."""
    system = prepare_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    # r2x read --exec explicitly supplies this name; other snippets import their own dependencies.
    namespace = {"sys": system}
    parser = doctest.DocTestParser()
    runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS)
    for match in BLOCK.finditer(page.read_text()):
        example = parser.get_doctest(match.group(1), namespace, str(page), str(page), 0)
        runner.run(example, clear_globs=False)
        namespace.update(example.globs)
    assert runner.tries > 0, "A marked page must execute examples"
    assert runner.failures == 0


def test_example_discovery_and_fences() -> None:
    """Fail when executable pages disappear or unmarked Python blocks bypass testing."""
    assert len(PAGES) >= 8
    for page in CONTENT.rglob("*.md"):
        assert not re.search(r"^```python\s*$", page.read_text(), re.MULTILINE), page


def test_doctest_checks_expected_output() -> None:
    """A wrong expectation must fail, rather than merely executing the command."""
    runner = doctest.DocTestRunner()
    example = doctest.DocTestParser().get_doctest(
        ">>> 2 + 2\n5\n", {}, "negative control", "negative-control", 0
    )
    runner.run(example, out=lambda message: None)
    assert runner.failures == 1
    assert runner.tries == 1


def test_public_docstrings() -> None:
    """Check runnable configuration and context examples exposed in the API page."""
    from r2x_sienna import plugin_config

    modules = (plugin_config,)
    for module in modules:
        result = doctest.testmod(module)
        assert result.attempted > 0
        assert result.failed == 0
