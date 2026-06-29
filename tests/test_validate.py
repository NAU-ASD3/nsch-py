"""Tests for Validate module"""

from __future__ import annotations

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from nsch.validate import check_na_rates


def test_computes_correct_NA_rates_per_year():
    df = pl.DataFrame(
        {"year": [2016, 2016, 2017, 2017], "x": [1, None, 3, 4], "y": [None, None, 5, 6]}
    )
    result = check_na_rates(df)
    expected = pl.DataFrame(
        {
            "variable": ["x", "y", "x", "y"],
            "year": [2016, 2016, 2017, 2017],
            "na_rate": [0.5, 1.0, 0.0, 0.0],
            "n_total": [2, 2, 2, 2],
        },
        schema={
            "variable": pl.Utf8,
            "year": pl.Int64,
            "na_rate": pl.Float64,
            "n_total": pl.Int64,
        },
    )
    # Ensure frames are comparing the correct rows to each other
    assert_frame_equal(result.sort(by=["variable", "year"]), expected.sort(by=["variable", "year"]))


def test_computes_correct_NA_rates_per_year_on_mixed_data():
    class LETTERS(pl.Enum):
        a = "a"
        b = "b"
        c = "c"
        d = "d"

    df = pl.DataFrame(
        {
            "year": [2016, 2016, 2017, 2017],
            "x": [LETTERS.a, None, LETTERS.c, LETTERS.d],
            "y": [None, None, 5, 6],
        }
    )
    result = check_na_rates(df)
    expected = pl.DataFrame(
        {
            "variable": ["x", "y", "x", "y"],
            "year": [2016, 2016, 2017, 2017],
            "na_rate": [0.5, 1.0, 0.0, 0.0],
            "n_total": [2, 2, 2, 2],
        },
        schema={
            "variable": pl.Utf8,
            "year": pl.Int64,
            "na_rate": pl.Float64,
            "n_total": pl.Int64,
        },
    )
    # Ensure frames are comparing the correct rows to each other
    assert_frame_equal(result.sort(by=["variable", "year"]), expected.sort(by=["variable", "year"]))


# Output should have a column named year, but year should not be treated as a variable
def test_excludes_year_column_from_variables_in_output():
    # Schema is not important here for checking data types, we are not comparing values
    df = pl.DataFrame(
        {"year": [2016, 2016, 2017, 2017], "x": [1, None, 3, 4], "y": [None, None, 5, 6]}
    )
    result = check_na_rates(df)
    assert "year" not in result["variable"].unique()


def test_returns_empty_dataframe_when_no_variables():
    df = pl.DataFrame({"year": [2016, 2016, 2017, 2017]})
    result = check_na_rates(df)
    expected = pl.DataFrame(
        {"variable": [], "year": [], "na_rate": [], "n_total": []},
        schema={
            "variable": pl.Utf8,
            "year": pl.Int64,
            "na_rate": pl.Float64,
            "n_total": pl.Int64,
        },
    )
    assert_frame_equal(result, expected)


def test_non_polars_dataframe_raises_type_error():
    df = {"year": [2016, 2017], "x": [1, 2]}
    with pytest.raises(TypeError, match="Polars DataFrame"):
        check_na_rates(df)


def test_missing_year_column_raises_value_error():
    df = pl.DataFrame({"x": [1, 2]})
    with pytest.raises(ValueError, match="year"):
        check_na_rates(df)
