"""Per-year column renaming for the harmonize stage.

``rename_vars`` applies the rename rules for one survey year, turning that
year's source column names into the harmonized names the rest of the pipeline
expects. It stays lazy: a LazyFrame goes in and a LazyFrame comes out, with no
collection. When a column is renamed, its ``_label`` companion is renamed to
match, so the value column and its human-readable labels stay paired.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    import polars as pl

__all__ = ["RenameRule", "rename_vars"]


class RenameRule(TypedDict):
    """One rename rule: the years it applies to, and the harmonized name."""

    years: list[str]
    new_name: str


def rename_vars(lf: pl.LazyFrame, renames: dict[str, RenameRule], year: int) -> pl.LazyFrame:
    """Rename columns for one survey year according to the rename rules.

    Parameters
    ----------
    lf : pl.LazyFrame
        One year's data, before renaming.
    renames : dict[str, RenameRule]
        Maps a source column name to its rule. A rule applies only when ``year``
        is in the rule's ``years``.
    year : int
        The survey year ``lf`` holds. Compared against each rule's ``years``,
        which the config stores as strings.

    Returns
    -------
    pl.LazyFrame
        The frame with matching columns renamed, each column's ``_label``
        companion renamed alongside it. Columns with no applicable rule, and
        rules naming a column that isn't present, are left alone.

    Examples
    --------
    >>> import polars as pl
    >>> lf = pl.LazyFrame({"gowhensick": [4, 8]})
    >>> rule = {"gowhensick": {"years": ["2023"], "new_name": "k4q02_r"}}
    >>> rename_vars(lf, rule, 2023).collect().columns
    ['k4q02_r']
    """
    # A LazyFrame has no cheap `.columns`; ask the schema for the names.
    present = set(lf.collect_schema().names())
    # The config stores years as strings; `year` arrives as an int.
    year_str = str(year)
    mapping: dict[str, str] = {}
    for old, rule in renames.items():
        if year_str not in rule["years"] or old not in present:
            continue
        new_name = rule["new_name"]
        mapping[old] = new_name
        # A column's labels live in `<name>_label`; rename them together.
        old_label = f"{old}_label"
        if old_label in present:
            mapping[old_label] = f"{new_name}_label"
    return lf.rename(mapping)
