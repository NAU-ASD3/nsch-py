"""Functions for the harmonize module"""

from __future__ import annotations

import random
import warnings
from typing import TYPE_CHECKING, TypedDict

import polars as pl
import pyreadstat

from nsch._types import TaggedNA

if TYPE_CHECKING:
    from pathlib import Path

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
    ...     {"hoursleep": [1, 2, 3, 4], "hoursleep05": [None, None, 3, 4], "hhid": [5, 6, 7, 8]}
    ... )
    >>> merges: dict[str, MergeRule] = {
    ...     "sleep": {
    ...         "years": ["2023"],
    ...         "column_preferred": "hoursleep",
    ...         "column_fallback": "hoursleep05",
    ...     }
    ... }
    >>> merge_vars(lf, merges, 2023).collect()
    shape: (4, 2)
    ┌──────┬───────┐
    │ hhid ┆ sleep │
    │ ---  ┆ ---   │
    │ i64  ┆ i64   │
    ╞══════╪═══════╡
    │ 5    ┆ 1     │
    │ 6    ┆ 2     │
    │ 7    ┆ 3     │
    │ 8    ┆ 4     │
    └──────┴───────┘
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
                preferred_values == TaggedNA.LOGICAL_SKIP
            )

            # No cast to column type or int, polars will infer the type (divergence from R)
            # protects against mismatching types in columns to merge
            merged_lf = merged_lf.with_columns(
                pl.when(use_fallback)
                .then(fallback_values)
                .otherwise(preferred_values)
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
                    .alias(label_column),
                )

            merged_lf = merged_lf.drop(
                column_fallback,
                column_preferred,
                label_fallback,
                label_preferred,
                strict=False,
            )

    return merged_lf


