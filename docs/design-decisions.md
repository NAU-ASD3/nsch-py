# Design decisions

This document records the technical decisions behind `nsch-py`: what was
chosen, what was considered, and why. It is written for new technical
reviewers joining the team who know Python and dataframes but have not
worked with Stata files or with this project's history. It is *not* an API
reference or a usage tutorial; for those, see the README.

> **Work in progress.** This page describes the target architecture and the
> reasoning behind it. Several of the modules and functions named below (the
> read layer, the harmonize and combine stages, the pipeline orchestrator, the
> config models) are still being built. The design is settled; the code is
> landing one function at a time.

A through-line runs through every section: Stata stores four distinct
missingness types per variable, and preserving those four types end-to-end
is the single requirement that shapes the rest of the design.

---

## 1. Why we read `.dta` + `.do` files directly, not CSV intermediates

The NSCH is published as Stata files. The natural first instinct, and the
path most non-Stata-native pipelines take, is to convert each year to CSV
once, then build the rest of the pipeline on the CSVs. `nsch-py` does not.

### Stata's four tagged-NA types

Stata distinguishes five categories of missing data for any numeric
variable: a plain `.`, and four *tagged* missing values `.m`, `.n`, `.l`,
`.d`. Each tag is a distinct in-memory value; CAHMI uses them in NSCH to
encode the *reason* a value is missing:

- `.m`: no valid response (missing for an unknown reason).
- `.n`: not in universe (the question did not apply, e.g. school
  enrollment for an infant).
- `.l`: logical skip (earlier answers caused the survey to skip this
  item).
- `.d`: suppressed by CAHMI for confidentiality before release.

These distinctions are not cosmetic. "Not in universe" is structurally
different from "didn't answer", and downstream analyses (rate
denominators, imputation eligibility, model masking) need to treat them
differently.

### What CSV does to them

CSV has no encoding for tagged missingness. Exporting a Stata variable to
CSV collapses every one of `.`, `.m`, `.n`, `.l`, `.d` to the same empty
field; re-reading yields a single `null` per row with no way to recover
which tag was originally present. The loss is one-way and silent: by the
time the CSV reader sees the file, the information is already gone. The
same loss occurs through any format without tagged-NA semantics: a
single-NA `pandas.read_stata` call, a naive Parquet writer that collapses
missingness to `null`, and so on. The fix is not "be careful with the CSV
step." It is to not have a CSV step.

### The decision

`src/nsch/read.read_nsch_dta` reads `.dta` files directly with a Stata-aware
reader (`pyreadstat`; see §3) and rewrites the four tags to integer
sentinels that the rest of the pipeline carries through unchanged (see
§4). `src/nsch/read.parse_do` reads the matching `.do` file to recover the
variable definitions and value labels, which Stata stores separately from
the data itself.

A concrete example. Consider a variable encoding "child has been diagnosed
with autism", where `1` means yes, `2` means no, and the four NA tags are
all in use:

| Stata value | Meaning                            | CSV round-trip | `.dta` direct read |
| ----------- | ---------------------------------- | -------------- | ------------------ |
| `1`         | Yes                                | `1`            | `1`                |
| `2`         | No                                 | `2`            | `2`                |
| `.m`        | No response                        | (empty)        | `996`              |
| `.n`        | Not in universe                    | (empty)        | `997`              |
| `.l`        | Logical skip (parent screened out) | (empty)        | `998`              |
| `.d`        | Suppressed                         | (empty)        | `999`              |

After the CSV round-trip, every row of "not yes, not no" is
indistinguishable. After the direct read, a downstream denominator that
needs "respondents who were asked" can include `1`, `2`, `996`, `999`
while excluding `997` and `998`.

---

## 2. Why Polars over Pandas

Polars has the better philosophical fit with the project's reference
implementation. The R `nsch` package is written in `data.table` style:
expression-driven, no row index, in-memory by default, with a query
optimizer. Polars's API is a near-direct analogue, with the same
expression idioms and the same "rows are positional, columns are named"
data model, where Pandas's row index and method-chained mutation style
are a constant source of friction for a `data.table`-shaped mind.
Cross-language code review is easier when both halves read the same way.

Several secondary considerations point the same direction:

- **Nullable types are first-class.** Polars treats `null` consistently
  across all dtypes. Pandas has historically mixed `NaN`, `None`, and
  `pd.NA` depending on dtype, and pre-3.0 code in dependent libraries
  still surfaces those inconsistencies whenever the pipeline touches
  missing data.
