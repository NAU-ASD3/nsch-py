"""Tests for the acquire module."""

from __future__ import annotations

from pathlib import Path

from nsch.acquire import get_nsch_index

local_download_path = Path("tests/temp/temp.csv")


def test_get_nsch_index_creates_index_file() -> None:
    if local_download_path.exists():
        # Clear temp path to restart from clean
        local_download_path.unlink()
    get_nsch_index(local_html_path=local_download_path)
    assert local_download_path.exists()


def test_get_nsch_index_returns_list_of_years_after_2016() -> None:
    result = get_nsch_index(local_html_path=local_download_path)
    assert (result["year"] >= 2016).all()
    # assert year column contains no duplicates
    assert result["year"].is_unique().all()
