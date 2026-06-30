# nsch

A Python toolkit for downloading, harmonizing, and combining National Survey of Children's Health (NSCH) data across survey years.

## What it does

`nsch` reads NSCH Stata files (`.dta` + `.do`), applies per-year variable renames and value remappings via a declarative JSON config, combines years into a single tidy dataset, and returns a [Polars](https://pola.rs/) DataFrame suitable for downstream analysis.

The package is a Python reimplementation of the [R `nsch` package](https://github.com/NAU-ASD3/nsch). The R version remains the reference implementation until this package reproduces both the 2016–2023 and 2016–2024 datasets.

## Status

Pre-1.0 and under active development. The package skeleton is in place, and the per-function implementations land one at a time in later PRs, so the full pipeline isn't usable end to end yet.

## Installation

The package isn't on PyPI yet, so for now install it from source:

```bash
git clone https://github.com/NAU-ASD3/nsch-py
cd nsch-py
uv sync --group dev
```

That uses [uv](https://docs.astral.sh/uv/) to set up Python and the dependencies for you. Once a release is published, a plain `pip install nsch` will work too.

## Where to go next

- [Onboarding](onboarding.md) takes a new contributor from a fresh laptop to a first merged pull request.
- [Development walkthrough](development-walkthrough.md) follows one real change from issue to merge.
- [Design decisions](design-decisions.md) explains why the package is built the way it is.
- [CONTRIBUTING.md](https://github.com/NAU-ASD3/nsch-py/blob/main/CONTRIBUTING.md) is the full conventions reference.
