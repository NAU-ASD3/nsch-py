"""Tests for the harmonize module."""

from __future__ import annotations

from typing import TypedDict

import polars as pl
from polars.testing import assert_frame_equal

from nsch.harmonize import transform_values


class TransformValues(TypedDict):
    years: list[str]
    value: list[str]
    new_value: list[str]
    new_label: list[str]


# -------------------------
# Tests:
# Correct indices are matched for correct years
#   (Bundle with correct year is changed)
# multiple indices for values are remapped
# Missing years in transform is flagged
# empty df returns empty
# label col is created when not there and all cols are correct
#   (bundle when checking a whole df)
# non-matching year leaves values and labels unchanged
# transforms with only label don't modify values but do modify labels
# silently skips variables not in lf
# -------------------------

################
# QUESTIONS
# NA_character_ in R expected df = None? What kind of NA? Does polars have typed NAs?


def test_value_are_remapped_for_matching_year():
    lf = pl.LazyFrame({"k2q01_d": [1, 2, 3]})
    transforms = {
        "k2q01_d": TransformValues(
            {"years": ["2016", "2017"], "value": "2", "new_value": "1", "new_label": "Yes"}
        )
    }
    result = transform_values(lf, transforms, 2016)
    expected = pl.LazyFrame({"k2q01_d": [1, 1, 3]}, {"k2q01_d_label": [None, "Yes", None]})
    assert_frame_equal(result, expected)
