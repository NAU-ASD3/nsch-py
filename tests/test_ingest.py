"""Temporary holer for insgestion tests, until a more permanent home is found"""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import polars as pl

from nsch.ingest import read_nsch_dta

# Unzip data to be used by all tests
# Data is found in r package's extdata folder
# unzip nsch_2024_tropical_2024_06_06.zip -d tests/data
unzip_path = "tests/data/nsch_2024_topical_Stata.zip"
temp_dir = "tests/data/temp"
with ZipFile(unzip_path, "r") as zip_object:
    if not Path(temp_dir).is_dir():
        # create a temporary directory to unzip the data into
        Path.mkdir(temp_dir)
    zip_object.extractall(temp_dir)

dta2024 = "tests/data/temp/nsch_2024e_topical.dta"


def test_return_is_a_lazy_frame() -> None:
    assert isinstance(read_nsch_dta(dta2024), pl.LazyFrame)


def test_year_column_is_an_integer() -> None:
    result = read_nsch_dta(dta2024)
    assert isinstance(result.collect_schema()["year"], pl.Int64)  # Should this be smaller?


# Test missing file throws error

# Test nulls are remapped with sentinels

# stratum is an int

# overallocation should not be an issue here?
