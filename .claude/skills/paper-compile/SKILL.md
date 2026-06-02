---
name: paper-compile
description: Compile an academic LaTeX paper project with pdflatex and bibtex. Diagnoses LaTeX errors, checks page-limit compliance, runs bibtex, fixes undefined references and overfull-hbox warnings.
argument-hint: "[--clean] [--page-check]"
disable-model-invocation: true
paths: ["**/main.tex", "**/.paper-config.yml"]
allowed-tools: Read Bash(pdflatex *) Bash(bibtex *) Bash(make *) Bash(latexmk *) Skill
---

# paper-compile

Compile a LaTeX academic paper project with the pdflatex + bibtex pipeline,
diagnose errors, and check page-limit compliance for the configured venue.

This skill is `disable-model-invocation: true`. User must invoke explicitly
via `/paper-compile [--clean] [--page-check]`. Manual-only because
compilation runs an external tool and writes to `build/`.

## Project config loading (mandatory first step)

Same as `paper-draft`. If no `.paper-config.yml` is found, stop.

## What this skill does

1. Parse `$ARGUMENTS` for optional flags:
   - `--clean`: remove `build/`, `*.aux`, `*.bbl`, `*.blg`, `*.log`, `*.out`,
     `*.toc` before compiling
   - `--page-check`: after successful compile, count pages and compare against
     `page_limit` from `.paper-config.yml`. Warn if over.
2. Delegate to the `compiler` agent. The agent:
   - Runs `pdflatex main.tex`
   - Runs `bibtex main`
   - Runs `pdflatex main.tex` twice more (for cross-references)
   - Parses LaTeX log for errors and warnings
   - For each error, suggests a fix
   - For overfull `\hbox` warnings, points to the offending line
3. If `--page-check` is set, run `pdfinfo build/main.pdf | grep Pages` and
   compare to `page_limit`.

## Handoff schemas

None.

## Next steps

- `/paper-draft <section>` if the compile reveals missing or short sections
- `/paper-cite check` if undefined-reference errors mention missing bibtex keys
