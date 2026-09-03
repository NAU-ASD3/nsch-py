"""Tests for the acquire module."""

from __future__ import annotations

import io
import zipfile
from typing import TYPE_CHECKING

import httpx
import polars as pl
import pytest

from nsch.acquire import NSCH_DATA_URL, NSCH_URL_PREFIX, get_all_years, get_nsch_index, get_year

if TYPE_CHECKING:
    from pathlib import Path

# Fake URLs for mock 2021 html index page
YEAR_URL = "https://www.mock/datasets.2021.html"
ZIP_URL = "http://www.mock.com/mock_2021_topical_Stata.zip"


def test_get_nsch_index_creates_index_file_and_removes_duplicates(
    tmp_path: Path, respx_mock
) -> None:
    fake_index_html = (
        f'<a href="{NSCH_URL_PREFIX}2016.html">2016</a>'
        f'<a href="{NSCH_URL_PREFIX}2017.html">2017</a>'
        f'<a href="{NSCH_URL_PREFIX}2017.html">2017 duplicate</a>'
    )

    respx_mock.get(NSCH_DATA_URL).respond(text=fake_index_html)

    html_path = tmp_path / "index.html"
    result = get_nsch_index(local_html_path=html_path)

    assert html_path.exists()
    # also asserts years are confined to those listed in the index
    assert sorted(result["year"].to_list()) == [2016, 2017]
    assert result.height == 2


def test_get_nsch_index_reaches_out_to_network_when_no_path_given(respx_mock) -> None:
    fake_index_html = (
        f'<a href="{NSCH_URL_PREFIX}2016.html">2016</a>'
        f'<a href="{NSCH_URL_PREFIX}2017.html">2017</a>'
    )

    route = respx_mock.get(NSCH_DATA_URL).mock(
        return_value=httpx.Response(200, text=fake_index_html)
    )

    result = get_nsch_index()
    print(result)

    # assert a request made to the specified route was actually made
    assert route.called
    # make sure exactly one call was made, catches re-downloads
    assert route.call_count == 1
    # assert years come back
    assert sorted(result["year"].to_list()) == [2016, 2017]


# Testing functions for get_year
def create_mock_zipfile() -> bytes:
    """Build an in-memory zip file's bytes so respx_mock can serve it as content."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("mock_2021_topical.dta", "fake stata data")
    return buffer.getvalue()


def create_mock_index_page(respx_mock, hrefs: tuple[str, ...] = (ZIP_URL,)) -> bytes:
    """Build a fake HTML page for 2021, containing exactly one topical_Stata.zip link"""
    links = " ".join(f'<a href="{href}">STATA data file</a>' for href in hrefs)
    fake_html = f"<!DOCTYPE html><html><body>{links}</body></html>"
    respx_mock.get(YEAR_URL).respond(text=fake_html)
    # include a file with bytes actually zipped
    respx_mock.get(ZIP_URL).respond(content=create_mock_zipfile())


def test_get_year_downloads_if_webpage_not_in_data_path(tmp_path: Path, respx_mock) -> None:
    create_mock_index_page(respx_mock)

    result = get_year(YEAR_URL, tmp_path)

    assert result == tmp_path / "mock_2021_topical_Stata.zip"
    assert (tmp_path / "datasets.2021.html").exists()
    assert (tmp_path / "mock_2021_topical_Stata.zip").exists()
    assert (tmp_path / "mock_2021_topical.dta").exists()
    assert len(respx_mock.calls) == 2  # one for the html page, one for the zip


def test_get_year_does_nothing_if_already_exists_locally(tmp_path: Path, respx_mock) -> None:
    (tmp_path / "datasets.2021.html").write_text(f'<a href="{ZIP_URL}">STATA data file</a>')
    (tmp_path / "mock_2021_topical_Stata.zip").write_bytes(create_mock_zipfile())

    # fake HTML page for 2021, containing exactly one topical_Stata.zip link
    # Mocks are still registered (not skipped) even though we expect zero calls
    create_mock_index_page(respx_mock)
    result = get_year(YEAR_URL, tmp_path)

    # Make sure there are no calls, will raise NoMockAddress if requests.get is unnecessarily called
    respx_mock.assert_all_called = False

    assert len(respx_mock.calls) == 0
    assert result == tmp_path / "mock_2021_topical_Stata.zip"
    assert (tmp_path / "mock_2021_topical.dta").exists()


def test_get_year_raises_error_if_no_zip_links_found(tmp_path: Path, respx_mock) -> None:
    create_mock_index_page(respx_mock, hrefs=())

    with pytest.raises(ValueError, match="found 0"):
        get_year(YEAR_URL, tmp_path)


def test_get_year_raises_error_if_more_than_one_zip_link_found(tmp_path: Path, respx_mock) -> None:
    # Place both links on the same line to make sure we count regex matches
    # rather than lines themselves
    create_mock_index_page(respx_mock, hrefs=(ZIP_URL, ZIP_URL))

    with pytest.raises(ValueError, match="found 2"):
        get_year(YEAR_URL, tmp_path)


def test_get_year_raises_http_error_on_bad_status(tmp_path: Path, respx_mock) -> None:
    respx_mock.get(YEAR_URL).respond(403)
    with pytest.raises(httpx.HTTPStatusError):
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


def test_get_year_follows_redirect_on_html_page(tmp_path: Path, respx_mock) -> None:
    redirected_url = "https://www.mock/datasets_2021_alt.html"
    fake_html = f'<!DOCTYPE html><html><body><a href="{ZIP_URL}">STATA data file</a></body></html>'

    respx_mock.get(YEAR_URL).respond(302, headers={"Location": redirected_url})
    respx_mock.get(redirected_url).respond(text=fake_html)
    # Get another file (similarity of zip contents doesn't matter)
    respx_mock.get(ZIP_URL).respond(content=create_mock_zipfile())

    result = get_year(YEAR_URL, tmp_path)

    assert result == tmp_path / "mock_2021_topical_Stata.zip"
    assert (tmp_path / "mock_2021_topical.dta").exists()
    # 3 calls: YEAR_URL (302) -> redirected_url (200) -> ZIP_URL (200)
    assert len(respx_mock.calls) == 3


def test_get_all_years_raises_on_duplicate_year_files(tmp_path: Path) -> None:
    (tmp_path / "nsch_2024_topical.dta").touch()
    (tmp_path / "nsch_2024e_topical.dta").touch()
    (tmp_path / "nsch_2024_topical.do").touch()

    with pytest.raises(ValueError, match=r"2024"):
        get_all_years(data_path=tmp_path, download=False)
