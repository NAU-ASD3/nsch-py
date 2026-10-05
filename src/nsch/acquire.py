"""Functions for the acquire layer"""

from __future__ import annotations

import re
import tempfile
import zipfile
from pathlib import Path

import httpx
import polars as pl

__all__ = ["get_all_years", "get_nsch_index", "get_year"]

NSCH_URL_PREFIX = "https://www.census.gov/programs-surveys/nsch/data/datasets."
NSCH_DATA_URL = NSCH_URL_PREFIX + "html"


def get_nsch_index(local_html_path: Path | None = None) -> pl.DataFrame:
    """
    Download and parse the NSCH index web page to obtain a list of years for which
    survey data are available. We can then do a loop over years, to download data
    from each available year.

    Parameters
    ----------
    local_html_path: Path
        Local file in which HTML will be downloaded, if it does not already exist.

    Returns
    -------
    A ``pl.DataFrame`` containing one row per year of data, and columns ``url``, ``year``.
    """
    # If no file path is passed for caching, create a temp file
    if local_html_path is None:
        local_html_path = Path(tempfile.mkdtemp()) / "nsch_index.html"

    local_html_path = Path(local_html_path)
    if not local_html_path.exists():
        # create empty parent directories if they don't exist
        local_html_path.parent.mkdir(parents=True, exist_ok=True)
        response = httpx.get(NSCH_DATA_URL, timeout=30, follow_redirects=True)
        response.raise_for_status()
        local_html_path.write_bytes(response.content)

    # Get text of html paths on the index page
    html_text = local_html_path.read_text(encoding="utf-8").splitlines()
    # Get html strings with each year, escape special characters
    # name url with group and "url" and, if present, name found digits with the group "year"
    url_pattern = r"(?P<url>" + re.escape(NSCH_URL_PREFIX) + r"(?P<year>[0-9]+)\.html)"

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


def get_year(
    year_url: str, data_path: Path = Path("NSCH_data/00_original_Stata"), verbose: bool = False
) -> Path:
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
    A ``Path`` to the resulting download
    """
    # don't need to check if year_url is string, python will pass objects and mypy handles typing
    # same for data_path and verbose
    data_path = Path(data_path)
    Path(data_path).mkdir(parents=True, exist_ok=True)

    year_html = Path(year_url).name
    data_path_year_html = Path(data_path) / year_html
    if not data_path_year_html.exists():
        if verbose:
            print(f"Downloading {year_url} -> {data_path}")
        # download the year-specific html page
        response = httpx.get(year_url, timeout=30, follow_redirects=True)
        response.raise_for_status()
        data_path_year_html.write_bytes(response.content)
    lines = data_path_year_html.read_text(encoding="utf-8").splitlines()
    # Make sure URLS on the same line are split
    text = "\n".join(lines)

    # match protocol-relative "//...topical_Stata.zip"
    pattern = r"(?:https?:)?//[^\s\"'<>]*?topical_Stata\.zip"
    matches = re.findall(pattern, text)

    if len(matches) != 1:
        raise ValueError(f"Expected 1 topical_Stata.zip url on {year_url} but found {len(matches)}")

    raw_url = matches[0]
    http_url = raw_url if raw_url.startswith("http") else "https:" + raw_url

    year_zip = http_url.split("/")[-1]
    data_path_year_zip = data_path / year_zip

    if not data_path_year_zip.exists():
        response = httpx.get(http_url, timeout=30, follow_redirects=True)
        response.raise_for_status()
        data_path_year_zip.write_bytes(response.content)

    # unzip the downloaded zip file into the data_path directory
    with zipfile.ZipFile(data_path_year_zip, "r") as zip_ref:
        zip_ref.extractall(data_path)

    # Return zip file path like the R function
    return Path(data_path_year_zip)


def get_all_years(
    data_path: Path, years: list[int] | None = None, download: bool = False
) -> pl.DataFrame:
    """Discover NSCH data files for all available years

    Finds ``.dta`` and ``.do`` files in a data directory using glob
    patterns, returning a ``pl.DataFrame`` mapping each year to its
    file paths. Handles non-standard filenames such as "nsch_2024e_topical.dta".
    Optionally downloads data first via ``get_year``.

    Parameters
    ----------
    data_path: Path
        Directory containing NSCH ``.dta`` and ``.do`` files.
    years: list[int]
        Optional integer list of years to include.
        If ``None``, all discovered years are returned.
    download: bool
        If ``True``, downloads data via ``get_year`` before discovering files.


    Returns
    -------
    A ``pl.DataFrame`` with columns ``year`` (integer), ``dta_path`` (character),
    and ``do_path``(character).
    """
    if download:
        # Get list of files from index
        index_df = get_nsch_index()
        if years is not None and len(years) > 0:
            index_df = index_df.filter(pl.col("year").is_in(years))
        # use get_year to download each file from the webpage
        for i in range(0, index_df.height):
            get_year(index_df["url"][i], data_path=data_path)

    # Discover .dta and .do files, glob handles 2024's nsch_2024e_topical.dta.
    df_dict = {}
    for suffix in ["dta", "do"]:
        files = list(Path(data_path).glob(f"*topical*.{suffix}"))
        if len(files) == 0:
            raise ValueError(f"No .{suffix} files found in data path: {data_path}")

        # Extract the 4-digit year from each filename.
        # Raises ValueError if no year found (match is None)
        file_years = []
        for f in files:
            match = re.search(r"[0-9]{4}", f.name)
            if match is None:
                raise ValueError(f"Could not extract a 4-digit year from filename: {f.name}")
            file_years.append(int(match.group()))
        # Throw a helpful error if there are same-year collisions rather than a raw polars
        # 1:1 error in the join below
        if len(file_years) != len(set(file_years)):
            dupes = sorted({y for y in file_years if file_years.count(y) > 1})
            raise ValueError(f"Multiple .{suffix} files found for year(s): {dupes}")
        col_name = f"{suffix}_path"
        df_dict[suffix] = pl.DataFrame({"year": file_years, col_name: [str(f) for f in files]})

    joined_dta_do = (
        df_dict["dta"]
        .join(df_dict["do"], on="year", how="full", coalesce=True, validate="1:1")
        .sort("year")
    )

    # Make sure we have .do files for every .dta and vice versa
    missing = joined_dta_do.filter(pl.col("dta_path").is_null() | pl.col("do_path").is_null())
    if missing.height > 0:
        raise ValueError(f"Mismatched .dta/.do files for years: {missing['year'].to_list()}")
    if years is not None:
        years_int = [int(y) for y in years]
        joined_dta_do = joined_dta_do.filter(pl.col("year").is_in(years_int))
    if joined_dta_do.height == 0:
        raise ValueError(r"No matching .dta files found for the requested years")

    return joined_dta_do
