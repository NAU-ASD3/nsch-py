"""Testing functions for the combine module"""

from __future__ import annotations

import polars as pl
from polars.testing import assert_frame_equal, assert_series_equal

from nsch.combine import apply_do_labels


def test_numeric_column_is_converted_to_enum_with_correct_levels() -> None:
    lf = pl.LazyFrame({"sc_sex": [1, 2, 1, 2]})
    define_lf = pl.LazyFrame(
        {
            "variable": ["sc_sex"] * 5,
            "value": ["1", "2", "m", "n", "d"],
            "desc": [
                "Male",
                "Female",
                "No valid response",
                "Not in universe",
                "Suppressed for confidentiality",
            ],
        }
    )
    result = apply_do_labels(lf=lf, define_lf=define_lf).collect()

    expected = pl.Series(
        "sc_sex",
        ["Male", "Female", "Male", "Female"],
        dtype=pl.Enum(["Male", "Female"]),
    )
    assert_series_equal(result["sc_sex"], expected)


def test_sentinel_codes_all_map_to_None() -> None:
    lf = pl.LazyFrame({"sc_sex": [1, 996, 997, 998, 999]})
    define_lf = pl.LazyFrame(
        {
            "variable": ["sc_sex"] * 6,
            "value": ["1", "2", "m", "n", "l", "d"],
            "desc": [
                "Male",
                "Female",
                "No valid response",
                "Not in universe",
                "Logical skip",
                "Suppressed for confidentiality",
            ],
        }
    )
    result = apply_do_labels(lf, define_lf).collect()
    expected = pl.Series("sc_sex", ["Male", None, None, None, None], dtype=pl.Enum(["Male"]))
    assert_series_equal(result["sc_sex"], expected)


def test_label_column_takes_priority_over_do_derived_labels() -> None:
    lf = pl.LazyFrame({"birthwt": [1, 2, 3], "birthwt_label": ["Custom VLB Label", None, None]})
    define_lf = pl.LazyFrame(
        {
            "variable": ["birthwt"] * 6,
            "value": ["1", "2", "3", ".m", ".n", ".d"],
            "desc": [
                "Very low birth weight",
                "Low birth weight",
                "Not low birth weight",
                "No valid response",
                "Not in universe",
                "Suppressed for confidentiality",
            ],
        }
    )
    result = apply_do_labels(lf, define_lf)
    expected = pl.LazyFrame(
        {"birthwt": ["Custom VLB Label", "Low birth weight", "Not low birth weight"]},
        schema={
            "birthwt": pl.Enum(
                [
                    "Very low birth weight",
                    "Low birth weight",
                    "Not low birth weight",
                    "Custom VLB Label",
                ]
            )
        },
    )
    assert_frame_equal(result, expected)


def test_numeric_columns_without_define_entries_are_untouched() -> None:
    lf = pl.LazyFrame({"fpl_i1": [100, 200, 997]})
    define_lf = pl.LazyFrame({"variable": ["sc_sex"], "value": ["1"], "desc": ["Male"]})
    result = apply_do_labels(lf, define_lf)
    expected = pl.LazyFrame({"fpl_i1": [100, 200, None]})
    assert_frame_equal(result, expected)


# What is special in the 2024 data that requires a specific test?
