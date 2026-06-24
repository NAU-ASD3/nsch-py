# nsch

[![CI](https://github.com/NAU-ASD3/nsch-py/actions/workflows/ci.yml/badge.svg)](https://github.com/NAU-ASD3/nsch-py/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Python toolkit for downloading, harmonizing, and combining National Survey of Children's Health (NSCH) data across survey years.

`nsch` reads NSCH Stata files (`.dta` + `.do`), applies per-year variable renames and value remappings via a declarative JSON config, combines years into a single tidy dataset, and returns a [Polars](https://pola.rs/) DataFrame suitable for downstream analysis or machine learning.

> [!NOTE]
> **Work in progress.** This package is being built one function at a time and isn't usable end to end yet. The intended entry point, `get_clean_data` (see [Quick start](#quick-start)), is the target interface and isn't wired up yet. This README describes where the package is headed, not everything it does today.

## Status

Pre-1.0. APIs may change. The package is being developed under the NAU ASD3 Outcomes Project (NIH-funded). It is a Python reimplementation of the [R `nsch` package](https://github.com/NAU-ASD3/nsch); the R version remains the reference implementation until this package reproduces both the 2016–2023 and 2016–2024 datasets.

## Installation

```bash
# For development, and for now the only way to install (uv recommended):
git clone https://github.com/NAU-ASD3/nsch-py
cd nsch-py
uv sync --group dev

# As a user, once a release is published:
pip install nsch
```

## Quick start

Once the pipeline is complete, a single call will download, harmonize, and combine the requested years:

```python
from nsch import get_clean_data

df = get_clean_data(
    years=range(2016, 2025),
    data_dir="data/raw",
    config_path="src/nsch/data/variable-config.json",
)
print(df.shape)
print(df.columns)
```

`get_clean_data` is the intended public interface, driven by the declarative config at `config_path`. It isn't available yet; the harmonize, combine, and validate steps behind it are landing one function at a time.

## Why this package

The NSCH releases per-year Stata files with overlapping but non-identical variable sets. Combining multiple years requires:

- **Per-year variable renames** (e.g. `k2q01_d` in 2016 becomes `gendepin` in 2020).
- **Per-year value remappings** (e.g. a "yes/no/refused" coding may shift integers between years).
- **Preservation of Stata's four tagged-NA types** (`.m`, `.n`, `.l`, `.d`), each of which carries semantically distinct meaning.

This package centralizes those rules in a single audited configuration and applies them consistently. Reading the original `.dta` and `.do` files directly (rather than CSV intermediates) is required to preserve the four missingness types; this design is documented in [`docs/design-decisions.md`](docs/design-decisions.md).

## Documentation

Full documentation is published at <https://nau-asd3.github.io/nsch-py/>: an onboarding guide, a development walkthrough, and the design decisions behind the package. A function-level API reference will be added as the package gains functions.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for development setup, test conventions, and the PR workflow.

## Citation

If you use this package in research, please cite the underlying NSCH data per the [HRSA/MCHB guidelines](https://www.census.gov/programs-surveys/nsch.html) in addition to this package.

## License

MIT. See [`LICENSE`](LICENSE).

## Acknowledgements

This work is supported by the NIH Autism Data Science Initiative (ASD3 Outcomes Project) at Northern Arizona University.
