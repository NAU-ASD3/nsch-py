<!--
If this is a stacked PR, make this the first line of the description and fill it in:
⚠️ Stacked PR — branches from `<parent_branch>` (#<parent_PR>). Only the files listed below are new; others belong to the parent PR.
Then list the new files, and check the Files changed tab before requesting review.
-->

## What this does

<!-- One or two sentences. What does this PR add or change? -->

Closes #<!-- issue number -->

## Checklist

- [ ] Tests cover the new function or behavior, use synthetic data, and assert on full columns.
- [ ] Every new public function has a NumPy-style docstring (with a doctest example where it helps).
- [ ] `pyproject.toml` version is bumped to the day the PR lands (`YYYY.M.DD`; add `.1`, `.2`, ... if another PR already landed that day), and `uv.lock` is regenerated with `uv lock`.
- [ ] `CHANGELOG.md` has a matching `## YYYY.M.DD (PR#NN)` section at the top describing the change.
- [ ] `mkdocs.yml` nav is updated if a new public module was added.
- [ ] The full local check passes: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy src/`.

## Notes for the reviewer

<!-- Anything worth flagging: a design choice you weren't sure about, a place you'd like a closer look. -->