- **Lazy execution is built in.** Polars's `LazyFrame` with its query
  planner enables the projection / predicate pushdown and expression
  fusion described in §5. Pandas has no native equivalent.
- **Group-by and joins are multi-threaded.** Polars is ~5–15× faster on
  the operations that dominate the harmonization pipeline. NSCH is small
  enough that absolute performance is not the bottleneck, but the
  headroom matters if the pipeline grows.

### The trade-off

Pandas has a substantially larger ecosystem. Most scikit-learn-style ML
APIs expect Pandas inputs, and the modeling layer that consumes `nsch`
output is in that camp. The cost is paid at one place, the boundary
between data prep and modeling, with a single `.to_pandas()` call:

```python
from nsch import get_clean_data

df = get_clean_data(years=range(2016, 2025), data_dir="data/raw", ...)

X = df.drop("outcome").to_pandas()
y = df["outcome"].to_pandas()
model.fit(X, y)
```

The conversion is a single columnar copy via Arrow and happens exactly
once at the API boundary. Inside the data-prep pipeline, everything is
Polars.

---

## 3. Why pyreadstat over `pandas.read_stata`

`pandas.read_stata` and `pyreadstat.read_dta` both load a `.dta` file into
Python. They differ in a single feature that determines whether `nsch-py`
can exist at all: tagged-NA preservation.

`pandas.read_stata` has no equivalent of pyreadstat's `user_missing=True`
flag. Every tagged-NA value collapses to a single `NaN` in the resulting
DataFrame, and the tag is discarded, the same loss as the CSV path in
§1, just done in memory rather than on disk.

`pyreadstat.read_dta(path, user_missing=True)` returns each tagged value
as a distinct letter marker in the column (`"a"` for `.m`, `"b"` for
`.n`, and so on) and exposes the value-to-tag mapping in the metadata
object it returns alongside the DataFrame:

```python
import pyreadstat

df, meta = pyreadstat.read_dta("nsch_2024_topical.dta", user_missing=True, output_format="polars")

# A column that had values 1, 2, .m, .n, .l, .d in Stata now looks like:
#   df["k2q01_d"]  ->  [1.0, 2.0, "m", "n", "l", "d"]
# meta.missing_user_values["k2q01_d"] gives the letter -> tag mapping.
```

`src/nsch/read.read_nsch_dta` consumes this output and rewrites the letter
markers to the integer sentinels described in §4. The rewrite happens in
one private helper inside `read.py`; the rest of the pipeline sees the
column as plain numeric data:

```python
def read_nsch_dta(path: Path) -> pl.LazyFrame:
    df_pd, meta = pyreadstat.read_dta(str(path), user_missing=True, output_format="polars")
    # _rewrite_tagged_na uses meta.missing_user_values to map
    # "m"/"n"/"l"/"d" -> 996/997/998/999 per column.
    return _rewrite_tagged_na(pl.from_pandas(df_pd).lazy(), meta)
```

pyreadstat ships without type stubs as of this writing, so `mypy --strict`
needs a per-module override in `pyproject.toml`:

```toml
[[tool.mypy.overrides]]
module = "pyreadstat"
ignore_missing_imports = true
```

This is the only place in the package where mypy strictness is relaxed.

---

## 4. The 996/997/998/999 sentinel-code scheme

Once `read_nsch_dta` has the four tagged-NA markers in hand, the package needs
a representation that survives the rest of the pipeline. Three options
were considered: four boolean companion columns per variable, a single
string column per variable encoding the tag as `"m"` / `"n"` / `"l"` /
`"d"` / `null`, or integer sentinels in the same column as the data with
a fixed mapping. The package uses the third. The mapping lives in
`src/nsch/_types.py`:

```python
from enum import IntEnum

class TaggedNA(IntEnum):
    NO_RESPONSE = 996       # .m
    NOT_IN_UNIVERSE = 997   # .n
    LOGICAL_SKIP = 998      # .l
    SUPPRESSED = 999        # .d
```

Three considerations made integer sentinels the right choice.

**Continuity with the R reference implementation.** The R `nsch` package
already uses the 996/997/998/999 scheme. Matching it numerically means
the two pipelines produce comparable intermediate frames, which is what
makes the R-versus-Python equivalence test in `tests/test_pipeline.py`
feasible at all. A different convention would force translation at the
test boundary, and translation masks real divergences.

