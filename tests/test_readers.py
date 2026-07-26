"""Tests for the readers module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nsch.readers import parse_do

if TYPE_CHECKING:
    from pathlib import Path


def test_parse_do_raises_error_for_missing_file(tmp_path: Path) -> None:
    """Raise an informative error when the Stata do-file does not exist."""
    missing_file = tmp_path / "missing.do"

    with pytest.raises(
        FileNotFoundError,
        match="year.do.path should be the path to a Stata do file",
    ):
        parse_do(missing_file)
