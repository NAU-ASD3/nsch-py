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


# Test to merge Columns


def test_merges_prefferd_colums() -> None:
    lf = pl.LazyFrame({"gowhensick": [1, 2], "k4q02_r": [3, 4], "hhid": [5, 6]})
    merge: dict[str, MergeRule] = {
        "gowhensick": {
            "years": ["2023"],
            "column_preferred": "k4q02_r",
            "column_fallback": "gowhensick",
        }
    }
    result = merge_vars(lf, merge, 2023).collect()
    assert result.columns == ["k4q02_r", "hhid"]
    assert result["k4q02_r"].to_list() == [1, 2]
