"""Tests for the readers module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from nsch.readers import parse_do

if TYPE_CHECKING:
    from pathlib import Path


def test_parse_do_raises_error_for_missing_file(tmp_path: Path) -> None:
    """Raise an informative error when the Stata do-file does not exist."""
    missing_file = tmp_path / "missing.do"

    with pytest.raises(
        FileNotFoundError,
        match="year.do.path should be the path to a Stata do file",
    ):
        parse_do(missing_file)


def test_parse_do_parses_variable_labels(tmp_path: Path) -> None:
    """Parse ``label var`` statements from a Stata do-file."""
    do_file = tmp_path / "example.do"
    do_file.write_text(
        'label var SC_SEX "Sex of selected child"\n' 'label var SC_AGE "Age of selected child"\n'
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
    do_file.write_text('label define SC_SEX_lab 1 "Male"\n' 'label define SC_SEX_lab 2 "Female"\n')

    result = parse_do(do_file)

    expected = pl.DataFrame(
        {
            "variable": ["SC_SEX", "SC_SEX"],
            "value": ["1", "2"],
            "desc": ["Male", "Female"],
        }
    )

    assert_frame_equal(result.define.collect(), expected)
