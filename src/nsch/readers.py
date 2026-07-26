"""Functions for reading NSCH source files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from nsch._types import DoSpec


def parse_do(year_do_path: str | Path) -> DoSpec:
    """Parse variable and value labels from a Stata do-file."""
    from nsch._types import DoSpec

    path = Path(year_do_path)

    if not path.exists():
        raise FileNotFoundError(
            "year.do.path should be the path to a Stata do file, "
            f"but this file does not exist: {path}"
        )

    variable_rows: list[dict[str, str]] = []

    for line in path.read_text().splitlines():
        match = re.match(r'^\s*label\s+var\s+(\S+)\s+"([^"]*)"', line)

        if match:
            variable_rows.append(
                {
                    "variable": match.group(1),
                    "desc": match.group(2),
                }
            )

    var = pl.DataFrame(
        variable_rows,
        schema={
            "variable": pl.String,
            "desc": pl.String,
        },
    ).lazy()

    define = pl.DataFrame(
        schema={
            "variable": pl.String,
            "value": pl.String,
            "desc": pl.String,
        }
    ).lazy()

    return DoSpec(
        define=define,
        var=var,
    )
