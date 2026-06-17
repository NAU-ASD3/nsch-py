---
name: Implementation task
about: A scoped piece of the data-prep pipeline to build
title: ""
labels: enhancement
assignees: ""
---

## What needs to happen

<!-- One or two sentences. What function or behavior should exist after this is done? -->

## Where it goes

- Module: `src/nsch/<module>.py`
- Tests: `tests/test_<module>.py`

## Reference

<!-- The R version is the source of truth for behavior. Link the R function and its test. -->

- R source: `nsch/R/<function>.R`
- R test: `nsch/tests/testthat/test-<function>.R`
- Migration plan section: <!-- name the section -->

## Acceptance criteria

- [ ] The function has the signature described in the migration plan.
- [ ] Tests are written first, use synthetic in-memory data, and assert on full columns.
- [ ] A NumPy-style docstring is present, with a doctest example for anything non-trivial.
- [ ] `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy src/` passes locally.
- [ ] `CHANGELOG.md` has an entry under `[Unreleased]` referencing the PR.

## Notes

<!-- Anything that will save the next person time: a 2024 quirk, a Polars edge case, a tricky bit of the R logic. -->
