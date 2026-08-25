# Changelog

All notable changes to this project are documented here.

This mirrors the R `nsch` package's `NEWS.md`: one `## YYYY.M.DD (PR#NN)`
section per PR, newest first. Versions follow a date-based scheme, `YYYY.M.DD`,
bumped per PR to the date it lands. When two PRs land on the same day, the
second and later append a micro segment (`YYYY.M.DD.MICRO`, e.g. `2026.6.29.1`)
so each version stays unique and the date stays honest.

## 2026.8.24.1 (PR#68)

- Added `apply_do_labels` for converting coded values to `pl.Enum` labels from the `DoSpec` produced by `parse_do`, resolving remaining sentinel codes to null.

## 2026.8.24 (PR#61)

- Added `parse_do` for reading NSCH Stata `.do` files and introduced the `DoSpec` type for parsed variable and value labels.

## 2026.8.13 (PR#59)

- Added `read_nsch_dta` and  `readers.py` module for ingesting data and handling tagged NAs

## 2026.7.29.3 (PR#55)

- Added a Version 0 runbook documenting the workflow for adding a new NSCH survey year, covering variable configuration, transforms, renames, merges, and validation.

## 2026.7.29.2 (PR#60)

- Added `__all__` to `validate.py` declaring its three public checks

## 2026.7.29.1 (PR#32)

- Added `rename_vars` for per-year column renaming, which also renames the matching `_label` companion column.
- `rename_vars` raises `ValueError` on colliding rename rules: two rules targeting the same name, or a rule targeting a column that already exists.

## 2026.7.29 (PR#52)

- Added a project primer to the docs covering the research context, the top-level API, and a glossary of key terms.
- Aligned the PR and issue templates with the dated changelog convention (closes #58).

## 2026.7.21.1 (PR#43)

- Added `check_label_consistency` for reporting factor-level consistency across years

## 2026.7.21 (PR#49)

- Added `subset_vars` to select a subset of desired variables from a given LazyFrame

## 2026.7.14 (PR#44)

- Added `check_na_rates` for checking per-variable NA rates per year

## 2026.7.10 (PR#47)

- Added `transform_values` for per-year value and label transformation.

## 2026.7.3 (PR#38)

- Added `check_year_coverage` to report per-variable year coverage.

## 2026.6.29 (PR#46)

- Aligned the changelog and versioning convention with the R `nsch` package's `NEWS.md`: per-PR `## YYYY.M.DD (PR#NN)` sections, micro segments for same-day collisions.

## 2026.6.17 (PR#8)

- Added the `_types` module with the TaggedNA sentinel scheme.

## 2026.5.27 (PR#1)

- Initial repository scaffolding:
  - `pyproject.toml` with `[project]` metadata, runtime and dev dependency groups, and configuration for ruff, mypy, pytest, and coverage.
  - GitHub Actions CI workflow with lint, matrix test (Python 3.11–3.13 on Linux; 3.13 on macOS), build, docs, and dependency-review jobs.
  - GitHub Actions release workflow triggered on `v*` tag push.
  - Pre-commit hooks mirroring CI checks (ruff, mypy, basic hygiene).
  - Dependabot configuration for weekly grouped dependency updates.
  - Documentation skeleton (`mkdocs.yml`, `docs/index.md`).
  - Empty `src/nsch/` package and `tests/` directory ready for subsequent PRs.
