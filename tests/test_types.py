"""Tests for the shared types and constants in ``nsch._types``."""

from nsch._types import TaggedNA


def test_tagged_na_members_have_expected_sentinel_values():
    # The 996--999 mapping is a package convention shared with the R version.
    # If these change, every downstream comparison against a sentinel changes
    # too, so the test pins the whole set rather than any single member.
    assert [member.value for member in TaggedNA] == [996, 997, 998, 999]


def test_tagged_na_members_have_expected_names():
    assert [member.name for member in TaggedNA] == [
        "NO_RESPONSE",
        "NOT_IN_UNIVERSE",
        "LOGICAL_SKIP",
        "SUPPRESSED",
    ]


def test_tagged_na_compares_equal_to_its_integer_value():
    # IntEnum members compare equal to their underlying int, which is what lets
    # the pipeline use them directly in integer expressions.
    assert TaggedNA.NO_RESPONSE == 996
    assert TaggedNA.NOT_IN_UNIVERSE == 997
    assert TaggedNA.LOGICAL_SKIP == 998
    assert TaggedNA.SUPPRESSED == 999


def test_tagged_na_values_are_distinct():
    values = [member.value for member in TaggedNA]
    assert len(set(values)) == len(values)
