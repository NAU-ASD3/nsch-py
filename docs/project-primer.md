# Project Primer

**Last revised:** July 14, 2026 ·
**Maintainer:** Chris Reger ·
**Covers:** [`NAU-ASD3/nsch`](https://github.com/NAU-ASD3/nsch) (R) and [`NAU-ASD3/nsch-py`](https://github.com/NAU-ASD3/nsch-py) (Python)

This page gets revised as the project evolves, so the date above tells you how
stale it might be. If you spot something wrong or out of date, open an issue
or fix it in a PR.

---

This is the big-picture layer of the documentation. It covers what the
research project is, why these packages exist, what the top-level interface
looks like, and who the intended users are. If you are reviewing a PR and
wondering how the piece in front of you fits the whole, or you just joined
and want to know what you signed up for, start here. A
[Where to go next](#where-to-go-next) section at the end points different
kinds of readers to their next document.

---

## Part 1: The research project

### What we study

The ASD3 Outcomes Project at Northern Arizona University, funded through the
NIH Autism Data Science Initiative, studies health-care access and service
outcomes for children with autism in the United States. Our primary data
source is the [National Survey of Children's Health
(NSCH)](https://www.census.gov/programs-surveys/nsch.html), a large annual
survey of children's health, health care, and family context that the U.S.
Census Bureau fields on behalf of the Health Resources and Services
Administration's Maternal and Child Health Bureau (HRSA/MCHB).

A note on scale and access, since both surprise people. The survey reaches
tens of thousands of children per year — on the order of 20,000 to 55,000
depending on the year — so a combined 2016 to 2024 dataset runs to several
hundred thousand rows. And the public-use files are exactly that: public. No
application, no data-use agreement. The acquire stage of our pipeline
downloads them straight from the Census Bureau's site.

Methodologically, we lean on interpretable machine learning. Prediction alone
is rarely the interesting part. We want to know which factors drive the
predictions, and whether a model trained on some survey years still works on
others. That second question uses SOAK (Same/Other/All K-fold
cross-validation), an evaluation design that measures how well models
transfer across subsets of the data ([Hocking et al. 2026, open
access](https://doi.org/10.1002/sam.70055)). For us the subsets are spans of
survey years. The SOAK paper is also the project's published analysis to
date: its case studies include NSCH autism data from 2019 and 2020, so the
method and this project grew up together. When this document mentions "the
published analysis," that paper is the one it means.

### Where the code came from

The current work replicates and extends an earlier analysis pipeline built by
Vince, a previous researcher on the project, together with Toby Hocking.
Their work lives in three repositories: an [initial trial
run](https://github.com/tdhock/2024-01-ml-for-autism) of the ML methods on
the 2019 and 2020 data, a data-preparation repo that standardized a subset
of NSCH variables across 2016 to 2023, and a private HPC repo holding the
cluster scripts and outputs behind the published SOAK analysis. The R package came together over the year that followed; the Python
port began in summer 2026.

That first pass proved the concept, and we owe it a lot. It also had limits
we are deliberately correcting. The prep stage went through CSV
intermediates, which collapses the survey's four distinct kinds of missing
data into a single blank. Year-to-year variable drift was handled with
one-off fixes scattered through scripts, so there was no single place to
check whether a given recode was right. And the documentation was thin. The
code worked, but the knowledge of *why* it worked lived mostly in people's
heads.

The `nsch` packages redo that layer properly. We read the original Stata
files directly and keep the missing-data semantics intact. Every rename and
recode lives in one reviewed configuration file. And this time, documentation
is a deliverable in its own right: an onboarding guide, design-decision
writeups, a development walkthrough, and this primer, all published on the
[docs site](https://nau-asd3.github.io/nsch-py/) and kept current. If someone
new can't reconstruct our reasoning from the docs, we consider that a bug.

### The bigger picture

The replication is only the first consumer of this data. Planned and likely
work on the wider project includes deep learning models trained on the same
harmonized dataset, geospatial work mapping service access and outcomes, and
the construction of a composite index. Parts of the larger picture will also
draw on primary data sources beyond the NSCH.

That future matters for how we write code here today. These packages are
shared infrastructure for a family of studies, and several other efforts will
inherit whatever we get wrong. It is the main reason study-specific logic
stays out of the package and the general harmonization problem gets solved
carefully rather than just well enough for one paper.

### The repositories, and how they relate

| Repository | Language | Role |
|---|---|---|
| [`NAU-ASD3/nsch`](https://github.com/NAU-ASD3/nsch) | R | The original data package. Downloads, harmonizes, and combines NSCH years. Mature; the **reference implementation**. |
| [`NAU-ASD3/nsch-py`](https://github.com/NAU-ASD3/nsch-py) | Python | Ground-up reimplementation of the R package. This repo. |
| `nsch-ml-py` | Python | The analysis layer. Replicates the published analysis and extends it to newer survey years. Consumes the output of the data packages. |
| Prior repos ([`2024-01-ml-for-autism`](https://github.com/tdhock/2024-01-ml-for-autism), `ASD3-machine-learning-prep`, `ASD3-machine-learning` (private)) | R | The original pipeline being replicated. Kept as historical reference. |

The R package came first and remains the source of truth. The Python
reimplementation exists so the whole project can live in one language and use
the Python ML ecosystem (PyTorch, modern XGBoost, SHAP) that the analysis
layer needs. The R package's cached 2016 to 2024 output is the validation
gold standard. The Python package is not done until it reproduces that
output, and an integration test enforces the equivalence: row counts per year
match exactly, factor level sets match exactly, and a fixed set of cross-tabs
match exactly. Column order and dtypes are free to differ.

### Who's who

- **Dr. Olivia Lindly** (Health Sciences) leads the project and supervises
  the data and analysis work.
- **Dr. Ben Lucas** (Mathematics and Statistics) and **Dr. David Folch**
  (Geography, Planning and Recreation) are collaborating faculty on the wider
  project and serve as code reviewers.
- **Dr. Toby Hocking** developed SOAK and built the original analysis with
  Vince while at NAU. He is now at the Université de Sherbrooke in Canada and
  involved as a consultant. He remains the authority on the R package and its
  review standards, though he is much less involved day to day.
- **Chris Reger** (graduate student researcher) is the primary developer and
  maintainer of both data packages.
- **Sakina Lord** and **Rahmat Adepo** (graduate student researchers) are
  contributing developers, porting functions one at a time under review.

---

## Part 2: The `nsch` packages

Everything in this part applies to both the R and Python packages unless
noted. They implement the same pipeline. Where they differ, the difference is
deliberate and documented.

### The problem the package solves

The NSCH releases one Stata data file (`.dta`) per survey year, plus a `.do`
script defining the value labels. The files overlap heavily but never line up
cleanly. Some real examples of what drifts:

- **Variables get renamed.** A depression question is `k2q01_d` in 2016 and
  `gendepin` in 2020. Same question, different column name.
- **Codebooks reorganize.** The "where does this child usually go when sick"
  question spent years under the survey code `k4q02_r` before the 2024 file
  switched to the plain-language name `gowhensick`. The 2024 release also
  added a brand-new answer category, "Urgent Care Center," that no earlier
  year has.
- **Answer codes shift meaning.** For `k5q11`, the value 4 changed meaning
  between releases. Miss a shift like that and the merged data is quietly
  wrong, with no error raised anywhere.
- **Questions appear and disappear.** New topics get added; old ones drop out
  or split into multiple items.
- **Missingness is meaningful.** Stata distinguishes four tagged kinds of
  missing value (`.m`, `.n`, `.l`, `.d`). "This question did not apply to
  this child" is analytically different from "this question applied but was
  not answered," and our models care about the difference. Most tools,
  including the default pandas Stata reader, collapse all four into one
  generic NA.

Every multi-year NSCH analysis has to deal with all of this. Doing it ad hoc
invites silent errors. A missed rename drops a variable from half the years.
A missed recode flips an answer's meaning. Our approach is to centralize
every rule in one declarative configuration file, apply the rules with tested
code, and validate the combined result.

### What the data looks like

An illustrative sketch rather than literal survey records. Two raw survey
years for the depression question might look like this, with a Stata tagged
NA in the mix:

| year | column in raw file | raw value | meaning per that year's `.do` file |
|---|---|---|---|
| 2016 | `k2q01_d` | `1` | Yes |
| 2016 | `k2q01_d` | `.l` | Legitimate skip (question not asked for this child's age) |
| 2020 | `gendepin` | `2` | No |

After the pipeline, the same information lives in one column with one coding:

| year | `gendepin` |
|---|---|
| 2016 | `"Yes"` |
| 2016 | `null` (a skip, still distinguishable from a nonresponse) |
| 2020 | `"No"` |

The rules that make this happen live in the config file, not in the code. The
rename above is one entry, along the lines of:

```json
"rename": {
  "gendepin": {
    "k2q01_d": [2016, 2017, 2018, 2019]
  }
}
```

(Abridged; see `src/nsch/data/variable-config.json` for the real schema.)
Adding a new survey year mostly means auditing that year against the config
and the [CAHMI](https://www.childhealthdata.org/) crosswalk. It rarely means
writing new pipeline code. The 2024 audit, for example, caught the
`gowhensick` rename and the new urgent-care category before they could
corrupt a merge.

### What the pipeline does

Five stages, in order:

1. **Acquire.** Download the official `.dta` and `.do` files for each
   requested year from the Census Bureau.
2. **Read.** Parse each Stata file. Variable labels, value labels, and all
   four tagged missing-value types survive this step. Internally the tagged
   NAs become the sentinel codes 996 to 999 so they can travel through
   numeric processing without losing their identity.
3. **Harmonize**, per year. Rename variables to the common scheme, remap
   answer codes so the same answer means the same value in every year, merge
   split variables, and keep only the variables listed in the config.
4. **Combine.** Stack the harmonized years into one tidy table and apply the
   labels, so coded values become readable categories and sentinel codes
   resolve to their proper missing-value semantics.
5. **Validate.** Check the combined result: expected factor levels, plausible
   NA rates, full year coverage.

A few corners are genuinely fiddly. The 2016 file, for instance, lacks a
grade variable that later years have, so the combine stage includes a
documented imputation helper (`impute_a1_grade_2016`) rather than silently
dropping the year or the variable. When you hit something like this in
review, the [design decisions](design-decisions.md) doc is the place to look
for the rationale.

### The top-level API

One function is the public entry point, and it runs the entire pipeline:

```python
from nsch import get_clean_data

df = get_clean_data(
    years=range(2016, 2025),
    data_dir="data/raw",
    config_path="src/nsch/data/variable-config.json",
)
```

The return value is a single tidy [Polars](https://pola.rs/) DataFrame, one
row per surveyed child, with consistent variable names and categories across
all requested years. From there it is ordinary dataframe work:

```python
df.group_by("year").len()            # rows per survey year
df["gendepin"].value_counts()        # one consistent coding, all years
df.filter(pl.col("year") >= 2020)    # slice and go
```

The R package's equivalent, `nsch::get_clean_data()`, returns a `data.table`
and is fully wired up today.

Everything else in the package supports one of the five stages. Those
functions are exported and individually tested, so a contributor or a curious
analyst can run any stage in isolation. The intended usage, though, is the
single call above.

**A status note for reviewers:** in the Python package, `get_clean_data` is
the *target* interface. The functions behind it are landing one PR at a time,
which means an individual PR you review may implement one stage's primitive
while the end-to-end pipeline does not exist yet. The R package defines what
each function must do, and the migration plan defines the PR sequence. If a
PR seems like a small piece floating in space, that is why.

### Who the package is for

Two audiences, in priority order.

**The ASD3 analysis team, now.** The immediate customer is our own downstream
analysis work: the replication first, then the deep learning, mapping, and
index work described above. Analysis code should never touch raw Stata files
or per-year quirks. It calls `get_clean_data()` and starts from a clean
table. This is why analytical reproducibility (same rows, same categories,
same missingness semantics) is a hard requirement while byte-level details
are not.

**External NSCH researchers, later.** Multi-year NSCH harmonization is a
problem every research group using this survey has to solve, and most solve
it privately and imperfectly. Once the Python package reproduces the
reference output, we intend to release it on PyPI as a general-purpose tool.
Hence the config-driven design, and hence the rule that nothing
autism-specific or study-specific lives in the package. Study-specific steps,
such as joining CAHMI-derived variables like the developmental screening
indicator, belong in the analysis repo instead.

### Design principles

These shape most review comments, so they are worth knowing before you read
the code:

- **The config is the single source of truth for harmonization rules.**
  Authoritative inputs, like the parsed `.do` definitions, are never
  modified. When a lookup needs to bridge a rename, we add a translation
  layer (an alias map) instead of editing the source data.
- **Missingness is preserved end to end.** The four tagged NA types travel
  through the pipeline as distinct sentinel codes and only get resolved at
  the labeling step.
- **Functions are small, single-purpose, and non-mutating.** The pipeline is
  a composition of plain functions on dataframes. No class hierarchies, no
  frameworks.
- **Tests are strict.** Full-vector exact comparisons against synthetic data
  rather than spot checks of individual elements. This discipline came out of
  the R package's review process, and it is the reason the output can be
  trusted.
- **The R output is ground truth for the Python port.** The integration test
  defines what counts as parity: same rows, same levels, same cross-tabs.

### Current status and near-term roadmap

The R package's pipeline is feature-complete, with final fixes and reviews in
flight. Its next milestone is a clean end-to-end 2016 to 2024 run, cached as
the validation reference for everything downstream.

In the Python package, the scaffolding, CI, and documentation infrastructure
are merged. Functional code is landing as a sequence of layer-by-layer PRs:
read layer, config layer, harmonize layer, combine plus the orchestrator,
validation, and finally the integration test against the R output.

After that, the analysis replication consumes the merged dataset, and a
methods paper writes up the replication and the extension to 2024.

---

## Where to go next

Different readers need different next steps.

- **Joining as a contributor?** Go straight to [Onboarding](onboarding.md).
  It walks from a fresh laptop to a first merged PR, and the
  [development walkthrough](development-walkthrough.md) then follows one real
  change from issue to merge.
- **Reviewing code?** Skim
  [CONTRIBUTING.md](https://github.com/NAU-ASD3/nsch-py/blob/main/CONTRIBUTING.md)
  for the conventions being enforced, and keep
  [Design decisions](design-decisions.md) open for the architectural "why"
  behind anything that looks unusual.
- **Planning to use the data?** The [top-level API](#the-top-level-api)
  section above is most of what you need. The R package works today; the
  Python package is getting there. Reading the SOAK paper
  ([Hocking et al. 2026](https://doi.org/10.1002/sam.70055)) is the best
  preparation for the analysis-side discussions.
- **Just want the survey itself?** The Census Bureau's
  [NSCH page](https://www.census.gov/programs-surveys/nsch.html) has the raw
  files and official documentation, and CAHMI's
  [Data Resource Center](https://www.childhealthdata.org/) has
  variable-level resources including the crosswalk.

---

## Part 3: Glossary

**NSCH.** [National Survey of Children's
Health](https://www.census.gov/programs-surveys/nsch.html). An annual survey
(redesigned in 2016, hence our start year) of U.S. children's health and
health care, fielded by the Census Bureau for HRSA/MCHB.

**HRSA/MCHB.** The Health Resources and Services Administration's Maternal
and Child Health Bureau, the federal sponsor of the NSCH.

**CAHMI.** The [Child and Adolescent Health Measurement
Initiative](https://www.childhealthdata.org/). Publishes NSCH resources
including the **crosswalk**, a spreadsheet tracking every variable's name,
availability, and coding across survey years. We use it to audit our config
when adding a new year.

**`.dta` file.** Stata's binary data format. One per survey year.

**`.do` file.** A Stata script distributed alongside each `.dta` file that
defines the value labels, i.e. which integer codes mean which answers. We
parse it rather than retyping its contents, so the survey's own definitions
stay authoritative.

**Harmonize.** To transform each year's data so that the same question has
the same variable name and the same answer coding in every year. Covers
renames, value remapping, variable merges, and subsetting.

**Tagged NA.** Stata supports multiple named missing values. NSCH uses four:
`.m` (missing), `.n` (not applicable / not in universe), `.l` (legitimate
skip), and `.d` (don't know / suppressed). Each carries different meaning for
analysis.

**Sentinel codes.** The integers 996, 997, 998, and 999, used internally to
carry the four tagged NA types through numeric processing without losing
their identity. They resolve to proper missing values or categories at the
labeling step.

**Config / `variable-config.json`.** The declarative file listing every
variable we keep and every per-year rename, value transform, and merge rule.
The pipeline is generic; the NSCH-specific knowledge lives here.

**Factor levels / value labels.** The set of named categories a categorical
variable can take, such as "Yes" / "No". "Factor" is the R term; the Python
package represents these as Polars categorical or enum values. Cross-year
consistency of these levels is one of our core validation checks.

**Tidy data.** One row per observation (here, per surveyed child), one column
per variable, one table for the whole dataset. The shape the pipeline's
output guarantees.

**Reference implementation / gold standard.** The R package and its cached
2016 to 2024 output. The Python package is validated by reproducing it.

**Polars / LazyFrame.** Polars is the Python dataframe library the package is
built on. A LazyFrame is its deferred-execution mode: transformations are
described first and executed once at the end, which lets the engine optimize
the whole pipeline. Our pipeline stays lazy end to end.

**SOAK.** Same/Other/All K-fold cross-validation. Hocking et al.,
"Same/Other/All K-Fold Cross-Validation for Estimating Similarity of Patterns
in Data Subsets," *Statistical Analysis and Data Mining*, 2026
([doi:10.1002/sam.70055](https://doi.org/10.1002/sam.70055), open access;
implemented in the
[`mlr3resampling`](https://github.com/tdhock/mlr3resampling) R package). An
evaluation design that measures how well models trained on one subset of
data, such as one span of survey years, predict another. Used in the analysis
layer rather than the data packages, but the term comes up constantly in
project discussions.

**Monsoon.** NAU's SLURM-based high-performance computing cluster, run by
[Advanced Research Computing](https://in.nau.edu/arc/), where the ML training
runs. Relevant to the analysis layer only.
