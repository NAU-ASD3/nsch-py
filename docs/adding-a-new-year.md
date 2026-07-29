# Adding a New Survey Year

> **Version 0**

## Purpose

This guide describes the team's current process for adding a new National Survey of Children's Health (NSCH) survey year to the Python harmonization pipeline. As the Python pipeline evolves and additional survey years are incorporated, this guide should be updated to reflect the latest workflow.

The Python implementation is based on the existing R workflow. When a new survey year is released, contributors should review the new data files, compare them with the existing harmonization configuration, update any required transformation, rename, or merge rules, and validate that the harmonized output remains consistent across survey years.

> **Scope**
>
> This guide is intended only for adding new survey years to the
> 2016-present NSCH harmonization pipeline. It should not be used to
> combine pre 2016 NSCH surveys with the redesigned 2016 present series,
> because the two survey designs are not directly comparable.

## Resources

Use the following official resources when adding a new NSCH survey year:

- [Census NSCH Methodology Hub](https://www.census.gov/programs-surveys/nsch/technical-documentation/methodology.html)
  The main index for NSCH methodology, technical documentation, and per-year Data User FAQs.

- [NSCH Guide to Multi-Year Estimates](https://www2.census.gov/programs-surveys/nsch/technical-documentation/methodology/NSCH-Guide-to-Multi-Year-Estimates.pdf)
  Official Census guidance for combining data across multiple NSCH survey years.

- [NSCH Analytic Guide](https://www2.census.gov/programs-surveys/nsch/technical-documentation/methodology/NSCH-Analytic-Guide.pdf)
  A guide to correct NSCH analysis practices and common errors to avoid.

- **Per-year Data User FAQs**
  These are available through the [Census NSCH Methodology Hub](https://www.census.gov/programs-surveys/nsch/technical-documentation/methodology.html). Read the FAQ for the new survey year before editing `variable-config.json`.

- [CAHMI Guide to Topics and Questions](https://www.childhealthdata.org/learn-about-the-nsch/topics_questions)
  Interactive per-year catalogs that identify new questions, changed questions, and changed response options. Use this as an initial source when auditing transform and rename rules.

## Before You Begin

Before adding a new survey year, gather the resources needed to compare the new release with the existing harmonization pipeline.

You should have access to the following:

- **The NSCH Stata data (`.dta`) and accompanying `.do` file** for the new survey year. Where available, use the enhanced-weighting (`e`) data files (for example, `nsch_2024e_topical.dta`). The `.do` file defines variable labels and value labels that help interpret the data.

- **The `variable-config.json` file**, which contains the current harmonization configuration, including the desired variables, transformation rules, rename rules, and merge rules. This file is where most updates for a new survey year are made.

- **The official NSCH documentation or codebook** for the new survey year. The recommended Census and CAHMI sources are listed in the [Resources](#resources) section above. These materials provide the questionnaire, variable definitions, response options, and notes about changes from previous survey years, making it easier to identify differences that may require updates to the harmonization pipeline.

- **A local development environment** with the Python repository cloned, project dependencies installed, and the test suite working correctly. This ensures you can safely make changes and validate your updates before submitting them.

## Obtain the New Survey Files

Download the raw NSCH data files for the new survey year from the official NSCH data release. At a minimum, you should obtain:

- The Stata data file (`.dta`).
- The accompanying Stata do-file (`.do`).
- The official NSCH documentation or codebook for the survey year, using the sources listed in [Resources](#resources).

### Use the enhanced-weighting files

Where available, always use the enhanced weighting (`e`) NSCH data files, such as `nsch_2024e_topical.dta`. Census also re-released the 2016–2021 data using the enhanced weighting methodology and the `nsch_YYYYe` naming convention.

Only combine survey files that use the same weighting methodology. Do not mix enhanced weighting files with files produced under a different weighting methodology.

Store these files in a location where they can be accessed by the harmonization pipeline. Before making any code changes, verify that the files correspond to the same survey year, use a compatible weighting methodology, and can be opened successfully.

### Normalize `STRATUM` when combining years

When combining survey years, Census recommends recoding the `STRATUM` value `"2a"` to `"2"`. The pipeline's read layer performs this normalization so that the stratum values are represented consistently across years.

## Understanding `variable-config.json`

Most of the work involved in adding a new survey year is driven by the `variable-config.json` file. The configuration is organized into two parts:

- `desired_variables`: A flat list of harmonized names. Adding a variable means adding it here and confirming every year can produce it.
- `transformations`, which contains the rules used to transform response values, rename variables, and merge multiple   source variables into a single harmonized variable.

The top level structure of `variable-config.json` is organized as follows:

```text
variable-config.json
├── desired_variables
│   ├── year
│   ├── hhid
│   ├── stratum
│   ├── ...
│
└── transformations
    ├── transform
    │   ├── k4q02_r
    │   ├── hoursleep
    │   ├── gowhensick
    │   └── ...
    │
    ├── rename_columns
    │   ├── family_r
    │   ├── gowhensick
    │   ├── k2q41a
    │   └── ...
    │
    └── merge_columns
        ├── sleep
        └── ...
```
> The following sections describe the purpose of each configuration block and illustrate its structure using examples from the project's variable-config.json.

### `desired_variables`

`desired_variables` is a flat list of harmonized variable names that
should appear in the final combined dataset. Adding a variable means
adding its harmonized name to this list and confirming that every survey
year can produce it through a native variable, a rename rule, or a merge
rule.

For example:

```json
"desired_variables": [
  "year",
  "hhid",
  "stratum",
  "fwc",
  "fipsst"
]
```

In this example:

- Each entry is the name of a harmonized variable expected in the final dataset.
- Variables listed here should ultimately exist after all renaming, merging, and transformations have been applied.
- Adding a new variable typically requires updating this list as well as any supporting transformation, rename, or merge rules needed to produce it.

### `transform`

`transform` is keyed by harmonized variable name. Each rule specifies the survey years in which it applies and contains four paired arrays: `years`, `value`, `new_value`, and `new_label`.
The arrays are positional: the nth value in `value` maps to the nth entry in `new_value` and the nth entry in `new_label`. These arrays should always have the same length. The most common update when adding a new survey year is appending the new year to the `years` array after confirming that the response codes,
meanings, and labels have not changed.

For example:

```json
"k4q02_r": {
  "years": ["2016", "2017", "2018", "2019", "2020", "2021", "2022"],
  "value": ["1", "5", "6", "8", "998"],
  "new_value": ["1", "5", "6", "7", "8"],
  "new_label": [
    "Doctor's Office",
    "Clinic within a drug store or grocery store",
    "School (Nurse's Office, Athletic Trainer's Office)",
    "Some other place",
    "No usual place"
  ]
}
```

- `k4q02_r` is the harmonized variable whose values are being transformed.
- `years` specifies the survey years in which this rule applies.
- `value` contains the original response codes found in the raw data.
- `new_value` contains the harmonized response codes that replace those values.
- `new_label` provides the harmonized labels corresponding to each `new_value`.
- The `value`, `new_value`, and `new_label` arrays are positional. The first value maps to the first new value and first label, the second value maps to the second new value and second label, and so on. These arrays should always have the same length.

### `rename_columns`

`rename_columns` is keyed by the raw source variable name. Each rule contains the survey years in which that raw name appears and the harmonized variable name it should become.

For example:

```json
"gowhensick": {
  "years": ["2023", "2024"],
  "new_name": "k4q02_r"
}
```

In this example:

- `gowhensick` is the variable name in the raw survey files.
- `years` specifies the survey years where this raw name appears.
- `new_name` is the harmonized variable name that will be used throughout the pipeline.

### `merge_columns`

`merge_columns` is keyed by the harmonized output variable. Each rule contains a preferred source column, a fallback source column, and the survey years in which the merge applies.

For example:

```json
"sleep": {
  "years": ["2016", ..., "2024"],
  "column_preferred": "hoursleep",
  "column_fallback": "hoursleep05"
}
```

- `sleep` is the harmonized variable produced by the merge.
- `column_preferred` is the primary source column used whenever it contains a value.
- `column_fallback` is used only when the preferred column is missing.
- `years` specifies the survey years where this merge rule applies.

The remaining sections of this guide describe how to review each part of this configuration when incorporating a new survey year.

## Audit Desired Variables

The `desired_variables` list in `variable-config.json` defines the variables that should appear in the final harmonized dataset. Compare this list with the variables available in the newly released survey data to confirm that the required variables are still available.

>The crosswalk is the primary tool for auditing `desired_variables` because it quickly identifies variables that have been renamed, removed, or introduced in the new survey year. However, the crosswalk is not authoritative. Any differences it flags should be verified against the variable definitions in the `.do` file before making changes to `variable-config.json`.

During this review:

- Verify that each desired variable can still be produced for the new survey year.
- Check whether any variables have been renamed in the new survey release.
- Identify variables that are no longer collected or have changed meaning.
- Note any newly introduced survey variables that may require discussion before being added to the harmonized dataset.

If a desired variable has been renamed but still represents the same survey question, update the rename rules rather than changing the harmonized variable name.

> The harmonized dataset is designed to provide a consistent set of variables across survey years. Reviewing the desired variables first helps identify changes that may require updates to the harmonization configuration while preserving a stable output schema.

## Audit Transform Rules

The `transform` section of `variable-config.json` defines how response values and labels are standardized across survey years. Before adding a new survey year, review each transformation rule to determine whether it should also apply to the new release.

For each transformation rule:

- Compare the response values in the new survey year with the existing harmonized values.
- Verify that the response labels have not changed.
- Confirm that the meaning of each response option remains the same.
- If the new survey year uses different response codes or labels, update the transformation rule as needed.
- Add the new survey year to the rule only after confirming that the transformation is still valid.

> Survey response codes and labels may change from year to year even when the survey question remains the same. Transformation rules ensure that equivalent responses are represented consistently across all harmonized survey years.

### Example

Suppose a transformation currently applies to survey years 2016–2024. Before adding 2025 to the `years` list, verify that:

- the response values are unchanged,
- the response labels are unchanged, and
- the survey question still has the same meaning.

Only after confirming these should the new survey year be added to the transformation rule.

## Audit Rename Rules

The `rename_columns` section of `variable-config.json` defines how variable names from individual survey years are mapped to the harmonized variable names used throughout the pipeline.

When reviewing a new survey year:

- Check whether any variable names have changed compared to the previous survey year.
- Determine whether a renamed variable still represents the same survey question.
- If a variable has been renamed but its meaning has not changed, update the corresponding rename rule to include the new survey year.
- If a variable's meaning has changed, do not assume that a rename rule is appropriate. Review the official documentation and per-year change resources listed in [Resources](#resources) to determine whether additional changes are required.

> Variable names occasionally change between survey years even though they represent the same information. Rename rules allow the harmonization pipeline to produce a consistent set of variable names without changing the structure of the final dataset.

> **Note**
>
> Most survey years will require few or no changes to the rename rules. Only add or modify a rename rule when a variable has been renamed but continues to represent the same concept in the survey.

## Audit Merge Rules

The `merge_columns` section of `variable-config.json` defines how multiple survey variables are combined into a single harmonized variable. Review these rules to determine whether they remain valid for the new survey year.

For each merge rule:

- Verify that the preferred and fallback variables still exist in the new survey year.
- Confirm that both variables represent the same survey question or concept.
- Check whether the preferred variable is still the best source of information.
- If the preferred or fallback variable has changed, update the merge rule accordingly.
- Add the new survey year to the rule only after confirming that the merge logic is still appropriate.

> Some survey years store the same information in different variables or use different variable names for the same concept. Merge rules ensure that the harmonized dataset produces a single, consistent variable regardless of how the information is stored in the raw survey data.

### Example

Suppose the harmonized variable `sleep` is created from two raw survey variables:

- `hoursleep` (preferred)
- `hoursleep05` (fallback)

When reviewing a new survey year, verify that both variables still exist and continue to measure the child's sleep duration. If the survey introduces a new variable or changes the existing variables, review the merge rule before adding the new survey year.

## Check Answer Codes and Variable Meanings

Before finalizing the configuration for a new survey year, compare the existing harmonization rules with the official documentation, Data User FAQ, and CAHMI change resources listed in [Resources](#resources) to ensure that response codes and variable meanings remain consistent.

During this review:

- Verify that response codes represent the same categories as in previous survey years.
- Confirm that response labels have not changed.
- Check whether the wording or meaning of a survey question has changed.
- Review any newly introduced response options to determine whether updates to the transformation rules are required.
- If a variable now measures a different concept, do not assume that existing transformation, rename, or merge rules remain valid.

> Two survey variables may have the same name or response codes but represent different concepts if the survey question changes. Reviewing the survey documentation helps ensure that the harmonized dataset remains consistent and accurately represents the original survey data.

## Common Harmonization Patterns

Over multiple NSCH survey years, several recurring harmonization patterns have emerged. When adding a new survey year, check for these patterns before creating new configuration rules.

### Variable renames

A survey question may keep the same meaning while its raw variable name changes.

For example, the 2024 survey uses `gowhensick`, which is harmonized to `k4q02_r`. Likewise, newer surveys include variables such as `diabetes` and `eyedoctor` directly, whereas earlier years required rename rules.

However, similar names do not necessarily mean the questions are equivalent. Earlier in the project, `k4q31_r` was temporarily renamed to `eyedoctor`, but the rename was later removed after determining that the two variables represented different survey questions.

Always confirm that the survey question, response options, and meaning match before introducing a rename rule.

### New response options

A survey question may gain additional response options in a new survey year.

For example, the 2024 survey added **Urgent Care Center** as an option for an existing healthcare location question.

A new response option is not automatically assigned a harmonized code.
Instead, determine whether it should:

- map to an existing harmonized category,
- receive a new harmonized category, or
- require consultation with the project team.

Review both the survey documentation and existing transformation rules before making this decision.

### Semantic shifts under stable response codes

Sometimes the numeric response codes remain the same while their meaning changes.

For example:

- In 2024, `k5q11` changed the meaning of response value `4`.
- For `k8q30`, response value `4` changed from **Not at all** to
  **Not well at all**.

Some wording changes are harmless, while others may alter the meaning of the survey response.

When a wording change could affect interpretation, obtain approval from the project's domain expert before deciding whether the responses should remain harmonized.

### Label drift

Label drift occurs when the same response value has different label text across survey years.

Examples include:

- curly versus straight apostrophes
- differences in capitalization
- missing punctuation
- visually identical labels that differ because of hidden Unicode
  characters

Although these differences appear minor, they create separate factor levels during analysis if left unharmonized.

The standard solution is to add a transformation rule that maps all variants to one canonical label.

### Top-coding and binning changes

Some survey years change how response categories are grouped.

For example, `k11q43r` uses a different top-coded category in some years, and `hospitaler` changed from three response levels to four in 2022. These are not configuration problems if the underlying survey categories are genuinely different.
Instead of forcing harmonization through configuration, document the difference and treat it as an analysis or methodology decision.

### Sentinel value collisions

The project reserves tagged missing-value sentinels `996` through `999`. Most NSCH variables use much smaller response codes, but a few variables legitimately contain three-digit values. Whenever adding or modifying transformation rules, verify that genuine survey values are not accidentally treated as tagged missing values.

## Validate the Harmonized Dataset

After updating the harmonization configuration, run the pipeline and verify that the new survey year has been harmonized correctly.

During validation:

- Confirm that the pipeline completes successfully without errors.
- Verify that the expected harmonized variables are present in the output dataset.
- Check that renamed variables appear under their harmonized names.
- Confirm that merged variables contain the expected values.
- Review transformed variables to ensure response values and labels have been harmonized correctly.
- Compare a sample of records from the raw data with the harmonized output to verify that the transformations behave as expected.

In addition to these manual checks, the package provides several validation functions that help identify common harmonization issues.

### `check_year_coverage()`

Use `check_year_coverage()` to verify that the expected survey years are present in the combined dataset. This confirms that the newly added survey year has been successfully incorporated into the harmonized output and helps identify cases where a year may have been omitted during processing.

### `check_na_rates()`

Use `check_na_rates()` to compare missing-value rates across survey years. A sudden increase in missingness for the new survey year often indicates that a variable was renamed, transformed, or merged incorrectly, making this function useful for detecting silent harmonization errors.

### `check_label_consistency()`

Use `check_label_consistency()` to verify that categorical variables use consistent factor levels across survey years. This function detects label drift, including differences in capitalization, punctuation, wording, or other label inconsistencies that can unintentionally create duplicate categories in the harmonized dataset.

Together, these validation functions provide an additional layer of quality assurance beyond simply running the pipeline. They help confirm that the newly added survey year is consistent with previously harmonized years and that the resulting dataset is suitable for downstream analyses.

> A successful pipeline run does not necessarily mean the harmonized data are correct. Running the validation functions alongside manual review helps distinguish between a pipeline that executes successfully and one that produces a correctly harmonized dataset.

## Final Checklist

Before submitting your changes, confirm that you have completed the following:

- [ ] Downloaded the e-series `.dta`, the `.do`, and the official documentation for the new year, and confirmed the weighting methodology matches the years being combined.
- [ ] Read the new year's **Data User FAQ** and **CAHMI Guide to Topics and Questions** for flagged changes.
- [ ] Audited `desired_variables` against the crosswalk, then verified every flagged change against the `.do` define entries.
- [ ] Audited `transform` rules: response codes, labels (including apostrophes, capitalization, and invisible characters), and new response options.
- [ ] Audited `rename_columns` rules, confirming renamed variables still ask the same question.
- [ ] Audited `merge_columns` rules, confirming preferred and fallback variables both exist and still measure the same thing.
- [ ] Escalated any wording or meaning changes to the project's domain lead before deciding.
- [ ] Checked new three-digit codes against the `996`–`999` sentinel range.
- [ ] Flagged any top-coding or binning incomparabilities to the analysis side rather than patching them in the configuration.
- [ ] Updated `variable-config.json`, including appending the new year to every still-valid rule's `years` array.
- [ ] Ran the harmonization pipeline and the three validation checks (`check_year_coverage()`, `check_na_rates()`, and `check_label_consistency()`) on the combined output.
- [ ] Spot-checked a sample of transformed, renamed, and merged values against the raw data.

---

This document describes the current process for adding a new NSCH survey year to the Python harmonization pipeline. As the pipeline evolves and additional survey years are incorporated, this guide should be updated to reflect any changes to the workflow or configuration.
