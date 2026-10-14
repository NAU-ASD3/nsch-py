"""Functions for the harmonize module"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import polars as pl

from nsch._types import TaggedNA
from nsch.combine import apply_do_labels

if TYPE_CHECKING:
    from nsch.config import Config, MergeRule, RenameRule, TransformRule

__all__ = [
    "harmonize_year",
    "merge_vars",
    "rename_vars",
    "subset_vars",
    "transform_values",
]


def rename_vars(lf: pl.LazyFrame, renames: dict[str, RenameRule], year: int) -> pl.LazyFrame:
    """Rename columns for one survey year according to the rename rules.

    Applies the rename rules for one survey year, turning that
    year's source column names into the harmonized names the rest of the pipeline
    expects. It stays lazy: a LazyFrame goes in and a LazyFrame comes out, with no
    collection. When a column is renamed, its ``_label`` companion is renamed to
    match, so the value column and its human-readable labels stay paired.

    Parameters
    ----------
    lf : pl.LazyFrame
        One year's data, before renaming.
    renames : dict[str, RenameRule]
        Maps a source column name to its rule. A rule applies only when ``year``
        is in the rule's ``years``.
    year : int
        The survey year ``lf`` holds. Compared against each rule's ``years``,
        which the config stores as strings.

    Returns
    -------
    pl.LazyFrame
        The frame with matching columns renamed, each column's ``_label``
        companion renamed alongside it. Columns with no applicable rule, and
        rules naming a column that isn't present, are left alone.

    Raises
    ------
    ValueError
        If two rules rename different columns to the same name, or if a rule
        renames a column onto the name of one that already exists and isn't
        itself being renamed. Both point at a malformed config.

    Notes
    -----
    Renames are applied all at once rather than one after another. The R
    version loops and renames in place, so a pair of rules like ``a -> b`` and
    ``b -> c`` cascades there and ``a`` ends up as ``c``. Here both rules read
    the original column names, so ``a`` becomes ``b`` and the original ``b``
    becomes ``c``. Reading from the original names is the intended behavior: a
    rule should describe the column it names in the source data, not whatever
    an earlier rule happened to leave behind.

    Examples
    --------
    >>> import polars as pl
    >>> from nsch.config import RenameRule
    >>> lf = pl.LazyFrame({"gowhensick": [4, 8]})
    >>> rule = {"gowhensick": RenameRule(years=["2023"], new_name="k4q02_r")}
    >>> rename_vars(lf, rule, 2023).collect().columns
    ['k4q02_r']
    """
    # A LazyFrame has no cheap `.columns`; ask the schema for the names.
    present = set(lf.collect_schema().names())
    # The config stores years as strings; `year` arrives as an int.
    year_str = str(year)
    mapping: dict[str, str] = {}
    for old, rule in renames.items():
        if year_str not in rule.years or old not in present:
            continue
        new_name = rule.new_name
        mapping[old] = new_name
        # A column's labels live in `<name>_label`; rename them together.
        old_label = f"{old}_label"
        if old_label in present:
            mapping[old_label] = f"{new_name}_label"

    # Two rules pointing at the same name would silently collapse two columns
    # into one, so catch it here where we can name the year and the columns.
    seen: set[str] = set()
    duplicates: set[str] = set()
    for target in mapping.values():
        if target in seen:
            duplicates.add(target)
        seen.add(target)
    if duplicates:
        raise ValueError(
            f"Rename rules for {year} map more than one column to: {', '.join(sorted(duplicates))}"
        )

    # Renaming onto a column that already exists and isn't itself being renamed
    # collides. Polars raises for this, but without saying which year or rule
    # caused it.
    collisions = sorted(set(mapping.values()) & (present - set(mapping)))
    if collisions:
        raise ValueError(
            f"Rename rules for {year} target existing columns that are not "
            f"themselves renamed: {', '.join(collisions)}"
        )

    return lf.rename(mapping)


def transform_values(
    lf: pl.LazyFrame, transforms: dict[str, TransformRule], year: int
) -> pl.LazyFrame:
    """Apply value and label remapping rules to transform a single year's raw numeric pl.LazyFrame.

    ``transform_values`` applies value and label remapping rules to a single year's
    raw numeric ``pl.LazyFrame`` and returns a new (lazy) frame with values
    transformed. For each variable in ``transforms`` whose ``years`` vector includes
    ``str(year)`` it iterates over the paired ``value``/ ``new_value``/``new_label``
    entries and replaces each matching numeric value with its new value. It creates
    or updates the corresponding ``_label`` column with the ``new_label`` text for
    remapped rows and silently skips variables not present in the input ``pl.LazyFrame``.

    Parameters
    ----------
    lf : pl.LazyFrame
        One year's data before transforming.
    transforms : dict[str, TransformRule]
        Maps a source column name to its transform. A transform only applies when ``year``
        is in the transform's ``years``.
    year : int
        The survey year held by ``lf``. Compared against each transform's ``years``,
        which the config stores as strings.

    Returns
    -------
    pl.LazyFrame
        The frame with matching columns transformed and each column's ``_label``
        companion added or updated. Columns with no applicable transform, or not
        present in ``transforms``, are left alone.

    Examples
    --------
    >>> import polars as pl
    >>> from nsch.config import TransformRule
    >>> lf = pl.LazyFrame({"sex": [1, 2, 1]})
    >>> transforms = {
    ...     "sex": TransformRule.model_validate(
    ...         {
    ...             "years": ["2016"],
    ...             "value": ["1", "2"],
    ...             "new_value": ["1", "2"],
    ...             "new_label": ["Male", "Female"],
    ...         }
    ...     )
    ... }
    >>> transform_values(lf, transforms, 2016).collect()
    shape: (3, 2)
    ┌─────┬───────────┐
    │ sex ┆ sex_label │
    │ --- ┆ ---       │
    │ i64 ┆ str       │
    ╞═════╪═══════════╡
    │ 1   ┆ Male      │
    │ 2   ┆ Female    │
    │ 1   ┆ Male      │
    └─────┴───────────┘
    """
    transformed_lf = lf
    schema = transformed_lf.collect_schema()
    variable_names = set(schema.names())

    for transform_variable_name, details in transforms.items():
        transform_years = details.years
        if (transform_variable_name in variable_names) and (str(year) in transform_years):
            # Get column datatype for converting transform's string values
            column_dtype = schema[transform_variable_name]
            label_col = str(transform_variable_name) + "_label"

            if label_col not in variable_names:
                transformed_lf = transformed_lf.with_columns(
                    pl.lit(None, dtype=pl.Utf8).alias(label_col)
                )
                # Variable_names is a set, use .add instead of .append
                variable_names.add(label_col)

            # Create a mapping between values and new values/labels for the transform
            lookup = pl.DataFrame(
                {
                    transform_variable_name: pl.Series(details.value).cast(column_dtype),
                    "_new_value": pl.Series(details.new_value).cast(column_dtype),
                    "_new_label": details.new_label,
                }
            ).lazy()
            # if the number of values in the transform is not unique,
            # raise an error to protect against duplicate rows from a bad config
            if lookup.select(pl.col(transform_variable_name)).collect().n_unique() != len(
                details.value
            ):
                raise ValueError(
                    f"Duplicate values found in transform for variable {transform_variable_name}"
                )

            transformed_lf = (
                transformed_lf.join(
                    lookup, on=transform_variable_name, how="left", maintain_order="left"
                )
                .with_columns(
                    [
                        pl.coalesce(["_new_value", pl.col(transform_variable_name)]).alias(
                            transform_variable_name
                        ),
                        pl.coalesce(["_new_label", pl.col(label_col)]).alias(label_col),
                    ]
                )
                .drop("_new_value", "_new_label")
            )

    return transformed_lf


def subset_vars(lf: pl.LazyFrame, desired_variables: list[str]) -> pl.LazyFrame:
    """Select desired variables and their label companions.

    Returns a new ``pl.LazyFrame`` containing only the columns listed
    in ``desired_variables``, plus any corresponding ``_label``
    companion columns that exist.  Issues a ``warning`` for each
    variable in ``desired_variables`` not found in ``lf`` which is
    expected when a variable does not exist in a particular year.

    Parameters
    ----------
    lf : pl.LazyFrame
        A Polars LazyFrame to select desired variable from
    desired_variables : list[str]
        A list of desired variable column names, as strings

    Returns
    -------
    pl.LazyFrame
        Only the variables in ``desired_variables`` that are present, plus
        their ``_label`` columns.

    Examples
    --------
    >>> import polars as pl
    >>> lf = pl.LazyFrame(
    ...     {"a": [1, 2, 3], "a_label": ["x", "y", "z"], "b": [4, 5, 6], "c": [7, 8, 9]}
    ... )
    >>> subset_vars(lf, ["a", "c"]).collect()
    shape: (3, 3)
    ┌─────┬─────┬─────────┐
    │ a   ┆ c   ┆ a_label │
    │ --- ┆ --- ┆ ---     │
    │ i64 ┆ i64 ┆ str     │
    ╞═════╪═════╪═════════╡
    │ 1   ┆ 7   ┆ x       │
    │ 2   ┆ 8   ┆ y       │
    │ 3   ┆ 9   ┆ z       │
    └─────┴─────┴─────────┘
    """
    lf_variables = lf.collect_schema().names()
    # Warn for each desired variable not found in df.
    missing = [c for c in desired_variables if c not in lf_variables]
    for m in missing:
        warnings.warn(UserWarning(f"Desired variable {m} not found in lf"), stacklevel=2)

    # Collect the data columns plus any _label companions.
    present = [c for c in desired_variables if c in lf_variables]
    label_cols = [l_col + "_label" for l_col in present]
    label_cols = [l_col for l_col in label_cols if l_col in lf_variables]
    keep = present + label_cols
    return lf.select(keep)


def merge_vars(lf: pl.LazyFrame, merges: dict[str, MergeRule], year: int) -> pl.LazyFrame:
    """Merge preferred and fallback columns for a survey year.

    The preferred column is normally used. The fallback column is used when
    the preferred value is null or contains the logical skip sentinel, 998.

    If both corresponding ``_label`` columns exist, they are merged using
    the same preferred-versus-fallback condition.

    Original value and label columns are removed after merging.

    Parameters
    ----------
    lf : pl.LazyFrame
        A polars LazyFrame with the columns to merge.
    merges : dict[str, MergeRule]
        The config's ``merge_columns`` rules, keyed by the merged column's
        name. Each rule names the preferred and fallback columns and the
        years it applies to.
    year : int
        The year of data on which to perform the merge.

    Returns
    -------
    pl.LazyFrame
        The merged column and its ``_label`` column (if present), plus all
        untouched columns. The preferred and fallback columns are removed.

    Examples
    --------
    >>> import polars as pl
    >>> from nsch.config import MergeRule
    >>> lf = pl.LazyFrame(
    ...     {"hoursleep": [1, 2, 3, 4], "hoursleep05": [None, None, 3, 4], "hhid": [5, 6, 7, 8]}
    ... )
    >>> merges = {
    ...     "sleep": MergeRule(
    ...         years=["2023"], column_preferred="hoursleep", column_fallback="hoursleep05"
    ...     )
    ... }
    >>> merge_vars(lf, merges, 2023).collect()
    shape: (4, 2)
    ┌──────┬───────┐
    │ hhid ┆ sleep │
    │ ---  ┆ ---   │
    │ i64  ┆ i64   │
    ╞══════╪═══════╡
    │ 5    ┆ 1     │
    │ 6    ┆ 2     │
    │ 7    ┆ 3     │
    │ 8    ┆ 4     │
    └──────┴───────┘
    """

    merged_lf = lf
    schema = merged_lf.collect_schema()
    variable_names = set(schema.names())

    for merged_variable_name, details in merges.items():
        column_preferred = details.column_preferred
        column_fallback = details.column_fallback
        merge_years = details.years

        if (
            str(year) in merge_years
            and column_preferred in variable_names
            and column_fallback in variable_names
        ):
            preferred_values = pl.col(column_preferred)
            fallback_values = pl.col(column_fallback)

            use_fallback = (preferred_values.is_null()) | (
                preferred_values == TaggedNA.LOGICAL_SKIP
            )

            # No cast to column type or int, polars will infer the type (divergence from R)
            # protects against mismatching types in columns to merge
            merged_lf = merged_lf.with_columns(
                pl.when(use_fallback)
                .then(fallback_values)
                .otherwise(preferred_values)
                .alias(merged_variable_name)
            )

            label_preferred = column_preferred + "_label"
            label_fallback = column_fallback + "_label"
            label_column = merged_variable_name + "_label"

            if label_preferred in variable_names and label_fallback in variable_names:
                merged_lf = merged_lf.with_columns(
                    pl.when(use_fallback)
                    .then(pl.col(label_fallback))
                    .otherwise(pl.col(label_preferred))
                    .alias(label_column),
                )

            merged_lf = merged_lf.drop(
                column_fallback,
                column_preferred,
                label_fallback,
                label_preferred,
                strict=False,
            )

    return merged_lf


def _build_alias_map(
    renames: dict[str, RenameRule],
    merges: dict[str, MergeRule],
    year: int,
    columns: list[str],
) -> dict[str, str]:
    """Map post-rename and merge-output column names back to their .do names.

    ``apply_do_labels`` looks up labels by column name, but by the time it
    runs, renamed columns carry names the .do file never defined, and merge
    outputs are brand new. This map tells it where to look instead: a
    renamed column is labeled from its pre-rename define entries, and a
    merge output from its ``column_preferred`` source.

    Parameters
    ----------
    renames : dict[str, RenameRule]
        The config's ``rename_columns`` rules.
    merges : dict[str, MergeRule]
        The config's ``merge_columns`` rules.
    year : int
        The survey year; only rules listing it are considered.
    columns : list[str]
        The frame's column names before ``rename_vars`` runs.

    Returns
    -------
    dict[str, str]
        Output column name mapped to the .do variable to label it from.

    Notes
    -----
    An entry is added only for a rule that actually fires on this frame:
    a rename whose old column is present, and a merge whose two sources
    are present after the renames, matching the conditions in
    ``rename_vars`` and ``merge_vars``. A rule whose year list includes a
    year where its column already carries the new name therefore adds
    nothing, and the column is labeled under its own name. R's
    ``build_alias_map`` adds an entry for every rule listing the year and
    reaches the same labels through a fallback inside ``apply_do_labels``
    (R #52).

    When a merge's ``column_preferred`` was produced by a rename that fired,
    the merge output's entry follows the rename back to the original .do
    name. R stops at the new name and leaves that column unlabeled; the
    bundled config has no merge on a renamed column, so the two agree on
    every real year.

    Only the preferred source's define entries label a merge output. Labels
    from the fallback source survive only when a transform rule wrote them
    and both sources have a ``_label`` column, which ``merge_vars`` then
    merges alongside the data. If a rename and a merge produce the same
    output name, the merge entry wins, matching R's assignment order.
    """
    year_str = str(year)
    present = set(columns)
    renamed: dict[str, str] = {}
    for old_name, rename in renames.items():
        if year_str in rename.years and old_name in present:
            renamed[rename.new_name] = old_name
    # merge_vars sees the names after the renames.
    after_rename = (present - set(renamed.values())) | set(renamed)
    alias = dict(renamed)
    for out_name, merge in merges.items():
        sources_present = {merge.column_preferred, merge.column_fallback} <= after_rename
        if year_str in merge.years and sources_present:
            alias[out_name] = renamed.get(merge.column_preferred, merge.column_preferred)
    return alias


def harmonize_year(
    lf: pl.LazyFrame, config: Config, year: int, define_lf: pl.LazyFrame
) -> pl.LazyFrame:
    """Run one survey year through the full harmonization sequence.

    Applies, in order: ``transform_values``, ``rename_vars``,
    ``merge_vars``, ``subset_vars``, then ``apply_do_labels`` with an alias
    map so renamed and merged columns are labeled from the .do entries of
    their original source variables. Mirrors R's ``harmonize_year``, with
    the two differences listed under Notes.

    Parameters
    ----------
    lf : pl.LazyFrame
        One year's data as read by ``read_nsch_dta``.
    config : Config
        The validated configuration from ``read_config``.
    year : int
        The survey year of ``lf``; selects which rules apply.
    define_lf : pl.LazyFrame
        The ``define`` frame of that year's ``DoSpec`` from ``parse_do``.

    Returns
    -------
    pl.LazyFrame
        The harmonized, labeled year, restricted to ``desired_variables``.

    Raises
    ------
    ValueError
        From ``transform_values`` when a rule lists a value twice, and from
        ``rename_vars`` when two rules target one name or a target collides
        with an existing column.

    Warns
    -----
    UserWarning
        From ``subset_vars`` for each desired variable missing from the frame.

    Notes
    -----
    Two differences from R, both in how the alias map is built (see
    ``_build_alias_map``). Aliases come only from rules that fire on this
    frame, so a rule whose year list overshoots leaves the natively named
    column labeled under its own name; R gets the same result from a
    fallback in its ``apply_do_labels``. And a merge whose preferred source
    was renamed that year is labeled from the pre-rename name, where R
    leaves it unlabeled. The bundled config never hits the second case.

    Examples
    --------
    >>> import polars as pl
    >>> from nsch.config import Config
    >>> lf = pl.LazyFrame({"year": [2099, 2099], "fam_count": [1, 3]})
    >>> config = Config.model_validate(
    ...     {
    ...         "desired_variables": ["family"],
    ...         "transformations": {
    ...             "transform": {},
    ...             "rename_columns": {"fam_count": {"years": ["2099"], "new_name": "family"}},
    ...             "merge_columns": {},
    ...         },
    ...     }
    ... )
    >>> define_lf = pl.LazyFrame(
    ...     {
    ...         "variable": ["fam_count"] * 3,
    ...         "value": ["1", "2", "3"],
    ...         "desc": ["One", "Two", "Three"],
    ...     }
    ... )
    >>> harmonize_year(lf, config, 2099, define_lf).collect()
    shape: (2, 1)
    ┌────────┐
    │ family │
    │ ---    │
    │ enum   │
    ╞════════╡
    │ One    │
    │ Three  │
    └────────┘
    """
    rules = config.transformations
    lf = transform_values(lf, rules.transform, year)
    # The alias map needs the names before renaming to know which rules fire.
    columns = lf.collect_schema().names()
    lf = rename_vars(lf, rules.rename_columns, year)
    lf = merge_vars(lf, rules.merge_columns, year)
    lf = subset_vars(lf, config.desired_variables)
    alias = _build_alias_map(rules.rename_columns, rules.merge_columns, year, columns)
    return apply_do_labels(lf, define_lf, alias)
