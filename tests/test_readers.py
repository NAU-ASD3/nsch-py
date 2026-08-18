"""Tests for the readers module."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from nsch.readers import parse_do, read_nsch_dta


def test_parse_do_raises_error_for_missing_file(tmp_path: Path) -> None:
    """Raise an informative error when the Stata do-file does not exist."""
    missing_file = tmp_path / "missing.do"

    with pytest.raises(
        FileNotFoundError,
        match=r"year\.do\.path should be the path to a Stata do file",
    ):
        parse_do(missing_file)


def test_parse_do_parses_variable_labels(tmp_path: Path) -> None:
    """Parse ``label var`` statements from a Stata do-file."""
    do_file = tmp_path / "example.do"
    do_file.write_text(
        'label var SC_SEX "Sex of selected child"\nlabel var SC_AGE "Age of selected child"\n'
    )

    result = parse_do(do_file)

    expected = pl.DataFrame(
        {
            "variable": ["SC_SEX", "SC_AGE"],
            "desc": [
                "Sex of selected child",
                "Age of selected child",
            ],
        }
    )

    assert_frame_equal(result.var.collect(), expected)


def test_parse_do_parses_value_labels(tmp_path: Path) -> None:
    """Parse ``label define`` statements from a Stata do-file."""
    do_file = tmp_path / "example.do"
    do_file.write_text('label define SC_SEX_lab 1 "Male"\nlabel define SC_SEX_lab 2 "Female"\n')

    result = parse_do(do_file)

    expected = pl.DataFrame(
        {
            "variable": ["SC_SEX", "SC_SEX"],
            "value": ["1", "2"],
            "desc": ["Male", "Female"],
        }
    )

    assert_frame_equal(result.define.collect(), expected)


def test_parse_do_returns_variable_and_value_labels(tmp_path: Path) -> None:
    """Return both variable and value-label metadata from one do-file."""
    do_file = tmp_path / "example.do"
    do_file.write_text(
        'label var SC_SEX "Sex of selected child"\n'
        'label define SC_SEX_lab 1 "Male"\n'
        'label define SC_SEX_lab 2 "Female"\n'
    )

    result = parse_do(do_file)

    expected_var = pl.DataFrame(
        {
            "variable": ["SC_SEX"],
            "desc": ["Sex of selected child"],
        }
    )
    expected_define = pl.DataFrame(
        {
            "variable": ["SC_SEX", "SC_SEX"],
            "value": ["1", "2"],
            "desc": ["Male", "Female"],
        }
    )

    assert_frame_equal(result.var.collect(), expected_var)
    assert_frame_equal(result.define.collect(), expected_define)


dta_missing = Path("tests/data/tagged_missing.dta")
dta_mixed = Path("tests/data/mixed_types.dta")
dta_no_stratum = Path("tests/data/no_stratum.dta")


def test_return_is_a_lazy_frame() -> None:
    assert isinstance(read_nsch_dta(dta_missing), pl.LazyFrame)


def test_year_column_is_an_integer() -> None:
    result = read_nsch_dta(dta_mixed)
    assert isinstance(result.collect_schema()["year"], pl.Int64)


def test_missing_file_throws_informative_error() -> None:
    does_not_exist = Path("does_not_exist.dta")
    with pytest.raises(FileNotFoundError, match="does not exist"):
        read_nsch_dta(does_not_exist)


# Test nulls are remapped with sentinels, also asserts stratum is an integer
# Also checks a fully integer stratum column passes
def test_tagged_nas_are_replaced_with_sentinel_codes() -> None:
    df = read_nsch_dta(dta_missing).collect()
    expected = pl.DataFrame(
        {
            "year": [2099, 2099, 2099, 2099, 2099, 2099],
            "x": [1, 2, 996, 997, 998, 999],
            "stratum": [1, 2, 2, 1, 2, 2],
        },
        schema={"year": pl.Int64, "x": pl.Int32, "stratum": pl.Int64},
    )
    assert_frame_equal(df, expected)


# all datatypes have been remapped from stata to their corresponding polars type
def test_all_stata_types_remap_to_polars() -> None:
    df = read_nsch_dta(dta_mixed).collect()
    expected = pl.DataFrame(
        {
            "year": [2099] * 6,
            "x": [1.5, 2.0, 996, 997, 998, 999],
            "y": ["a", "b", "c", "e", "f", "g"],
            "stratum": [1, 2, 2, 1, 2, 2],
        },
        schema={"year": pl.Int64, "x": pl.Float64, "y": pl.Utf8, "stratum": pl.Int64},
    )
    assert_frame_equal(df, expected)


def test_raises_error_if_stratum_col_missing() -> None:
    with pytest.raises(ValueError, match="No stratum"):
        read_nsch_dta(dta_no_stratum).collect()
