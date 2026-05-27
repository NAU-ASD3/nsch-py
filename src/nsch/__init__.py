"""nsch — NSCH data preparation toolkit.

Download, harmonize, and combine National Survey of Children's Health data
across survey years. See the documentation at
https://nau-asd3.github.io/nsch-py/ for usage.
"""

from importlib.metadata import PackageNotFoundError, version

# The package version is sourced from the installed distribution metadata
# (set by hatchling from pyproject.toml at build time). The try/except
# handles the edge case of running directly from a source checkout that
# hasn't been installed — `uv sync` always installs in editable mode, so
# this branch is rarely hit in practice but matters for first-time setup.
try:
    __version__ = version("nsch")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
