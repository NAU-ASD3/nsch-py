"""The one-off 2016 ``a1_grade`` imputation that runs after ``combine_years``."""

from __future__ import annotations

import importlib.resources
import random
from typing import TYPE_CHECKING

import polars as pl
import pyreadstat

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["impute_a1_grade_2016"]


def impute_a1_grade_2016(
    combined_df: pl.DataFrame, dta_2016_path: Path, seed: int = 1
) -> pl.DataFrame:
    """Redistributes coarse 2016 grade imputation across finer categories used
    in 2017 and later.
    In 2016, Census imputed ``a1_grade`` (Adult 1's highest education level)
    into 3 coarse categories stored in ``a1_grade_i``, rather than the 9
    fine-grained categories used in 2017 and later.

    This function cannot use the standard per-year config-driven transform pipeline
    because it reads columns from the raw 2016 file that harmonization drops
    (``a1_grade_if``, ``a1_grade_i``) and draws at random, operations that the
    per-year transform/rename/merge system does not support.

    For each 2016 row where the imputation flag is set, the function reads the
    coarse group from the raw 2016 ``.dta`` file, then draws a fine category within
    that group. Reproducible given the same ``seed``.

    The sampling weights are how often each fine category occurs among respondents
    whose ``a1_grade`` was itself imputed (``a1_grade_if`` = 1) in 2017 to 2022, the
    pool the original analysis used. They ship with the package as
    ``nsch/data/a1_grade_2016_weights.csv``, the same file as the R package's, so the
    2016 values do not depend on which other years ``combined_df`` contains.

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

    Returns
    -------
    pl.DataFrame
        All years combined, with the flagged 2016 rows imputed.

    Raises
    ------
    ValueError
        If a1_grade_i contains values outside the coarse values
        {1, 2, 3} for imputed rows
    polars.exceptions.InvalidOperationError
        If a drawn category is not a level of ``a1_grade``'s Enum

    Notes
    -----
    R leaves a flagged row with an unknown coarse code empty instead of
    raising. Raising here is deliberate: in the real 2016 file all 1,524
    flagged rows have a code of 1, 2 or 3, so an unknown code means the
    input file is not what this function expects.
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
    # Check the column names from the file's metadata first, then read only those three
    # columns instead of the whole 2016 file.
    required_columns = ["hhid", "a1_grade_if", "a1_grade_i"]
    _, meta = pyreadstat.read_dta(str(dta_2016_path), metadataonly=True, output_format="polars")
    if not set(required_columns).issubset(set(meta.column_names)):
        raise ValueError("2016 .dta must contain hhid, a1_grade_if, and a1_grade_i columns")
    raw_2016, _ = pyreadstat.read_dta(
        str(dta_2016_path), usecols=required_columns, user_missing=True, output_format="polars"
    )

    # a1_grade_if is 1 for imputed rows. In the real 2016 file the other rows are missing
    # rather than 0, so match on == 1. Keep first occurrence per hhid, to mirror R's match().
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
    if rows_2016.height == 0:
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
            "Some College Credit, but no Degree",
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
        "Some College Credit, but no Degree": "More than high school",
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
        "Some College Credit, but no Degree": "Some college or Associate Degree",
        "Associate Degree (AA, AS)": "Some college or Associate Degree",
        "Bachelor's Degree (BA, BS, AB)": "College degree or higher",
        "Master's Degree (MA, MS, MSW, MBA)": "College degree or higher",
        "Doctorate (PhD, EdD) or Professional Degree (MD, DDS, DVM, JD)": (
            "College degree or higher"
        ),
    }

    # Sampling weights: how often each fine category occurs among respondents whose a1_grade was
    # itself imputed (a1_grade_if = 1) in 2017-2022, as in the original analysis. They ship with
    # the package, so 2016's values don't depend on which other years combined_df holds.
    # data-raw/a1_grade_2016_weights.R in NAU-ASD3/nsch rebuilds the file from the raw data.
    weights_csv = importlib.resources.files("nsch.data").joinpath("a1_grade_2016_weights.csv")
    counts = dict(pl.read_csv(weights_csv.read_bytes()).select("label", "n").iter_rows())
    group_weights = {
        group: (levels, [counts[level] for level in levels]) for group, levels in a1_groups.items()
    }

    # Probabilistically assign fine categories within each coarse group.
    rand_gen = random.Random(seed)
    coarse = rows_2016["coarse_data"].to_list()
    new_a1: list[str | None] = [None] * len(coarse)
    for group, (levels, weight) in group_weights.items():
        index = [i for i, coarse_vals in enumerate(coarse) if coarse_vals == group]
        if index:
            draws = rand_gen.choices(levels, weights=weight, k=len(index))
            for i, d in zip(index, draws, strict=False):
                new_a1[i] = d

    # Raise if a1 values are outside imputation range
    if any(v is None for v in new_a1):
        raise ValueError("a1_grade_i contains values outside {1, 2, 3} for imputed rows")

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
