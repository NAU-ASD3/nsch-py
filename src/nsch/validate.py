"""Calculate NA rates per column per year for the validate module

``check_na_rates`` checks, for each column per year,
the proportion of NA values for each column, broken down by year.
Useful for identifying variables with high missingness in
specific years, or for applying a threshold (e.g. exclude columns with
>10% missing) before downstream analysis.
"""

from __future__ import annotations

import polars as pl


def check_na_rates(df: pl.DataFrame) -> pl.DataFrame:
    """Check NA rates per column per year.

    Parameters:
    ----------
    df : pl.DataFrame
        A Polars Dataframe containing a 'year' column

    Returns:
    -------
    A Polars DataFrame with the columns `variable` (str), `year` (int),
    `na_rate` (float from 0 to 1), and `n_total` where `na_rate` is the
    proportion of NA values for each variable per year and `n_total`
    is the total number of rows for that year.

    Examples
    --------
    >>> import polars as pl
    >>> from nsch.validate import check_na_rates
    >>> df = pl.DataFrame(
    ...     {"year": [2016, 2016, 2017, 2017], "x": [1, None, 3, 4], "y": [None, None, 5, 6]}
    ... )
    >>> check_na_rates(df)
    shape: (4, 4)
    ┌──────────┬──────┬─────────┬─────────┐
    │ variable ┆ year ┆ na_rate ┆ n_total │
    │ ---      ┆ ---  ┆ ---     ┆ ---     │
    │ str      ┆ i64  ┆ f64     ┆ i64     │
    ╞══════════╪══════╪═════════╪═════════╡
    │ x        ┆ 2016 ┆ 0.5     ┆ 2       │
    │ x        ┆ 2017 ┆ 0.0     ┆ 2       │
    │ y        ┆ 2016 ┆ 1.0     ┆ 2       │
    │ y        ┆ 2017 ┆ 0.0     ┆ 2       │
    └──────────┴──────┴─────────┴─────────┘

    """
    if not isinstance(df, pl.DataFrame):
        raise TypeError("Input must be a Polars DataFrame")
    if "year" not in df.columns:
        raise ValueError("Input DataFrame must contain a 'year' column")

    # Leverage polars default to column operations: polars unpivot
    return (
        df.unpivot(index="year", variable_name="variable", value_name="value")
        .group_by(["year", "variable"])
        .agg(
            [
                pl.col("value").is_null().sum().alias("n_na").cast(pl.Int64),
                pl.len().alias("n_total").cast(pl.Int64),
            ]
        )
        .with_columns((pl.col("n_na") / pl.col("n_total")).alias("na_rate").cast(pl.Float64))
        .select(["variable", "year", "na_rate", "n_total"])
    )
