"""Tests for Validate module"""

from __future__ import annotations

import polars as pl
import pytest

from nsch.validate import check_year_coverage


# correct output format (Names, data table type)
def test_output_format():
    df = pl.DataFrame({"year": ["2016", "2017"], "x": [1, 2]})
    result = check_year_coverage(df)
    assert isinstance(result, pl.DataFrame)
    assert set(result.columns) == {"variable", "n_years_data", "n_years_total", "missing_years"}


# Contains year column
def test_contains_year_column():
    df = pl.DataFrame({"x": [1, 2]})
    try:
        check_year_coverage(df)
    except ValueError as e:
        assert str(e) == "Input DataFrame must contain a 'year' column."
    else:
        pytest.fail("Expected ValueError not raised.")


# Flags variables that are entirely \code{NA} for one or more years
# List years all NA (multiple NA Years)
# And where one year has some NA (at least one NA)
def test_identifies_variable_entirely_NA_in_multiple_years():
    df = pl.DataFrame(
        {
            "year": ["2016", "2016", "2017", "2017", "2018", "2018"],
            "x": [1, 2, 3, 4, 5, 6],
            "y": [1, 2, None, None, None, None],
        }
    )
    result = check_year_coverage(df)
    # Rather than assuming the order of the output,
    # filter for the variable of interest
    row = result.filter(pl.col("variable") == "y")
    assert row["n_years_data"][0] == 1
    assert row["n_years_total"][0] == 3
    assert row["missing_years"][0] == "2017, 2018"


# One year all NA (Single NA year)
def test_identifies_variable_entirely_NA_in_one_year():
    df = pl.DataFrame(
        {"year": ["2016", "2016", "2017", "2017"], "x": [1, 2, 3, 4], "y": [1, 2, None, None]}
    )
    result = check_year_coverage(df)
    row = result.filter(pl.col("variable") == "y")
    assert row["n_years_data"][0] == 1
    assert row["n_years_total"][0] == 2
    assert row["missing_years"][0] == "2017"


# checks whether it has at least one non-NA value in each year present in the data.
# No years with NA (All data present)
def test_fully_covered_variable_has_empty_missing_years():
    df = pl.DataFrame({"year": ["2016", "2017"], "x": [1, 2]})
    result = check_year_coverage(df)
    row = result.filter(pl.col("variable") == "x")
    assert row["missing_years"][0] == ""
