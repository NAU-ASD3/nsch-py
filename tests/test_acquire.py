"""Tests for the acquire module."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
import requests

from nsch.acquire import get_nsch_index, get_year

YEAR_URL = "https://www.census.gov/programs-surveys/nsch/data/datasets.2021.html"
ZIP_URL = "https://www2.census.gov/programs-surveys/nsch/datasets/2021/mock_2021_topical_Stata.zip"

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


# Testing functions for get_year
def create_mock_zipfile() -> bytes:
    """Build an in-memory zip file's bytes so requests_mock can serve it as content."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("mock_2021_topical.dta", "fake stata data")
    return buffer.getvalue()


def test_get_year_downloads_if_webpage_not_in_data_path(tmp_path, requests_mock) -> None:
    requests_mock.get(YEAR_URL, content=f'<a href="{ZIP_URL}">STATA data file</a>'.encode())
    requests_mock.get(ZIP_URL, content=create_mock_zipfile())
    result = get_year(YEAR_URL, tmp_path)

    assert result == tmp_path / "mock_2021_topical_Stata.zip"
    assert (tmp_path / "datasets.2021.html").exists()
    assert (tmp_path / "mock_2021_topical_Stata.zip").exists()
    assert (tmp_path / "mock_2021_topical.dta").exists()
    assert requests_mock.call_count == 2  # one for the html page, one for the zip


def test_get_year_does_nothing_if_already_exists_locally(tmp_path, requests_mock):
    (tmp_path / "datasets.2021.html").write_text(f'<a href="{ZIP_URL}">STATA data file</a>')
    (tmp_path / "mock_2021_topical_Stata.zip").write_bytes(create_mock_zipfile())

    result = get_year(YEAR_URL, tmp_path)
    # Make sure there are no calls, will raise NoMockAddress if
    # requests.get is unnecessarily called
    assert requests_mock.call_count == 0
    assert result == tmp_path / "mock_2021_topical_Stata.zip"
    assert (tmp_path / "mock_2021_topical.dta").exists()


def test_get_year_raises_error_if_no_zip_links_found(tmp_path, requests_mock):
    requests_mock.get(YEAR_URL, content=b"<html>no zip link here</html>")

    with pytest.raises(ValueError, match="found 0"):
        get_year(YEAR_URL, tmp_path)


def test_get_year_raises_error_if_more_than_one_zip_link_found(tmp_path, requests_mock):
    requests_mock.get(
        YEAR_URL,
        content=(f'<a href="{ZIP_URL}">one</a>\n<a href="{ZIP_URL}">two</a>').encode(),
    )

    with pytest.raises(ValueError, match="found 2"):
        get_year(YEAR_URL, tmp_path)


def test_get_year_raises_http_error_on_bad_status(tmp_path, requests_mock):
    # Uses the real requests.exceptions.HTTPError path via raise_for_status()
    requests_mock.get(YEAR_URL, status_code=403)

    with pytest.raises(requests.exceptions.HTTPError):
        get_year(YEAR_URL, tmp_path)
