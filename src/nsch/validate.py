"""Validation checks that run on the finished combined table.

Each function here takes the combined dataset and *describes* it without
changing it: a quality-control pass run after the pipeline has collected. They
work on an eager ``pl.DataFrame`` (not a ``LazyFrame``), and the four tagged-NA
sentinels (996-999) are already real nulls by the time they see the data.
"""

from __future__ import annotations

import polars as pl

__all__ = ["check_label_consistency", "check_year_coverage"]


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


def check_label_consistency(df: pl.DataFrame) -> pl.DataFrame:
    """Report whether each Enum column's levels stay the same across years.

    For every Enum column (the Polars stand-in for R's factors), look at the
    set of levels observed in each survey year and check whether that set is
    identical from year to year. A column whose categories drift between years
    is a sign that something went wrong during harmonization.

    Parameters
    ----------
    df : pl.DataFrame
        The combined table, with a ``year`` column. Categorical variables are
        ``pl.Enum`` columns.

    Returns
    -------
    pl.DataFrame
        One row per Enum column, with columns:

        - ``variable``: the column's name.
        - ``is_consistent``: ``True`` if the level set is identical in every
          year.
        - ``n_level_sets``: how many distinct level sets appear across years.
        - ``levels_by_year``: a per-year summary like ``2016={A|B}; 2017={A|C}``.

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
    ...         "year": [2016, 2016, 2017, 2017],
    ...         "status": pl.Series(["A", "B", "A", "C"], dtype=pl.Enum(["A", "B", "C"])),
    ...     }
    ... )
    >>> check_label_consistency(df).columns
    ['variable', 'is_consistent', 'n_level_sets', 'levels_by_year']
    """
    if "year" not in df.columns:
        raise ValueError("Input data must contain a 'year' column")

    # Compare the dtype object against pl.Enum. A string test like
    # str(dtype) == "Enum" is fragile: the text carries the categories too.
    enum_cols = [name for name, dtype in df.schema.items() if dtype == pl.Enum]
    all_years = sorted(df["year"].unique().to_list())

    variables: list[str] = []
    is_consistent: list[bool] = []
    n_level_sets: list[int] = []
    levels_by_year: list[str] = []

    for col in enum_cols:
        level_sets: list[str] = []
        year_labels: list[str] = []
        for year in all_years:
            # The levels actually observed that year, not the Enum's full
            # category list: drop nulls, dedupe, sort, join with "|".
            observed = (
                df.filter(pl.col("year") == year)[col]
                .drop_nulls()
                .cast(pl.String)
                .unique()
                .sort()
                .to_list()
            )
            key = "|".join(observed)
            level_sets.append(key)
            year_labels.append(f"{year}={{{key}}}")

        distinct_sets = set(level_sets)
        variables.append(col)
        is_consistent.append(len(distinct_sets) <= 1)
        n_level_sets.append(len(distinct_sets))
        levels_by_year.append("; ".join(year_labels))

    # schema_overrides fixes the dtypes so the no-Enum (empty) case still
    # returns the right columns instead of Polars inferring Null from [].
    return pl.DataFrame(
        {
            "variable": variables,
            "is_consistent": is_consistent,
            "n_level_sets": n_level_sets,
            "levels_by_year": levels_by_year,
        },
        schema_overrides={
            "variable": pl.String,
            "is_consistent": pl.Boolean,
            "n_level_sets": pl.Int64,
            "levels_by_year": pl.String,
        },
    )
