"""Remap answer codes per year for harmonize module

``transform_values`` applies value and label remapping rules to a single year's
raw numeric ``pl.LazyFrame``, modifying it by reference. For each variable in
``transforms`` whose ``years`` vector includes ``chr(year)` it iterates over
the paired ``value``/ ``new_value``/``new_label`` entries and replaces each
matching numeric value with its new value.

Creates or updates the corresponding ``_label`` column with the ``new_label``
text for remapped rows.

Silently skips variables not present in the input ``pl.LazyFrame``





"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import polars as pl

# Transforms are a named list of lists, treating name and inner lists as keys
# R treats everything, including years and numeric values, as strings
# likely a nested dictionary of strings

# Returns transformed as a new pl.LazyFrame (Because R returns invisibly)


def transform_values(
    lf: pl.LazyFrame, transforms: dict[str, dict[str, str]], year: int
) -> pl.LazyFrame:
    # for each label in transforms (variable name)
    # get the details (years, value, new_value, new_label)
    # if str(year) is in details' year list and the label (variable name)
    # is in the lazyframe, add "variable name_label" to the lf label column
    # if it already exists. If not, check and add
    # Get old and new values as numerics into their own variables
    # match up where, in the lf at the variable, the old values are
    # if there are matches, set the value at the matched index (i) at variable
    # name (j) to the new value at the corresponding index
    # also set value at matched index (i) in label column (j) to the new label
    # set is like a mutate+filter done on r invisible() frame functions (lazy version)
    raise NotImplementedError
