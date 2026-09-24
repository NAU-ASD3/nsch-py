"""Configuration models and loading functions for the NSCH pipeline"""

from pydantic import BaseModel


class TransformRule(BaseModel):
    """Configuration for transforming a varianble."""

    years: list[str]
    value: list[str]
    new_value: list[str]
    new_label: list[str]


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

    desired_variables: list[str]
    transformations: Transformations
