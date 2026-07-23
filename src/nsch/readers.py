"""Temporary holder for ingestion functions until they have a true home"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import polars as pl
import pyreadstat

if TYPE_CHECKING:
    from pathlib import Path

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
    """Helper function to map each missingness type per column"""
    # use meta.missing_user_values to map "m"/"n"/"l"/"d" -> 996/997/998/999 per column.
    for col, missing_values in meta.missing_user_values.items():
        local_map = {mv: TAGGED_NA_MAP[mv] for mv in missing_values}

        def _convert_tagged_nas(
            val: int | float | str | None, local_map: dict[str, int] = local_map
        ) -> int | None:
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
