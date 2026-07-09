"""Validation checks that run on the finished combined table.

Each function here takes the combined dataset and *describes* it without
changing it: a quality-control pass run after the pipeline has collected. They
work on an eager ``pl.DataFrame`` (not a ``LazyFrame``), and the four tagged-NA
sentinels (996-999) are already real nulls by the time they see the data."""
"""Per-variable year coverage for the validate module

``check_year_coverage`` checks that each column (excluding `year`) has
at least one non-missing value in each year present in the data. It accepts
a `pl.DataFrame` and returns a `pl.DataFrame` with a per-column summary of the
total number of years, total number of years with data,
and a list of years which are entirely missing for that column.
It gives a snapshot of missingness in variables across survey years.
"""

from __future__ import annotations

import polars as pl

__all__ = ["check_label_consistency", "check_year_coverage"]
    
def check_year_coverage(df: pl.DataFrame) -> pl.DataFrame:
    """Report per-variable year coverage across the combined data.

    Parameters
    ----------
    df: pl.DataFrame
        A DataFrame with a ``year`` column and one or more other columns
        with data collected across multiple years.
    
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
        A per-column summary containing the total number of years, the number
        of years with data, and a list of years for which all values are missing.

    Notes
    -----
    Empty results
        When the input contains no rows, the function still returns a Polars DataFrame
        with the canonical four columns and their declared dtypes.
        This is intentional: callers can always do ``df["col"]`` or check
        ``df.is_empty()`` without first guarding against a missing column.
        Contrast with R's ``rbindlist(list())`` which returns a 0x0 frame.

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
           