"""Validation checks that run on the finished combined table.

Each function here takes the combined dataset and *describes* it without
changing it: a quality-control pass run after the pipeline has collected. They
work on an eager ``pl.DataFrame`` (not a ``LazyFrame``), and the four tagged-NA
sentinels (996-999) are already real nulls by the time they see the data.
"""

from __future__ import annotations

import polars as pl

__all__ = ["check_factor_levels", "check_year_coverage"]


def check_year_coverage(df: pl.DataFrame) -> pl.DataFrame:
    """Summarize per-variable year coverage for the combined table.

    For every column except ``year``, report how many survey years hold at
    least one non-null value and which years the variable is entirely missing
    from.

    Parameters
    ----------
    df : pl.DataFrame
        The combined table, with a ``year`` column and one column per variable.

    Returns
    -------
    pl.DataFrame
        One row per variable, with columns:

        - ``variable``: the variable name.
        - ``n_years_data``: number of years with at least one non-null value.
        - ``n_years_total``: total number of distinct years in the input.
        - ``missing_years``: comma-joined years where the variable is entirely
          null, or ``""`` if it is present in every year.

    Raises
    ------
    ValueError
        If ``df`` has no ``year`` column.

    Examples
    --------
    >>> import polars as pl
    >>> df = pl.DataFrame({"year": [2016, 2016, 2017], "x": [1, 2, 3], "y": [10, None, None]})
    >>> check_year_coverage(df).columns
    ['variable', 'n_years_data', 'n_years_total', 'missing_years']
    """
    if "year" not in df.columns:
        raise ValueError("Input data must contain a 'year' column")

    var_names = [name for name in df.columns if name != "year"]
    all_years = sorted(df["year"].unique().to_list())
    n_years_total = len(all_years)

    variables: list[str] = []
    n_years_data: list[int] = []
    missing_years: list[str] = []

    for col in var_names:
        # A year "has data" for this variable if any row in that year is
        # non-null; dropping the null rows first leaves exactly those years.
        years_with_data = df.filter(pl.col(col).is_not_null())["year"].unique().to_list()
        years_absent = sorted(set(all_years) - set(years_with_data))

        variables.append(col)
        n_years_data.append(len(years_with_data))
        missing_years.append(",".join(str(year) for year in years_absent))

    # schema_overrides fixes the dtypes so the no-variable (empty) case still
    # returns the right columns instead of Polars inferring Null from [].
    return pl.DataFrame(
        {
            "variable": variables,
            "n_years_data": n_years_data,
            "n_years_total": [n_years_total] * len(var_names),
            "missing_years": missing_years,
        },
        schema_overrides={
            "variable": pl.String,
            "n_years_data": pl.Int64,
            "n_years_total": pl.Int64,
            "missing_years": pl.String,
        },
    )


def check_factor_levels(df: pl.DataFrame) -> pl.DataFrame:
    """Summarize the levels present in each Enum column.

    For every Enum column (the Polars stand-in for R's factors), report each
    level that appears in the data: how many rows carry it, how many survey
    years it shows up in, and which years those are. Non-Enum columns are
    ignored.

    Parameters
    ----------
    df : pl.DataFrame
        The combined table, with a ``year`` column. Categorical variables are
        ``pl.Enum`` columns.

    Returns
    -------
    pl.DataFrame
        One row per (variable, level) pair, with columns:

        - ``variable``: the Enum column's name.
        - ``level``: the level value.
        - ``count``: number of rows carrying that level.
        - ``n_years_present``: number of distinct years the level appears in.
        - ``years_present``: comma-joined years the level appears in.

        Zero rows if the table has no Enum columns.

    Raises
    ------
    ValueError
        If ``df`` has no ``year`` column.

    Examples
    --------
    >>> import polars as pl
    >>> df = pl.DataFrame(
    ...     {
    ...         "year": [2016, 2016, 2017],
    ...         "status": pl.Series(["A", "B", "A"], dtype=pl.Enum(["A", "B"])),
    ...     }
    ... )
    >>> check_factor_levels(df).columns
    ['variable', 'level', 'count', 'n_years_present', 'years_present']
    """
    if "year" not in df.columns:
        raise ValueError("Input data must contain a 'year' column")

    # Compare the dtype object against pl.Enum. A string test like
    # str(dtype) == "Enum" is fragile: the text carries the categories too.
    enum_cols = [name for name, dtype in df.schema.items() if dtype == pl.Enum]

    # An explicit empty frame fixes the column order and dtypes for the
    # no-Enum-column case, and anchors the concat below.
    empty = pl.DataFrame(
        schema={
            "variable": pl.String,
            "level": pl.String,
            "count": pl.Int64,
            "n_years_present": pl.Int64,
            "years_present": pl.String,
        }
    )

    summaries = [
        df.select(pl.col("year"), pl.col(col).cast(pl.String).alias("level"))
        .drop_nulls("level")
        .group_by("level")
        .agg(
            pl.len().cast(pl.Int64).alias("count"),
            pl.col("year").n_unique().cast(pl.Int64).alias("n_years_present"),
            # Sort years before joining so "2016,2017" reads in order.
            pl.col("year").unique().sort().cast(pl.String).str.join(",").alias("years_present"),
        )
        .with_columns(variable=pl.lit(col))
        .select("variable", "level", "count", "n_years_present", "years_present")
        for col in enum_cols
    ]

    return pl.concat([*summaries, empty])
