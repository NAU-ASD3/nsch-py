"""Tests for the validate module."""

from __future__ import annotations

import polars as pl
import pytest

from nsch.validate import check_label_consistency, check_year_coverage

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


# --- check_label_consistency ------------------------------------------------


def test_detects_inconsistent_levels_across_years() -> None:
    df = pl.DataFrame(
        {
            "year": [2016, 2016, 2017, 2017],
            "status": pl.Series(["A", "B", "A", "C"], dtype=pl.Enum(["A", "B", "C"])),
        }
    )
    result = check_label_consistency(df)
    assert result.columns == ["variable", "is_consistent", "n_level_sets", "levels_by_year"]
    status_row = result.filter(pl.col("variable") == "status")
    assert status_row["is_consistent"].to_list() == [False]
    assert status_row["n_level_sets"].to_list() == [2]
    assert status_row["levels_by_year"].to_list() == ["2016={A|B}; 2017={A|C}"]


def test_consistent_levels_across_years_returns_true() -> None:
    df = pl.DataFrame(
        {
            "year": [2016, 2016, 2017, 2017],
            "status": pl.Series(["A", "B", "A", "B"], dtype=pl.Enum(["A", "B"])),
        }
    )
    result = check_label_consistency(df)
    status_row = result.filter(pl.col("variable") == "status")
    assert status_row["is_consistent"].to_list() == [True]
    assert status_row["n_level_sets"].to_list() == [1]


def test_skips_non_enum_columns() -> None:
    df = pl.DataFrame(
        {
            "year": [2016, 2017],
            "x": [1.0, 2.0],
            "status": pl.Series(["A", "A"], dtype=pl.Enum(["A"])),
        }
    )
    result = check_label_consistency(df)
    assert result["variable"].to_list() == ["status"]


def test_returns_empty_when_no_enum_columns_present() -> None:
    df = pl.DataFrame({"year": [2016, 2017], "x": [1, 2]})
    result = check_label_consistency(df)
    assert result.columns == ["variable", "is_consistent", "n_level_sets", "levels_by_year"]
    assert result.height == 0


def test_label_consistency_errors_without_year_column() -> None:
    df = pl.DataFrame({"status": pl.Series(["A", "B"], dtype=pl.Enum(["A", "B"]))})
    with pytest.raises(ValueError, match="year"):
        check_label_consistency(df)
