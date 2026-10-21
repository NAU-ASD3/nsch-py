"""Tests for impute_a1_grade_2016."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pyreadstat
import pytest
from polars.testing import assert_frame_equal, assert_frame_not_equal

from nsch.impute import impute_a1_grade_2016

# Function to create Synthetic .dta in data/make_fixtures.py
PATH_2016_DTA: Path = Path("tests/data/2016_impute_test.dta")
PATH_2016_LARGE_DTA: Path = Path("tests/data/2016_large_impute_test.dta")


A1_LEVELS = [
    "8th grade or less",
    "9th-12th grade; No diploma",
    "High School Graduate or GED Completed",
    "Completed a vocational, trade, or business school program",
    "Some College Credit, but No Degree",
    "Associate Degree (AA, AS)",
    "Bachelor's Degree (BA, BS, AB)",
    "Master's Degree (MA, MS, MSW, MBA)",
    "Doctorate (PhD, EdD) or Professional Degree (MD, DDS, DVM, JD)",
]

HIGRADE_LEVELS = [
    "Less than high school",
    "High school (including vocational, trade, or business school)",
    "More than high school",
]

HIGRADE_TVIS_LEVELS = [
    "Less than high school",
    "High school (including vocational, trade, or business school)",
    "Some college or Associate Degree",
    "College degree or higher",
]

# Coarse a1_grade_i category (as a string) -> fine a1_grade levels
A1_GROUPS = {
    "1": A1_LEVELS[0:2],
    "2": A1_LEVELS[2:4],
    "3": A1_LEVELS[4:9],
}

# Fine a1_grade level -> 3-level higrade
FINE_TO_HIGRADE = {
    A1_LEVELS[0]: HIGRADE_LEVELS[0],
    A1_LEVELS[1]: HIGRADE_LEVELS[0],
    A1_LEVELS[2]: HIGRADE_LEVELS[1],
    A1_LEVELS[3]: HIGRADE_LEVELS[1],
    A1_LEVELS[4]: HIGRADE_LEVELS[2],
    A1_LEVELS[5]: HIGRADE_LEVELS[2],
    A1_LEVELS[6]: HIGRADE_LEVELS[2],
    A1_LEVELS[7]: HIGRADE_LEVELS[2],
    A1_LEVELS[8]: HIGRADE_LEVELS[2],
}

# Fine a1_grade level -> 4-level higrade_tvis
FINE_TO_TVIS = {
    A1_LEVELS[0]: HIGRADE_TVIS_LEVELS[0],
    A1_LEVELS[1]: HIGRADE_TVIS_LEVELS[0],
    A1_LEVELS[2]: HIGRADE_TVIS_LEVELS[1],
    A1_LEVELS[3]: HIGRADE_TVIS_LEVELS[1],
    A1_LEVELS[4]: HIGRADE_TVIS_LEVELS[2],
    A1_LEVELS[5]: HIGRADE_TVIS_LEVELS[2],
    A1_LEVELS[6]: HIGRADE_TVIS_LEVELS[3],
    A1_LEVELS[7]: HIGRADE_TVIS_LEVELS[3],
    A1_LEVELS[8]: HIGRADE_TVIS_LEVELS[3],
}

A1_ENUM = pl.Enum(A1_LEVELS)
HIGRADE_ENUM = pl.Enum(HIGRADE_LEVELS)
TVIS_ENUM = pl.Enum(HIGRADE_TVIS_LEVELS)


def make_combined_test_dataframe(
    n_rows_2016: int = 10, n_rows_other_years: int = 40, seed: int = 1
) -> pl.DataFrame:
    """Helper function for testing impute_a1_grades. Builds a minimal combined_df with rows for
    2016 containing ``None`` for a1_grade, and rows for other years containing populated
    a1_grade values.

    Parameters
    ----------
    n_rows_2016 : int
        Number of rows with the year 2016 to be included.
    n_rows_other_years : int
        Number of rows with years other than 2016 to be included.
    seed : int
        Seed for random functions. Default 1.

    Returns
    -------
    A ``pl.DataFrame`` containing missing and populated a1_grade rows for 2016 and other years,
    respectively.
    """
    rng = np.random.default_rng(seed)
    other_grades = rng.choice(A1_LEVELS, size=n_rows_other_years, replace=True).tolist()

    dt_other = pl.DataFrame(
        {
            "year": pl.Series([2017] * n_rows_other_years, dtype=pl.Int32),
            "hhid": pl.Series(range(1, n_rows_other_years + 1), dtype=pl.Int32) + 1000,
            "a1_grade": pl.Series(other_grades, dtype=A1_ENUM),
            "higrade": pl.Series([FINE_TO_HIGRADE[g] for g in other_grades], dtype=HIGRADE_ENUM),
            "higrade_tvis": pl.Series([FINE_TO_TVIS[g] for g in other_grades], dtype=TVIS_ENUM),
        }
    )

    dt_2016 = pl.DataFrame(
        {
            "year": pl.Series([2016] * n_rows_2016, dtype=pl.Int32),
            "hhid": pl.Series(range(1, n_rows_2016 + 1), dtype=pl.Int32),
            "a1_grade": pl.Series([None] * n_rows_2016, dtype=A1_ENUM),
            "higrade": pl.Series([None] * n_rows_2016, dtype=HIGRADE_ENUM),
            "higrade_tvis": pl.Series([None] * n_rows_2016, dtype=TVIS_ENUM),
        }
    )

    return pl.concat([dt_2016, dt_other])


def test_a1_grade_imputation_is_reproducable_with_same_seed() -> None:
    """Test imputation result is reproducable when the same seed is used for each call"""
    combine_df = make_combined_test_dataframe(10, 40)
    # DataFrame is not modified in-place like the R version, so no need for 2 combine frames
    imputed_df_1 = impute_a1_grade_2016(combine_df, PATH_2016_DTA, seed=42)
    imputed_df_2 = impute_a1_grade_2016(combine_df, PATH_2016_DTA, seed=42)
    assert_frame_equal(imputed_df_1, imputed_df_2)


def test_a1_grade_imputation_is_different_with_different_seed() -> None:
    """Test imputation result is different when the different seeds are used for each call"""
    combine_df = make_combined_test_dataframe(100, 400)
    # DataFrame is not modified in-place like the R version, so no need for 2 combine frames
    imputed_df_1 = impute_a1_grade_2016(combine_df, PATH_2016_LARGE_DTA, seed=1)
    imputed_df_2 = impute_a1_grade_2016(combine_df, PATH_2016_LARGE_DTA, seed=2)
    assert_frame_not_equal(imputed_df_1, imputed_df_2)


def test_a1_grade_imputation_modifies_only_2016_rows_with_impute_flags() -> None:
    """Test only 2016 rows with impute flags are modified,
    rows with non-impute flags are not modified"""
    combine_df = make_combined_test_dataframe(10, 40)
    imputed_df = impute_a1_grade_2016(combine_df, PATH_2016_DTA, seed=1)

    # derive flagged hhids and their coarse group independently from the raw file
    raw, _ = pyreadstat.read_dta(str(PATH_2016_DTA), user_missing=True, output_format="polars")
    coarse_by_hhid = dict(
        raw.filter(pl.col("a1_grade_if") == 1)
        .unique(subset="hhid", keep="first", maintain_order=True)
        .select(
            pl.col("hhid").cast(combine_df.schema["hhid"], strict=False),
            pl.col("a1_grade_i").cast(pl.Int64).cast(pl.String),
        )
        .iter_rows()
    )
    mask = (combine_df["year"] == 2016) & combine_df["hhid"].is_in(list(coarse_by_hhid))

    # flagged rows: fine category lies in the coarse group, derived columns are consistent
    cols = ["hhid", "a1_grade", "higrade", "higrade_tvis"]
    for hhid, a1, higrade, tvis in imputed_df.filter(mask).select(cols).iter_rows():
        assert a1 in A1_GROUPS[coarse_by_hhid[hhid]]
        assert higrade == FINE_TO_HIGRADE[a1]
        assert tvis == FINE_TO_TVIS[a1]

    # Make sure only values are changed, not data length or types/columns
    assert imputed_df.schema == combine_df.schema
    assert imputed_df.height == combine_df.height
    assert mask.any(), "no flagged 2016 rows in test data, test does not check anything"
    # everything not flagged (other years, unflagged 2016 rows) is untouched
    assert_frame_equal(combine_df.filter(~mask), imputed_df.filter(~mask))


def test_a1_grade_imputation_raises_on_invalid_coarse_code(tmp_path: Path) -> None:
    """Test flagged 2016 rows with a coarse code outside {1, 2, 3} raise instead of becoming null"""
    combine_df = make_combined_test_dataframe(3, 40)
    bad_dta = tmp_path / "bad_2016.dta"
    pyreadstat.write_dta(
        pl.DataFrame({"hhid": [1, 2, 3], "a1_grade_if": [1, 1, 1], "a1_grade_i": [1, 2, 4]}),
        str(bad_dta),
    )
    with pytest.raises(ValueError, match="outside"):
        impute_a1_grade_2016(combine_df, bad_dta, seed=1)


def test_a1_grade_imputation_raises_when_dta_lacks_required_columns(tmp_path: Path) -> None:
    """A 2016 file without a1_grade_i raises a clear error before any data is read"""
    combine_df = make_combined_test_dataframe(3, 40)
    no_coarse_dta = tmp_path / "no_coarse_2016.dta"
    pyreadstat.write_dta(
        pl.DataFrame({"hhid": [1, 2, 3], "a1_grade_if": [1, 1, 1]}),
        str(no_coarse_dta),
    )
    with pytest.raises(ValueError, match="must contain hhid, a1_grade_if, and a1_grade_i"):
        impute_a1_grade_2016(combine_df, no_coarse_dta, seed=1)
