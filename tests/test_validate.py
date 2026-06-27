"""Tests for Validate module"""

from __future__ import annotations

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from nsch.validate import check_year_coverage


def test_correct_output_format_and_missing_years():
    # Checks correct output format (column names, data table type)
    # Flags variables that are entirely NA for one or more years
    # Checks whether a fully covered variable has at least one non-NA value
    # in each year present in the data. (All data present for that variable)

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
    # Check contains year column
    df = pl.DataFrame({"x": [1, 2]})
    with pytest.raises(ValueError, match="year"):
        check_year_coverage(df)


def test_identifies_variable_entirely_NA_in_one_year():
    # One year all NA (Single NA year)
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
    # Checks that empty DataFrame returns a typed empty DataFrame
    # with the canonical four columns and their declared dtypes.
    df = pl.DataFrame({"year": []})
    result = check_year_coverage(df)
    assert isinstance(result, pl.DataFrame)
    assert set(result.columns) == {"variable", "n_years_data", "n_years_total", "missing_years"}
    assert result.is_empty()


def test_non_polars_dataframe_raises_type_error():
    # Check that non-polars DataFrame raises TypeError
    df = {"year": ["2016", "2016"], "x": [1, 2]}
    with pytest.raises(TypeError, match="polars"):
        check_year_coverage(df)
