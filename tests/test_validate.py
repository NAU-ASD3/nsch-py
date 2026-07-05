"""Tests for Validate module"""

from __future__ import annotations

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from nsch.validate import check_na_rates, check_year_coverage

"""Testing For ``check_year_coverage``"""


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
    df = pl.DataFrame({"x": [1, 2]})
    with pytest.raises(ValueError, match="year"):
        check_year_coverage(df)


def test_null_year_raises_value_error():
    # Safeguards against missingness from earlier in the pipeline
    df = pl.DataFrame({"year": ["2016", None, "2017"], "x": [1, 2, 3]})
    with pytest.raises(ValueError, match="year"):
        check_year_coverage(df)


def test_identifies_variable_entirely_NA_in_one_year():
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


"""Testing For ``check_na_rates``"""


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
    df = pl.DataFrame(
        {
            "year": [2016, 2016, 2017, 2017],
            "x": pl.Series(["a", None, "c", "d"], dtype=pl.Enum(["a", "b", "c", "d"])),
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


def test_returns_typed_empty_dataframe_when_no_variables():
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
    df_check_na = {"year": [2016, 2017], "x": [1, 2]}
    df_check_coverage = {"year": ["2016", "2016"], "x": [1, 2]}
    with pytest.raises(TypeError, match="Polars DataFrame"):
        check_na_rates(df_check_na)
        check_year_coverage(df_check_coverage)


def test_missing_year_column_raises_value_error():
    df = pl.DataFrame({"x": [1, 2]})
    with pytest.raises(ValueError, match="year"):
        check_na_rates(df)
