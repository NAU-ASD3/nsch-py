"""Tests for the harmonize module."""

from __future__ import annotations

import warnings

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from nsch.harmonize import TransformValues, subset_vars, transform_values


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