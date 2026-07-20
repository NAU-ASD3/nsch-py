"""Temporary holer for insgestion tests, until a more permanent home is found"""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import polars as pl
from polars.testing import assert_frame_equal

from nsch.read import read_nsch_dta

# Unzip data to be used by all tests
# Data is found in r package's extdata folder
# unzip nsch_2024_tropical_2024_06_06.zip -d tests/data
unzip_path = "tests/data/nsch_2024_topical_Stata.zip"
temp_dir = "tests/data/temp"
with ZipFile(unzip_path, "r") as zip_object:
    if not Path(temp_dir).is_dir():
        # create a temporary directory to unzip the data into
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
    zip_object.extractall(temp_dir)

dta2024 = "tests/data/temp/nsch_2024e_topical.dta"


def test_return_is_a_lazy_frame() -> None:
    assert isinstance(read_nsch_dta(dta2024), pl.LazyFrame)


def test_year_column_is_an_integer() -> None:
    result = read_nsch_dta(dta2024)
    assert isinstance(result.collect_schema()["year"], pl.Int64)  # Should the int type be smaller?


# Test missing file throws error


# Test nulls are remapped with sentinels
def test_tagged_nas_are_replaced_with_sentinel_codes() -> None:
    dta_path = "tests/data/temp/sample_dta_with_tagged_na.dta"
    df = read_nsch_dta(dta_path).collect()
    expected = pl.DataFrame(
        {
            "year": [2099, 2099, 2099, 2099, 2099, 2099],
            "x": pl.Series(
                [1, 2, 996, 997, 998, 999],
                dtype=pl.Int64,
            ),
        }
    )
    return assert_frame_equal(df, expected)


# stratum is an int

# overallocation should not be an issue here?
