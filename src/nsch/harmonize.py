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

    # Alter to vectors for polars style, create a map and use .replace()
    transformed_lf = lf  # Is this valid for the idea of not mutating in place?
    # Useful for leaving unchanged columns
    # Get lf column names (variable names)
    variable_names = lf.collect_schema().names()
    # loop through transform keys and grab inner dicts
    for transform_variable_name in transforms:
        # if label in lf names and year in dict's year list
        details = transforms[transform_variable_name]
        transform_years = list(details["years"])
        if (transform_variable_name in variable_names) & (str(year) in transform_years):
            # access dictionary at that label
            # create map of old values to new values
            value_map = {details["value"]: details["new_value"]}
            label_map = {details["value"]: details["new_label"]}
            print(label_map)
            label_col = str(transform_variable_name) + "_label"
            if (label_col) not in variable_names:
                transformed_lf = transformed_lf.with_columns(
                    pl.lit(None, dtype=pl.Utf8).alias(label_col)
                )
                # Add new label column to be found in variable_names for next iteration
                variable_names.append(label_col)
            # Modify label column or (Later test) add then modify
            # modify whole column as a vector using the remap and add to return lf
            transformed_lf = transformed_lf.with_columns(
                pl.col(label_col).replace(label_map).alias(label_col),
                pl.col(transform_variable_name).replace(value_map).alias(transform_variable_name),
            )
        # else, leave column unchanged in return lf
    return transformed_lf
