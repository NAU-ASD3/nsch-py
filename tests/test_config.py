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
    config_data = make_valid_config()
    config_data["desired_variables"] = []
    with pytest.raises(ValueError, match="desired_variables"):
        Config.model_validate(config_data)


def test_non_character_desired_variables_raises_error() -> None:
    config_data = make_valid_config()
    config_data["desired_variables"] = [1, 2, 3, 4, 5]
    with pytest.raises(ValueError, match="desired_variables"):
        Config.model_validate(config_data)


def test_mismatched_transform_vector_lengths_raises_error() -> None:
    config_data = make_valid_config()
    config_data["transformations"]["transform"]["bad_var"] = {
        "years": ["2016"],
        "value": ["1", "2"],
        "new_value": ["1"],
        "new_label": ["A", "B"],
    }
    with pytest.raises(ValueError, match="length"):
        Config.model_validate(config_data)


def test_missing_rename_columns_new_name_raises_error() -> None:
    config_data = make_valid_config()
    config_data["transformations"]["rename_columns"]["bad_rename"] = {
        "years": ["2016"],
        # new_name is missing
    }
    with pytest.raises(ValueError, match="new_name"):
        Config.model_validate(config_data)


def test_missing_merge_columns_fields_raise_error() -> None:
    config_data = make_valid_config()
    config_data["transformations"]["merge_columns"]["bad_merge"] = {
        "years": ["2016"],
        "column_preferred": "a",
        # column_fallback is missing
    }
    with pytest.raises(ValueError, match="column_fallback"):
        Config.model_validate(config_data)
