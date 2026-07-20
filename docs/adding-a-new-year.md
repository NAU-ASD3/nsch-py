# Adding a New Survey Year

> **Version 0**

## Purpose

This guide describes the team's current process for adding a new National Survey of Children's Health (NSCH) survey year to the Python harmonization pipeline. As the Python pipeline evolves and additional survey years are incorporated, this guide should be updated to reflect the latest workflow.

The Python implementation is based on the existing R workflow. When a new survey year is released, contributors should review the new data files, compare them with the existing harmonization configuration, update any required transformation, rename, or merge rules, and validate that the harmonized output remains consistent across survey years.

## Before You Begin

Before adding a new survey year, gather the resources needed to compare the new release with the existing harmonization pipeline.

You should have access to the following:

- **The raw NSCH data (`.dta`) and accompanying `.do` file** for the new survey year. The data file contains the survey responses, while the `.do` file defines variable labels and value labels that help interpret the data.

- **The `variable-config.json` file**, which contains the current harmonization configuration, including the desired variables, transformation rules, rename rules, and merge rules. This file is where most updates for a new survey year are made.

- **The official NSCH documentation or codebook** for the new survey year. This provides the questionnaire, variable definitions, response options, and notes about changes from previous survey years, making it easier to identify differences that may require updates to the harmonization pipeline.

- **A local development environment** with the Python repository cloned, project dependencies installed, and the test suite working correctly. This ensures you can safely make changes and validate your updates before submitting them.

## Obtain the New Survey Files

Download the raw NSCH data files for the new survey year from the official NSCH data release. At a minimum, you should obtain:

- The Stata data file (`.dta`).
- The accompanying Stata do-file (`.do`).
- The official NSCH documentation or codebook for the survey year.

Store these files in a location where they can be accessed by the harmonization pipeline. Before making any code changes, verify that the files correspond to the same survey year and that they can be opened successfully.

## Understanding `variable-config.json`

Most of the work involved in adding a new survey year is driven by the `variable-config.json` file. This configuration defines:

- `desired_variables`: the variables that should appear in the final harmonized dataset.
- `transform`: value transformations used to harmonize response codes and labels across survey years.
- `rename_columns`: mappings from raw survey variable names to harmonized variable names.
- `merge_columns`: rules for combining multiple raw variables into a single harmonized variable.

The remaining sections of this guide describe how to review each part of this configuration when incorporating a new survey year.

## Audit Desired Variables

The `desired_variables` list in `variable-config.json` defines the variables that should appear in the final harmonized dataset. Compare this list with the variables available in the newly released survey data to confirm that the required variables are still available.

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
- If a variable's meaning has changed, do not assume that a rename rule is appropriate. Review the survey documentation to determine whether additional changes are required.

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

Before finalizing the configuration for a new survey year, compare the survey documentation with the existing harmonization rules to ensure that response codes and variable meanings remain consistent.

During this review:

- Verify that response codes represent the same categories as in previous survey years.
- Confirm that response labels have not changed.
- Check whether the wording or meaning of a survey question has changed.
- Review any newly introduced response options to determine whether updates to the transformation rules are required.
- If a variable now measures a different concept, do not assume that existing transformation, rename, or merge rules remain valid.

> Two survey variables may have the same name or response codes but represent different concepts if the survey question changes. Reviewing the survey documentation helps ensure that the harmonized dataset remains consistent and accurately represents the original survey data.

## Validate the Harmonized Dataset

After updating the harmonization configuration, run the pipeline and verify that the new survey year has been harmonized correctly.

During validation:

- Confirm that the pipeline completes successfully without errors.
- Verify that the expected harmonized variables are present in the output dataset.
- Check that renamed variables appear under their harmonized names.
- Confirm that merged variables contain the expected values.
- Review transformed variables to ensure response values and labels have been harmonized correctly.
- Compare a sample of records from the raw data with the harmonized output to verify that the transformations behave as expected.

If any unexpected values, missing variables, or inconsistencies are found, review the corresponding transformation, rename, or merge rules before finalizing the update.

> Successfully running the pipeline does not necessarily mean the harmonized data are correct. Validation helps ensure that the configuration changes produce the intended output and that the new survey year is consistent with previously harmonized years.

## Final Checklist

Before submitting your changes, confirm that you have completed the following:

- [ ] Downloaded the correct `.dta`, `.do`, and official documentation for the new survey year.
- [ ] Reviewed the `desired_variables` list to ensure all required harmonized variables can still be produced.
- [ ] Audited the transformation rules and updated them where response codes or labels changed.
- [ ] Audited the rename rules and updated them where variable names changed but the underlying survey question remained the same.
- [ ] Audited the merge rules and confirmed that the preferred and fallback variables are still appropriate.
- [ ] Reviewed the survey documentation for changes in variable definitions, question wording, or response options.
- [ ] Updated `variable-config.json` as needed.
- [ ] Ran the harmonization pipeline successfully.
- [ ] Validated the harmonized output by checking a sample of transformed, renamed, and merged variables.
- [ ] Confirmed that the new survey year produces a harmonized dataset that is consistent with previous survey years.

---

This document describes the current process for adding a new NSCH survey year to the Python harmonization pipeline. As the pipeline evolves and additional survey years are incorporated, this guide should be updated to reflect any changes to the workflow or configuration.
