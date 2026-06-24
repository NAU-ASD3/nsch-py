"""Test check_year_coverage()"""

from __future__ import annotations

import polars as pl

from nsch.validate import check_year_coverage

# Behaviors to check:

# correct output format (Names, data table type)
# Contains year column


# Flags variables that are entirely \code{NA} for one or more years
# List years all NA (multiple NA Years)
# One year all NA (Single NA year)
def test_identifies_variable_entirely_NA_in_one_year():
    df = pl.DataFrame(
        {"year": ["2016", "2016", "2017", "2017"], "x": [1, 2, 3, 4], "y": [1, 2, None, None]}
    )
    result = check_year_coverage(df)
    assert result["missing_years"][1] == "2017"


# checks whether it has at least one non-NA value in each year present in the data.
# No years with NA (All data present)
def test_fully_covered_variable_has_empty_missing_years():
    df = pl.DataFrame({"year": ["2016", "2017"], "x": [1, 2]})
    result = check_year_coverage(df)
    assert (result["missing_years"] == "").all()

    # One year some NA (at least one NA)
