"""Tests for Config module."""

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
