"""Temporary holder for ingestion functions until they have a true home"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import polars as pl
import pyreadstat

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
    "object": pl.Int32,
}

TAGGED_NA_MAP = {
    "m": 996,
    "n": 997,
    "l": 998,
    "d": 999,
}


def _rewrite_tagged_na(lf: pl.LazyFrame, meta: pyreadstat.metadata_container) -> pl.LazyFrame:
    """Helper function for ``read_nsch_dta`` to map each missingness type per column

    Parameters
    ----------
    lf : pl.LazyFrame
        The input LazyFrame, read from the STATA file in ``read_nsch_dta``.
    meta : pyreadstat.metadata_container
        A container holding the metatdata of the STATA file read in ``read_nsch_dta``
        containing the STATA missing user values to use for tagged missingness mapping.

    Returns
    -------
    A ``pl.LazyFrame`` of the STATA data with the missing values remapped to their sentinel
    values as defined in the ``_types`` module.
    """
    # use meta.missing_user_values to map "m"/"n"/"l"/"d" -> 996/997/998/999 per column.
    for col, missing_values in meta.missing_user_values.items():
        local_map: dict[str, int] = {
            mv: TAGGED_NA_MAP[mv] for mv in missing_values if isinstance(mv, str)
        }

        def _convert_tagged_nas(
            val: int | float | str | None, local_map: dict[str, int] = local_map
        ) -> int | None:
            """Helper function to conver each type of missingness in the form of an apply mapping

            Parameters
            ----------
            val : int | float | str | None
                The current value stored in the ``pl.LazyFrame``.
            local_map : dict[str, int]
                A mapping of each missing user value in the STATA metadata to the
                appropriate NA tag defined in the ``_types`` module.

            Returns
            -------
            The appropriate mapped value as either an ``int`` or ``None``.
            """
            if val is None:
                return None
            if isinstance(val, str):
                return local_map[val]
            if isinstance(val, float) and math.isnan(val):
                return None
            return int(val)

        lf = lf.with_columns(
            pl.col(col).map_elements(_convert_tagged_nas, return_dtype=pl.Int64).alias(col)
        )
    return lf


def read_nsch_dta(path: Path) -> pl.LazyFrame:
    """Reads a single NSCH Stata ``dta`` file and returns a ``pl.LazyFrame``
    with polars numeric and charachter columns.

    Performs three cleaning steps during ingestion:
    1. Replaces Stata tagged ``NA`` values (``.m``, ``.n``, ``.l``, ``.d}``)
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
    >>> import polars as pl
    >>> from pathlib import Path
    >>> dta_missing = "tests/data/tagged_missing.dta"
    >>> dta_path = Path(dta_missing)
    >>> df = read_nsch_dta(dta_path).collect()
    >>> print(df)
    shape: (6, 3)
    ┌──────┬─────┬─────────┐
    │ year ┆ x   ┆ stratum │
    │ ---  ┆ --- ┆ ---     │
    │ i64  ┆ i64 ┆ i64     │
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
    # _rewrite_tagged_na maps remaps nulls to our sentinel values
    # pyreadstat removes the . before missing values, so these are strings
    # with only the associated missingness letter
    lf = _rewrite_tagged_na(df.lazy(), meta)

    # Normalize stratum column: some years have "2A" which must become
    # numeric 2 for consistency.
    lf = lf.with_columns(
        pl.col("stratum").str.replace(r"^2[aA]?$", "2").cast(pl.Int64),
        pl.col("year").cast(pl.Int64),
    )

    # Convert schema to polars datatypes
    # already_handled holds columns already converted to Int64 by _rewrite_tagged_na
    already_handled = {"stratum", "year", *meta.missing_user_values.keys()}
    to_cast = set(meta.column_names) - already_handled
    polars_schema = {col: READSTAT_TO_POLARS[meta.readstat_variable_types[col]] for col in to_cast}
    return lf.select(
        pl.col(col) if col in already_handled else pl.col(col).cast(polars_schema[col])
        for col in meta.column_names
    )