**The pipeline stays numeric until factor conversion.** Most
harmonization transforms (value remapping, column merging, year-specific
renames) operate on integer-coded variables directly. Keeping the
tagged-NA values as integers in the same column lets those transforms
compose cleanly without ever special-casing missingness. When a variable
finally becomes a categorical via `src/nsch/harmonize.apply_do_labels`,
the sentinels drop to null in one place: the boundary where the
variable's dtype changes from numeric to `pl.Enum`.

**Sentinel values are out of band by inspection.** NSCH coded values top
out at low double digits for nearly every variable. 996–999 are visibly
not legitimate response codes, which makes a stray sentinel easy to spot
in a cross-tab. For the very small number of variables that *do* use
three-digit codes, the relevant config rules avoid colliding with
996–999; the R-side audit of `variable-config.json` confirmed this for
2016–2024, and the same JSON is consumed here.

### Lifecycle of a tag

A tagged value moves through the pipeline as follows: Stata source
contains `.m`; `readers.read_nsch_dta` rewrites it to `996` and the column
becomes plain `Int64`/`Float64`; the harmonize stages
(`transform_values`, `rename_vars`, `merge_vars`, `subset_vars`) treat
`996` as an ordinary value; `apply_do_labels` converts the variable to a
`pl.Enum`, mapping all four sentinels to null at the same step that maps
numeric codes to their factor levels. The output carries `pl.Enum`
columns whose null values are the union of all four tagged-NA reasons.
Consumers that need to distinguish reasons read from an upstream
intermediate frame, before `apply_do_labels` collapses them.

The sentinel codes are a *package* convention, not a Stata convention;
the specific numbers are arbitrary except for matching the R version.

---

## 5. Why the pipeline is `LazyFrame` end-to-end

Polars has two materialization modes: `DataFrame` (eager, every
operation runs immediately) and `LazyFrame` (deferred, operations build
a plan that the query optimizer executes when `.collect()` is called).
`nsch-py` is written end-to-end in the lazy mode.

### The pattern

Every public function in `src/nsch/harmonize.py`, the per-year stages of
`src/nsch/combine.py`, and the top-level orchestrator in
`src/nsch/pipeline.py` takes a `pl.LazyFrame` and returns a
`pl.LazyFrame`. The single `.collect()` lives inside
`combine.combine_years()`, after all years have been concatenated.

The shape of a typical chain, taken from `harmonize.harmonize_year`:

```python
def harmonize_year(
    lf: pl.LazyFrame,
    config: Config,
    year: int,
    define_df: pl.DataFrame,
) -> pl.LazyFrame:
    return (
        lf
        .pipe(transform_values, config.transformations.transform, year)
        .pipe(rename_vars, config.transformations.rename_columns, year)
        .pipe(merge_vars, config.transformations.merge_columns, year)
        .pipe(subset_vars, config.desired_variables)
        .pipe(apply_do_labels, define_df)
    )
```

Every `.pipe()` step receives a `LazyFrame` and returns one. The chain
composes into a single query plan, which the optimizer is free to
rearrange before executing.

### What the optimizer can do with the plan

Three optimizations matter in practice, none of them available if any
step collapses to eager:

- **Projection pushdown.** `subset_vars` later in the chain restricts
  the columns the pipeline ultimately keeps; the optimizer pushes that
  restriction up to the read step, so columns destined to be dropped
  are never loaded. NSCH topical files have ~400 columns and the
  package typically keeps ~50.
- **Predicate pushdown.** Filters move toward the source, so rows that
  would be excluded later never participate in an intermediate
  computation.
- **Expression fusion.** Two `.with_columns()` calls on the same frame
  fuse into a single pass. The `transform_values` step writes both the
  remapped value and the `_label` companion column in the same
  iteration.

In an eager pipeline, each step would materialize an intermediate frame
and the optimizer would have no visibility past the current call, so the
work above would happen N times for an N-step chain.

### The discipline that keeps it lazy

Type signatures enforce the mode. Every harmonize/combine/pipeline
function annotates input and return as `pl.LazyFrame`. A function that
accidentally returns a `DataFrame`, the result of an unnecessary
`.collect()`, is caught by `mypy --strict`. The lazy/eager boundary
becomes visible at the type level.

The only authorized `.collect()` in the core pipeline is inside
`combine.combine_years()`. Tests are allowed to call `.collect()` for
assertions, but no production code path does. The anti-pattern this
guards against is a mid-pipeline `.collect()` inserted for debugging
and left in place: output is unchanged, but the query plan is severed,
everything downstream becomes opaque to the optimizer for everything
upstream, and the performance regression is silent.

