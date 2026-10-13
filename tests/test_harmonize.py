"""Tests for the harmonize module."""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import polars as pl
import pyreadstat
import pytest
from polars.testing import assert_frame_equal, assert_frame_not_equal

from nsch.harmonize import (
    MergeRule,
    RenameRule,
    TransformValues,
    impute_a1_grade_2016,
    merge_vars,
    rename_vars,
    subset_vars,
    transform_values,
)


def test_value_is_remapped_for_matching_year_and_label_column_is_created():
    lf = pl.LazyFrame({"k2q01_d": [1.0, 2.0, 3.0]})
    transforms = {
        "k2q01_d": TransformValues(
            {"years": ["2016", "2017"], "value": ["2"], "new_value": ["1"], "new_label": ["Yes"]}
        )
    }
    result = transform_values(lf, transforms, 2016).collect()
    expected = pl.DataFrame({"k2q01_d": [1.0, 1.0, 3.0], "k2q01_d_label": [None, "Yes", None]})
    assert_frame_equal(result, expected)


def test_no_changes_for_non_matching_years():
    lf = pl.LazyFrame({"k2q01_d": [1, 2, 3]})
    transforms = {
        "k2q01_d": TransformValues(
            {"years": ["2017"], "value": ["2"], "new_value": ["1"], "new_label": ["Yes"]}
        )
    }
    result = transform_values(lf, transforms, 2020).collect()
    expected = pl.DataFrame({"k2q01_d": [1, 2, 3]})
    assert_frame_equal(result, expected)


def test_multiple_values_and_multiple_columns_are_remapped_for_matching_year():
    lf = pl.LazyFrame({"family": [1, 2, 3, 4], "hoursleep": [1, 2, 3, 4]})
    transforms = {
        "family": TransformValues(
            {
                "years": ["2016"],
                "value": ["1", "2", "3", "4"],
                "new_value": ["1", "1", "2", "2"],
                "new_label": ["Two Parents", "Two Parents", "Other", "Other"],
            }
        ),
        "hoursleep": TransformValues(
            {
                "years": ["2016", "2017"],
                "value": ["1", "2", "3", "4"],
                "new_value": ["1", "1", "3", "3"],
                "new_label": ["7 hours", "7 hours", "8 hours", "8 hours"],
            },
        ),
    }
    result = transform_values(lf, transforms, 2016).collect()
    expected = pl.DataFrame(
        {
            "family": [1, 1, 2, 2],
            "hoursleep": [1, 1, 3, 3],
            "family_label": ["Two Parents", "Two Parents", "Other", "Other"],
            "hoursleep_label": ["7 hours", "7 hours", "8 hours", "8 hours"],
        }
    )
    assert_frame_equal(result, expected)


def test_label_only_transforms_work():
    lf = pl.LazyFrame({"sex": [1, 2, 1]})
    transforms = {
        "sex": TransformValues(
            {
                "years": ["2017"],
                "value": ["1", "2"],
                "new_value": ["1", "2"],
                "new_label": ["Male", "Female"],
            }
        )
    }
    result = transform_values(lf, transforms, 2017).collect()
    expected = pl.DataFrame({"sex": [1, 2, 1], "sex_label": ["Male", "Female", "Male"]})
    assert_frame_equal(result, expected)


def test_missing_variable_in_lf_is_silently_skipped():
    lf = pl.LazyFrame({"x": [1, 2]})
    transforms = {
        "not_here": TransformValues(
            {"years": ["2017"], "value": ["1"], "new_value": ["2"], "new_label": ["Two"]}
        )
    }
    # If warnings are raised, treat as errors
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = transform_values(lf, transforms, 2017).collect()
        assert_frame_equal(result, pl.DataFrame({"x": [1, 2]}))


def test_existing_label_cols_are_updated_with_values_filled():
    lf = pl.LazyFrame({"k2q01_d": [2.0, 2.0, 3.0], "k2q01_d_label": ["No", None, None]})
    transforms = {
        "k2q01_d": TransformValues(
            {"years": ["2016", "2017"], "value": ["2"], "new_value": ["2"], "new_label": ["Yes"]}
        )
    }
    result = transform_values(lf, transforms, 2016).collect()
    expected = pl.DataFrame({"k2q01_d": [2.0, 2.0, 3.0], "k2q01_d_label": ["Yes", "Yes", None]})
    assert_frame_equal(result, expected)


def test_empty_input_returns_empty():
    lf = pl.LazyFrame()
    transforms = {
        "k2q01_d": TransformValues(
            {"years": ["2016", "2017"], "value": ["2"], "new_value": ["2"], "new_label": ["Yes"]}
        )
    }
    result = transform_values(lf, transforms, 2017)
    assert_frame_equal(lf.collect(), result.collect())


