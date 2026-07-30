"""Ingestion functions for the Readers module"""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl
import pyreadstat

import nsch._types as types

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["read_nsch_dta"]


READSTAT_TO_POLARS = {
    "double": pl.Float64,
    "float": pl.Float32,
    "int32": pl.Int32,
    "int16": pl.Int16,
    "int8": pl.Int8,
    "string": pl.Utf8,
}

TAGGED_NA_MAP = {
    "m": types.TaggedNA.NO_RESPONSE,
    "n": types.TaggedNA.NOT_IN_UNIVERSE,
    "l": types.TaggedNA.LOGICAL_SKIP,
    "d": types.TaggedNA.SUPPRESSED,
}


def _rewrite_tagged_na(lf: pl.LazyFrame, meta: pyreadstat.metadata_container) -> pl.LazyFrame:
    """Helper function for ``read_nsch_dta`` to map each missingness type per column

    Parameters
    ----------
    lf : pl.LazyFrame
        The input LazyFrame, read from the STATA file in ``read_nsch_dta``.
    meta : pyreadstat.metadata_container
        A container holding the metadata of the STATA file read in ``read_nsch_dta``
        containing the STATA missing user values to use for tagged missingness mapping.

    Returns
    -------
    A ``pl.LazyFrame`` of the STATA data with the missing values remapped to their sentinel
    values as defined in the ``_types`` module.
    """
    schema = lf.collect_schema()

    # Convert schema to polars datatypes
    polars_schema = {
        col: READSTAT_TO_POLARS[meta.readstat_variable_types[col]] for col in schema.names()
    }
    return lf.with_columns(
        [
            (
                pl.col(col).replace_strict(
                    TAGGED_NA_MAP, default=pl.col(col), return_dtype=polars_schema[col]
                )
                if col in meta.missing_user_values
                else pl.col(col)
            )
            .cast(polars_schema[col])
            .alias(col)
            for col in schema.names()
        ]
    )


def read_nsch_dta(path: Path) -> pl.LazyFrame:
    """Reads a single NSCH Stata ``dta`` file and returns a ``pl.LazyFrame``
    with polars numeric and character columns.

    Performs three cleaning steps during ingestion:
    1. Replaces Stata tagged ``NA`` values (``.m``, ``.n``, ``.l``, ``.d``)
        with integer sentinel codes using the ``Tagged_NA`` class in ``_types.py``
    2. Replaces STATA types for each column with their corresponding ``polars``
        type.
    3. Normalizes ``stratum`` column by converting ``"2A"`` to integer ``2``
        (a known encoding inconsistency in some NSCH years). This is done at
        read time rather than in the JSON harmonization config because the
        config-driven transform mechanism operates via numeric-only comparisons
        and cannot match the non-numeric ``"2A"`` value.

    Parameters
    ----------
    path: Path
        The path to the NSCH ``.dta`` file on the local machine.

    Returns
    -------
    A ``pl.LazyFrame`` containing the ingested ``.dta`` file with tagged NAs remapped,
    data types normalized, and the ``stratum`` string quirk handled.

    Examples
    --------
    >>> import numpy as np
    >>> import polars as pl
    >>> import pyreadstat
    >>> import tempfile
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as tmpdir:
    ...     dta_path = Path(tmpdir) / "tagged_missing.dta"
    ...     x_col = np.array([1, 2, "m", "n", "l", "d"], dtype=object)
    ...     df = pl.DataFrame(
    ...         {
    ...             "year": [2099] * 6,
    ...             "x": x_col,
    ...             "stratum": [1, "2A", "2a", 1, 2, 2],
    ...         },
    ...         strict=False,
    ...     )
    ...     pyreadstat.write_dta(
    ...         df,
    ...         str(dta_path),
    ...         missing_user_values={"x": ["m", "n", "l", "d"]},
    ...         variable_value_labels={"x": {1: "Yes", 2: "No"}},
    ...         variable_format={"year": "int32", "x": "int32", "stratum": "int32"},
    ...     )
    ...     df = read_nsch_dta(dta_path).collect()
    >>> print(df)
    shape: (6, 3)
    ┌──────┬─────┬─────────┐
    │ year ┆ x   ┆ stratum │
    │ ---  ┆ --- ┆ ---     │
    │ i64  ┆ i32 ┆ i64     │
    ╞══════╪═════╪═════════╡
    │ 2099 ┆ 1   ┆ 1       │
    │ 2099 ┆ 2   ┆ 2       │
    │ 2099 ┆ 996 ┆ 2       │
    │ 2099 ┆ 997 ┆ 1       │
    │ 2099 ┆ 998 ┆ 2       │
    │ 2099 ┆ 999 ┆ 2       │
    └──────┴─────┴─────────┘
    """
    if not path.exists():
        raise FileNotFoundError(
            f".dta path should be the path to a Stata.dta file, "
            f"but this file does not exist: {path}"
        )
    df, meta = pyreadstat.read_dta(str(path), user_missing=True, output_format="polars")
    # Cast Object datatypes to string before ganding to _rewrite_tagged_na
    # Polars gets stuck if there are Object types
    object_cols = [c for c in df.columns if df.schema[c] == pl.Object]

    df = df.with_columns(
        [
            pl.Series(
                col,
                [
                    v if v is None else str(v) if not isinstance(v, str) else v
                    for v in df.get_column(col).to_list()
                ],
                dtype=pl.String,
            )
            for col in object_cols
        ]
    )

    # _rewrite_tagged_na maps remaps nulls to our sentinel values
    # pyreadstat removes the . before missing values, so these are strings
    # with only the associated missingness letter
    lf = _rewrite_tagged_na(df.lazy(), meta)

    # Normalize stratum column: some years have "2A" which must become
    # numeric 2 for consistency.
    schema = lf.collect_schema()
    # Next grabs the first stratum column it sees instead of building the whole column list
    # .lower protects against inconsitant capitalization but not other naming inconsistancies
    stratum_col = next((c for c in schema.names() if c.lower() == "stratum"), None)

    if stratum_col is None:
        raise ValueError("No stratum column found")

    # Make sure str.replace only runs on columns that are already string types
    stratum_expr = (
        pl.col(stratum_col).str.replace(r"^2[aA]?$", "2").cast(pl.Int64)
        if stratum_col is not None and schema[stratum_col] == pl.String
        else pl.col(stratum_col).cast(pl.Int64)
    )

    return lf.with_columns(
        stratum_expr.alias("stratum"),
        pl.col("year").cast(pl.Int64),
    )
