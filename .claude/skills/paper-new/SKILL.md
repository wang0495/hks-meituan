---
name: paper-new
description: Create and scaffold a new academic LaTeX paper project for NeurIPS, ICML, CVPR, IEEE TPAMI, ACL or EMNLP. Initializes .paper-config.yml, main.tex, sections/, Makefile.
argument-hint: "[venue] [subfield]"
disable-model-invocation: true
allowed-tools: Read Write Bash(mkdir *) Bash(touch *) Skill
---

# paper-new

Create a new academic LaTeX paper project: collect PaperConfig, write
`.paper-config.yml`, scaffold `main.tex / sections/ / figures/ / scripts/ /
references.bib / Makefile`, then hand off to the `structure_architect` agent
for outline design.

This skill is `disable-model-invocation: true`. The user must invoke it
explicitly via `/paper-new [venue] [subfield]`. Auto-trigger is intentionally
disabled because creating a project has filesystem side effects.

## What this skill does

1. Parse `$ARGUMENTS` for optional `venue` (string) and `subfield` (enum:
   ML, CV, NLP, systems, architecture, other).
2. If `.paper-config.yml` already exists in the cwd, ask the user whether to
   reinitialize. If yes, back up the old file as `.paper-config.yml.bak`.
3. Walk the user through the PaperConfig collection wizard:
   - venue (if not from argument)
   - venue_type (auto-detect from venue name when possible)
   - subfield (if not from argument)
   - page_limit (default by venue: NeurIPS 9, IEEE TPAMI null)
   - word_target (default by venue: NeurIPS 8000, IEEE TPAMI 12000)
4. Derive `template` and `citation_style` from venue (no user input):
   - NeurIPS / ICML -> `neurips_2026` + `natbib`
   - CVPR / ICCV -> `cvpr_2026` + `natbib`
   - IEEE TPAMI -> `IEEEtran` + `IEEE`
   - ACL / EMNLP -> `acl_2026` + `natbib`
   - other -> `article` + `natbib`
5. Write `.paper-config.yml` with `schema_version: 3` and the v2 superset
   fields documented in `docs/superpowers/specs/2026-04-11-academic-paper-plugin-design.md`
   section 3.4.1.
6. Scaffold the project tree:
   ```
   <project>/
   +-- main.tex
   +-- sections/
   |   +-- introduction.tex
   |   +-- related_work.tex
   |   +-- method.tex
   |   +-- experiments.tex
   |   +-- results.tex
   |   +-- discussion.tex
   |   +-- conclusion.tex
   +-- figures/
   +-- scripts/
   +-- references.bib (empty)
   +-- Makefile
   ```
7. Delegate to the `structure_architect` agent (via Skill or Task) to design
   the section outline. Pass the freshly written `.paper-config.yml` path so
   the agent can read it.

## Project config loading

This skill is the one that CREATES `.paper-config.yml`, so it does not require
an existing config. Steps 1-6 above produce the config. Step 7 starts using it.

## Handoff schemas

`structure_architect` produces `StructureOutline` (see references/handoff_schemas.md).

## Next steps

After scaffolding, common follow-ups:
- `/paper-draft introduction` to write the first section
- `/paper-figure bar comparing methods` to add figures
- `/paper-cite add Vaswani 2017 attention` to add citations
