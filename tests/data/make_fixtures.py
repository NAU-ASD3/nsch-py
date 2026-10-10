"""Generates a set of tiny synthetic .dta files for testing readers.py and harmonize.py.
This script is the source of truth for .dta files used in testing.
"""

from pathlib import Path

import numpy as np
import polars as pl
import pyreadstat


def create_tagged_missing_dta() -> None:
    # Create a synthetic data set using pyreadstat.write_dta and missing_user_values
    # that contains a few rows, a few columns, and tagged NAs (.m, .n, .l, .d)
    # at known positions, and a stratum column carrying the "2A" quirk

    x_col = np.array([1, 2, "m", "n", "l", "d"], dtype=object)

    df = pl.DataFrame(
        {
            "year": [2099] * 6,
            "x": x_col,
            "stratum": [1, 2, 2, 1, 2, 2],
        },
        strict=False,
    )

    pyreadstat.write_dta(
        df,
        "tests/data/tagged_missing.dta",
        missing_user_values={"x": ["m", "n", "l", "d"]},
        variable_value_labels={"x": {1: "Yes", 2: "No"}},
        variable_format={"year": "int32", "x": "int32", "stratum": "int32"},
    )


def create_mixed_types_dta() -> None:
    # Creates a dataset with mix of floats, string, and integer values
    x_col = np.array([1.5, 2.0, "m", "n", "l", "d"], dtype=object)

    df = pl.DataFrame(
        {
            "year": [2099] * 6,
            "x": x_col,
            # d is a tagged stata type, so skip it
            "y": ["a", "b", "c", "e", "f", "g"],
            "stratum": [1, 2, "2A", 1, "2a", 2],
        },
        strict=False,
    )

    pyreadstat.write_dta(
        df,
        "tests/data/mixed_types.dta",
        missing_user_values={"x": ["m", "n", "l", "d"]},
        variable_value_labels={"x": {1.5: "Yes", 2.0: "No"}},
        variable_format={"year": "float", "x": "float", "y": "str", "stratum": "int32"},
    )


def create_no_stratum_data() -> None:
    # Creates a dataset with mix of floats, string, and integer values
    x_col = np.array([1.5, 2.0, "m", "n", "l", "d"], dtype=object)

    df = pl.DataFrame(
        {
            "year": [2099] * 6,
            "x": x_col,
            # d is a tagged stata type, so skip it
            "y": ["a", "b", "c", "e", "f", "g"],
        },
        strict=False,
    )

    pyreadstat.write_dta(
        df,
        "tests/data/no_stratum.dta",
        missing_user_values={"x": ["m", "n", "l", "d"]},
        variable_value_labels={"x": {1.5: "Yes", 2.0: "No"}},
        variable_format={"year": "float", "x": "float", "y": "str", "stratum": "int32"},
    )


# create a synthetic 2016 .dta with hhid, a1_grade_if, a1_grade_i to test impute_a1_grade_2016()
def create_2016_dta(n: int = 10, filename: Path = "2016_impute_test") -> None:
    df = pl.DataFrame(
        {
            "year": [2016] * n,
            "hhid": list(range(1, n + 1)),
            "a1_grade_if": [True] * n,
            "a1_grade_i": np.random.choice([1, 2, 3], size=n, replace=True),
        },
        strict=False,
    )

    pyreadstat.write_dta(
        df,
        dst_path=Path("tests/data") / (filename + ".dta"),
    )


create_tagged_missing_dta()
create_mixed_types_dta()
create_no_stratum_data()
create_2016_dta()
create_2016_dta(n=100, filename="2016_large_impute_test")
