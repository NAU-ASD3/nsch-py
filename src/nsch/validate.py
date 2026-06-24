"""Report number of years per column present in data.

For each column excluding `year`, ``check_year_coverage`` checks for
at leas one non-NA value in each year present in the data. It accepts
a finished DataFrame and returns DataFrame with a per-column summary of the
total number of years, total number of years with data, and a list of years
which are entirely NA for that column. It gives a snapshot of missingness
in the data and is implemented in the validation stage.

Parameters
----------
df: pl.DataFrame

Returns
-------

Examples
--------
>>>

"""

from __future__ import annotations

import polars as pl


def check_year_coverage(df: pl.DataFrame) -> pl.DataFrame:
    var_names = df.columns
    var_names.remove("year")
    all_years = set(df["year"].sort())
    n_years_total = len(all_years)

    out_list = []

    for i in range(0, len(var_names)):
        col = var_names[i]
        year_counts = df.group_by("year").agg(pl.col(col).is_not_null().sum().alias("n_non_na"))
        years_with_data = year_counts.filter(pl.col("n_non_na") > 0)["year"]
        years_missing = list(all_years.difference(years_with_data))

        out_list.append(
            {
                "variable": col,
                "n_years_data": years_with_data.len(),
                "n_years_total": n_years_total,
                # missing years list should be a single string
                "missing_years": ", ".join(years_missing),
            }
        )

    return pl.DataFrame(
        out_list,
        schema=[
            ("variable", pl.String),
            ("n_years_data", pl.Int64),
            ("n_years_total", pl.Int64),
            ("missing_years", pl.String),
        ],
        orient="row",
    )
