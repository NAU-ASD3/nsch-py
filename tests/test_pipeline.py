"""R-parity test: ``get_clean_data`` against the cached R 2016-2024 output (#27).

This runs only on a machine with the real NSCH files. Set two environment
variables:

- ``NSCH_REAL_DATA_DIR``: the folder of NSCH Stata files (``.dta`` and ``.do``)
  that ``get_all_years`` searches.
- ``NSCH_R_REFERENCE``: the R export, ``nsch-harmonized-2016-2024_<date>.csv.gz``,
  written by ``export-harmonized.R`` in NAU-ASD3/nsch-ml-paper.

Without both, every test here is skipped, which is how CI runs it.

The reference used for the wrap-up was generated on 2026-10-12 from
NAU-ASD3/nsch commit fbdccb4: 386,083 rows by 168 columns.

Rows are matched on (year, hhid), so neither side's row order matters. Every
cell must agree except where the 2016 ``a1_grade`` imputation draws at random:
R's ``sample()`` and Python's RNG give different draws from the same seed, so
those cells are checked by the coarse group they were drawn within and by the
overall 2016 distribution instead.
"""

from __future__ import annotations

import os
from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

DATA_DIR = os.environ.get("NSCH_REAL_DATA_DIR")
R_REFERENCE = os.environ.get("NSCH_R_REFERENCE")

pytestmark = pytest.mark.skipif(
    not (DATA_DIR and R_REFERENCE),
    reason="set NSCH_REAL_DATA_DIR and NSCH_R_REFERENCE to run the R-parity test",
)

YEARS = list(range(2016, 2025))
KEY = ["year", "hhid"]

# The imputation picks a fine a1_grade category within the coarse group (1, 2, 3)
# recorded in the 2016 file, then derives higrade and higrade_tvis from it
# (R's impute_a1_grade_2016.R). higrade is fixed by the group, so it is compared
# cell for cell. a1_grade and higrade_tvis vary within a group, so in 2016 they
# are compared through these maps to the group instead.
A1_GRADE_GROUP = {
    "8th grade or less": "1",
    "9th-12th grade; No diploma": "1",
    "High School Graduate or GED Completed": "2",
    "Completed a vocational, trade, or business school program": "2",
    "Some College Credit, but No Degree": "3",
    "Associate Degree (AA, AS)": "3",
    "Bachelor's Degree (BA, BS, AB)": "3",
    "Master's Degree (MA, MS, MSW, MBA)": "3",
    "Doctorate (PhD, EdD) or Professional Degree (MD, DDS, DVM, JD)": "3",
}
HIGRADE_TVIS_GROUP = {
    "Less than high school": "1",
    "High school (including vocational, trade, or business school)": "2",
    "Some college or Associate Degree": "3",
    "College degree or higher": "3",
}
IMPUTED_IN_2016 = {"a1_grade": A1_GRADE_GROUP, "higrade_tvis": HIGRADE_TVIS_GROUP}

# How far a 2016 a1_grade category's share may drift between R and Python
# (absolute, as a proportion of 2016 rows with a grade).
A1_GRADE_SHARE_TOLERANCE = 0.005


@pytest.fixture(scope="module")
def py_df() -> pl.DataFrame:
    """The Python pipeline's output for 2016-2024."""
    try:
        from nsch import get_clean_data  # type: ignore[attr-defined]
    except ImportError:
        pytest.skip("get_clean_data isn't available yet (#26)")
    assert DATA_DIR is not None
    return get_clean_data(data_path=Path(DATA_DIR), years=YEARS)


@pytest.fixture(scope="module")
def r_df() -> pl.DataFrame:
    """The R reference, every column read as text (fwrite writes missing values as empty)."""
    assert R_REFERENCE is not None
    return pl.read_csv(R_REFERENCE, infer_schema_length=0, null_values="")


@pytest.fixture(scope="module")
def joined(py_df: pl.DataFrame, r_df: pl.DataFrame) -> pl.DataFrame:
    """Python and R rows side by side, matched on (year, hhid); R's columns end in ``_r``."""
    py = py_df.with_columns(pl.col(KEY).cast(pl.Int64))
    r = r_df.with_columns(pl.col(KEY).cast(pl.Float64).cast(pl.Int64))
    return py.join(r, on=KEY, how="full", suffix="_r", coalesce=True, validate="1:1")


def _pair(col: str, dtype: pl.DataType) -> tuple[pl.Expr, pl.Expr]:
    """The Python column and its R twin, made comparable.

    Numeric columns are compared as Float64, since R's CSV writes 1 where Polars
    holds 1.0. Everything else is compared as text, which is how R's CSV holds
    factor labels.
    """
    if dtype.is_numeric():
        return pl.col(col).cast(pl.Float64), pl.col(f"{col}_r").cast(pl.Float64, strict=False)
    return pl.col(col).cast(pl.String), pl.col(f"{col}_r")


def _year_counts(df: pl.DataFrame) -> pl.DataFrame:
    return df.group_by(pl.col("year").cast(pl.Int64)).len().sort("year")


