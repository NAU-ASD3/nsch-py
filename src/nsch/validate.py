"""Validation checks for the combined NSCH data."""

from __future__ import annotations

import polars as pl


def check_year_coverage(df: pl.DataFrame) -> pl.DataFrame:
    """Report per-variable year coverage across the combined data.

    Checks that each column (excluding `year`) has at least one non-missing value
    in each year present in the data. It accepts a `pl.DataFrame` and returns a
    ``pl.DataFrame`` with a per-column summary of the total number of years, total
    number of years with data, and a list of years which are entirely missing for
    that column. It gives a snapshot of missingness in variables across survey years.

    Parameters
    ----------
    df: pl.DataFrame
        A DataFrame with a ``year`` column and one or more other columns
        with data collected across multiple years.

    Returns
    -------
    pl.DataFrame
        A per-column summary containing the total number of years, the number
        of years with data, and a list of years for which all values are missing.

    Notes
    -----
    Empty results
        When the input contains no rows, the function still returns a Polars DataFrame
        with the canonical four columns and their declared dtypes. This is intentional:
        callers can always do ``df["col"]`` or check ``df.is_empty()`` without first
        guarding against a missing column. This deviates from the R version's
        ``rbindlist(list())`` which returns a 0x0 frame.

    Examples
    --------
    >>> import polars as pl
    >>> from nsch.validate import check_year_coverage
    >>> df = pl.DataFrame(
    ...     {"year": ["2016", "2016", "2017", "2017"], "x": [1, 2, 3, 4], "y": [1, 2, None, None]}
    ... )
    >>> check_year_coverage(df)
    shape: (2, 4)
    ┌──────────┬──────────────┬───────────────┬───────────────┐
    │ variable ┆ n_years_data ┆ n_years_total ┆ missing_years │
    │ ---      ┆ ---          ┆ ---           ┆ ---           │
    │ str      ┆ i64          ┆ i64           ┆ str           │
    ╞══════════╪══════════════╪═══════════════╪═══════════════╡
    │ x        ┆ 2            ┆ 2             ┆               │
    │ y        ┆ 1            ┆ 2             ┆ 2017          │
    └──────────┴──────────────┴───────────────┴───────────────┘
    """
    # make sure input df is a polars DataFrame and contains a year column
    if not isinstance(df, pl.DataFrame):
        raise TypeError("Input must be a polars DataFrame.")
    if "year" not in df.columns:
        raise ValueError("Input DataFrame must contain a 'year' column.")
    if df["year"].is_null().any():
        raise ValueError("'year' column must not contain null values")

    var_names = [c for c in df.columns if c != "year"]
    all_years = df["year"].unique()
    n_years_total = len(all_years)

    variables: list[str] = []
    n_years_data: list[int] = []
    n_years_total_list: list[int] = []
    # years are treated as strings for concatenation in the missing_years column
    missing_years: list[str] = []

    for col in var_names:
        # Get the total number of years with non-NA values for this variable
        year_counts = df.group_by("year").agg(pl.col(col).is_not_null().sum().alias("n_non_na"))
        years_with_data = year_counts.filter(pl.col("n_non_na") > 0)["year"]
        # python will only take the difference of two sets,
        # so the series from .unique() needs conversion first
        years_missing = list(set(all_years) - set(years_with_data))

        variables.append(col)
        n_years_data.append(years_with_data.len())
        n_years_total_list.append(n_years_total)
        # Turn the list of missing years into a comma-separated string
        missing_years.append(",".join(str(y) for y in sorted(years_missing)))

    # An empty dataframe returns a typed empty dataframe unlike R's 0x0 return frame
    return pl.DataFrame(
        {
            "variable": variables,
            "n_years_data": n_years_data,
            "n_years_total": n_years_total_list,
            "missing_years": missing_years,
        },
        schema={
            "variable": pl.Utf8,
            "n_years_data": pl.Int64,
            "n_years_total": pl.Int64,
            "missing_years": pl.Utf8,
        },
    )


def check_na_rates(df: pl.DataFrame) -> pl.DataFrame:
    """Calculate Per-column NA rates by year.

    Calculates the proportion of missing values for each column, broken down by
    year. Useful for identifying variables with high missingness in specific
    years, or for applying a threshold (e.g. exclude columns with >10% missing)
    before downstream analysis.

    Parameters
    ----------
    df : pl.DataFrame
        A Polars DataFrame containing a ``year`` column

    Returns
    -------
    pl.DataFrame
        A DataFrame with the columns ``variable`` (str), ``year`` (int),
        ``na_rate`` (float between 0 and 1), and ``n_total``. ``na_rate``
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
        raise TypeError("Input must be a polars DataFrame")
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
