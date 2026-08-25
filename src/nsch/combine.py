"""Functions for the combine module"""

from __future__ import annotations

import polars as pl

from nsch._types import STATA_TAG_TO_SENTINEL, TaggedNA

__all__ = ["apply_do_labels"]


def _scan_override_labels(
    lf: pl.LazyFrame, label_cols: list[tuple[str, str | None, dict[float, str]]]
) -> dict[str, set[str]]:
    """Helper function for ``apply_do_labels`` that scans the ``lf`` for override label values
    present in each ``_label`` column. A label introduced only from the override rather than from
    the ``.do`` file will map to a valid ``pl.Enum`` category.

    Parameters
    ----------
    lf : pl.LazyFrame
        The frame of raw numeric survey data ingested by ``apply_do_labels``.

    label_cols : list[tuple[str, str|None, dict[float, str]]]
        A mapping between the column name, label name, and lookup label name
        created within ``apply_do_labels``

    Returns
    -------
    A dict[str, set[str]] containing the set of labels associated with an
    override label for conversion into ``pl.Enum`` in ``apply_do_labels``

    Notes
    -----
    The ``.collect()`` call is deliberate. The function has to peek at the actual data to see which
    override labels really occur in each _label column before building any expressions. This is
    still relatively cheap as the "projection pushdown" of ``polars`` means only the ``_label``
    columns get read, not the whole frame.
    """
    override_label_cols = [lc for _, lc, _ in label_cols if lc]
    override_values: dict[str, set[str]] = {}
    # Collapse each override label column into a list, then unpack to prevent failures on
    # series of different lengths
    if override_label_cols:
        distinct_df = lf.select(
            pl.col(lc).drop_nulls().unique().implode() for lc in override_label_cols
        ).collect()
        override_values = {lc: set(distinct_df[lc][0]) for lc in override_label_cols}
    return override_values