def test_matching_year_but_no_matching_values_creates_null_label_column():
    lf = pl.LazyFrame({"k2q01_d": [1, 2, 3]})
    transforms = {
        "k2q01_d": TransformValues(
            {"years": ["2017"], "value": ["4"], "new_value": ["5"], "new_label": ["Yes"]}
        )
    }
    result = transform_values(lf, transforms, 2017).collect()
    expected = pl.DataFrame(
        {"k2q01_d": [1, 2, 3], "k2q01_d_label": [None, None, None]},
        schema={"k2q01_d": pl.Int64, "k2q01_d_label": pl.Utf8},
    )
    assert_frame_equal(result, expected)


def test_raises_error_for_duplicate_values_in_lookup():
    # Protects against a bad Config
    lf = pl.LazyFrame({"k2q01_d": [1, 2, 3]})
    transforms = {
        "k2q01_d": TransformValues(
            {
                "years": ["2016", "2017"],
                "value": ["2", "2"],
                "new_value": ["2", "3"],
                "new_label": ["Yes", "Yes"],
            }
        )
    }
    with pytest.raises(ValueError, match="Duplicate"):
        transform_values(lf, transforms, 2016)


def test_subset_vars_retains_only_desired_columns_plus_labels():
    lf = pl.LazyFrame({"a": [1, 2, 3], "a_label": ["x", "y", "z"], "b": [4, 5, 6], "c": [7, 8, 9]})
    result = subset_vars(lf, ["a", "c"])
    assert result.collect_schema().names() == ["a", "c", "a_label"]


def test_warning_for_missing_desired_subset_variable():
    df = pl.LazyFrame({"a": [1, 2, 3], "a_label": ["x", "y", "z"], "b": [4, 5, 6], "c": [7, 8, 9]})
    with pytest.warns(UserWarning, match="not found"):
        subset_vars(df, ["a", "x"])


# tests for rename_vars
def test_renames_a_column_for_a_matching_year() -> None:
    lf = pl.LazyFrame({"gowhensick": [1, 2, 3], "hhid": [10, 20, 30]})
    renames: dict[str, RenameRule] = {
        "gowhensick": {"years": ["2023", "2024"], "new_name": "k4q02_r"}
    }
    result = rename_vars(lf, renames, 2023)
    # The function stays lazy: nothing is collected until the caller asks.
    assert isinstance(result, pl.LazyFrame)
    collected = result.collect()
    assert collected.columns == ["k4q02_r", "hhid"]
    assert collected["k4q02_r"].to_list() == [1, 2, 3]


def test_leaves_columns_unchanged_for_a_nonmatching_year() -> None:
    lf = pl.LazyFrame({"gowhensick": [1, 2, 3]})
    renames: dict[str, RenameRule] = {
        "gowhensick": {"years": ["2023", "2024"], "new_name": "k4q02_r"}
    }
    # 2016 isn't in the rule's years, so the column keeps its source name.
    result = rename_vars(lf, renames, 2016).collect()
    assert result.columns == ["gowhensick"]


def test_ignores_rules_for_columns_that_are_absent() -> None:
    lf = pl.LazyFrame({"hhid": [10, 20, 30]})
    renames: dict[str, RenameRule] = {"gowhensick": {"years": ["2023"], "new_name": "k4q02_r"}}
    result = rename_vars(lf, renames, 2023).collect()
    assert result.columns == ["hhid"]


def test_renames_the_label_companion_too() -> None:
    lf = pl.LazyFrame({"gowhensick": [4, 8], "gowhensick_label": ["Clinic", "Other"]})
    renames: dict[str, RenameRule] = {"gowhensick": {"years": ["2023"], "new_name": "k4q02_r"}}
    result = rename_vars(lf, renames, 2023).collect()
    assert result.columns == ["k4q02_r", "k4q02_r_label"]
    assert result["k4q02_r_label"].to_list() == ["Clinic", "Other"]


def test_applies_several_rules_in_one_call() -> None:
    lf = pl.LazyFrame({"gowhensick": [1], "family_r": [2], "hhid": [3]})
    renames: dict[str, RenameRule] = {
        "gowhensick": {"years": ["2023"], "new_name": "k4q02_r"},
        "family_r": {"years": ["2023"], "new_name": "family"},
    }
    result = rename_vars(lf, renames, 2023).collect()
    expected = pl.DataFrame({"k4q02_r": [1], "family": [2], "hhid": [3]})
    assert_frame_equal(result, expected)


def test_empty_renames_leaves_the_frame_unchanged() -> None:
    lf = pl.LazyFrame({"hhid": [1, 2]})
    result = rename_vars(lf, {}, 2023).collect()
    assert_frame_equal(result, pl.DataFrame({"hhid": [1, 2]}))


def test_renames_are_applied_simultaneously_not_chained() -> None:
    # R renames in a loop, so these two rules cascade there and gowhensick
    # ends up as k4q02_r. Here both rules read the original names, so each
    # column moves exactly one step.
    lf = pl.LazyFrame({"gowhensick": [1], "family_r": [2]})
    renames: dict[str, RenameRule] = {
        "gowhensick": {"years": ["2023"], "new_name": "family_r"},
        "family_r": {"years": ["2023"], "new_name": "k4q02_r"},
    }
    result = rename_vars(lf, renames, 2023).collect()
    expected = pl.DataFrame({"family_r": [1], "k4q02_r": [2]})
    assert_frame_equal(result, expected)


