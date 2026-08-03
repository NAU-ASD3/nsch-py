"""Tests for the acquire module."""

from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

import polars as pl
import pytest
import requests

from nsch.acquire import get_all_years, get_nsch_index, get_year

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


def test_get_year_does_nothing_if_already_exists_locally(tmp_path, requests_mock) -> None:
    (tmp_path / "datasets.2021.html").write_text(f'<a href="{ZIP_URL}">STATA data file</a>')
    (tmp_path / "mock_2021_topical_Stata.zip").write_bytes(create_mock_zipfile())

    result = get_year(YEAR_URL, tmp_path)
    # Make sure there are no calls, will raise NoMockAddress if
    # requests.get is unnecessarily called
    assert requests_mock.call_count == 0
    assert result == tmp_path / "mock_2021_topical_Stata.zip"
    assert (tmp_path / "mock_2021_topical.dta").exists()


def test_get_year_raises_error_if_no_zip_links_found(tmp_path, requests_mock) -> None:
    requests_mock.get(YEAR_URL, content=b"<html>no zip link here</html>")

    with pytest.raises(ValueError, match="found 0"):
        get_year(YEAR_URL, tmp_path)


def test_get_year_raises_error_if_more_than_one_zip_link_found(tmp_path, requests_mock) -> None:
    requests_mock.get(
        YEAR_URL,
        content=(f'<a href="{ZIP_URL}">one</a>\n<a href="{ZIP_URL}">two</a>').encode(),
    )

    with pytest.raises(ValueError, match="found 2"):
        get_year(YEAR_URL, tmp_path)


def test_get_year_raises_http_error_on_bad_status(tmp_path, requests_mock) -> None:
    # Uses the real requests.exceptions.HTTPError path via raise_for_status()
    requests_mock.get(YEAR_URL, status_code=403)

    with pytest.raises(requests.exceptions.HTTPError):
        get_year(YEAR_URL, tmp_path)


@pytest.fixture(autouse=True)
def clean_test_dir():
    d = Path("tests/temp")
    d.mkdir(parents=True, exist_ok=True)
    yield
    shutil.rmtree(d, ignore_errors=True)


def test_discovers_dta_and_do_files_with_standard_naming(tmp_path) -> None:
    # Create temp test directory with fake .dta and .do files
    path_strings = [
        "nsch_2016_topical.dta",
        "nsch_2016_topical.do",
        "nsch_2017_topical.dta",
        "nsch_2017_topical.do",
    ]
    for path_string in path_strings:
        (tmp_path / path_string).touch()

    result = get_all_years(data_path=tmp_path, download=False)

    assert isinstance(result, pl.DataFrame)
    assert sorted(result["year"].to_list()) == [2016, 2017]
    assert result.columns == ["year", "dta_path", "do_path"]


def test_get_all_years_discovers_files_with_non_standard_naming(tmp_path) -> None:
    (tmp_path / "nsch_2024e_topical.dta").touch()
    (tmp_path / "nsch_2024_topical.do").touch()
    result = get_all_years(data_path=tmp_path, download=False)
    assert result["year"].to_list() == [2024]


def test_get_all_years_filters_to_requested_years(tmp_path) -> None:
    for year in range(2016, 2018):
        file_path = tmp_path / ("nsch_" + str(year) + "_topical.dta")
        file_path.touch()
        file_path_do = tmp_path / ("nsch_" + str(year) + "_topical.do")
        file_path_do.touch()
    result = get_all_years(data_path=tmp_path, years=[2016, 2017], download=False)
    assert result["year"].to_list() == [2016, 2017]


def test_get_all_years_throws_error_when_no_dta_files_found(tmp_path) -> None:
    with pytest.raises(ValueError, match="No \\.dta files found"):
        get_all_years(data_path=tmp_path, download=False)
