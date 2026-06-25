"""Per-variable year coverage for the validate

``check_year_coverage`` checks, for each column excluding `year`,
at least one non-NA value in each year present in the data. It accepts
a collected LazyFrame as a DataFrame and returns DataFrame with a
per-column summary of the total number of years, total number of years
with data, and a list of years which are entirely NA for that column.
It gives a snapshot of missingness in variablse accross survey years.
"""

from __future__ import annotations

import polars as pl


def check_year_coverage(df: pl.DataFrame) -> pl.DataFrame:
    """Report number of years per column present in data.


    Parameters
    ----------
    df: pl.DataFrame
        A DataFrame with a ``year`` column and one or more other columns
        with data collected across multiple years.

    Returns
    -------
    pl.DataFrame
        A per-column summary of the total number of years, total number of years
        with data, and a list of years which are entirely NA for that column.

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

    var_names = df.columns
    var_names.remove("year")
    all_years = set(df["year"].sort())
    n_years_total = len(all_years)

    variables: list[str] = []
    n_years_data: list[int] = []
    n_years_total_list: list[int] = []
    missing_years: list[str] = []

    if len(var_names) > 0:
        for i in range(0, len(var_names)):
            col = var_names[i]
            # Get the total number of years with non-NA values for this variable
            year_counts = df.group_by("year").agg(pl.col(col).is_not_null().sum().alias("n_non_na"))
            years_with_data = year_counts.filter(pl.col("n_non_na") > 0)["year"]
            years_missing = list(all_years.difference(years_with_data))

            variables.append(col)
            n_years_data.append(years_with_data.len())
            n_years_total_list.append(n_years_total)
            # Turn the list of missing years into a comma-separated string
            missing_years.append(", ".join(sorted(years_missing)))

    return pl.DataFrame(
        {
            "variable": variables,
            "n_years_data": n_years_data,
            "n_years_total": n_years_total_list,
            "missing_years": missing_years,
        },
        orient="row",
    )