def test_raises_when_two_rules_target_the_same_name() -> None:
    lf = pl.LazyFrame({"gowhensick": [1], "family_r": [2]})
    renames: dict[str, RenameRule] = {
        "gowhensick": {"years": ["2023"], "new_name": "k4q02_r"},
        "family_r": {"years": ["2023"], "new_name": "k4q02_r"},
    }
    with pytest.raises(ValueError, match="more than one column"):
        rename_vars(lf, renames, 2023)


def test_raises_when_a_rename_target_collides_with_an_existing_column() -> None:
    lf = pl.LazyFrame({"gowhensick": [1], "k4q02_r": [2]})
    renames: dict[str, RenameRule] = {"gowhensick": {"years": ["2023"], "new_name": "k4q02_r"}}
    with pytest.raises(ValueError, match="existing columns"):
        rename_vars(lf, renames, 2023)


# Tests for merge_vars
def test_merges_preferred_columns() -> None:
    # Also tests that polars infers correct data type when types do not match
    lf = pl.LazyFrame({"a": [1.0, 2.5, 3.0, 4.0], "b": [None, None, 3, 4], "c": [5, 6, 7, 8]})
    merges: dict[str, MergeRule] = {
        "ab_merged": {
            "years": ["2023"],
            "column_preferred": "a",
            "column_fallback": "b",
        }
    }
    expected = pl.DataFrame({"c": [5, 6, 7, 8], "ab_merged": [1.0, 2.5, 3.0, 4.0]})
    result = merge_vars(lf, merges, 2023).collect()
    assert_frame_equal(expected, result)


def test_merges_label_columns() -> None:
    lf = pl.LazyFrame(
        {"a": [1, None], "b": [None, 2], "a_label": ["One", None], "b_label": [None, "Two"]}
    )
    merges: dict[str, MergeRule] = {
        "merged": {"years": ["2016"], "column_preferred": "a", "column_fallback": "b"}
    }

    expected = pl.DataFrame({"merged": [1, 2], "merged_label": ["One", "Two"]})
    result = merge_vars(lf, merges, 2016).collect()
    assert_frame_equal(expected, result)


# Test label column stays in sync when logical skip (998) triggers the use of the fallback value
def test_logical_skip_uses_fallback_in_preferred_and_label_columns() -> None:
    lf = pl.LazyFrame(
        {
            "a": [1, 998, 998],
            "b": [None, 2, None],
            "a_label": ["One", None, None],
            "b_label": [None, "Two", None],
        }
    )
    merges: dict[str, MergeRule] = {
        "merged": {"years": ["2016"], "column_preferred": "a", "column_fallback": "b"}
    }
    result = merge_vars(lf, merges, 2016).collect()
    expected = pl.DataFrame({"merged": [1, 2, None], "merged_label": ["One", "Two", None]})
    assert_frame_equal(result, expected)


def test_missing_source_columns_are_silently_skipped() -> None:
    lf = pl.LazyFrame({"x": [1, 2]})
    merges: dict[str, MergeRule] = {
        "merged": {
            "years": ["2016"],
            "column_preferred": "not_here",
            "column_fallback": "also_not_here",
        }
    }

    result = merge_vars(lf, merges, 2016)
    assert_frame_equal(lf, result)


def test_non_logical_skip_does_not_use_fallback_value() -> None:
    # also makes sure columns not mentioned in mergeRule remain unchanged
    lf = pl.LazyFrame(
        {"col_a": [996, 997, 998, 999], "col_b": [2, 3, 4, 5], "col_c": [0.01, 0.02, 0.03, 0.04]}
    )
    merges: dict[str, MergeRule] = {
        "merged": {"years": ["2016"], "column_fallback": "col_b", "column_preferred": "col_a"}
    }
    result = merge_vars(lf, merges, 2016)
    expected = pl.LazyFrame({"col_c": [0.01, 0.02, 0.03, 0.04], "merged": [996, 997, 4, 999]})
    assert_frame_equal(result, expected)


def test_no_merge_applied_for_a_non_matching_year() -> None:
    lf = pl.LazyFrame({"col_a": [1, None], "col_b": [None, 2]})
    merges: dict[str, MergeRule] = {
        "merged": {"years": ["2016"], "column_fallback": "col_b", "column_preferred": "col_a"}
    }
    result = merge_vars(lf, merges, 2017)
    assert_frame_equal(result, lf)


def test_no_merge_applied_when_only_one_column_present() -> None:
    lf = pl.LazyFrame({"col_a": [1, None]})
    merges: dict[str, MergeRule] = {
        "merged": {"years": ["2016"], "column_fallback": "col_b", "column_preferred": "col_a"}
    }
    result = merge_vars(lf, merges, 2016)
    assert_frame_equal(result, lf)


# Tests for impute_a1_grade_2016
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
