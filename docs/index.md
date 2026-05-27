# nsch

A Python toolkit for downloading, harmonizing, and combining National Survey of Children's Health (NSCH) data across survey years.

## What it does

`nsch` reads NSCH Stata files (`.dta` + `.do`), applies per-year variable renames and value remappings via a declarative JSON config, combines years into a single tidy dataset, and returns a [Polars](https://pola.rs/) DataFrame suitable for downstream analysis.

The package is a Python reimplementation of the [R `nsch` package](https://github.com/NAU-ASD3/nsch). The R version remains the reference implementation until this package reproduces both the 2016–2023 and 2016–2024 datasets.

## Status

Pre-1.0. The package skeleton is in place; per-function implementations land in subsequent PRs.

## Installation

```bash
pip install nsch
```

For development:

```bash
git clone https://github.com/NAU-ASD3/nsch-py
cd nsch-py
uv sync --group dev
```

## Next steps

- [Contributing](https://github.com/NAU-ASD3/nsch-py/blob/main/CONTRIBUTING.md) — development setup and PR workflow.
- API reference and design decisions will be added as functions land.
