"""Functions for the combine module"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import polars as pl

__all__ = ["apply_do_labels"]


def apply_do_labels(
    lf: pl.LazyFrame, define_lf: pl.DataFrame, alias: dict[str, str] | None = None
) -> pl.LazyFrame:
    """Converts numeric columns in a ``pl.LazyFrame`` to the ``Polars`` Enum dtype using
    label definitions ``define`` table in the ``DoSpec`` from ``parse_do()``. For each variable
    present in both ``lf`` and ``define_lf``, real value codes are mapped to ``Polars`` Enum
    dtype and sentinal codes (996-999) become ``None`` (null). If a ``_label`` companion column
    exists (created by ``transform_values``), those labels override the ``.do``-derived labels
    for matching rows, and the companio column is removed. Columns with no matching ``define``
    entries are left numeric, but sentinal codes are still replaced with ``None``.

    When a column's name in ``lf`` differs from the variable name in ``define_lf`` because an
    upstream ``rename_vars`` or ``merge_vars`` change the column name, pass an ``alias`` map so
    labels can still be found under the original name.

    Parameters
    ----------
    lf : pl.LazyFrame
        A frame of raw numeric survey data, typically
        produced by the transform/rename/merge/subset pipeline.

    define_lf : pl.LazyFrame
        A frame with columns ``variable``, ``value``, and ``desc``
        as returned by ``parse_do`` from ``nsch.readers``.
        Contains the value-to-label mapping for each survey variable.

    alias : list[str]
        An optional list mapping a column name in ``lf`` to the
        variable name to look up in ``define_lf``. Used by ``harmonize_year``
        to handle columns whose names changed via ``rename_vars`` or ``merge_vars``
        from ``nsch.harmonize``. For example, ["family" : "family_r"] tells this
        function to label the ``family`` column using ``family_r``'s
        define entries. Default is ``None``.

    Returns
    -------
    A pl.LazyFrame with categorical columns converted to factors and continuous
    columns remaining numeric with sentinel codes replaced by ``None``.

    Examples
    --------
    """

    raise NotImplementedError
