---
name: paper-cite
description: Manage references.bib in an academic LaTeX paper project. Add bibtex entries, validate natbib citation commands, check citation compliance (orphan citations, self-citation ratio, source currency).
argument-hint: "<action> <args>"
paths: ["**/references.bib", "**/main.tex", "**/sections/*.tex", "**/.paper-config.yml"]
allowed-tools: Read Write Edit Skill
---

# paper-cite

Manage `references.bib` in an academic LaTeX paper project: add new bibtex
entries, validate natbib/IEEE citation commands, run compliance checks
(orphan citations, self-citation ratio, source currency).

## Project config loading (mandatory first step)

Same as `paper-draft`. If no `.paper-config.yml` is found, stop.

## What this skill does

1. Parse `$ARGUMENTS` for `<action>` and remaining args:
   - `add <author> <year> <topic>` - add a new bibtex entry
   - `check` - run all compliance checks
   - `fix` - auto-fix simple issues (citation key style, missing fields)
   - `list` - list all entries with their cite count in the paper
2. Delegate to the `citation_manager` agent. The agent:
   - For `add`: search the user's prior bibtex files (if any) for matching
     entries, otherwise prompt the user for the missing fields and write a
     new bibtex entry
   - For `check`: scan all `\cite{...}` commands in the .tex files and the
     bibtex file; report orphans (cited but not in .bib), unused (in .bib
     but not cited), self-citations exceeding `quality.max_self_citation_ratio`
     in `.paper-config.yml`, and entries older than 5 years (warning)
   - For `fix`: applies fixes for the simple cases identified by `check`
   - For `list`: produces a table

## Handoff schemas

None.

## Next steps

- `/paper-compile` to verify the new bibtex entries resolve correctly
- `/paper-draft <section>` to use the new citations in the section text
