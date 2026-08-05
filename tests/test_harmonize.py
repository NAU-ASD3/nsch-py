"""Tests for the harmonize module."""

from __future__ import annotations

import polars as pl

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
# After writing each test, we can use uv run pytest tests/test_harmonize.py
# TODO: Convert to use assert_frame_equal
def test_merges_preferrd_colums() -> None:
    lf = pl.LazyFrame({"gowhensick": [1, 2], "k4q02_r": [3, 4], "hhid": [5, 6]})
    merge: dict[str, MergeRule] = {
        "gowhensick": {
            "years": ["2023"],
            "column_preferred": "k4q02_r",
            "column_fallback": "gowhensick",
        }
    }
    # Create a pl.DataFrame called "expected" that contains what our result should look like
    result = merge_vars(lf, merge, 2023).collect()
    # Assert using assert_frame_equal(expected, result) instead of the two assert statements below
    assert result.columns == ["k4q02_r", "hhid"]
    assert result["k4q02_r"].to_list() == [1, 2]


# Test label columns are also merged

# Test no merge for a non-matching year -> merge_vars input year does not match MergeRule years

# Test missing source columns are silently skipped

# Test logical skip 998 in the preferred column uses the fallback value

# Test non-logical skip values (sentinals that are not 998) do NOT use the fallback value

# Test label column stays in sync when logical skip triggers the use of the fallback value
