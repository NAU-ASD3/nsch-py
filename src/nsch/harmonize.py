"""Functions for the harmonize module"""

from __future__ import annotations

import warnings
from typing import TypedDict

import polars as pl

from nsch import _types

__all__ = [
    "MergeRule",
    "RenameRule",
    "TransformValues",
    "merge_vars",
    "rename_vars",
    "subset_vars",
    "transform_values",
]


class RenameRule(TypedDict):
    """One rename rule: the years it applies to, and the harmonized name."""

    years: list[str]
    new_name: str


class MergeRule(TypedDict):
    """One merge rule with its applicable years and source columns."""

    years: list[str]
    column_preferred: str
    column_fallback: str


class TransformValues(TypedDict):
    """One transform rule: the years and values it applies to, and the new values and labels."""

    years: list[str]
    value: list[str]
    new_value: list[str]
    new_label: list[str]


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

    Raises
    ------
    ValueError
        If two rules rename different columns to the same name, or if a rule
        renames a column onto the name of one that already exists and isn't
        itself being renamed. Both point at a malformed config.

    Notes
    -----
    Renames are applied all at once rather than one after another. The R
    version loops and renames in place, so a pair of rules like ``a -> b`` and
    ``b -> c`` cascades there and ``a`` ends up as ``c``. Here both rules read
    the original column names, so ``a`` becomes ``b`` and the original ``b``
    becomes ``c``. Reading from the original names is the intended behavior: a
    rule should describe the column it names in the source data, not whatever
    an earlier rule happened to leave behind.

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

    # Two rules pointing at the same name would silently collapse two columns
    # into one, so catch it here where we can name the year and the columns.
    seen: set[str] = set()
    duplicates: set[str] = set()
    for target in mapping.values():
        if target in seen:
            duplicates.add(target)
        seen.add(target)
    if duplicates:
        raise ValueError(
            f"Rename rules for {year} map more than one column to: {', '.join(sorted(duplicates))}"
        )

    # Renaming onto a column that already exists and isn't itself being renamed
    # collides. Polars raises for this, but without saying which year or rule
    # caused it.
    collisions = sorted(set(mapping.values()) & (present - set(mapping)))
    if collisions:
        raise ValueError(
            f"Rename rules for {year} target existing columns that are not "
            f"themselves renamed: {', '.join(collisions)}"
        )

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
    remapped rows and silently skips variables not present in the input ``pl.LazyFrame``.

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

            # Create a mapping between values and new values/labels for the transform
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


def subset_vars(lf: pl.LazyFrame, desired_variables: list[str]) -> pl.LazyFrame:
    """Select desired variables and their label companions.

    Returns a new ``pl.LazyFrame`` containing only the columns listed
    in ``desired_variables``, plus any corresponding ``_label``
    companion columns that exist.  Issues a ``warning`` for each
    variable in ``desired_variables`` not found in ``lf`` which is
    expected when a variable does not exist in a particular year.

    Parameters
    ----------
    lf : pl.LazyFrame
        A Polars LazyFrame to select desired variable from
    desired_variables : list[str]
        A list of desired variable column names, as strings

    Returns
    -------
    a pl.LazyFrame containing only the variables selected using
    ``desired_variables`` and their ``_label`` columns

    Examples
    --------
    >>> import polars as pl
    >>> lf = pl.LazyFrame(
    ...     {"a": [1, 2, 3], "a_label": ["x", "y", "z"], "b": [4, 5, 6], "c": [7, 8, 9]}
    ... )
    >>> subset_vars(lf, ["a", "c"]).collect()
    shape: (3, 3)
    ┌─────┬─────┬─────────┐
    │ a   ┆ c   ┆ a_label │
    │ --- ┆ --- ┆ ---     │
    │ i64 ┆ i64 ┆ str     │
    ╞═════╪═════╪═════════╡
    │ 1   ┆ 7   ┆ x       │
    │ 2   ┆ 8   ┆ y       │
    │ 3   ┆ 9   ┆ z       │
    └─────┴─────┴─────────┘
    """
    lf_variables = lf.collect_schema().names()
    # Warn for each desired variable not found in df.
    missing = [c for c in desired_variables if c not in lf_variables]
    for m in missing:
        warnings.warn(UserWarning(f"Desired variable {m} not found in lf"), stacklevel=2)

    # Collect the data columns plus any _label companions.
    present = [c for c in desired_variables if c in lf_variables]
    label_cols = [l_col + "_label" for l_col in present]
    label_cols = [l_col for l_col in label_cols if l_col in lf_variables]
    keep = present + label_cols
    return lf.select(keep)


def merge_vars(lf: pl.LazyFrame, merges: dict[str, MergeRule], year: int) -> pl.LazyFrame:
    """Merge preferred and fallback columns for a survey year.

    The preferred column is normally used. The fallback column is used when
    the preferred value is null or contains the logical skip sentinel, 998.

    If both corresponding ``_label`` columns exist, they are merged using
    the same preferred-versus-fallback condition.

    Original value and label columns are removed after merging.

    Parameters
    ----------
    lf : pl.LazyFrame
        A polars LazyFrame with the columns to merge.
    merges : dict[str, MergeRule]
        A named dictionary containing a Merge Rule and Year from the ``.json`` config file.
        This structure defines the mapping between the preferred and fallback columns
        for a given year.
    year : int
        The year of data on which to perform the merge.

    Returns
    -------
    A pl.LazyFrame containing the merged column and its associated ``_label`` column, if present,
    as well as any other untouched columns. The original preferred and fallback columns are removed.

    Examples
    --------
    >>> import polars as pl
    >>> lf = pl.LazyFrame(
    ...     {"gowhensick": [1, 2, 3, 4], "k4q02_r": [None, None, 3, 4], "hhid": [5, 6, 7, 8]}
    ... )
    >>> merges: dict[str, MergeRule] = {
    ...     "gowhensick_merged": {
    ...         "years": ["2023"],
    ...         "column_preferred": "k4q02_r",
    ...         "column_fallback": "gowhensick",
    ...     }
    ... }
    >>> merge_vars(lf, merges, 2023).collect()
    shape: (4, 2)
    ┌──────┬───────────────────┐
    │ hhid ┆ gowhensick_merged │
    │ ---  ┆ ---               │
    │ i64  ┆ i64               │
    ╞══════╪═══════════════════╡
    │ 5    ┆ 1                 │
    │ 6    ┆ 2                 │
    │ 7    ┆ 3                 │
    │ 8    ┆ 4                 │
    └──────┴───────────────────┘
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