def apply_do_labels(
    lf: pl.LazyFrame, define_lf: pl.LazyFrame, alias: dict[str, str] | None = None
) -> pl.LazyFrame:
    """Converts numeric columns in a ``pl.LazyFrame`` to the ``Polars`` Enum dtype using
    label definitions ``define`` table in the ``DoSpec`` from ``parse_do()``. For each variable
    present in both ``lf`` and ``define_lf``, real value codes are mapped to ``Polars`` Enum
    dtype and sentinel codes (996-999) become ``None`` (null). If a ``_label`` companion column
    exists (created by ``transform_values``), those labels override the ``.do``-derived labels
    for matching rows, and the companion column is removed. Columns with no matching ``define``
    entries are left numeric, but `TaggedNA` codes are still replaced with ``None``.

    When a column's name in ``lf`` differs from the variable name in ``define_lf`` because an
    upstream ``rename_vars`` or ``merge_vars`` change the column name, pass an ``alias`` map so
    labels can still be found under the original name.

    Parameters
    ----------
    lf : pl.LazyFrame
        A frame of raw numeric survey data, typically
        produced by the transform/rename/merge/subset pipeline.

    define_lf : pl.LazyFrame
        The ``define`` frame in the ``DoSpec`` with columns ``variable``,
        ``value``, and ``desc`` as returned by ``parse_do`` from ``nsch.readers``.
        Contains the value-to-label mapping for each survey variable.

    alias : dict[str, str]
        An optional dict mapping a column name in ``lf`` to the
        variable name to look up in ``define_lf``. Used by ``harmonize_year``
        to handle columns whose names changed via ``rename_vars`` or ``merge_vars``
        from ``nsch.harmonize``. For example, {"family" : "family_r"} tells this
        function to label the ``family`` column using ``family_r``'s
        define entries. Default is ``None``.

    Returns
    -------
    A pl.LazyFrame with categorical columns converted to factors and continuous
    columns remaining numeric with sentinel codes replaced by ``None``.

    Examples
    --------
    >>> import polars as pl
    >>> lf = pl.LazyFrame({"sc_sex": [1, 2, 997, 998]})
    >>> define_lf = pl.LazyFrame(
    ...     {
    ...         "variable": ["sc_sex"] * 5,
    ...         "value": ["1", "2", ".m", ".n", ".d"],
    ...         "desc": [
    ...             "Male",
    ...             "Female",
    ...             "No valid response",
    ...             "Not in universe",
    ...             "Suppressed for confidentiality",
    ...         ],
    ...     }
    ... )
    >>> apply_do_labels(lf=lf, define_lf=define_lf).collect()
    shape: (4, 1)
    ┌────────┐
    │ sc_sex │
    │ ---    │
    │ enum   │
    ╞════════╡
    │ Male   │
    │ Female │
    │ null   │
    │ null   │
    └────────┘
    """
    sentinel_codes = [tag.value for tag in TaggedNA]
    missing_values = STATA_TAG_TO_SENTINEL.keys()

    schema = lf.collect_schema()
    lf_vars = schema.names()

    define_df = define_lf.collect()

    # Make alias an empty dict if it does not exist (is None)
    alias = alias or {}

    # Get the values from the .do define tables that are not NA tags
    # Use ~ to negate element-wise and not on the series whose truth value is ambiguous
    # Sorts to mirror the ordered factor levels in R
    real_defs = (
        define_df.filter(~pl.col("value").is_in(missing_values))
        # Cast to pl.Float64 will fail loudly in the event of a non-numeric column rather than
        # quietly giving NA like as.numeric in the R code does
        .with_columns(pl.col("value").cast(pl.Float64).alias("_num"))
        .sort("_num")
    )

    # ordered dict-map where insertion order == numeric sort order from the above sort,
    # which becomes the Enum's category order
    value_maps: dict[str, dict[float, str]] = {
        variable: dict(zip(group["_num"], group["desc"], strict=False))
        for (variable,), group in real_defs.group_by("variable", maintain_order=True)
    }

    lf_var_set = set(lf_vars)

    # Map column name and label to lookup_name if lookup_name exists and has real values
    # combines the defined_vars + value_maps checks
    mapped_cols: list[tuple[str, str | None, dict[float, str]]] = []
    plain_numeric_cols: list[str] = []

    for col in lf_vars:
        if col.endswith("_label"):
            continue
        # If col is found in alias, return its value. Otherwise return the original column name
        lookup_name = alias.get(col, col)
        mapping = value_maps.get(lookup_name)

        if mapping:
            label_col: str | None = f"{col}_label" if f"{col}_label" in lf_var_set else None
            mapped_cols.append((col, label_col, mapping))
        elif schema[col].is_numeric():
            plain_numeric_cols.append(col)

    override_values = _scan_override_labels(lf, mapped_cols)

    exprs: list[pl.Expr] = []
    label_cols_to_drop: list[str] = []

    for col, label_col, mapping in mapped_cols:
        col_dtype = schema[col]

        # convert mapping to float rather than whole column
        col_mapping: dict[int, str] | dict[float, str]
        if col_dtype.is_integer():
            col_mapping = {int(k): v for k, v in mapping.items() if float(k).is_integer()}
        else:
            col_mapping = mapping

        # Enum categories are built from the full .do-defined label set to mirror R's factor.levels
        categories = list(mapping.values())
        if label_col:
            # Add any override labels not already covered by the .do file, so replace_strict and the
            # final Enum cast both recognize them as valid
            # These labels are appended sorted rather than in the order of first appearance,
            # which diverges from the R logic
            extra = sorted(override_values.get(label_col, set()) - set(categories))
            categories += extra

        # Map real value codes to labels
        # Codes with no matching key become null automatically via default = None
        factor_expr = pl.col(col).replace_strict(col_mapping, default=None, return_dtype=pl.Utf8)

        if label_col:
            # Non-null values in the _label column override the .do-derived label for that row
            factor_expr = (
                pl.when(pl.col(label_col).is_not_null())
                .then(pl.col(label_col))
                .otherwise(factor_expr)
            )
            label_cols_to_drop.append(label_col)

        exprs.append(factor_expr.cast(pl.Enum(categories)).alias(col))

    # Null out sentinel codes for columns that are entirely missing
    for col in plain_numeric_cols:
        exprs.append(
            pl.when(pl.col(col).is_in(sentinel_codes))
            .then(None)
            .otherwise(pl.col(col))
            .cast(schema[col])
            .alias(col)
        )

    # All column transformations run in a single with_columns call rather than one call per column
    if exprs:
        lf = lf.with_columns(exprs)
    # _label companion columns are consumed as overrides above and dropped
    if label_cols_to_drop:
        lf = lf.drop(label_cols_to_drop)

    return lf
