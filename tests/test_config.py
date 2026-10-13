"""Tests for Config module."""

from pathlib import Path

import pytest

from nsch.config import Config, read_config


def make_valid_config() -> dict[str, object]:
    """Create a minimal valid configuration for testing."""
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
    """Validate that a valid configuration passes validation."""
    config_data = make_valid_config()
    config = Config.model_validate(config_data)

    assert isinstance(config, Config)


def test_empty_desired_variables_raises_error() -> None:
    """Raise an error for an empty desired_variables list."""
    config_data = make_valid_config()
    config_data["desired_variables"] = []
    with pytest.raises(ValueError, match="desired_variables"):
        Config.model_validate(config_data)


def test_non_character_desired_variables_raises_error() -> None:
    """Raise an error for non-string values in desired_variables."""
    config_data = make_valid_config()
    config_data["desired_variables"] = [1, 2, 3, 4, 5]
    with pytest.raises(ValueError, match="desired_variables"):
        Config.model_validate(config_data)


def test_mismatched_transform_vector_lengths_raises_error() -> None:
    """Raise an error for mismatched transform vector lengths."""
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
    """Raise an error when a rename rule is missing new_name."""
    config_data = make_valid_config()
    config_data["transformations"]["rename_columns"]["bad_rename"] = {
        "years": ["2016"],
        # new_name is missing
    }
    with pytest.raises(ValueError, match="new_name"):
        Config.model_validate(config_data)


def test_missing_merge_columns_fields_raise_error() -> None:
    """Raise an error when a merge rule is missing a required field."""
    config_data = make_valid_config()
    config_data["transformations"]["merge_columns"]["bad_merge"] = {
        "years": ["2016"],
        "column_preferred": "a",
        # column_fallback is missing
    }
    with pytest.raises(ValueError, match="column_fallback"):
        Config.model_validate(config_data)


def test_error_for_non_existent_file(tmp_path: Path) -> None:
    """Raise an informative error when the config file does not exist."""
    does_not_exist = tmp_path / "does_not_exist.json"
    with pytest.raises(
        FileNotFoundError, match="config_path should be the path to a JSON config file"
    ):
        read_config(does_not_exist)


def test_error_for_malformed_json(tmp_path: Path) -> None:
    """Raise an informative error for malformed JSON."""
    bad_json = tmp_path / "bad_json.json"
    bad_json.write_text("{ not valid json !!!}")
    with pytest.raises(ValueError, match="config_path should contain valid JSON"):
        read_config(bad_json)


def test_bundled_config_passes_validation() -> None:
    """Validate the bundled configuration successfully."""
    config = read_config()

    assert isinstance(config, Config)


def test_missing_transformation_sections_default_to_empty() -> None:
    """Default missing transformation sections to empty dictionaries."""
    config_data = {
        "desired_variables": ["year"],
        "transformations": {},
    }
    config = Config.model_validate(config_data)

    assert config.transformations.transform == {}
    assert config.transformations.rename_columns == {}
    assert config.transformations.merge_columns == {}
