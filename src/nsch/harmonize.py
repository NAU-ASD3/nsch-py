"""Functions for the harmonize module"""

from __future__ import annotations

from typing import TypedDict

import polars as pl

__all__ = ["RenameRule", "TransformValues", "rename_vars", "transform_values"]


class RenameRule(TypedDict):
    """One rename rule: the years it applies to, and the harmonized name."""

    years: list[str]
    new_name: str


class TransformValues(TypedDict):
    """One variable's transform rule:
    the years and values it applies to, and the new values and labels."""

    years: list[str]
    value: list[str]
    new_value: list[str]
    new_label: list[str]


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


def transform_values(
    lf: pl.LazyFrame, transforms: dict[str, TransformValues], year: int
) -> pl.LazyFrame:
    """Apply value and label remapping rules to transform a single year's raw numeric pl.LazyFrame.

    ``transform_values`` applies value and label remapping rules to a single year's
    raw numeric ``pl.LazyFrame`` and returns a new (lazy) frame with values
    transformed. For each variable in ``transforms`` whose ``years`` vector includes
    ``str(year)`` it iterates over the paired ``value``/ ``new_value``/``new_label``
    entries and replaces each matching numeric value with its new value. It creates
    or updates the corresponding ``_label`` column with the ``new_label`` text for
    remapped rows and silently skips variables not present in the input ``pl.LazyFrame``

    Parameters
    ----------
    lf : pl.LazyFrame
        One year's data before transforming.
    transforms : dict[str, TransformValues]
        Maps a source column name to its transform. A transform only applies when ``year``
        is in the transform's ``years``.
    year : int
        The survey year held by ``lf``. Compared against each transform's ``years``,
        which the config stores as strings.

    Returns
    -------
    pl.LazyFrame
        The frame with matching columns transformed and each column's ``_label``
        companion added or updated. Columns with no applicable transform, or not
        present in ``transforms``, are left alone.

    Examples
    --------
    >>> import polars as pl
    >>> lf = pl.LazyFrame({"sex": [1, 2, 1]})
    >>> transforms = {
    ...     "sex": TransformValues(
    ...         {
    ...             "years": ["2016"],
    ...             "value": ["1", "2"],
    ...             "new_value": ["1", "2"],
    ...             "new_label": ["Male", "Female"],
    ...         }
    ...     )
    ... }
    >>> transform_values(lf, transforms, 2016).collect()
    shape: (3, 2)
    ┌─────┬───────────┐
    │ sex ┆ sex_label │
    │ --- ┆ ---       │
    │ i64 ┆ str       │
    ╞═════╪═══════════╡
    │ 1   ┆ Male      │
    │ 2   ┆ Female    │
    │ 1   ┆ Male      │
    └─────┴───────────┘
    """
    transformed_lf = lf
    schema = transformed_lf.collect_schema()
    variable_names = set(schema.names())

    for transform_variable_name, details in transforms.items():
        transform_years = details["years"]
        if (transform_variable_name in variable_names) and (str(year) in transform_years):
            # Get column datatype for converting transform's string values
            column_dtype = schema[transform_variable_name]
            label_col = str(transform_variable_name) + "_label"

            if label_col not in variable_names:
                transformed_lf = transformed_lf.with_columns(
                    pl.lit(None, dtype=pl.Utf8).alias(label_col)
                )
                # Variable_names is a set, use .add instead of .append
                variable_names.add(label_col)

            # Create a mapping bewtween values and new values/labels for the transform
            lookup = pl.DataFrame(
                {
                    transform_variable_name: pl.Series(details["value"]).cast(column_dtype),
                    "_new_value": pl.Series(details["new_value"]).cast(column_dtype),
                    "_new_label": details["new_label"],
                }
            ).lazy()
            # if the number of values in the transform is not unique,
            # raise an error to protect against duplicate rows from a bad config
            if lookup.select(pl.col(transform_variable_name)).collect().n_unique() != len(
                details["value"]
            ):
                raise ValueError(
                    f"Duplicate values found in transform for variable {transform_variable_name}"
                )

            transformed_lf = (
                transformed_lf.join(
                    lookup, on=transform_variable_name, how="left", maintain_order="left"
                )
                .with_columns(
                    [
                        pl.coalesce(["_new_value", pl.col(transform_variable_name)]).alias(
                            transform_variable_name
                        ),
                        pl.coalesce(["_new_label", pl.col(label_col)]).alias(label_col),
                    ]
                )
                .drop("_new_value", "_new_label")
            )

    return transformed_lf
