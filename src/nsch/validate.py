"""Per-column NA rates per year for the validate module

``check_na_rates`` calculates the proportion of missing values for each
column, broken down by year. Useful for identifying variables with high
missingness in specific years, or for applying a threshold (e.g. exclude
columns with >10% missing) before downstream analysis.
"""

from __future__ import annotations

import polars as pl


def check_na_rates(df: pl.DataFrame) -> pl.DataFrame:
    """Calculate per-column NA rates by year.

    Parameters
    ----------
    df : pl.DataFrame
        A Polars DataFrame containing a ``year`` column

    Returns
    -------
    pl.DataFrame
        A DataFrame with the columns ``variable`` (str), ``year`` (int),
        ``na_rate`` (float between0 and 1), and ``n_total``. ``na_rate``
        is the proportion of NA values for each variable per year and
        ``n_total`` is the total number of rows for that year.

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

    # Leverage polars strength for column operations: polars unpivot
    return (
        # Convert all columns except year to True/False indicating NA status
        df.select("year", pl.exclude("year").is_null())
        .unpivot(index="year", variable_name="variable", value_name="is_na")
        .group_by(["year", "variable"])
        .agg(
            [
                pl.col("is_na").sum().cast(pl.Int64).alias("n_na"),
                pl.len().cast(pl.Int64).alias("n_total"),
            ]
        )
        .with_columns((pl.col("n_na") / pl.col("n_total")).alias("na_rate"))
        .select(["variable", "year", "na_rate", "n_total"])
        .sort(by=["variable", "year"])
    )
