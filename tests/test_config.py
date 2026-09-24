"""Tests for Config module."""

import pytest

from nsch.config import Config


def make_valid_config() -> dict[str, object]:
    return {
        "desired_variables": ["year", "sc_sex"],
        "transformations": {
            "transform": {
                "sc_sex": {
                    "years": ["2016"],
                    "value": ["1"],
                    "new_value": ["1"],
                    "new_label": ["Male"],
                }
            },
            "rename_columns": {
                "old_col": {
                    "years": ["2016"],
                    "new_name": "new_col",
                }
            },
            "merge_columns": {
                "merged": {
                    "years": ["2016"],
                    "column_preferred": "col_a",
                    "column_fallback": "col_b",
                }
            },
        },
    }


def test_valid_config_passes_validation() -> None:
    config_data = make_valid_config()
    config = Config.model_validate(config_data)

    assert isinstance(config, Config)


def test_empty_desired_variables_raises_error() -> None:
    Config_data = make_valid_config()
    Config_data["desired_variables"] = []
    with pytest.raises(ValueError, match="desired_variables"):
        Config.model_validate(Config_data)
