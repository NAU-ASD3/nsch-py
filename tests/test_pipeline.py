"""Tests for the NSCH pipeline."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import polars as pl
import pyreadstat
import pytest
from polars.testing import assert_frame_equal

from nsch import get_clean_data

if TYPE_CHECKING:
    from pathlib import Path


def test_get_clean_data_raises_when_data_path_has_no_files(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"No \.dta files found"):
        get_clean_data(data_path=tmp_path, download=False)


def test_get_clean_data_runs_two_synthetic_years(tmp_path: Path) -> None:
    """Two small years go through read, harmonize, label, and combine."""
    do_lines = [
        'label var sc_sex "Sex of child"',
        'label define sc_sex_lab 1 "Male"',
        'label define sc_sex_lab 2 "Female", add',
        'label define fam_r_lab 1 "Two parents"',
        'label define fam_r_lab 2 "One parent", add',
    ]
    for year, sexes in [(2017, [1, 2, 2]), (2018, [2, 1, 1])]:
        raw = pl.DataFrame(
            {
                "year": [year] * 3,
                "hhid": [year * 1000 + i for i in range(3)],
                "stratum": [1] * 3,
                "sc_sex": sexes,
                "fam_r": [1, 2, 1],
            }
        )
        pyreadstat.write_dta(raw, str(tmp_path / f"nsch_{year}e_topical.dta"))
        (tmp_path / f"nsch_{year}_topical.do").write_text("\n".join(do_lines) + "\n")

    config = {
        "desired_variables": ["year", "hhid", "sc_sex", "family"],
        "transformations": {
            "transform": {},
            "rename_columns": {"fam_r": {"years": ["2017", "2018"], "new_name": "family"}},
            "merge_columns": {},
        },
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))

    result = get_clean_data(
        config_path=config_path,
        data_path=tmp_path,
        years=[2017, 2018],
    )

    expected = pl.DataFrame(
        {
            "year": [2017, 2017, 2017, 2018, 2018, 2018],
            "hhid": [
                2017000.0,
                2017001.0,
                2017002.0,
                2018000.0,
                2018001.0,
                2018002.0,
            ],
            "sc_sex": ["Male", "Female", "Female", "Female", "Male", "Male"],
            "family": ["Two parents", "One parent", "Two parents"] * 2,
        },
        schema={
            "year": pl.Int64,
            "hhid": pl.Float64,
            "sc_sex": pl.Enum(["Male", "Female"]),
            "family": pl.Enum(["Two parents", "One parent"]),
        },
    )
    assert_frame_equal(result, expected)
