"""Tests for the harmonize module."""

from __future__ import annotations

import warnings

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from nsch.harmonize import (
    MergeRule,
    RenameRule,
    TransformValues,
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
    # Also tests polars infers correct data type when types do not match
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
    # Assert on full frame
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


# Test label column stays in sync when logical skip triggers the use of the fallback value
# Test logical skip 998 in the preferred column uses the fallback value
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
    # also makes sure columns not mentioned in mergeRule are not changed
    lf = pl.LazyFrame(
        {"col_a": [996, 997, 998, 999], "col_b": [2, 3, 4, 5], "col_c": [0.01, 0.02, 0.03, 0.04]}
    )
    merges: dict[str, MergeRule] = {
        "merged": {"years": ["2016"], "column_fallback": "col_b", "column_preferred": "col_a"}
    }
    result = merge_vars(lf, merges, 2016)
    expected = pl.LazyFrame({"col_c": [0.01, 0.02, 0.03, 0.04], "merged": [996, 997, 4, 999]})
    assert_frame_equal(result, expected)


# Test no merge when merge_vars input year does not match MergeRule years
def test_non_matching_year() -> None:
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
