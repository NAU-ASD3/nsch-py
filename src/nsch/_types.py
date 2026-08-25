"""Shared types and constants for the nsch package.

This module is the single place where the package's foundational types and
sentinel constants live. Everything else imports from here, so it has no
internal dependencies and is safe to import from any other module.

The most important thing defined here is :class:`TaggedNA`, the sentinel-code
scheme that lets the pipeline carry Stata's four distinct "missing" reasons
through the harmonization steps as ordinary integers, before they are converted
to null at the very end. See ``docs/design-decisions.md`` for the full rationale.
"""

from enum import IntEnum
from typing import NamedTuple

import polars as pl

__all__ = ["DoSpec", "TaggedNA"]


class DoSpec(NamedTuple):
    """Label metadata parsed from a Stata do-file.

    Attributes
    ----------
    define
        Value-label definitions parsed from ``label define`` statements.
    var
        Variable descriptions parsed from ``label var`` statements.
    """

    define: pl.LazyFrame
    var: pl.LazyFrame


class TaggedNA(IntEnum):
    """Sentinel codes for Stata's four tagged missing-value types.

    NSCH Stata files encode several semantically different reasons a value can
    be missing, using Stata's "tagged" missing values (``.m``, ``.n``, ``.l``,
    ``.d``). Those distinctions carry real meaning. A "logical skip" (the
    question did not apply to this child) is not the same as a "no response"
    (the question applied but went unanswered), and the analysis cares about the
    difference.

    Stata's tagged missing values have no native equivalent in Polars or in a
    CSV export, both of which would collapse all four into a single null. To
    avoid losing the distinction, ``read_dta`` maps each tag to a reserved
    integer in the 996--999 range and the pipeline carries those integers
    forward. ``apply_do_labels`` converts them back to null at the end, once the
    distinctions are no longer needed downstream.

    The numbers 996--999 are a convention of this package, not of Stata or of
    NSCH. They were chosen to sit outside the range of any real survey response
    so they can never collide with a genuine value. The R ``nsch`` package uses
    the same four numbers, which keeps the two implementations comparable.

    Because this is an :class:`~enum.IntEnum`, each member compares equal to its
    integer value, so ``TaggedNA.NO_RESPONSE == 996`` is ``True`` and the
    members can be used directly anywhere an ``int`` is expected.

    Attributes
    ----------
    NO_RESPONSE : int
        ``996`` (Stata ``.m``). The question applied but no valid response was
        recorded.
    NOT_IN_UNIVERSE : int
        ``997`` (Stata ``.n``). The respondent was outside the population the
        question was asked of.
    LOGICAL_SKIP : int
        ``998`` (Stata ``.l``). A prior answer meant this question was skipped
        by design.
    SUPPRESSED : int
        ``999`` (Stata ``.d``). The value was withheld for confidentiality.

    Examples
    --------
    >>> TaggedNA.LOGICAL_SKIP
    <TaggedNA.LOGICAL_SKIP: 998>
    >>> int(TaggedNA.SUPPRESSED)
    999
    >>> TaggedNA.NO_RESPONSE == 996
    True
    """

    NO_RESPONSE = 996  # Stata .m -- applied, but no valid response
    NOT_IN_UNIVERSE = 997  # Stata .n -- respondent outside the question's universe
    LOGICAL_SKIP = 998  # Stata .l -- skipped by design because of a prior answer
    SUPPRESSED = 999  # Stata .d -- withheld for confidentiality
