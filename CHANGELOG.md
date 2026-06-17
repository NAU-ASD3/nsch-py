# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow a date-based scheme: `YYYY.M.DD`.

## [Unreleased]

## [2026.6.17] - 2026-06-17

- Added _types module with the TaggedNA sentinel scheme (#N)

## [2026.5.27] — 2026-05-27

### Added

- Initial repository scaffolding (PR #1):
  - `pyproject.toml` with `[project]` metadata, runtime and dev dependency groups, and configuration for ruff, mypy, pytest, and coverage.
  - GitHub Actions CI workflow with lint, matrix test (Python 3.11–3.13 on Linux; 3.13 on macOS), build, docs, and dependency-review jobs.
  - GitHub Actions release workflow triggered on `v*` tag push.
  - Pre-commit hooks mirroring CI checks (ruff, mypy, basic hygiene).
  - Dependabot configuration for weekly grouped dependency updates.
  - Documentation skeleton (`mkdocs.yml`, `docs/index.md`).
  - Empty `src/nsch/` package and `tests/` directory ready for subsequent PRs.