def test_same_columns(py_df: pl.DataFrame, r_df: pl.DataFrame) -> None:
    """Both outputs have the same columns; order is free to differ."""
    assert sorted(py_df.columns) == sorted(r_df.columns)


def test_rows_per_year_match(py_df: pl.DataFrame, r_df: pl.DataFrame) -> None:
    """Each year has exactly as many rows as in R."""
    assert_frame_equal(_year_counts(py_df), _year_counts(r_df))


def test_same_households_each_year(py_df: pl.DataFrame, r_df: pl.DataFrame) -> None:
    """Every (year, hhid) in one output is in the other."""

    def keys(df: pl.DataFrame) -> pl.DataFrame:
        return df.select(
            pl.col("year").cast(pl.Int64), pl.col("hhid").cast(pl.Float64).cast(pl.Int64)
        ).sort(KEY)

    assert_frame_equal(keys(py_df), keys(r_df))


def test_label_sets_match(py_df: pl.DataFrame, r_df: pl.DataFrame) -> None:
    """Every labeled column uses the same set of labels in both outputs."""
    labeled = [col for col, dtype in py_df.schema.items() if isinstance(dtype, pl.Enum)]
    assert labeled, "no labeled (Enum) columns in the Python output"
    diffs = {}
    for col in labeled:
        py_labels = set(py_df[col].drop_nulls().cast(pl.String).unique().to_list())
        r_labels = set(r_df[col].drop_nulls().unique().to_list())
        if py_labels != r_labels:
            diffs[col] = {
                "only_python": sorted(py_labels - r_labels),
                "only_r": sorted(r_labels - py_labels),
            }
    assert not diffs, diffs


def test_cells_match_outside_the_2016_imputation(py_df: pl.DataFrame, joined: pl.DataFrame) -> None:
    """Every cell matches R, except the randomly imputed 2016 cells checked below."""
    mismatches = {}
    for col, dtype in py_df.schema.items():
        if col in KEY:
            continue
        python_value, r_value = _pair(col, dtype)
        rows = joined.filter(pl.col("year") != 2016) if col in IMPUTED_IN_2016 else joined
        n = rows.select((~python_value.eq_missing(r_value)).sum()).item()
        if n:
            mismatches[col] = n
    assert not mismatches, f"cells that differ from R, by column: {mismatches}"


@pytest.mark.parametrize("col", sorted(IMPUTED_IN_2016))
def test_2016_imputed_columns_match_by_group(joined: pl.DataFrame, col: str) -> None:
    """In 2016, a1_grade and higrade_tvis fall in the same coarse group as in R, row for row."""
    groups = IMPUTED_IN_2016[col]
    rows = joined.filter(pl.col("year") == 2016)
    seen = set(rows[col].drop_nulls().cast(pl.String).unique().to_list())
    seen |= set(rows[f"{col}_r"].drop_nulls().unique().to_list())
    assert seen <= set(groups), f"labels with no group: {sorted(seen - set(groups))}"
    python_group = pl.col(col).cast(pl.String).replace_strict(groups, default=None)
    r_group = pl.col(f"{col}_r").replace_strict(groups, default=None)
    n = rows.select((~python_group.eq_missing(r_group)).sum()).item()
    assert n == 0, f"{n} rows in 2016 where {col} lands in a different group than in R"


def test_2016_a1_grade_distribution_matches(py_df: pl.DataFrame, r_df: pl.DataFrame) -> None:
    """Each 2016 a1_grade category's share is within the tolerance of R's."""

    def shares(df: pl.DataFrame) -> pl.DataFrame:
        return (
            df.filter(pl.col("year").cast(pl.Int64) == 2016)
            .select(pl.col("a1_grade").cast(pl.String))
            .drop_nulls()
            .group_by("a1_grade")
            .len()
            .select("a1_grade", share=pl.col("len") / pl.col("len").sum())
        )

    both = (
        shares(py_df)
        .join(shares(r_df), on="a1_grade", how="full", suffix="_r", coalesce=True)
        .fill_null(0.0)
    )
    worst = both.select((pl.col("share") - pl.col("share_r")).abs().max()).item()
    assert worst < A1_GRADE_SHARE_TOLERANCE, both.sort("a1_grade")


def test_autism_by_year_crosstab_matches(py_df: pl.DataFrame, r_df: pl.DataFrame) -> None:
    """The year by k2q35a (ever told autism) cross-tab matches R exactly.

    The cell-level test already covers this; the cross-tab is the spot-check
    named in the summer plan and the one the paper reports.
    """

    def crosstab(df: pl.DataFrame) -> pl.DataFrame:
        return (
            df.select(pl.col("year").cast(pl.Int64), pl.col("k2q35a").cast(pl.String))
            .group_by("year", "k2q35a")
            .len()
            .sort("year", "k2q35a", nulls_last=True)
        )

    assert_frame_equal(crosstab(py_df), crosstab(r_df))
