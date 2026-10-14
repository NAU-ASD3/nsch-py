# Changelog

All notable changes to this project are documented here.

This mirrors the R `nsch` package's `NEWS.md`: one `## YYYY.M.DD (PR#NN)`
section per PR, newest first. Versions follow a date-based scheme, `YYYY.M.DD`,
bumped per PR to the date it lands. When two PRs land on the same day, the
second and later append a micro segment (`YYYY.M.DD.MICRO`, e.g. `2026.6.29.1`)
so each version stays unique and the date stays honest.

## 2026.10.14.1 (PR#102)

- Supports polars 2.0: the dependency is now `polars>=1.43.2,<3`
- `apply_do_labels` casts the 996-999 sentinel codes to each column's dtype before `is_in`, which polars 2.0 requires
- `combine_years` collects on the in-memory engine; on polars 2.0's default streaming engine the full 2016-2024 run took minutes instead of seconds

## 2026.10.14 (PR#101)

- `read_nsch_dta` maps Stata byte columns to `Int16` instead of `Int8`, so tagged missing values keep their 996-999 sentinels instead of silently becoming null
- `combine_years` combines a column that is labeled in only some years as text with a warning, as R's `rbindlist` does, instead of raising

## 2026.10.13.3 (PR#99)

- Added `impute_a1_grade_2016` to a new `impute` module to redistribute coarse grade levels accross the finer categories used in 2017 onwards.

## 2026.10.13.2 (PR#89)

- Added `combine_years` to stack harmonized per-year frames into one collected `DataFrame`, widening `Enum` columns to the union of their per-year categories and filling columns absent from a year with null

## 2026.10.13.1 (PR#88)

- Added `harmonize_year`, wiring transform, rename, merge, subset, and labeling for one survey year with an alias map so renamed and merged columns are labeled from their original `.do` entries
- The harmonize functions now take the config layer's Pydantic rule models (`RenameRule`, `MergeRule`, `TransformRule`) and `harmonize_year` takes a `Config`, replacing the duplicate TypedDicts
- `harmonize_year`'s alias map only includes rename and merge rules that fire on the frame, so a rule whose year list includes a year where the column already has its new name leaves that column labeled under its own name (R reaches the same labels through a fallback in its `apply_do_labels`, R #52). A merge whose preferred source was renamed that year is labeled from the pre-rename `.do` name, where R leaves it unlabeled

## 2026.10.13 (PR#96)

- `apply_do_labels` falls back to a column's own define entries when its alias points at a name with none that year (alias year-list overshoot), matching R's fix in NAU-ASD3/nsch#63

## 2026.10.12.1 (PR#92)

- Made `parse_do`'s docstring example self-contained (writes a small do-file to a temp directory) so every module's doctests run clean

## 2026.10.12 (PR#81)

- Explained the deliberate 998 (logical-skip) recodes in the new-year runbook and cross-referenced them from the sentinel-collision section

## 2026.10.7 (PR#86)

- Added Pydantic models and `read_config` for loading and validating the NSCH configuration, including the bundled `variable-config.json`.
## 2026.10.4 (PR#78)

- Moved the tagged-NA letter map to `_types.STATA_TAG_TO_SENTINEL` with bare letters as the canonical keys (matching pyreadstat and R) and pointed `readers.py` at it, closing #71
- `apply_do_labels` now adds the leading dot at the point of use to match `parse_do`'s dotted output; a seam test runs a real `.do` file through both to keep the two in agreement

## 2026.9.14.2 (PR#77)

- Updated `.pre-commit-config.yaml` to run mypy, ruff, and ruff-format as local hooks through uv, so the hooks, the gate, and CI share one tool version in one environment

## 2026.9.14.1 (PR#66)

- Added `get_nsch_index` for reading the NSCH index page and getting links to each dataset
- Added `get_year` to download one year's NSCH Stata `.dta` and `.do` files
- Added `get_all_years` to build a `pl.DataFrame` of all `.dta` and `.do` files found in a directory

## 2026.9.14 (PR#73)

- Added `merge_vars` for per-column merges based on the config.

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
