---
title: "Browse package versions"
---

This site documents current `main` and does not publish a separate documentation build for every release.

- [Release notes](https://github.com/NatLabRockies/r2x-sienna/releases) describe packaged changes.
- [Git tags](https://github.com/NatLabRockies/r2x-sienna/tags) let you browse the README, docs, and API source at an actual release.
- [PyPI package](https://pypi.org/project/r2x-sienna/) lists published distributions and Python requirements.
- [Canonical changelog](https://github.com/NatLabRockies/r2x-sienna/blob/main/CHANGELOG.md) records release history.

Check the version in the Python environment used by your workflow:

```bash
python -c "from importlib.metadata import version; print(version('r2x-sienna'))"
```

For CLI installations, use `r2x list r2x-sienna` to inspect the managed plugin.
Choose the matching tag on GitHub before comparing configuration or signatures; current documentation can include unreleased changes.
