"""The one-off 2016 ``a1_grade`` imputation that runs after ``combine_years``."""

from __future__ import annotations

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

    Returns
    -------
    pl.DataFrame
        All years combined, with the flagged 2016 rows imputed.

    Raises
    ------
    ValueError
        If a1_grade_i contains values outside the coarse values
        {1, 2, 3} for imputed rows
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
