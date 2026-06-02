---
name: paper-revise
description: Process external reviewer comments on an academic paper submission. Parses comments, classifies Major/Minor/Editorial, builds RevisionRoadmap, drafts response letter in Reviewer-Action-Change format.
argument-hint: "[<comments-file>]"
disable-model-invocation: true
paths: ["**/main.tex", "**/sections/*.tex", "**/.paper-config.yml"]
allowed-tools: Read Write Edit Skill
---

# paper-revise

Process external reviewer comments on an academic paper submission. Parses
comments into structured items, classifies them, builds a `RevisionRoadmap`,
and drafts a response letter in Reviewer-Action-Change (R-A-C) format.

This skill is `disable-model-invocation: true`. User must invoke explicitly
via `/paper-revise [<comments-file>]`. Manual-only because revision requires
external reviewer input that the user must provide.

## Project config loading (mandatory first step)

Same as `paper-draft`. If no `.paper-config.yml` is found, stop.

## What this skill does

1. Parse `$ARGUMENTS` for optional `<comments-file>` path. If not provided,
   prompt the user to paste the reviewer comments inline.
2. Delegate to the `revision_coach` agent. The agent:
   - Parses comments into individual items (one per reviewer paragraph)
   - Classifies each as Major / Minor / Editorial based on keywords and
     reviewer recommendation
   - Assigns priority P1/P2/P3
   - Detects cross-reviewer conflicts (where two reviewers ask for opposite
     changes)
   - Produces a `RevisionRoadmap` (see references/handoff_schemas.md)
3. Generate a response letter draft in R-A-C format using the
   `templates/revision_response.md` template. Each item gets a structured
   entry: Reviewer comment -> proposed Action -> resulting Change.
4. Save the roadmap to `build/revision_roadmap.json` and the draft response
   to `build/response_letter.md`.

## Handoff schemas

This skill produces `RevisionRoadmap` (via the `revision_coach` agent), which
`paper-draft` consumes to execute the revisions.

## Next steps

- `/paper-draft <section>` with the roadmap as input to execute the revisions
- `/paper-compile` after revisions to verify the paper still builds
