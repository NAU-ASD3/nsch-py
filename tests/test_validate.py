"""Tests for Validate module"""

from __future__ import annotations

import polars as pl
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
        }
    )
    # Ensure frames are comparing the correct rows to each other
    assert_frame_equal(result.sort(by=["variable", "year"]), expected.sort(by=["variable", "year"]))


# Output should have a column named year, but year should not be treated as a variable
def test_excludes_year_column_from_variables_in_output():
    df = pl.DataFrame(
        {"year": [2016, 2016, 2017, 2017], "x": [1, None, 3, 4], "y": [None, None, 5, 6]}
    )
    result = check_na_rates(df)
    assert "year" not in result["variable"].unique()
