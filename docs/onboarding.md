# Onboarding

Welcome to the team. This guide gets you from a fresh laptop to your first
merged pull request. It assumes you are new to most of this, so it moves slowly
and explains the why as it goes. If you already know Git and Python packaging,
you can skim to [Your first contribution](#your-first-contribution); the full
reference for conventions is in [CONTRIBUTING.md](https://github.com/NAU-ASD3/nsch-py/blob/main/CONTRIBUTING.md).

If anything here is unclear or out of date, that is a bug in this document. Open
an issue or fix it in a PR. Improving the onboarding is a great first contribution.

## What this project is, in plain terms

The National Survey of Children's Health (NSCH) is a large yearly survey about
the health and care of children in the United States. Our research group uses it
to study health-care access and outcomes for children with autism.

The survey releases one data file per year. The problem is that the files do not
line up cleanly across years: a question can be renamed, the answer codes can
shift, and new questions appear while old ones drop out. Before anyone can study
trends over time, someone has to stitch the years together into one consistent
table. That stitching is what this package does.

This Python package is a re-write of an existing R package that already does the
job. The R version works and stays as our reference. We are rebuilding it in
Python so the whole project can live in one language and use the Python tools the
modeling work needs. Your job, mostly, is to port pieces of the R package into
Python, one function at a time, with tests.

The package is early. Most of the functions described in the plan do not exist
yet. Building them is the work, and there is plenty of it.

## The mental model in five minutes

Here is the whole pipeline in one breath. Do not worry about the details yet;
this is just the shape of the thing.

1. **Download** one Stata file per survey year.
2. **Read** each file, keeping the labels and the different kinds of missing data
   intact.
3. **Harmonize** each year: rename the columns to a common scheme, remap answer
   codes so the same answer means the same number in every year, and keep only
   the variables we care about.
4. **Combine** all the years into one table.
5. **Check** the result for obvious problems.

One detail is worth flagging now because it drives a lot of the design. The
survey distinguishes several reasons a value can be missing. "This question did
not apply to this child" is genuinely different from "this question applied but
nobody answered it," and our analysis cares about the difference. Most tools
throw that distinction away and turn everything into a single blank. We go out of
our way to keep it. If you see numbers like 996, 997, 998, and 999 in the code,
that is the scheme we use to carry those four kinds of missing through the
pipeline. The reasoning is written up in
[docs/design-decisions.md](design-decisions.md), which is worth reading once you
have the basics down.

## What you will need installed

You need three things. Take them one at a time.

- **Git**, for version control. If `git --version` prints a version in your
  terminal, you have it. If not, install it from [git-scm.com](https://git-scm.com/).
- **uv**, the tool we use to manage Python itself and all the package's
  dependencies. Install it by following
  [the uv install guide](https://docs.astral.sh/uv/getting-started/installation/).
  You do not need to install Python separately; uv handles that.
- **An editor.** [VS Code](https://code.visualstudio.com/) is a good default and
  is what most of the team uses, but any editor is fine.

You also need a GitHub account, and someone on the team needs to add you to the
`NAU-ASD3` organization so you can push branches. Ask if you do not have access yet.

## One-time setup

Open a terminal and run these, one block at a time.

Clone the repository and move into it:

```bash
git clone https://github.com/NAU-ASD3/nsch-py
cd nsch-py
```

Install everything the project needs. The first run downloads the right Python
version and all the dependencies into a local folder; later runs are fast:

```bash
uv sync --group dev
```

Turn on the pre-commit hooks. These run the formatter and a few checks
automatically every time you commit, so you catch small problems before they
reach a reviewer:

```bash
uv run pre-commit install
```

Now confirm everything works by running the test suite:

```bash
uv run pytest
```

You should see a short run that ends in `passed`. If it does, your setup is good.
If it does not, that is worth sorting out before you write any code; ask the team
and include the error you saw.

A note on `uv run`: it runs a command inside the project's own isolated
environment without you having to "activate" anything. You will type `uv run`
in front of most commands. That is normal and expected.

## A tour of the codebase

```
nsch-py/
├── src/nsch/          the package itself
│   ├── __init__.py    declares the public API
│   ├── _types.py      shared types and the missing-data sentinel codes
│   └── ...            more modules get added here as we build them
├── tests/             one test file per module
├── docs/              the documentation site source
│   ├── design-decisions.md   why the package is built the way it is
│   └── onboarding.md         this file
├── CONTRIBUTING.md    the full conventions reference
├── pyproject.toml     project metadata and dependency list
└── README.md          the project overview
```

Most of `src/nsch/` is not written yet. The
[migration plan](https://github.com/NAU-ASD3/nsch) describes the modules we are
building toward (reading files, the config layer, the harmonize steps, combining
years, the checks). Each one is, or will be, a tracked issue.

`src/nsch/_types.py` is a good first file to read. It is small, it has no moving
parts, and the style of it (the docstring, the comments that explain the why, the
matching test in `tests/test_types.py`) is the style we want everywhere.

## The R reference, and how to use it

The R package at [NAU-ASD3/nsch](https://github.com/NAU-ASD3/nsch) is the source
of truth for what each function should do. When you pick up a task to port a
function, the workflow is:

1. Open the R version of that function, usually `R/<name>.R`, and its test,
   usually `tests/testthat/test-<name>.R`. Read both until you understand what
   the function does and what its tests expect.
2. Read the part of the migration plan that describes the Python version. The
   signature sometimes changes on purpose (for example, returning a new frame
   instead of modifying one in place).
3. Write your tests first, in Python, in our style.
4. Write the function.
5. Run the checks and open a PR.

Do not translate the R line by line. Some R habits do not fit Python, and forcing
them in makes the code awkward. Match the behavior, not the syntax. When in doubt
about what the behavior should be, the R tests usually answer it, and if they do
not, ask.

## Your first contribution

Here is the whole loop, start to finish. The first time through, expect it to
take a while. That is fine.

**1. Pick an issue.** Look at the
[open issues](https://github.com/NAU-ASD3/nsch-py/issues), especially anything
labeled `good first issue`. Those are picked to be small and to not lean on the rest of the pipeline.
Comment on the one you want so nobody doubles up.

**2. Make a branch.** Never work directly on `main`. Start from an up-to-date
`main` and branch off it:

```bash
git checkout main
git pull
git checkout -b add-subset-vars      # name it after what you are doing
```

**3. Write the test first.** Find the matching test file (or create it), and
write a test that describes the behavior you are about to build. It will fail,
because the function does not exist yet. That is the point. Run it and watch it
fail:

```bash
uv run pytest tests/test_<module>.py
```

**4. Write the function.** Make the test pass. Keep the function small and give
it a docstring. Look at `_types.py` and its test for the house style.

**5. Run the full local check.** This is the same set of checks the project runs
automatically on every PR, so running it yourself first means no surprises:

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy src/
```

If the formatter complains, `uv run ruff format .` fixes most of it for you.

**6. Commit and push.** Commit in small, sensible steps. Then push your branch:

```bash
git add .
git commit -m "add subset_vars for selecting desired columns"
git push -u origin add-subset-vars
```

**7. Open the pull request.** Go to the repository on GitHub and open a PR from
your branch. A template appears with a checklist; fill it in. Link the issue you
are closing. Then a reviewer takes a look.

**8. Respond to review.** You will almost certainly get comments, including on
your first few PRs. This is normal and it is how the code stays consistent, not a
judgment of you. Make the changes, push again (the PR updates itself), and reply
to the comments. When it is approved, someone merges it.

That is the whole cycle. Every contribution, from the smallest to the largest,
goes through these same steps.

## The conventions that matter most

[CONTRIBUTING.md](https://github.com/NAU-ASD3/nsch-py/blob/main/CONTRIBUTING.md) has the full list. These are the few that
new contributors trip on most often, so they are worth knowing up front.

- **Tests come first, and tests use small made-up data.** A handful of rows you
  type out by hand, not a real survey file. Compare whole columns at once
  (`assert df["x"].to_list() == [1, 2, 3]`), never a single cell by position.
- **Functions take a frame and return a new frame.** Nothing is modified in
  place. Each step hands a fresh result to the next.
- **One `.collect()` at the end, not in the middle.** The pipeline stays "lazy"
  so the data library can optimize the whole chain at once. If you are not sure
  what this means yet, you will pick it up; just avoid calling `.collect()`
  inside a step.
- **Comment the why, not the what.** `# loop over years` tells a reader nothing.
  `# year is text in the config but a number in the data, so compare as text`
  saves them ten minutes.
- **Ask before adding a new dependency or a new class.** This codebase is small
  functions, not class hierarchies, and every dependency is a long-term cost. Both
  are fine sometimes, but they are worth a quick conversation first.

## Getting unstuck

Getting stuck is part of the work, not a sign you are doing it wrong. A good
order to try:

1. Re-read the error message slowly. Python's errors usually point at the real
   problem in the last few lines.
2. Look at how a similar, already-written function does it.
3. Check [CONTRIBUTING.md](https://github.com/NAU-ASD3/nsch-py/blob/main/CONTRIBUTING.md) and
   [design-decisions.md](design-decisions.md).
4. Ask the team. Include what you tried, what you expected, and what happened. A
   question with that much context is easy to answer quickly.

There is no such thing as a question that is too basic here. Asking early saves
everyone time.

## Glossary

- **NSCH.** The National Survey of Children's Health, the yearly survey this
  package processes.
- **Harmonize.** Make the different survey years line up: same column names, same
  answer codes, same set of variables.
- **Stata file.** The `.dta` (data) and `.do` (a script describing the variables
  and their labels) files the survey is released in. We read both.
- **Tagged NA.** Stata's way of recording several distinct reasons a value is
  missing. NSCH uses four. We keep them separate rather than blurring them into
  one blank. See `TaggedNA` in `src/nsch/_types.py`.
- **Sentinel codes.** The numbers 996 through 999 we use to carry the four
  missing-data reasons through the pipeline before turning them into real blanks
  at the end.
- **LazyFrame.** A table that records the steps you want to run but waits to
  actually run them until you ask for the result with `.collect()`. This lets the
  library optimize the whole sequence at once.
- **The R package.** The original, working version at
  [NAU-ASD3/nsch](https://github.com/NAU-ASD3/nsch). It defines the correct
  behavior; we match it.
