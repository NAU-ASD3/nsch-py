"""Configuration models and loading functions for the NSCH pipeline"""

import importlib.resources
import json
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field, model_validator


class TransformRule(BaseModel):
    """Configuration for transforming a varianble."""

    years: list[str]
    value: list[str]
    new_value: list[str]
    new_label: list[str]

    @model_validator(mode="after")
    def validate_paired_lengths(self) -> Self:
        """Validate that paired transformation arrays have equal lengths.

        Returns
        -------
        Self
            The validated transformation rule.

        Raises
        ------
        ValueError
            If value, new_value, and new_label have different lengths.
        """

        lengths = {
            "value": len(self.value),
            "new_value": len(self.new_value),
            "new_label": len(self.new_label),
        }

        if len(set(lengths.values())) != 1:
            length_details = ", ".join(f"{name}={length}" for name, length in lengths.items())
            raise ValueError(f"mismatched length: {length_details}")

        return self


class RenameRule(BaseModel):
    """Configuration for renaming a variable"""

    years: list[str]
    new_name: str


class MergeRule(BaseModel):
    """Configuration for merging variables"""

    years: list[str]
    column_preferred: str
    column_fallback: str


class Transformations(BaseModel):
    """Configuration for variable transformation"""

    transform: dict[str, TransformRule]
    rename_columns: dict[str, RenameRule]
    merge_columns: dict[str, MergeRule]


class Config(BaseModel):
    """Configuration for NSCH pipeline"""

    desired_variables: list[str] = Field(min_length=1)
    transformations: Transformations


def read_config(path: Path | str | None = None) -> Config:
    """Read and validate an NSCH JSON configuration file.

    Parameters
    ----------
    path
        Path to the JSON configuration file. If None, the bundled configuration file is used.

    Returns
    -------
    Config
        The validated NSCH configuration.

    Raises
    ------
    ValueError
        If the file does not exist or does not contain valid JSON.
    """
    if path is None:
        config_path = importlib.resources.files("nsch.data").joinpath("variable-config.json")
    else:
        config_path = Path(path)
        if not config_path.exists():
            raise ValueError(
                "config_path should be the path to a JSON config file, "
                f"but this file does not exist: {config_path}"
            )

    try:
        config_data = json.loads(config_path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"config_path should contain valid JSON, but parsing failed: {e}") from e

    return Config.model_validate(config_data)
