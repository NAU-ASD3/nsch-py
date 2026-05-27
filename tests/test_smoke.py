"""Smoke tests for the package skeleton.

These tests verify that the package is importable and that its version
metadata is exposed correctly. They will be removed once real tests
displace them in subsequent PRs.
"""

from __future__ import annotations

import nsch


def test_package_imports() -> None:
    """The package must be importable."""
    assert nsch is not None


def test_version_is_a_string() -> None:
    """The package exposes a version string."""
    assert isinstance(nsch.__version__, str)
    assert len(nsch.__version__) > 0
