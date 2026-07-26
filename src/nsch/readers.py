"""Functions for reading NSCH source files."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nsch._types import DoSpec


def parse_do(year_do_path: str | Path) -> DoSpec:
    """Parse variable and value labels from a Stata do-file."""
    path = Path(year_do_path)

    if not path.exists():
        raise FileNotFoundError(
            "year.do.path should be the path to a Stata do file, "
            f"but this file does not exist: {path}"
        )

    raise NotImplementedError
