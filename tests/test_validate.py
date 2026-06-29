"""Tests for the validate module."""

from __future__ import annotations

import polars as pl
import pytest

from nsch.validate import check_factor_levels, check_year_coverage

# --- check_year_coverage ----------------------------------------------------


def test_identifies_variable_entirely_null_in_one_year() -> None:
    df = pl.DataFrame(
        {
            "year": [2016, 2016, 2017, 2017],
            "x": [1, 2, 3, 4],
            "y": [1, 2, None, None],
        }
    )
    result = check_year_coverage(df)
    assert result.columns == ["variable", "n_years_data", "n_years_total", "missing_years"]
    y_row = result.filter(pl.col("variable") == "y")
    assert y_row["n_years_data"].to_list() == [1]
    assert y_row["n_years_total"].to_list() == [2]
    assert y_row["missing_years"].to_list() == ["2017"]


def test_fully_covered_variable_has_empty_missing_years() -> None:
    df = pl.DataFrame({"year": [2016, 2017], "x": [1, 2]})
    result = check_year_coverage(df)
    assert result.filter(pl.col("variable") == "x")["missing_years"].to_list() == [""]


def test_errors_when_year_column_is_missing() -> None:
    df = pl.DataFrame({"x": [1, 2, 3]})
    with pytest.raises(ValueError, match="year"):
        check_year_coverage(df)


def test_empty_frame_returns_empty_summary() -> None:
    # Only a year column means no variables to report: an empty summary,
    # but still with the right columns and dtypes.
    df = pl.DataFrame(schema={"year": pl.Int64})
    result = check_year_coverage(df)
    assert result.columns == ["variable", "n_years_data", "n_years_total", "missing_years"]
    assert result.height == 0
    assert result.schema["n_years_data"] == pl.Int64


# --- check_factor_levels ----------------------------------------------------


def test_detects_level_present_in_only_some_years() -> None:
    df = pl.DataFrame(
        {
            "year": [2016, 2016, 2017, 2017],
            "status": pl.Series(["A", "B", "A", "A"], dtype=pl.Enum(["A", "B"])),
        }
    )
    result = check_factor_levels(df)
    assert result.columns == ["variable", "level", "count", "n_years_present", "years_present"]
    b_row = result.filter((pl.col("variable") == "status") & (pl.col("level") == "B"))
    assert b_row.height == 1
    assert b_row["n_years_present"].to_list() == [1]
    assert b_row["years_present"].to_list() == ["2016"]


def test_reports_a_level_present_in_every_year() -> None:
    df = pl.DataFrame(
        {
            "year": [2016, 2016, 2017, 2017],
            "status": pl.Series(["A", "B", "A", "B"], dtype=pl.Enum(["A", "B"])),
        }
    )
    result = check_factor_levels(df)
    a_row = result.filter((pl.col("variable") == "status") & (pl.col("level") == "A"))
    assert a_row["n_years_present"].to_list() == [2]
    assert a_row["years_present"].to_list() == ["2016,2017"]


def test_handles_multiple_enum_columns() -> None:
    df = pl.DataFrame(
        {
            "year": [2016, 2017],
            "status": pl.Series(["A", "B"], dtype=pl.Enum(["A", "B"])),
            "grade": pl.Series(["X", "Y"], dtype=pl.Enum(["X", "Y"])),
        }
    )
    result = check_factor_levels(df)
    assert set(result["variable"].to_list()) == {"status", "grade"}
    assert result.height == 4  # two levels in each of two columns


def test_returns_empty_for_input_with_no_enum_columns() -> None:
    df = pl.DataFrame({"year": [2016, 2017], "age": [5, 6], "score": [10, 20]})
    result = check_factor_levels(df)
    assert result.columns == ["variable", "level", "count", "n_years_present", "years_present"]
    assert result.height == 0


def test_factor_levels_errors_without_year_column() -> None:
    df = pl.DataFrame({"status": pl.Series(["A", "B"], dtype=pl.Enum(["A", "B"]))})
    with pytest.raises(ValueError, match="year"):
        check_factor_levels(df)
