---
name: paper-figure
description: Generate publication-quality matplotlib or seaborn figures for an academic LaTeX paper. 11 EECS chart types (bar, line, heatmap, ROC, ablation, scaling). Output to figures/*.pdf.
argument-hint: "<chart-type> <description>"
paths: ["**/main.tex", "**/figures/", "**/scripts/*.py", "**/.paper-config.yml"]
allowed-tools: Read Write Edit Bash(python *) Skill
---

# paper-figure

Generate a publication-quality figure for an academic LaTeX paper using
matplotlib or seaborn, save it as PDF in `figures/`, and write the matching
Python source in `scripts/`.

## Project config loading (mandatory first step)

Same as `paper-draft` (see that file for the exact 5-step protocol). If no
`.paper-config.yml` is found in the cwd ancestor chain, stop with the
"No paper project found" error.

## What this skill does

1. Parse `$ARGUMENTS` for `<chart-type>` and `<description>`.
2. Recognized chart types: `bar`, `line`, `scatter`, `heatmap`, `roc`,
   `ablation`, `scaling`, `confusion-matrix`, `box`, `violin`, `pareto`.
3. Delegate to the `visualization` agent. The agent:
   - Generates a Python script using matplotlib/seaborn with publication
     defaults (300 DPI, colorblind-safe palette, proper rcParams)
   - Saves the figure as `figures/<slug>.pdf`
   - Saves the script as `scripts/<slug>.py`
   - Returns the LaTeX include snippet for the user to paste
4. Run the script with `python3 scripts/<slug>.py` to actually produce the
   PDF. Verify the output file exists and is non-empty.

## Handoff schemas

None. This skill is self-contained.

## Next steps

- `/paper-draft <section>` to reference the new figure in the section text
- `/paper-compile` to verify the figure renders in the PDF
