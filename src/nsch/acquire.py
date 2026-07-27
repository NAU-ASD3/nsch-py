"""Functions for the Acquire layer"""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl
import requests  # type: ignore

__all__ = ["get_nsch_index"]


nsch_url_prefix = "https://www.census.gov/programs-surveys/nsch/data/datasets."
nsch_data_url = nsch_url_prefix + "html"


def get_nsch_index(local_html_path: Path) -> pl.DataFrame:
    """
    Download and parse the NSCH index web page to obtain a list
    of years for which survey data are available.
    We can then do a loop over years,
    to download data from each available year.

    Parameters
    ----------
    local_html_path: Path
        Local file in which HTML will be downloaded, if it does not already exist.

    Returns
    -------
    A pl.DataFrame containing one row per year of data, and columns ``url``, ``year``.
    """
    local_html_path = Path(local_html_path)
    if not local_html_path.exists():
        response = requests.get(nsch_data_url, timeout=30)
        response.raise_for_status()
        local_html_path.write_bytes(response.content)

    # Get text of html paths on the index page
    html_text = local_html_path.read_text(encoding="utf-8").splitlines()
    # Get html strings with each year, escape special charachters
    # name url with group and "url" and, if present, name found digits with the group "year"
    url_pattern = r"(?P<url>" + re.escape(nsch_url_prefix) + r"(?P<year>[0-9]+)\.html)"

    # create a dataframe from the url path with:
    # url as a list containing nsch url prefix, year as int, and .html string
    rows = [
        {"url": m.group("url"), "year": int(m.group("year"))}
        for m in re.finditer(url_pattern, "\n".join(html_text))
    ]

    year_dt = pl.DataFrame(
        rows,
        schema={"url": pl.Utf8, "year": pl.Int64},
    )

    # return only the unique years of the dataframe
    return year_dt.unique(maintain_order=True)


def get_year(year_url: str, data_path: Path, verbose: bool = False) -> None:
    """Download one year of NSCH data

    If the input web page does not exist in the data_path
    directory, then it will be downloaded. Looks on that web page for a
    link to a topical Stata zip file, and then downloads it if it does not
    exist in the data_path directory. Finally, the contents of the
    zip file are unzipped into the data_path directory.

    Parameters
    ----------
    year_url: str
        URL to a NSCH year-specific data web page, as returned by ``get_nsch_index``

    data_path: Path
        Local path where data files will be downloaded, default "NSCH_data/00_original_Stata".

    verbose: bool
        Show messages for download

    Returns
    -------
    None, unzips data into the data_path directory

    """


def get_all_years(data_path: Path, download: bool) -> None:
    r"""Discover NSCH data files for all available years

    Finds ``.dta`` and ``.do`` files in a data directory using glob
    patterns, returning a ``pl.DataFrame`` mapping each year to its
    file paths. Handles non-standard filenames such as "nsch_2024e_topical.dta".
    Optionally downloads data first via ``get_year``.

    Parameters
    ----------
    data_path: Path
        Directory containing NSCH \code{.dta} and \code{.do} files.}
    years: int
        Optional integer vector of years to include.
        If ``None``, all discovered years are returned.
    download: bool
        If ``True``, downloads data via ``get_year`` before discovering files.


    Returns
    -------
    A ``pl.DataFrame`` with columns ``year`` (integer), ``dta_path`` (character),
    and ``do.path``(character).
    """
