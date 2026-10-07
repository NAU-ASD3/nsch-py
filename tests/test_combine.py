"""Testing functions for the combine module"""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl
import pytest
from polars.testing import assert_frame_equal, assert_series_equal

from nsch.combine import apply_do_labels, combine_years
from nsch.readers import parse_do

if TYPE_CHECKING:
    from pathlib import Path


def test_numeric_column_is_converted_to_enum_with_correct_levels() -> None:
    lf = pl.LazyFrame({"sc_sex": [1, 2, 1, 2]})
    define_lf = pl.LazyFrame(
        {
            "variable": ["sc_sex"] * 5,
            "value": ["1", "2", ".m", ".n", ".d"],
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
            "value": ["1", "2", ".m", ".n", ".l", ".d"],
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
    expected = pl.Series(
        "sc_sex", ["Male", None, None, None, None], dtype=pl.Enum(["Male", "Female"])
    )
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


def test_variable_with_only_missing_codes_falls_through_to_plain_numeric() -> None:
    lf = pl.LazyFrame({"all_missing": [996, 997, None]})
    define_lf = pl.LazyFrame(
        {
            "variable": ["all_missing"] * 4,
            "value": [".m", ".n", ".l", ".d"],
            "desc": [
                "No Response",
                "Not In Universe",
                "Logical Skip",
                "Suppressed",
            ],
        }
    )
    result = apply_do_labels(lf, define_lf)
    expected = pl.LazyFrame({"all_missing": [None, None, None]}, schema={"all_missing": pl.Int64})
    assert_frame_equal(result, expected)


def test_provided_alias_map_is_used() -> None:
    lf = pl.LazyFrame({"family": [1, 2, 998]})
    define_lf = pl.LazyFrame(
        {
            "variable": ["family_r"] * 4,
            "value": ["1", "2", "3", ".d"],
            "desc": [
                "Two biogical/adoptive parents, currently married",
                "Two biogical/adoptive parents, not currently married",
                "Two parents (at least one not biological/adoptive), currently married",
                "Suppressed for Confidentiality",
            ],
        }
    )
    result = apply_do_labels(lf, define_lf, alias={"family": "family_r"})
    expected = pl.LazyFrame(
        {
            "family": [
                "Two biogical/adoptive parents, currently married",
                "Two biogical/adoptive parents, not currently married",
                None,
            ]
        },
        schema={
            "family": pl.Enum(
                [
                    "Two biogical/adoptive parents, currently married",
                    "Two biogical/adoptive parents, not currently married",
                    "Two parents (at least one not biological/adoptive), currently married",
                ]
            )
        },
    )
    assert_frame_equal(result, expected)


def test_a_frame_with_multiple_label_overrides_of_different_lengths() -> None:
    # a frame with two transformed columns, each with its own _label overrides with a
    # different number of distinct override values (Non-None length differs)
    lf = pl.LazyFrame(
        {
            "birthwt": [1, 996, 996],
            "birthwt_label": ["Custom VLB Label", None, None],
            "family": [4, 5, 6],
            "family_label": [
                "Two biogical/adoptive parents, currently married",
                "Two biogical/adoptive parents, not currently married",
                "Two parents (at least one not biological/adoptive), currently married",
            ],
        }
    )
    define_lf = pl.LazyFrame(
        {
            "variable": [
                "birthwt",
                "birthwt",
                "birthwt",
                "birthwt",
                "family",
                "family",
                "family",
                "family",
            ],
            "value": ["1", "2", "3", ".m", "4", "5", "6", ".d"],
            "desc": [
                "Very low birth weight",
                "Low birth weight",
                "Not low birth weight",
                "No valid response",
                "Two biogical/adoptive parents, currently married",
                "Two biogical/adoptive parents, not currently married",
                "Two parents (at least one not biological/adoptive), currently married",
                "Suppressed for Confidentiality",
            ],
        }
    )
    result = apply_do_labels(lf, define_lf)
    expected = pl.LazyFrame(
        {
            "birthwt": ["Custom VLB Label", None, None],
            "family": [
                "Two biogical/adoptive parents, currently married",
                "Two biogical/adoptive parents, not currently married",
                "Two parents (at least one not biological/adoptive), currently married",
            ],
        },
        schema={
            "birthwt": pl.Enum(
                [
                    "Very low birth weight",
                    "Low birth weight",
                    "Not low birth weight",
                    "Custom VLB Label",
                ]
            ),
            "family": pl.Enum(
                [
                    "Two biogical/adoptive parents, currently married",
                    "Two biogical/adoptive parents, not currently married",
                    "Two parents (at least one not biological/adoptive), currently married",
                ]
            ),
        },
    )
    assert_frame_equal(result, expected)


def test_apply_do_labels_correctly_handles_nulls_from_parse_do(tmp_path: Path) -> None:
    """Dotted missing values from a real .do file are nulled by apply_do_labels."""
    do_file = tmp_path / "example.do"
    do_file.write_text(
        'label var SC_SEX "Sex of Selected Child"\n'
        'label define SC_SEX_lab 1 "Male"\n'
        'label define SC_SEX_lab 2 "Female"\n'
        'label define SC_SEX_lab .m "No valid response"\n'
        'label define SC_SEX_lab .d "Suppressed"\n'
    )

    do_lf = parse_do(do_file)

    lf = pl.LazyFrame({"SC_SEX": [1, 1, 996, 999]})

    result = apply_do_labels(lf, do_lf.define)

    expected = pl.LazyFrame(
        {"SC_SEX": ["Male", "Male", None, None]},
        schema={
            "SC_SEX": pl.Enum(["Male", "Female"]),
        },
    )
    assert_frame_equal(result, expected)


# Testing Functions for combine_years


def test_combines_multiple_year_frames_in_order() -> None:
    """Rows from each year stack in list order with every year present once."""
    y16 = pl.LazyFrame({"year": [2016, 2016, 2016], "x": [1, 2, 3]})
    y17 = pl.LazyFrame({"year": [2017, 2017, 2017], "x": [4, 5, 6]})

    result = combine_years([y16, y17])

    expected = pl.DataFrame({"year": [2016] * 3 + [2017] * 3, "x": [1, 2, 3, 4, 5, 6]})
    assert_frame_equal(result, expected)


def test_columns_missing_from_some_years_are_filled_with_null() -> None:
    """A column present in one year only is null for the other years."""
    y16 = pl.LazyFrame({"year": [2016, 2016], "x": [1, 2], "var2": [10.0, 20.0]})
    y17 = pl.LazyFrame({"year": [2017, 2017], "x": [3, 4]})

    result = combine_years([y16, y17])

    expected = pl.DataFrame(
        {"year": [2016, 2016, 2017, 2017], "x": [1, 2, 3, 4], "var2": [10.0, 20.0, None, None]}
    )
    assert_frame_equal(result, expected)


def test_enum_categories_are_unioned_across_years() -> None:
    """Enum columns widen to the union of per-year categories, first appearance first."""
    y16 = pl.LazyFrame({"year": [2016, 2016], "place": ["Clinic", "Office"]}).with_columns(
        pl.col("place").cast(pl.Enum(["Clinic", "Office"]))
    )
    y24 = pl.LazyFrame({"year": [2024, 2024], "place": ["Office", "Urgent Care"]}).with_columns(
        pl.col("place").cast(pl.Enum(["Clinic", "Office", "Urgent Care"]))
    )

    result = combine_years([y16, y24])

    expected = pl.DataFrame(
        {"year": [2016, 2016, 2024, 2024], "place": ["Clinic", "Office", "Office", "Urgent Care"]},
        schema={"year": pl.Int64, "place": pl.Enum(["Clinic", "Office", "Urgent Care"])},
    )
    assert_frame_equal(result, expected)


def test_error_for_duplicate_year_values_across_frames() -> None:
    """The same year in two frames is an error naming the year."""
    a = pl.LazyFrame({"year": [2016, 2016], "x": [1, 2]})
    b = pl.LazyFrame({"year": [2016, 2016], "x": [3, 4]})

    with pytest.raises(ValueError, match="duplicate year"):
        combine_years([a, b])


def test_error_for_missing_year_column() -> None:
    """A frame without a year column is an error naming its position."""
    with pytest.raises(ValueError, match=r"element 0 .* 'year'"):
        combine_years([pl.LazyFrame({"x": [1, 2]})])


def test_error_for_empty_list() -> None:
    """An empty list is an error rather than an empty frame."""
    with pytest.raises(ValueError, match="non-empty"):
        combine_years([])
