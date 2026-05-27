# Contributing to nsch

Thanks for your interest in contributing. This document covers the development setup, conventions, and PR workflow. It assumes familiarity with Python, Git, and GitHub PRs.

## Setup

Prerequisites:

- [`uv`](https://docs.astral.sh/uv/) (the project's package manager)
- Git

```bash
git clone https://github.com/NAU-ASD3/nsch-py
cd nsch-py
uv sync --group dev
uv run pre-commit install
```

`uv sync` installs all runtime and development dependencies into a project-local virtual environment at `.venv/`. You do not need to activate it — `uv run <command>` handles that.

## Running things

```bash
uv run pytest                              # full test suite
uv run pytest tests/test_harmonize.py      # a single file
uv run pytest -k "transform_values"        # by test name pattern
uv run pytest --cov=src/nsch               # with coverage
uv run ruff check .                        # lint
uv run ruff format --check .               # format check
uv run ruff format .                       # auto-format
uv run mypy src/                           # type check
uv run mkdocs serve                        # docs site on localhost:8000
```

The full local CI mirror (run before opening a PR):

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy src/
```

A green local run is the gate for opening a PR.

## Code style

- **Type hints on every public signature.** `mypy --strict` must pass. Distinguish `pl.LazyFrame`, `pl.DataFrame`, and `pl.Series` in signatures.
- **NumPy-style docstrings on every public function.** Include parameter descriptions, return type, and at least one `>>> ` doctest example for non-trivial functions.
- **`pathlib.Path` for paths**, never `str`. Functions that accept paths annotate them as `Path | str` and `Path(...)` them internally.
- **`snake_case`** for functions, variables, and modules. No dotted parameter names.
- **`logging.getLogger(__name__)`** for diagnostics, never `print()`.
- **`Enum` / `IntEnum`** for finite sets of named values. No magic numbers in function bodies.
- **Imports are sorted by ruff.** Don't hand-curate import order.
- **Comment generously, especially the "why."** A comment that explains a non-obvious choice (a workaround for a Stata quirk, a Polars edge case) is more valuable than one that restates the code.

## Architecture invariants

These are not preferences. Violations are bugs:

1. **Stata tagged NAs are preserved via the sentinel-code scheme.** `read_dta` maps `.m → 996`, `.n → 997`, `.l → 998`, `.d → 999`. The four missingness types must survive as distinct numeric values until `apply_do_labels` converts them to null.
2. **The pipeline is `LazyFrame` end-to-end.** One `.collect()` per top-level call, inside `combine_years` or at the integration-test boundary. No mid-pipeline collects.
3. **No mutation.** Every transform returns a new frame.
4. **Functions are small and single-purpose.** Aim for under 50 lines.
5. **Config is loaded once as a Pydantic model.** Downstream code consumes the model, not a raw dict.

See [`docs/design-decisions.md`](docs/design-decisions.md) for the rationale behind each.

## Test conventions

- **Use plain `assert`.** pytest's introspection produces good diffs.
- **Assert on full columns, not element index.** `assert df["x"].to_list() == [1, 2, 3]`, never `assert df["x"][0] == 1`.
- **Synthetic data in unit tests.** Use 3–10 row in-memory `pl.LazyFrame`s. No reading real `.dta` files in unit tests.
- **One behavior per test.** Names describe the behavior: `test_values_are_remapped_for_matching_year`, not `test_transform_1`.
- **No test depends on filesystem state, network, or process-wide state.**

Real-data integration tests live in `tests/test_pipeline.py` and are gated by the `NSCH_REAL_DATA_DIR` environment variable. They are skipped in CI.

Example test (mirrors the R repo's style):

```python
def test_values_are_remapped_for_matching_year():
    lf = pl.LazyFrame({"k2q01_d": [1.0, 2.0, 3.0]})
    transforms = {
        "k2q01_d": {
            "years": ["2016", "2017"],
            "value": ["2"], "new_value": ["1"], "new_label": ["Yes"],
        }
    }
    result = transform_values(lf, transforms, 2016).collect()
    assert result["k2q01_d"].to_list() == [1.0, 1.0, 3.0]
    assert result["k2q01_d_label"].to_list() == [None, "Yes", None]
```

## PR workflow

We use a stacked-PR workflow: each PR depends only on earlier PRs in the stack, and each is independently reviewable.

For stacked PRs, the first line of the PR description must be:

> ⚠️ Stacked PR — branches from `<parent_branch>` (#<parent_PR>). Only files listed below are new; others belong to parent PR.

followed by an explicit list of new files. Check the **Files changed** tab before requesting review to confirm you aren't sending duplicated work.

Every PR must include:

- A version bump in `pyproject.toml`. Format: `2026.M.DD` matching today's date.
- A matching entry in `CHANGELOG.md` under `[Unreleased]`, referencing the PR number.
- Complete tests for any new function or behavior.
- Complete docstrings on any new public API.
- An update to the mkdocs nav (`mkdocs.yml`) if a new public module is added.
- A green local CI mirror run.

PR titles use the imperative mood, lowercase: `add transform_values for per-year remapping`, not `Added transform_values`.

## Adding a dependency

Runtime dependencies are reviewed carefully — each one is a maintenance cost. Before adding one:

1. Verify the functionality isn't already available in the standard library or in an existing dependency.
2. Confirm the package is actively maintained (recent releases, open issues triaged).
3. Confirm license compatibility with MIT.
4. Mention it in the PR description with rationale.

```bash
uv add <package>           # runtime
uv add --group dev <pkg>   # development only
```

## Reporting bugs

Open an issue. Include:

- Python version, OS, and `uv pip list` output.
- A minimal reproducible example.
- What you expected vs. what happened.
