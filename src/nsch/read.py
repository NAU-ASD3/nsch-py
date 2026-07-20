"""Temporary holder for ingestion functions until they have a true home"""

from __future__ import annotations

import polars as pl
import pyreadstat

from nsch._types import TaggedNA


def read_nsch_dta(dta_path: str) -> pl.LazyFrame:
    df: pl.DataFrame
    df, meta = pyreadstat.read_dta(
        filename_path=dta_path, user_missing=True, output_format="polars"
    )
    # Replace tagged NA values with integer sentinel codes: TaggedNA defined in _types
    tagged_na_map = {
        ".m": TaggedNA.NO_RESPONSE,
        ".n": TaggedNA.NOT_IN_UNIVERSE,
        ".l": TaggedNA.LOGICAL_SKIP,
        ".d": TaggedNA.SUPPRESSED,
    }
    for col in df.columns:
        if df[col].dtype == pl.Utf8:
            df = df.with_columns(
                pl.col(col).replace_strict(tagged_na_map, default=pl.col(col)).alias(col)
            )
    print(df.head())

    # Convert stata int and char to polars (pl.Int64, pl.Utf8)

    # Normalize stratum column: some years have "2A" which must become
    # numeric 2 for consistency. (From R Code)
    return df.lazy()
