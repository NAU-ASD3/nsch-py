"""Tests for the readers module"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from nsch.readers import read_nsch_dta

dta_missing = Path("tests/data/tagged_missing.dta")
dta_mixed = Path("tests/data/mixed_types.dta")


def test_return_is_a_lazy_frame() -> None:
    assert isinstance(read_nsch_dta(dta_missing), pl.LazyFrame)


def test_year_column_is_an_integer() -> None:
    result = read_nsch_dta(dta_mixed)
    assert isinstance(result.collect_schema()["year"], pl.Int64)


def test_missing_file_throws_informative_error():
    does_not_exist = Path("does_not_exist.dta")
    with pytest.raises(FileNotFoundError, match="does not exist"):
        read_nsch_dta(does_not_exist)


# Test nulls are remapped with sentinels, also asserts stratum is an integer
def test_tagged_nas_are_replaced_with_sentinel_codes() -> None:
    df = read_nsch_dta(dta_missing).collect()
    expected = pl.DataFrame(
        {
            "year": [2099, 2099, 2099, 2099, 2099, 2099],
            "x": [1, 2, 996, 997, 998, 999],
            "stratum": [1, 2, 2, 1, 2, 2],
        },
        schema={"year": pl.Int64, "x": pl.Int64, "stratum": pl.Int64},
    )
    return assert_frame_equal(df, expected)


# all datatypes have been remapped from stata to their corresponding polars type
def test_all_stata_types_remap_to_polars():
    df = read_nsch_dta(dta_mixed).collect()
    expected = pl.DataFrame(
        {
            "year": [2099] * 6,
            "x": [1, 2, 996, 997, 998, 999],
            "y": ["a", "b", "c", "e", "f", "g"],
            "stratum": [1, 2, 2, 1, 2, 2],
        },
        schema={"year": pl.Int64, "x": pl.Int64, "y": pl.Utf8, "stratum": pl.Int64},
    )
    return assert_frame_equal(df, expected)
