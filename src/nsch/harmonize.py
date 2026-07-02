"""Remap answer codes per year for harmonize module

``transform_values`` applies value and label remapping rules to a single year's
raw numeric ``pl.LazyFrame``, modifying it by reference. For each variable in
``transforms`` whose ``years`` vector includes ``chr(year)` it iterates over
the paired ``value``/ ``new_value``/``new_label`` entries and replaces each
matching numeric value with its new value.

Creates or updates the corresponding ``_label`` column with the ``new_label``
text for remapped rows.

Silently skips variables not present in the input ``pl.LazyFrame``

"""

from __future__ import annotations

from typing import TypedDict

import polars as pl

__all__ = ["TransformValues", "transform_values"]


class TransformValues(TypedDict):
    years: list[str]
    value: list[str]
    new_value: list[str]
    new_label: list[str]


def transform_values(
    lf: pl.LazyFrame, transforms: dict[str, TransformValues], year: int
) -> pl.LazyFrame:
    """Apply value and label remapping rules to transform a single year's raw numeric pl.LazyFrame.

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
    # Use a set for faster looping
    variable_names = set(schema.names())

    for transform_variable_name, details in transforms.items():
        transform_years = details["years"]
        if (transform_variable_name in variable_names) & (str(year) in transform_years):
            # Get colum datatype for casting back after casting to string to transform values
            column_dtype = schema[transform_variable_name]
            label_col = str(transform_variable_name) + "_label"

            column_as_string = pl.col(transform_variable_name).cast(pl.Utf8)
            condition = column_as_string.is_in(details["value"])

            value_transform = (
                pl.when(condition)
                .then(
                    column_as_string.replace(old=details["value"], new=details["new_value"]).cast(
                        column_dtype
                    )
                )
                .otherwise(pl.col(transform_variable_name))
                .alias(transform_variable_name)
            )
            label_transform = (
                pl.when(condition)
                .then(column_as_string.replace(old=details["value"], new=details["new_label"]))
                .otherwise(
                    pl.col(label_col)
                    if label_col in variable_names
                    else pl.lit(None, dtype=pl.Utf8)
                )
                .alias(label_col)
            )
            if label_col not in variable_names:
                # Variable_names is a set, use .add instead of .append
                variable_names.add(label_col)
            transformed_lf = transformed_lf.with_columns([value_transform, label_transform])
    return transformed_lf
