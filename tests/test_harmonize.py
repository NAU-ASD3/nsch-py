"""Tests for the harmonize module."""

from __future__ import annotations

from typing import TypedDict

import polars as pl
from polars.testing import assert_frame_equal

from nsch.harmonize import transform_values


class TransformValues(TypedDict):
    years: list[str]
    value: list[str]
    new_value: list[str]
    new_label: list[str]


# -------------------------
# Tests:
# empty df returns empty
# -------------------------

################
# QUESTIONS
# NA_character_ in R expected df = None? What kind of NA? Does polars have typed NAs?
# PR note: Only works when transforms have same lenghth for value, new_value, and new_label
# PR note: Does not check for transforming mixed data, done on the lazy frame when
# enums are still ints. Relies on Json so presence of years in transform is not checked
# PR note: Empty test necessary?
# PR note: Order of output columns matter?


def test_value_is_remapped_for_matching_year_and_label_column_is_created():
    lf = pl.LazyFrame({"k2q01_d": [1, 2, 3]})
    transforms = {
        "k2q01_d": TransformValues(
            {"years": ["2016", "2017"], "value": ["2"], "new_value": ["1"], "new_label": ["Yes"]}
        )
    }
    result = transform_values(lf, transforms, 2016).collect()
    expected = pl.DataFrame({"k2q01_d": [1, 1, 3], "k2q01_d_label": [None, "Yes", None]})
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
    lf = pl.LazyFrame({"sex": [1, 2]})
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
    expected = pl.DataFrame({"sex": [1, 2], "sex_label": ["Male", "Female"]})
    assert_frame_equal(result, expected)


def test_missing_variable_in_lf_is_silently_skipped():
    lf = pl.LazyFrame({"x": [1, 2]})
    transforms = {
        "not_here": TransformValues(
            {"years": ["2017"], "value": ["1"], "new_value": ["2"], "new_label": ["Two"]}
        )
    }
    result = transform_values(lf, transforms, 2017).collect()
    assert_frame_equal(result, pl.DataFrame({"x": [1, 2]}))
    # How to test that no warning or error is raised?


def test_existing_label_cols_are_updated_with_values_filled():
    lf = pl.LazyFrame({"k2q01_d": [2, 2, 3], "k2q01_d_label": ["No", None, None]})
    transforms = {
        "k2q01_d": TransformValues(
            {"years": ["2016", "2017"], "value": ["2"], "new_value": ["2"], "new_label": ["Yes"]}
        )
    }
    result = transform_values(lf, transforms, 2016).collect()
    expected = pl.DataFrame({"k2q01_d": [2, 2, 3], "k2q01_d_label": ["Yes", "Yes", None]})
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
