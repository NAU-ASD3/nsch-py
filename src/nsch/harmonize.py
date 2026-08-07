"""Functions for the Harmonize module"""

from __future__ import annotations

from typing import TypedDict

import polars as pl

from nsch import _types

__all__ = ["MergeRule", "RenameRule", "merge_vars", "rename_vars"]


class RenameRule(TypedDict):
    """One rename rule: the years it applies to, and the harmonized name."""

    years: list[str]
    new_name: str


class MergeRule(TypedDict):
    """One merge rule with its applicable years and source columns."""

    years: list[str]
    column_preferred: str
    column_fallback: str


def rename_vars(lf: pl.LazyFrame, renames: dict[str, RenameRule], year: int) -> pl.LazyFrame:
    """Rename columns for one survey year according to the rename rules.

    Applies the rename rules for one survey year, turning that
    year's source column names into the harmonized names the rest of the pipeline
    expects. It stays lazy: a LazyFrame goes in and a LazyFrame comes out, with no
    collection. When a column is renamed, its ``_label`` companion is renamed to
    match, so the value column and its human-readable labels stay paired.

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


def merge_vars(
    lf: pl.LazyFrame,
    merges: dict[str, MergeRule],
    year: int,
) -> pl.LazyFrame:
    """Merge preferred and fallback columns for a survey year.

    The preferred column is normally used. The fallback column is used when
    the preferred value is null or contains the logical skip sentinel, 998.

    If both corresponding ``_label`` columns exist, they are merged using
    the same preferred-versus-fallback condition.

    Original value and label columns are removed after merging.
    """

    merged_lf = lf
    schema = merged_lf.collect_schema()
    variable_names = set(schema.names())

    for merged_variable_name, details in merges.items():
        column_preferred = details["column_preferred"]
        column_fallback = details["column_fallback"]
        merge_years = details["years"]

        if (
            str(year) in merge_years
            and column_preferred in variable_names
            and column_fallback in variable_names
        ):
            preferred_values = pl.col(column_preferred)
            fallback_values = pl.col(column_fallback)

            use_fallback = (preferred_values.is_null()) | (
                preferred_values == _types.TaggedNA.LOGICAL_SKIP
            )

            merged_lf = merged_lf.with_columns(
                pl.when(use_fallback)
                .then(fallback_values)
                .otherwise(preferred_values)
                .cast(schema[column_preferred])  # Might be fragile
                .alias(merged_variable_name)
            )

            label_preferred = column_preferred + "_label"
            label_fallback = column_fallback + "_label"
            label_column = merged_variable_name + "_label"

            if label_preferred in variable_names and label_fallback in variable_names:
                merged_lf = merged_lf.with_columns(
                    pl.when(use_fallback)
                    .then(pl.col(label_fallback))
                    .otherwise(pl.col(label_preferred))
                    .alias(label_column)
                )

            merged_lf = merged_lf.drop(
                column_fallback,
                column_preferred,
                label_fallback,
                label_preferred,
                strict=False,
            )

    return merged_lf
