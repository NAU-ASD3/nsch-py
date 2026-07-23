"""Generates a set of tiny synthetic .dta files for testing readers.py.
This script is the source of truth for .dta files used in testing.
"""

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
            "stratum": [1, 2, "2A", 1, 2, 2],
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
        variable_value_labels={"x": {1: "Yes", 2: "No"}},
        variable_format={"year": "float", "x": "float", "y": "str", "stratum": "int32"},
    )


create_tagged_missing_dta()
create_mixed_types_dta()
