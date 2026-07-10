"""Tests for validate module"""

from __future__ import annotations

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from nsch.validate import check_year_coverage


def test_correct_output_format_and_missing_years():
    # Checks the output format (column names and DataFrame type).
    # Flags variables that are entirely missing for one or more years.
    # Verifies that a fully covered variable has at least one non-missing
    # value in every year present in the data.

    df = pl.DataFrame(
        {
            "year": ["2016", "2016", "2017", "2017", "2018", "2018"],
            "x": [1, 2, 3, 4, 5, 6],
            "y": [1, 2, None, None, None, None],
        }
    )
    result = check_year_coverage(df)
    expected = pl.DataFrame(
        {
            "variable": ["x", "y"],
            "n_years_data": [3, 1],
            "n_years_total": [3, 3],
            "missing_years": ["", "2017,2018"],
        }
    )
    assert_frame_equal(result, expected)


def test_contains_year_column():
    # Raises an error when the required ``year`` column is missing.
    df = pl.DataFrame({"x": [1, 2]})
    with pytest.raises(ValueError, match="year"):
        check_year_coverage(df)


def test_null_year_raises_value_error():
    # Raises an error if the ``year`` column contains null values
    # Safeguards against missingness from earlier in the pipeline
    df = pl.DataFrame({"year": ["2016", None, "2017"], "x": [1, 2, 3]})
    with pytest.raises(ValueError, match="year"):
        check_year_coverage(df)


def test_identifies_variable_entirely_NA_in_one_year():
    # Identifies a variable that is entirely missing in a single year.
    df = pl.DataFrame(
        {"year": ["2016", "2016", "2017", "2017"], "x": [1, 2, 3, 4], "y": [1, 2, None, None]}
    )
    result = check_year_coverage(df)
    expected = pl.DataFrame(
        {
            "variable": ["x", "y"],
            "n_years_data": [2, 1],
            "n_years_total": [2, 2],
            "missing_years": ["", "2017"],
        }
    )
    assert_frame_equal(result, expected)


def test_empty_dataframe_returns_typed_empty_dataframe():
    # Returns a typed empty DataFrame with the canonical four columns
    # and their declared dtypes when no variables are present.
    df = pl.DataFrame({"year": ["2016", "2017"]})
    result = check_year_coverage(df)
    assert isinstance(result, pl.DataFrame)
    assert set(result.columns) == {"variable", "n_years_data", "n_years_total", "missing_years"}
    assert result.schema == {
        "variable": pl.Utf8,
        "n_years_data": pl.Int64,
        "n_years_total": pl.Int64,
        "missing_years": pl.Utf8,
    }
    assert result.is_empty()


def test_dataframe_with_empty_variable_column_returns_zero_values():
    # Returns zero values for a DataFrame with an empty variable column
    df = pl.DataFrame({"year": [], "x": []})
    result = check_year_coverage(df)
    expected = pl.DataFrame(
        {
            "variable": ["x"],
            "n_years_data": [0],
            "n_years_total": [0],
            "missing_years": [""],
        }
    )
    assert_frame_equal(result, expected)


def test_non_polars_dataframe_raises_type_error():
    # Raises ``TypeError`` when the input is not a Polars DataFrame.
    df = {"year": ["2016", "2016"], "x": [1, 2]}
    with pytest.raises(TypeError, match="polars"):
        check_year_coverage(df)
