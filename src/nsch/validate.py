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

    """
    # Leverage polars default to column operations: polars unpivot
    # unpivot df to long format, with columns year, variable, and value
    # group by year and variable to look at values fitting only that pair's intersection
    return (
        df.unpivot(index="year", variable_name="variable", value_name="value")
        .group_by(["year", "variable"])
        .agg(
            [
                # for the grouped pair value intersection, add columns with the
                # count of the number of NA values and number of total values
                pl.col("value").is_null().sum().alias("n_na").cast(pl.Int64),
                pl.len().alias("n_total").cast(pl.Int64),
            ]
        )
        .with_columns(
            # use those count columns to calculate the NA rate and call it `na_rate`
            (pl.col("n_na") / pl.col("n_total")).alias("na_rate").cast(pl.Float64)
        )
        .select(
            # grab, from this grouped and aggregated dataframe, only columns of interest
            ["variable", "year", "na_rate", "n_total"]
        )
    )
