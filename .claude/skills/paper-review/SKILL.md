---
name: paper-review
description: Simulate peer review on an academic LaTeX paper draft. Generates 5 reviewer personas, runs independent reviews with 5-dimension scoring, devils-advocate stress tests, editorial synthesis decision.
argument-hint: "[--sections=<list>]"
paths: ["**/main.tex", "**/sections/*.tex", "**/.paper-config.yml"]
allowed-tools: Read Skill
---

# paper-review

Simulate peer review on an academic LaTeX paper draft. Runs the full review
pipeline: 5 reviewer personas -> 5-dimension scoring -> devils-advocate
stress test -> editorial synthesis decision -> revision roadmap.

## Project config loading (mandatory first step)

Same as `paper-draft`. If no `.paper-config.yml` is found, stop.

## What this skill does

1. Parse `$ARGUMENTS` for optional `--sections=<comma-list>` to limit review
   to specific sections (default: review the whole paper).
2. Delegate to the `peer_reviewer` agent. The agent:
   - Generates 5 reviewer personas tailored to the paper's `subfield`
   - For each persona, produces an independent `ReviewReport` with
     5-dimension scores (originality, rigor, evidence, coherence, writing)
   - Each `ReviewReport` includes recommendation (accept/minor/major/reject)
3. Invoke the `devils_advocate` agent to run 7 stress tests on the same
   draft (counter-arguments, cherry-picking detection, "So What?" test,
   etc.). Output is a 6th `ReviewReport` with `reviewer_id: DA`.
4. Invoke the `editorial_synthesizer` agent to weight all 6 reports by
   confidence and produce a final decision plus a `RevisionRoadmap`.
5. Save the review report to `build/review_report.md` (using the
   `templates/review_report.md` template format).

## Handoff schemas

This skill orchestrates multiple agents that produce:
- `ReviewReport` (one per reviewer, 5+1 total)
- `RevisionRoadmap` (final, from editorial_synthesizer)

See `references/handoff_schemas.md` for full schemas.

## Next steps

- `/paper-revise` (when external reviewer comments arrive) to compare with
  this simulated review
- `/paper-draft <section>` to address the highest-priority items from the
  RevisionRoadmap
