"""Temporary holer for insgestion tests, until a more permanent home is found"""

from __future__ import annotations

from pathlib import Path

import polars as pl
from polars.testing import assert_frame_equal

from nsch.readers import read_nsch_dta

dta2024 = Path("tests/data/tagged_missing.dta")


def test_return_is_a_lazy_frame() -> None:
    assert isinstance(read_nsch_dta(dta2024), pl.LazyFrame)


def test_year_column_is_an_integer() -> None:
    result = read_nsch_dta(dta2024)
    assert isinstance(result.collect_schema()["year"], pl.Int64)


# Test missing file throws error


# Test nulls are remapped with sentinels
def test_tagged_nas_are_replaced_with_sentinel_codes() -> None:
    df = read_nsch_dta(dta2024).collect()
    expected = pl.DataFrame(
        {
            "year": [2099, 2099, 2099, 2099, 2099, 2099],
            "x": pl.Series(
                [1, 2, 996, 997, 998, 999],
                dtype=pl.Int64,
            ),
            "stratum": pl.Series([1, 2, 2, 1, 2, 2], dtype=pl.Int64),
        }
    )
    return assert_frame_equal(df, expected)


# stratum is an int

# overallocation should not be an issue here?
