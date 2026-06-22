"""Per-year column renaming for the harmonize stage.

``rename_vars`` applies the rename rules for one survey year, turning that
year's source column names into the harmonized names the rest of the pipeline
expects. It stays lazy: a LazyFrame goes in and a LazyFrame comes out, with no
collection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    import polars as pl

__all__ = ["RenameRule", "rename_vars"]


class RenameRule(TypedDict):
    years: list[str]
    new_name: str


def rename_vars(lf: pl.LazyFrame, renames: dict[str, RenameRule], year: int) -> pl.LazyFrame:
    present = set(lf.collect_schema().names())
    year_str = str(year)
    mapping: dict[str, str] = {}
    for old, rule in renames.items():
        if year_str not in rule["years"] or old not in present:
            continue
        mapping[old] = rule["new_name"]
    return lf.rename(mapping)