---

## 6. Why no workflow framework

A reasonable instinct on seeing a multi-stage data pipeline is to reach
for a workflow tool: `targets` (which the R-side modeling layer uses),
Prefect, Snakemake, Dagster, or similar. `nsch-py` does not. The
orchestrator in `src/nsch/pipeline.py` is a single function that loops
over years and composes the harmonize stages with `.pipe()`. No DAG,
no caching layer, no scheduler.

The case for a framework rests on two benefits: caching of intermediate
results, and a declarative graph. Both are real, but their cost-benefit
for this package is unfavorable today.

The pipeline is small enough that function composition is clearer. The
entire flow is six stages per year and one combine step; a reviewer
reads `harmonize_year` and `combine_years` end-to-end in a few minutes
and sees the whole shape of the work. A DAG declaration puts the same
information in a separate registry (readable, but no longer next to
the code) and adds vocabulary a `data.table`-shaped reviewer has to
learn before reading the pipeline at all.

Caching trades complexity for a speedup not currently needed. A full
2016–2024 run takes a few minutes on a laptop. The variable-config
file is the only input that changes meaningfully between runs, and a
config change typically invalidates most downstream stages anyway, so the
case where targets-style caching wins (one stage's inputs change, the
rest reuse) is rare here. Caches also have to be invalidated correctly,
and silent staleness in a data-prep cache produces subtly wrong outputs
with no error to trace.

The escape hatch is open. If pipeline runtime becomes a bottleneck, for
instance in HPC sweeps where many reruns per day is normal, wrapping
the existing stages as targets or Prefect tasks is mechanical. The
harmonize functions already have the right shape: pure, typed inputs,
no shared state. What's hard to undo is committing to a framework early
and finding it shapes the API in ways that make the simple use case
awkward.

---

## 7. Why Pydantic for config validation

The harmonization rules live in `src/nsch/data/variable-config.json`:
which variables to keep, which to rename per year, which to merge, and
which value remappings to apply. The R version validates this file with
`validate_config()`, roughly 60 lines of hand-written field checks. The
checks are correct but verbose, and the failure messages are only as
good as whatever string the author remembered to write.

`nsch.config` declares the expected shape as Pydantic v2 models;
validation happens automatically on load.

```python
from typing import Self
from pydantic import BaseModel, model_validator

class TransformRule(BaseModel):
    years: list[str]
    value: list[str]
    new_value: list[str]
    new_label: list[str]

    @model_validator(mode="after")
    def parallel_arrays_must_match_in_length(self) -> Self:
        # value, new_value, new_label are parallel: entry i in each list
        # defines one remapping. Equal lengths required or downstream
        # zip() silently drops rows.
        n = len(self.value)
        if not (len(self.new_value) == n and len(self.new_label) == n):
            raise ValueError(
                f"value/new_value/new_label must be the same length, "
                f"got {len(self.value)}/{len(self.new_value)}/{len(self.new_label)}"
            )
        return self


class Config(BaseModel):
    desired_variables: list[str]
    transformations: Transformations


def read_config(path: Path) -> Config:
    return Config.model_validate_json(path.read_text())
```

If the JSON is malformed, a field is missing, a list of strings contains
an integer, or the cross-field length check fails, Pydantic raises
`ValidationError` with the exact field path and reason. There is no
separate `validate_config()` step because validation *is* loading.

Beyond the line-count win, two benefits matter. The models are
executable schema: a reviewer who wants to know what fields
`TransformRule` has reads the class definition, and there is no parallel
documentation to drift out of sync with the implementation. And
downstream code is type-checked: the harmonize layer accesses config
via attribute syntax (`config.transformations.transform[var].years`),
and `mypy --strict` verifies that `.years` exists and is a `list[str]`
at every callsite. A dict-access alternative cannot be checked at all;
a typo or a renamed field would only fail at runtime on the row that
happens to need it.

Advanced Pydantic features (custom serializers, generic models,
`mode="before"` validators) are deliberately not used; the models above
are the entire pattern in the package.

---

## Where to read next

- The README for the package's user-facing overview and quick start.
- The [Onboarding](onboarding.md) guide and the
  [Development walkthrough](development-walkthrough.md) for how the work
  actually gets done day to day.
- Function-level API reference, which will be generated under `api/` as
  the functions land.
