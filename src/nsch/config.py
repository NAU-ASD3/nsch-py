"""Configuration models and loading functions for the NSCH pipeline"""

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
        """Validate that paired transformation arrays have equal lenghts"""

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
