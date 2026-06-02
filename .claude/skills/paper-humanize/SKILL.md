---
name: paper-humanize
description: Remove AI writing patterns from English text with academic-aware overrides. Auto-detects LaTeX context for passive voice, hyphenated compounds, title case, curly quotes handling.
argument-hint: "[<file-or-paste>]"
disable-model-invocation: true
allowed-tools: Read Edit Skill
---

# paper-humanize

Apply the 29 AI-writing-detection patterns from
`references/humanizer_patterns.md` to a chunk of English text, with
academic-aware overrides from `references/humanizer_academic_overrides.md`
when invoked inside a paper project (`.paper-config.yml` present).

This skill is `disable-model-invocation: true`. Users must invoke it
explicitly via `/paper-humanize [<file-or-paste>]`. Manual-only because
rewriting prose is destructive -- the user must consent.

## Project config loading (mandatory first step)

1. Walk up from cwd to filesystem root looking for `.paper-config.yml`.
2. If found: parse the YAML, validate `schema_version == 3`, set
   `mode = "academic"`. Look for `.paper-config.local.yml` and let
   `humanizer.mode` override the auto-detected mode.
3. If not found: set `mode = "general"`. The skill still runs, but no
   academic overrides apply.

## What this skill does

1. Parse `$ARGUMENTS`:
   - If a file path is given, Read the file's content as the input text.
   - If no argument, prompt the user to paste the text inline.
2. Delegate to the `humanizer_engine` agent. Pass the text and the
   detected mode.
3. The agent runs the apply -> self-audit -> final loop (see
   `agents/humanizer_engine.md`) and returns the cleaned text.
4. If the input came from a file, present a unified diff of the
   proposed changes for the user to approve before writing back.
5. If the input was pasted inline, just print the cleaned output.

## Mode reference

| Mode | When | Patterns applied |
|---|---|---|
| `academic` | `.paper-config.yml` found in cwd ancestor chain | 29 patterns minus 2 SKIP-conditional, with 10 MODIFY rules respecting academic overrides |
| `general` | No `.paper-config.yml` found | All 29 patterns, no exceptions |

The two modes are documented fully in `references/humanizer_academic_overrides.md`.

## Coexistence with the standalone humanizer plugin

This skill (`academic-paper:paper-humanize`) is namespaced and does NOT
conflict with the separate `humanize` plugin from humania-org. Use this
one inside paper projects, the other for general-purpose text.

## Next steps

- `/paper-draft <section>` to apply the cleaned text back into a section
- `/paper-compile` to verify the LaTeX still builds after rewriting
