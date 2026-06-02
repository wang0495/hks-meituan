---
name: paper-draft
description: Draft or revise a section of an academic LaTeX paper (abstract, intro, related work, method, experiments, results, discussion, conclusion). Uses TEEL paragraph framework and PaperConfig word budget.
argument-hint: "<section-name>"
paths: ["**/main.tex", "**/sections/*.tex", "**/sections/**/*.tex", "**/.paper-config.yml"]
allowed-tools: Read Write Edit Skill
---

# paper-draft

Draft or revise a section of an academic LaTeX paper.

## Project config loading (mandatory first step)

1. Walk up from cwd to filesystem root looking for `.paper-config.yml`.
2. If not found, stop and report:
   `"No paper project found. Run /paper-new first or cd into a paper project root."`
3. If found, parse the YAML and validate `schema_version == 3`.
4. Look for `.paper-config.local.yml` in the same directory; if present, merge
   its keys into the config (local overrides shared).
5. Resolve all paths in `paths.*` relative to the directory containing
   `.paper-config.yml` (NOT cwd). Reject absolute or `..`-prefixed paths with
   an error.

## What this skill does

Delegates to the `draft_writer` agent. The agent:
- Uses the TEEL paragraph framework (Topic-Evidence-Explanation-Link)
- Tracks word count against `word_target` from PaperConfig
- Applies the writing quality check from `references/writing_quality_check.md`
- Reads existing `sections/<section_name>.tex` if present (revision mode)
- Writes the resulting LaTeX into `sections/<section_name>.tex`

The section name is taken from `$ARGUMENTS`. Recognized values:
`abstract`, `introduction`, `related_work`, `method` (or `methodology`),
`experiments`, `results`, `discussion`, `conclusion`.

## Handoff schemas

This skill consumes:
- `StructureOutline` from `paper-new` via `structure_architect`
- `ArgumentBlueprint` from `argument_builder` (when invoked first)
- `RevisionRoadmap` from `paper-revise` via `revision_coach` (during revision)

It produces final section LaTeX text. See `references/handoff_schemas.md`.

## Next steps

- `/paper-figure` to add figures referenced in the new section
- `/paper-cite add ...` to add new citations
- `/paper-compile` to verify the paper still builds
