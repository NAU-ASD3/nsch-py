"""Top-level orchestration of the NSCH cleaning pipeline."""

import logging
from pathlib import Path

import polars as pl

from nsch.acquire import get_all_years
from nsch.combine import combine_years
from nsch.config import read_config
from nsch.harmonize import harmonize_year
from nsch.impute import impute_a1_grade_2016
from nsch.readers import parse_do, read_nsch_dta

__all__ = ["get_clean_data"]

logger = logging.getLogger(__name__)


def get_clean_data(
    config_path: Path | str | None = None,
    data_path: Path = Path("NSCH_data/00_original_Stata"),
    years: list[int] | None = None,
    download: bool = False,
    impute_2016: bool = True,
    seed: int = 1,
) -> pl.DataFrame:
    """Load, harmonize, and combine NSCH survey data.

    Parameters
    ----------
    config_path : Path | str | None
        JSON configuration path. If None, use the bundled configuration.
    data_path : Path
        Directory containing the survey .dta and .do files.
    years : list[int] | None
        Survey years to include. If None, include all discovered years.
    download : bool
        Download survey files before discovering them.
    impute_2016 : bool
        Apply the 2016 adult education imputation when 2016 is present.
    seed : int
        Random seed for the 2016 imputation. Defaults to 1.

    Returns
    -------
    pl.DataFrame
        Combined, harmonized survey data, optionally imputed for 2016.

    Notes
    -----
    Mirrors R's get_clean_data. Per-year processing remains lazy until
    combine_years collects the combined result.
    """

    config = read_config(config_path)
    files = get_all_years(
        data_path=data_path,
        years=years,
        download=download,
    )

    year_frames: list[pl.LazyFrame] = []
    for row in files.iter_rows(named=True):
        year = row["year"]
        logger.info("Processing year %s", year)
        data = read_nsch_dta(Path(row["dta_path"]))
        do_spec = parse_do(Path(row["do_path"]))
        harmonized = harmonize_year(data, config, year, do_spec.define)
        year_frames.append(harmonized)

    combined = combine_years(year_frames)

    if impute_2016 and 2016 in combined["year"].to_list():
        dta_2016_path = Path(files.filter(pl.col("year") == 2016)["dta_path"].item())
        combined = impute_a1_grade_2016(
            combined,
            dta_2016_path,
            seed=seed,
        )

    return combined