def impute_a1_grade_2016(
    combined_df: pl.DataFrame, dta_2016_path: Path, seed: int = 1
) -> pl.DataFrame:
    """Redistributes coarse 2016 grade imputation across finer categories used
    in 2017 and later.
    In 2016, Census imputed ``a1_grade`` (Adult 1's highest education level)
    into 3 coarse categories stored in ``a1_grade_i``, rather than the 9
    fine-grained categories used in 2017 and later.

    This function cannot use the standard per-year config-driven transform pipeline
    because it requires cross-year proportion computation and probabilistic
    redistribution - operations that the per-year transform/rename/merge system
    does not support.

    For each 2016 row where the imputation flag is set, the function reads the
    coarse group from the raw 2016 ``.dta`` file, then uses weights derived from
    the non-2016 ``a1_grade`` distribution to assign a fine category. Reproducible
    given the same ``seed``.

    After assigning fine ``a1_grade`` values, the function deterministically
    updates ``higrade`` (3-level) and ``higrade_tvis`` (4-level) to be consistent,
    using the same mappings that ``apply_do_labels`` derives from the ``.do`` files.

    Parameters
    ----------
    combined_df : pl.DataFrame
        A pl.DataFrame of combined multi-year survey data, as returned by
        ``combine_years``. Must contain columns ``year``, ``hhid``, ``a1_grade``,
        ``higrade``, and ``higrade_tvis` (all factors).

    dta_2016_path : Path
        The path to the raw 2016 Stata ``.dta`` file. Must contain columns
        ``hhid``, ``a1_grade_if`` (imputation flag), and ``a1_grade_i`` (coarse
        imputed category: 1 = less than high school, 2 = high school graduate,
        3 = more than high school.)

    seed : int
        Integer seed used to set seed value before sampling to impute. Default ``1``.

    Returns:
    --------
        A pl.DataFrame of all years combined and values imputed.
    """
    # Make sure combined_df contains a `year` and an `hhid` column
    col_names = combined_df.columns
    if "year" not in col_names:
        raise ValueError("combined_df must contain a `year` column")
    if "hhid" not in col_names:
        raise ValueError("combined_df must contain a `hhid` column")

    # Read Raw 2016 .dta to access the imputation flag (a1_grade_if)
    # and coarse imputed category (a1_grade_i) because these columns are
    # not carried through harmonization.
    raw_2016, _ = pyreadstat.read_dta(str(dta_2016_path), user_missing=True, output_format="polars")
    required_columns = ["hhid", "a1_grade_if", "a1_grade_i"]
    if not set(required_columns).issubset(set(raw_2016.columns)):
        raise ValueError("2016 .dta must contain hhid, a1_grade_if, and a1_grade_i columns")

    # a1_grade_if: 0 = not imputed, 1 = imputed (tagged NAs become sentinels 996-999, so we match on
    # == 1). Keep first occurrence per hhid, to mirror R's match().
    imp_lookup = (
        raw_2016.select(required_columns)
        .filter(pl.col("a1_grade_if") == 1)  # Select imputed values only
        .unique(
            subset="hhid", keep="first", maintain_order=True
        )  # Select hhid to match to combined df
        .select(
            pl.col("hhid").cast(combined_df.schema["hhid"], strict=False),
            pl.col("a1_grade_i").cast(pl.Int64, strict=False).cast(pl.String).alias("coarse_data"),
        )
    )

    # Find 2016 rows in the combined data that were imputed
    # and join to the imp_lookup table of imputed hhids on hhid
    # using an inner join to select where hhid in list of imputed hhids
    indexed_df = combined_df.with_row_index("_row")
    rows_2016 = (
        indexed_df.filter(pl.col("year") == 2016)
        .join(imp_lookup, on="hhid", how="inner")
        .select("_row", "coarse_data")
        .sort("_row")
    )
    # Make if no rows for imputation found, return the input dataframe
    # without making changes
    if indexed_df.height == 0:
        return combined_df

    # Mapping from coarse a1_grade_i categories (1, 2, 3) to the fine
    # 9-category a1_grade levels used in 2017 onwards.
    #   1 = "Less than High School"  -> codes 1-2
    #   2 = "High School Graduate"   -> codes 3-4
    #   3 = "More than High School"  -> codes 5-9
    a1_groups = {
        "1": ["8th grade or less", "9th-12th grade; No diploma"],
        "2": [
            "High School Graduate or GED Completed",
            "Completed a vocational, trade, or business school program",
        ],
        "3": [
            "Some College Credit, but No Degree",
            "Associate Degree (AA, AS)",
            "Bachelor's Degree (BA, BS, AB)",
            "Master's Degree (MA, MS, MSW, MBA)",
            "Doctorate (PhD, EdD) or Professional Degree (MD, DDS, DVM, JD)",
        ],
    }

    # Mapping from fine a1_grade labels to the 3-level higrade variable.
    fine_to_higrade = {
        "8th grade or less": "Less than high school",
        "9th-12th grade; No diploma": "Less than high school",
        "High School Graduate or GED Completed": (
            "High school (including vocational, trade, or business school)"
        ),
        "Completed a vocational, trade, or business school program": (
            "High school (including vocational, trade, or business school)"
        ),
        "Some College Credit, but No Degree": "More than high school",
        "Associate Degree (AA, AS)": "More than high school",
        "Bachelor's Degree (BA, BS, AB)": "More than high school",
        "Master's Degree (MA, MS, MSW, MBA)": "More than high school",
        "Doctorate (PhD, EdD) or Professional Degree (MD, DDS, DVM, JD)": ("More than high school"),
    }

    # Mapping from fine a1_grade labels to the 4-level higrade_tvis
    # (a more detailed breakdown than higrade).
    fine_to_tvis = {
        "8th grade or less": "Less than high school",
        "9th-12th grade; No diploma": "Less than high school",
        "High School Graduate or GED Completed": (
            "High school (including vocational, trade, or business school)"
        ),
        "Completed a vocational, trade, or business school program": (
            "High school (including vocational, trade, or business school)"
        ),
        "Some College Credit, but No Degree": "Some college or Associate Degree",
        "Associate Degree (AA, AS)": "Some college or Associate Degree",
        "Bachelor's Degree (BA, BS, AB)": "College degree or higher",
        "Master's Degree (MA, MS, MSW, MBA)": "College degree or higher",
        "Doctorate (PhD, EdD) or Professional Degree (MD, DDS, DVM, JD)": (
            "College degree or higher"
        ),
    }

    # Compute the distribution of fine a1_grade categories from non-2016 rows
    # to use as sampling weights to redistribute coarse 2016 levels across
    # fine categories.
    fine_levels = pl.DataFrame(
        {
            "a1_grade": [level for levels in a1_groups.values() for level in levels],
            "group": [group for group, levels in a1_groups.items() for _ in levels],
        }
    )

    other_grades = (
        (
            indexed_df.filter((pl.col("year") != 2016) & pl.col("a1_grade").is_not_null())
            .select(pl.col("a1_grade"))
            .cast(pl.String)
        )
        .group_by("a1_grade")
        .len()
    )

    weights = (
        fine_levels.join(other_grades, on="a1_grade", how="left")
        .with_columns(pl.col("len").fill_null(0))  # mirror R's counts[is.na(counts)] <- 0
        # if the sum of a group is zero, fill with 1
        .with_columns(
            pl.when(pl.col("len").sum().over("group") == 0)
            .then(1)
            .otherwise(pl.col("len"))
            .alias("counts")
        )
    )
    # group -> (fine levels, weights) in a1_groups order
    group_weights = {
        group: (level, weight)
        for group, level, weight in weights.group_by("group", maintain_order=True)
        .agg("a1_grade", "counts")
        .iter_rows()
    }

    # Probabilistically assign fine categories within each coarse group.
    rand_gen = random.Random(seed)
    coarse = rows_2016["coarse_data"].to_list()
    new_a1 = [None] * len(coarse)
    for group, (levels, weight) in group_weights.items():
        index = [i for i, coarse_vals in enumerate(coarse) if coarse_vals == group]
        if index:
            draws = rand_gen.choices(levels, weights=weight, k=len(index))
            for (
                i,
                d,
            ) in zip(index, draws, strict=False):
                new_a1[i] = d

    # update row by row, preserving each column's existing enum (R factor) datatype and levels
    updated_df = pl.DataFrame(
        {"_row": rows_2016["_row"], "_new": pl.Series(new_a1, dtype=pl.String)}
    )
    indexed_df = indexed_df.join(updated_df, on="_row", how="left")
    is_target = pl.col("_row").is_in(rows_2016["_row"].implode())

    new_values = {
        "a1_grade": pl.col("_new"),
        "higrade": pl.col("_new").replace_strict(
            fine_to_higrade, default=None, return_dtype=pl.String
        ),
        "higrade_tvis": pl.col("_new").replace_strict(
            fine_to_tvis, default=None, return_dtype=pl.String
        ),
    }

    return indexed_df.with_columns(
        pl.when(is_target)
        .then(expr)
        .otherwise(pl.col(col).cast(pl.String))
        .cast(combined_df.schema[col])
        .alias(col)
        for col, expr in new_values.items()
    ).drop("_row", "_new")
