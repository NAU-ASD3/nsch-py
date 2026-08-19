"""Tests for the harmonize module."""

from __future__ import annotations

import polars as pl
from polars.testing import assert_frame_equal

from nsch.harmonize import MergeRule, RenameRule, merge_vars, rename_vars


def test_renames_a_column_for_a_matching_year() -> None:
    lf = pl.LazyFrame({"gowhensick": [1, 2, 3], "hhid": [10, 20, 30]})
    renames: dict[str, RenameRule] = {
        "gowhensick": {"years": ["2023", "2024"], "new_name": "k4q02_r"}
    }
    result = rename_vars(lf, renames, 2023).collect()
    assert result.columns == ["k4q02_r", "hhid"]
    assert result["k4q02_r"].to_list() == [1, 2, 3]


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
    assert result.columns == ["k4q02_r", "family", "hhid"]


# Tests for merge_vars


def test_merges_preferred_colums() -> None:
    lf = pl.LazyFrame(
        {"gowhensick": [1, 2, 3, 4], "k4q02_r": [None, None, 3, 4], "hhid": [5, 6, 7, 8]}
    )
    merges: dict[str, MergeRule] = {
        "gowhensick_merged": {
            "years": ["2023"],
            "column_preferred": "k4q02_r",
            "column_fallback": "gowhensick",
        }
    }
    # Create a pl.DataFrame called "expected" that contains what our result should look like
    expected = pl.DataFrame(
        {
            "hhid": [5, 6, 7, 8],
            "gowhensick_merged": [1, 2, 3, 4],
        }
    )
    result = merge_vars(lf, merges, 2023).collect()
    # Assert on full frame
    assert_frame_equal(expected, result)


# Test label columns are also merged
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


# Test non-logical skip values (sentinals that are not 998) do NOT use the fallback value
def test_non_logical_skip_does_not_use_fallback_value() -> None:
    lf = pl.LazyFrame({"col_a": [996, 997, 998, 999], "col_b": [2, 3, 4, 5]})
    merges: dict[str, MergeRule] = {
        "merged": {"years": ["2016"], "column_fallback": "col_b", "column_preferred": "col_a"}
    }
    result = merge_vars(lf, merges, 2016)
    expected = pl.LazyFrame({"merged": [996, 997, 4, 999]})
    assert_frame_equal(result, expected)


# Test no merge for a non-matching year -> when merge_vars input year does not match MergeRule years
def test_non_matching_year() -> None:
    lf = pl.LazyFrame({"col_a": [1, None], "col_b": [None, 2]})
    merges: dict[str, MergeRule] = {
        "merged": {"years": ["2016"], "column_fallback": "col_b", "column_preferred": "col_a"}
    }
    result = merge_vars(lf, merges, 2017)
    # TODO: Finish the expected lazy frame to match what we actually plan to test
    expected = pl.LazyFrame({"merged": [996, 997, 4, 999]})
    assert_frame_equal(result, expected)
