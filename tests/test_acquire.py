"""Tests for the acquire module."""

from __future__ import annotations

import io
import zipfile
from typing import TYPE_CHECKING

import polars as pl
import pytest
import requests

from nsch.acquire import get_all_years, get_nsch_index, get_year

if TYPE_CHECKING:
    from pathlib import Path

# Fake URLs for mock 2021 html index page
YEAR_URL = "https://www.mock/datasets.2021.html"
ZIP_URL = "http://www.mock.com/mock_2021_topical_Stata.zip"


def test_get_nsch_index_creates_index_file(tmp_path: Path) -> None:
    html_path = tmp_path / "index.html"
    get_nsch_index(local_html_path=html_path)
    assert html_path.exists()


def test_get_nsch_index_returns_list_of_years_after_2016(tmp_path: Path) -> None:
    html_path = tmp_path / "index.html"
    result = get_nsch_index(local_html_path=html_path)
    assert (result["year"] >= 2016).all()
    assert result["year"].is_unique().all()


# Testing functions for get_year
def create_mock_zipfile() -> bytes:
    """Build an in-memory zip file's bytes so requests_mock can serve it as content."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("mock_2021_topical.dta", "fake stata data")
    return buffer.getvalue()


def create_mock_index_page(requests_mock, hrefs: tuple[str, ...] = (ZIP_URL,)) -> bytes:
    """Build a fake HTML page for 2021, containing exactly one topical_Stata.zip link"""
    links = " ".join(f'<a href="{href}">STATA data file</a>' for href in hrefs)
    fake_html = f"<!DOCTYPE html><html><body>{links}</body></html>"
    requests_mock.get(YEAR_URL, text=fake_html)
    # include a file with bytes actually zipped
    requests_mock.get(ZIP_URL, content=create_mock_zipfile())


def test_get_year_downloads_if_webpage_not_in_data_path(tmp_path: Path, requests_mock) -> None:
    create_mock_index_page(requests_mock)

    result = get_year(YEAR_URL, tmp_path)

    assert result == tmp_path / "mock_2021_topical_Stata.zip"
    assert (tmp_path / "datasets.2021.html").exists()
    assert (tmp_path / "mock_2021_topical_Stata.zip").exists()
    assert (tmp_path / "mock_2021_topical.dta").exists()
    assert requests_mock.call_count == 2  # one for the html page, one for the zip


def test_get_year_does_nothing_if_already_exists_locally(tmp_path: Path, requests_mock) -> None:
    (tmp_path / "datasets.2021.html").write_text(f'<a href="{ZIP_URL}">STATA data file</a>')
    (tmp_path / "mock_2021_topical_Stata.zip").write_bytes(create_mock_zipfile())

    # fake HTML page for 2021, containing exactly one topical_Stata.zip link
    # Mocks are still registered (not skipped) even though we expect zero calls
    create_mock_index_page(requests_mock)

    result = get_year(YEAR_URL, tmp_path)

    # Make sure there are no calls, will raise NoMockAddress if
    # requests.get is unnecessarily called
    assert requests_mock.call_count == 0
    assert result == tmp_path / "mock_2021_topical_Stata.zip"
    assert (tmp_path / "mock_2021_topical.dta").exists()


def test_get_year_raises_error_if_no_zip_links_found(tmp_path: Path, requests_mock) -> None:
    requests_mock.get(YEAR_URL, content=b"<html>no zip link here</html>")
    create_mock_index_page(requests_mock, hrefs=())

    with pytest.raises(ValueError, match="found 0"):
        get_year(YEAR_URL, tmp_path)


def test_get_year_raises_error_if_more_than_one_zip_link_found(
    tmp_path: Path, requests_mock
) -> None:
    # Place both links on the same line to make sure we cout regex matches
    # rather than lines themselves
    create_mock_index_page(requests_mock, hrefs=(ZIP_URL, ZIP_URL))

    with pytest.raises(ValueError, match="found 2"):
        get_year(YEAR_URL, tmp_path)


def test_get_year_raises_http_error_on_bad_status(tmp_path: Path, requests_mock) -> None:
    # Uses requests.exceptions.HTTPError path via raise_for_status()
    requests_mock.get(YEAR_URL, status_code=403)

    with pytest.raises(requests.exceptions.HTTPError):
        get_year(YEAR_URL, tmp_path)


def test_discovers_dta_and_do_files_with_standard_naming(tmp_path: Path) -> None:
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


def test_get_all_years_discovers_files_with_non_standard_naming(tmp_path: Path) -> None:
    (tmp_path / "nsch_2024e_topical.dta").touch()
    (tmp_path / "nsch_2024_topical.do").touch()
    result = get_all_years(data_path=tmp_path, download=False)
    assert result["year"].to_list() == [2024]


def test_get_all_years_filters_to_requested_years(tmp_path: Path) -> None:
    for year in range(2016, 2018):
        file_path = tmp_path / ("nsch_" + str(year) + "_topical.dta")
        file_path.touch()
        file_path_do = tmp_path / ("nsch_" + str(year) + "_topical.do")
        file_path_do.touch()
    result = get_all_years(data_path=tmp_path, years=[2016, 2017], download=False)
    assert result["year"].to_list() == [2016, 2017]


def test_get_all_years_throws_error_when_no_dta_files_found(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No \\.dta files found"):
        get_all_years(data_path=tmp_path, download=False)
