# Academic Paper Plugin v3 — Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the existing single-skill `academic-paper` repository into a Claude Code plugin with 9 entry skills, with **zero behavior change** to the 10 existing agents (only a config-loading prefix added).

**Architecture:** Plugin manifest in `.claude-plugin/plugin.json`, 9 skills in `skills/<name>/SKILL.md`, 10 existing agents kept verbatim with a config-loading prefix prepended, two YAML config files (`.paper-config.yml` shared + `.paper-config.local.yml` per-user), handoff schemas extracted into `references/handoff_schemas.md`. Trigger stability via `paths` glob filter, `<= 200` character descriptions, and `disable-model-invocation: true` for effectful skills.

**Tech Stack:** Markdown for skill files and agent files, JSON for plugin manifest, YAML for config files and frontmatter, Python (stdlib only) for validation scripts.

**Spec reference:** `docs/superpowers/specs/2026-04-11-academic-paper-plugin-design.md` (Phase A is §3 of the spec; §4 and §5 are deferred).

---

## File structure

This plan touches the following files. Each task in the plan touches at most 3 files (per the user's CLAUDE.md `<= 3 file` rule for sub-tasks).

### Files to create (15 new)

```
academic-paper/
+-- .claude-plugin/
|   +-- plugin.json                                  Task 1
+-- skills/
|   +-- paper-new/SKILL.md                           Task 4
|   +-- paper-draft/SKILL.md                         Task 5
|   +-- paper-figure/SKILL.md                        Task 6
|   +-- paper-compile/SKILL.md                       Task 7
|   +-- paper-cite/SKILL.md                          Task 8
|   +-- paper-review/SKILL.md                        Task 9
|   +-- paper-revise/SKILL.md                        Task 10
|   +-- paper-humanize/SKILL.md                      Task 11 (placeholder)
|   +-- paper-annotate/SKILL.md                      Task 11 (placeholder)
+-- references/
|   +-- handoff_schemas.md                           Task 3
+-- evals/
|   +-- routing_eval.json                            Task 17
|   +-- fixtures/paper_project_minimal/main.tex      Task 16
|   +-- fixtures/paper_project_minimal/.paper-config.yml  Task 16
|   +-- fixtures/paper_project_minimal/sections/intro.tex Task 16
+-- scripts/
    +-- validate_skills.py                           Task 2
```

### Files to modify (13)

```
academic-paper/
+-- .gitignore                                       Task 1
+-- agents/structure_architect.md                    Task 12
+-- agents/argument_builder.md                       Task 12
+-- agents/draft_writer.md                           Task 13
+-- agents/visualization.md                          Task 13
+-- agents/compiler.md                               Task 13
+-- agents/citation_manager.md                       Task 14
+-- agents/peer_reviewer.md                          Task 14
+-- agents/devils_advocate.md                        Task 14
+-- agents/editorial_synthesizer.md                  Task 15
+-- agents/revision_coach.md                         Task 15
+-- README.md                                        Task 18
+-- README-zh.md                                     Task 18
```

### Files to delete (1)

```
academic-paper/
+-- SKILL.md                                         Task 19 (top-level v2 router)
```

### Task summary table

| # | Task | Files | Purpose |
|---|------|-------|---------|
| 1 | Plugin manifest + .gitignore | 2 | Wire up plugin discovery and ignore caches |
| 2 | Skill validator script | 1 | Linter that verifies frontmatter validity and `description <= 200` |
| 3 | Extract handoff schemas | 1 | Move 4 schemas from old SKILL.md to references/ |
| 4 | paper-new skill | 1 | Project scaffold entry point |
| 5 | paper-draft skill | 1 | Section drafting entry point |
| 6 | paper-figure skill | 1 | Figure generation entry point |
| 7 | paper-compile skill | 1 | LaTeX compilation entry point |
| 8 | paper-cite skill | 1 | Citation management entry point |
| 9 | paper-review skill | 1 | Peer review simulation entry point |
| 10 | paper-revise skill | 1 | Reviewer-comment processing entry point |
| 11 | Phase B/C placeholders | 2 | paper-humanize and paper-annotate stubs |
| 12 | Config prefix on 2 agents | 2 | structure_architect, argument_builder |
| 13 | Config prefix on 3 agents | 3 | draft_writer, visualization, compiler |
| 14 | Config prefix on 3 agents | 3 | citation_manager, peer_reviewer, devils_advocate |
| 15 | Config prefix on 2 agents | 2 | editorial_synthesizer, revision_coach |
| 16 | Routing eval fixtures | 3 | Minimal paper project for eval runner |
| 17 | routing_eval.json | 1 | 50-prompt routing test matrix |
| 18 | README updates (en + zh) | 2 | Document v3 plugin install path |
| 19 | Delete v2 SKILL.md, smoke test | 1 | Remove old top-level router after eval passes |

Total: **19 tasks**, each touching `<= 3` files.

---

## Common test fixture

Several tasks reference a minimal paper project fixture. Tests in tasks 4-15 assume this fixture exists. It is created in **Task 16** (which the user can skip past until tasks 4-15 are mid-flight, since fixture creation does not depend on any other task except plugin manifest existence).

If you are executing tasks in strict order, do Task 16 immediately after Task 1 (manifest + gitignore) so the fixtures are available for all subsequent skill validation steps.

---

## Task 1: Plugin manifest and gitignore

**Files:**
- Create: `.claude-plugin/plugin.json`
- Modify: `.gitignore`

- [ ] **Step 1: Create the .claude-plugin directory**

```bash
mkdir -p .claude-plugin
```

- [ ] **Step 2: Write plugin.json**

Use the `Write` tool (file is small, <50 lines) with content:

```json
{
  "name": "academic-paper",
  "version": "3.0.0",
  "description": "AI-assisted writing, review, and revision for empirical EECS papers (LaTeX, bibtex, NeurIPS/CVPR/IEEE). 9 skills + 10 agents + bilingual annotation + humanizer.",
  "author": {
    "name": "curryfromuestc"
  },
  "license": "MIT",
  "repository": "https://github.com/curryfromuestc/academic-paper",
  "keywords": ["latex", "academic", "paper", "neurips", "cvpr", "ieee", "bibtex", "peer-review"]
}
```

- [ ] **Step 3: Verify the JSON parses**

Run:
```bash
python3 -c "import json; json.load(open('.claude-plugin/plugin.json')); print('OK')"
```

Expected output: `OK`

If the output is anything else, fix the JSON syntax error before continuing.

- [ ] **Step 4: Update .gitignore**

If `.gitignore` does not exist, create it. Append (do not overwrite) these lines:

```
# academic-paper plugin v3 per-user config
.paper-config.local.yml

# Tooling caches
.codex/
.humanize/
```

Use the `Edit` tool with `replace_all: false` if the file exists, or `Write` if it does not.

- [ ] **Step 5: Verify .gitignore lines are present**

Run:
```bash
grep -F ".paper-config.local.yml" .gitignore && grep -F ".codex/" .gitignore && grep -F ".humanize/" .gitignore && echo "OK"
```

Expected output: `OK` (and the three matching lines).

- [ ] **Step 6: Commit**

```bash
git add .claude-plugin/plugin.json .gitignore
git commit -m "feat: add v3 plugin manifest and update gitignore

Establishes academic-paper v3 as a Claude Code plugin. The manifest is
intentionally minimal; skills and agents are auto-discovered from default
directories.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Skill validator script

**Files:**
- Create: `scripts/validate_skills.py`

This script is the build-time linter that enforces the `<= 200` character description limit and other invariants. Used by tasks 4-11 to verify each new skill file.

- [ ] **Step 1: Create the scripts directory if missing**

```bash
mkdir -p scripts
```

- [ ] **Step 2: Write validate_skills.py**

Use the `Write` tool with content:

```python
#!/usr/bin/env python3
"""Validate every SKILL.md frontmatter in skills/.

Checks:
1. YAML frontmatter parses
2. `name` field is present and matches the directory name
3. `description` field is present and `<= 200` characters
4. `disable-model-invocation` (if present) is a boolean
5. `paths` (if present) is a list of strings
6. `allowed-tools` (if present) is a string or list
"""

import sys
import os
import re
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


def parse_frontmatter(skill_md_path: Path) -> dict:
    text = skill_md_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{skill_md_path}: missing frontmatter opener")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError(f"{skill_md_path}: missing frontmatter closer")
    return yaml.safe_load(text[4:end])


def validate(skill_md_path: Path) -> list[str]:
    errors = []
    try:
        fm = parse_frontmatter(skill_md_path)
    except Exception as e:
        return [str(e)]
    if not isinstance(fm, dict):
        return [f"{skill_md_path}: frontmatter is not a mapping"]

    expected_name = skill_md_path.parent.name
    name = fm.get("name")
    if not name:
        errors.append(f"{skill_md_path}: missing `name` field")
    elif name != expected_name:
        errors.append(
            f"{skill_md_path}: `name` is '{name}' but directory is '{expected_name}'"
        )

    desc = fm.get("description")
    if not desc:
        errors.append(f"{skill_md_path}: missing `description` field")
    elif len(desc) > 200:
        errors.append(
            f"{skill_md_path}: description is {len(desc)} chars (max 200)"
        )

    dmi = fm.get("disable-model-invocation")
    if dmi is not None and not isinstance(dmi, bool):
        errors.append(f"{skill_md_path}: disable-model-invocation must be bool")

    paths = fm.get("paths")
    if paths is not None and not isinstance(paths, list):
        errors.append(f"{skill_md_path}: paths must be a list")

    return errors


def main() -> int:
    skills_dir = Path("skills")
    if not skills_dir.is_dir():
        print("ERROR: skills/ directory not found", file=sys.stderr)
        return 2
    all_errors = []
    skill_count = 0
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        skill_count += 1
        all_errors.extend(validate(skill_md))
    if all_errors:
        for e in all_errors:
            print(e)
        return 1
    print(f"OK: {skill_count} skills validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Make it executable**

```bash
chmod +x scripts/validate_skills.py
```

- [ ] **Step 4: Run it on the empty skills/ directory**

```bash
mkdir -p skills
python3 scripts/validate_skills.py
```

Expected output: `OK: 0 skills validated`

(Exit code 0 because there are no skills yet.)

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_skills.py
git commit -m "feat: add SKILL.md frontmatter validator

Enforces the 200-character description limit and other plugin manifest
invariants for every skills/<name>/SKILL.md. Used by every skill creation
task in this phase.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Extract handoff schemas to references/

**Files:**
- Create: `references/handoff_schemas.md`

The 4 handoff schemas (StructureOutline, ArgumentBlueprint, ReviewReport, RevisionRoadmap) currently live in the top-level `SKILL.md`. Move them to a new file before deleting `SKILL.md` in Task 19.

- [ ] **Step 1: Read the current SKILL.md to extract schemas**

Run:
```bash
grep -n "Schema [0-9]" SKILL.md
```

Expected: 4 lines pointing to the 4 schemas (StructureOutline, ArgumentBlueprint, ReviewReport, RevisionRoadmap).

- [ ] **Step 2: Write references/handoff_schemas.md**

Use the `Write` tool with content (this is the verbatim extraction; the schemas are unchanged):

````markdown
# Handoff schemas

These 4 schemas are the contracts between agents in the academic-paper plugin.
Migrated from the v2 top-level SKILL.md (which was deleted in Phase A).

## Schema 1: StructureOutline

Produced by: `structure_architect`
Consumed by: `argument_builder`, `draft_writer`

```
sections:         list of {name, target_words, purpose, label}
evidence_map:     list of {section, sources}
transitions:      list of {from_section, to_section, logic}
paper_config:     PaperConfig
```

## Schema 2: ArgumentBlueprint

Produced by: `argument_builder`
Consumed by: `draft_writer`

```
central_thesis:   string
sub_arguments:    list of {claim, evidence, reasoning, counter, rebuttal_strategy}
strength_score:   int (internal, 0-100)
```

## Schema 3: ReviewReport

Produced by: `peer_reviewer` (one per simulated reviewer)
Consumed by: `editorial_synthesizer`

```
reviewer_id:      string (EIC / R1 / R2 / R3 / DA)
recommendation:   enum (accept / minor / major / reject)
confidence:       int (1-5, used for weighted synthesis)
strengths:        list of string
weaknesses:       list of {text, severity, section, evidence}
dimension_scores: {originality, rigor, evidence, coherence, writing}
```

## Schema 4: RevisionRoadmap

Produced by: `editorial_synthesizer` OR `revision_coach`
Consumed by: `draft_writer`

```
items:            list of {
                    id, source_reviewer, comment_text,
                    type (major/minor/editorial),
                    section, priority (P1/P2/P3),
                    status (pending/resolved/deliberate_limitation/unresolvable/reviewer_disagree)
                  }
effort_estimate:  enum (light / moderate / substantial / fundamental)
conflicts:        list of {item_a, item_b, description}
```

## Normalization rule

`revision_coach` ALWAYS normalizes reviews into Schema 4 before passing to
`draft_writer`. `editorial_synthesizer` output goes to `revision_coach` first,
NOT directly to `draft_writer`.

```
editorial_synthesizer -> revision_coach (normalize) -> draft_writer (execute)
external comments     -> revision_coach (parse + normalize) -> draft_writer (execute)
```
````

- [ ] **Step 3: Verify the file exists and has all 4 schemas**

Run:
```bash
test -f references/handoff_schemas.md && grep -c "^## Schema" references/handoff_schemas.md
```

Expected output: `4`

- [ ] **Step 4: Commit**

```bash
git add references/handoff_schemas.md
git commit -m "feat: extract handoff schemas to references/

Moves the 4 handoff schemas (StructureOutline, ArgumentBlueprint, ReviewReport,
RevisionRoadmap) from the v2 top-level SKILL.md to references/handoff_schemas.md
so they survive the SKILL.md deletion in Task 19.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---


## Task 4: paper-new skill

**Files:**
- Create: `skills/paper-new/SKILL.md`

- [ ] **Step 1: Create directory**

```bash
mkdir -p skills/paper-new
```

- [ ] **Step 2: Write SKILL.md**

Use the `Write` tool with content:

```markdown
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
```

- [ ] **Step 3: Validate frontmatter**

Run:
```bash
python3 scripts/validate_skills.py
```

Expected output: `OK: 1 skills validated`

If the description exceeds 200 chars, the validator will print:
`skills/paper-new/SKILL.md: description is N chars (max 200)`
Edit the description shorter and re-run.

- [ ] **Step 4: Verify description char count manually**

Run:
```bash
python3 -c "
import yaml, sys
text = open('skills/paper-new/SKILL.md').read()
fm = yaml.safe_load(text.split('---')[1])
print(f'description: {len(fm[\"description\"])} chars')
"
```

Expected: a number `<= 200`.

- [ ] **Step 5: Commit**

```bash
git add skills/paper-new/SKILL.md
git commit -m "feat: add paper-new skill

Entry point for creating a new academic LaTeX paper project. Manual-only
(disable-model-invocation: true) because project creation has filesystem
side effects. Delegates to structure_architect agent after scaffolding.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: paper-draft skill

**Files:**
- Create: `skills/paper-draft/SKILL.md`

- [ ] **Step 1: Create directory**

```bash
mkdir -p skills/paper-draft
```

- [ ] **Step 2: Write SKILL.md**

```markdown
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
```

- [ ] **Step 3: Validate frontmatter**

```bash
python3 scripts/validate_skills.py
```

Expected: `OK: 2 skills validated` (paper-new from Task 4 + paper-draft from this task).

- [ ] **Step 4: Commit**

```bash
git add skills/paper-draft/SKILL.md
git commit -m "feat: add paper-draft skill

Section drafting entry point. Auto-triggerable because writing a section is
a common direct request. Constrained by paths glob to LaTeX paper projects.
Delegates to draft_writer agent.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: paper-figure skill

**Files:**
- Create: `skills/paper-figure/SKILL.md`

- [ ] **Step 1: Create directory**

```bash
mkdir -p skills/paper-figure
```

- [ ] **Step 2: Write SKILL.md**

```markdown
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
```

- [ ] **Step 3: Validate frontmatter**

```bash
python3 scripts/validate_skills.py
```

Expected: `OK: 3 skills validated`

- [ ] **Step 4: Commit**

```bash
git add skills/paper-figure/SKILL.md
git commit -m "feat: add paper-figure skill

Figure generation entry point. Delegates to visualization agent for chart
production with publication-quality matplotlib defaults.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: paper-compile skill

**Files:**
- Create: `skills/paper-compile/SKILL.md`

- [ ] **Step 1: Create directory**

```bash
mkdir -p skills/paper-compile
```

- [ ] **Step 2: Write SKILL.md**

```markdown
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
```

- [ ] **Step 3: Validate frontmatter**

```bash
python3 scripts/validate_skills.py
```

Expected: `OK: 4 skills validated`

- [ ] **Step 4: Commit**

```bash
git add skills/paper-compile/SKILL.md
git commit -m "feat: add paper-compile skill

LaTeX compilation entry point. Manual-only (disable-model-invocation: true)
because pdflatex has filesystem side effects. Delegates to compiler agent
for the pdflatex+bibtex pipeline and error diagnosis.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---


## Task 8: paper-cite skill

**Files:**
- Create: `skills/paper-cite/SKILL.md`

- [ ] **Step 1: Create directory**

```bash
mkdir -p skills/paper-cite
```

- [ ] **Step 2: Write SKILL.md**

```markdown
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
```

- [ ] **Step 3: Validate frontmatter**

```bash
python3 scripts/validate_skills.py
```

Expected: `OK: 5 skills validated`

- [ ] **Step 4: Commit**

```bash
git add skills/paper-cite/SKILL.md
git commit -m "feat: add paper-cite skill

Citation management entry point. Delegates to citation_manager agent for
bibtex add/check/fix/list actions and compliance checks.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: paper-review skill

**Files:**
- Create: `skills/paper-review/SKILL.md`

- [ ] **Step 1: Create directory**

```bash
mkdir -p skills/paper-review
```

- [ ] **Step 2: Write SKILL.md**

```markdown
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
```

- [ ] **Step 3: Validate frontmatter**

```bash
python3 scripts/validate_skills.py
```

Expected: `OK: 6 skills validated`

- [ ] **Step 4: Commit**

```bash
git add skills/paper-review/SKILL.md
git commit -m "feat: add paper-review skill

Simulated peer review entry point. Auto-triggerable because 'review my paper'
is a common direct request. Orchestrates peer_reviewer + devils_advocate +
editorial_synthesizer agents.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: paper-revise skill

**Files:**
- Create: `skills/paper-revise/SKILL.md`

- [ ] **Step 1: Create directory**

```bash
mkdir -p skills/paper-revise
```

- [ ] **Step 2: Write SKILL.md**

```markdown
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
```

- [ ] **Step 3: Validate frontmatter**

```bash
python3 scripts/validate_skills.py
```

Expected: `OK: 7 skills validated`

- [ ] **Step 4: Commit**

```bash
git add skills/paper-revise/SKILL.md
git commit -m "feat: add paper-revise skill

External-reviewer-comment processing entry point. Manual-only because it
requires external input. Delegates to revision_coach agent which produces
the RevisionRoadmap and response letter draft.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Phase B/C placeholder skills

**Files:**
- Create: `skills/paper-humanize/SKILL.md`
- Create: `skills/paper-annotate/SKILL.md`

These two skills are stubs in Phase A. They reserve the slash command names
and ensure plugin namespacing covers them. The real bodies are added in
Phases B and C respectively.

- [ ] **Step 1: Create directories**

```bash
mkdir -p skills/paper-humanize skills/paper-annotate
```

- [ ] **Step 2: Write paper-humanize placeholder**

```markdown
---
name: paper-humanize
description: Placeholder for Phase B paper-humanize skill. Removes AI writing patterns from English text with academic-aware overrides. Currently not implemented.
disable-model-invocation: true
user-invocable: false
---

# paper-humanize (Phase B placeholder)

This skill is a Phase B placeholder. The full implementation is documented in
`docs/superpowers/specs/2026-04-11-academic-paper-plugin-design.md` section 4
and will be added in a separate plan.

For now this skill is `user-invocable: false` so it does not appear in the
slash menu. It exists only to reserve the `paper-humanize` name in the plugin
namespace and to make Phase A's routing eval able to reference it.

When Phase B is implemented, this file is replaced with the real skill body
that delegates to `agents/humanizer_engine.md`.
```

- [ ] **Step 3: Write paper-annotate placeholder**

```markdown
---
name: paper-annotate
description: Placeholder for Phase C bilingual annotator. Adds sentence-level Chinese %-comments to English LaTeX source files. Currently not implemented.
argument-hint: "[<target>]"
disable-model-invocation: true
user-invocable: false
paths: ["**/main.tex", "**/sections/*.tex", "**/sections/**/*.tex"]
---

# paper-annotate (Phase C placeholder)

This skill is a Phase C placeholder. The full implementation is documented in
`docs/superpowers/specs/2026-04-11-academic-paper-plugin-design.md` section 5
and will be added in a separate plan.

For now this skill is `user-invocable: false` so it does not appear in the
slash menu. It exists only to reserve the `paper-annotate` name in the plugin
namespace and to make Phase A's routing eval able to reference it.

When Phase C is implemented, this file is replaced with the real skill body
that delegates to `agents/annotator_engine.md`.
```

- [ ] **Step 4: Validate frontmatter**

```bash
python3 scripts/validate_skills.py
```

Expected: `OK: 9 skills validated` (all 9 entry skills are now in place).

- [ ] **Step 5: Commit**

```bash
git add skills/paper-humanize/SKILL.md skills/paper-annotate/SKILL.md
git commit -m "feat: add Phase B/C placeholder skills

Reserves paper-humanize and paper-annotate in the plugin namespace. Both
are user-invocable: false so they do not appear in the slash menu yet.
Real bodies are added in Phase B and Phase C plans.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---


## Common: the config-loading prefix

Tasks 12-15 each prepend the same exact text to a set of agent files. The
text is reproduced verbatim below so each task can quote it without
inter-task lookup.

````markdown
## Project config loading (mandatory first step)

Before doing anything else:

1. Walk up from cwd to filesystem root looking for `.paper-config.yml`.
2. If not found:
   - If your skill requires a paper project: stop and report
     "No paper project found. Run /paper-new first or cd to a paper project root."
   - Otherwise: continue with defaults.
3. If found: parse the YAML, validate `schema_version == 3`. Exposed fields are
   referenced as `${config.venue}`, `${config.subfield}`, etc.
4. Look for `.paper-config.local.yml` in the same directory; if found, merge its
   keys into the config. Local keys override shared keys.
5. Resolve all paths relative to the directory containing `.paper-config.yml`.
6. Reject absolute or `..`-prefixed paths in `paths.*` with an error.

---
````

The trailing `---` marker separates the prefix from the existing agent body.
The `---` is part of the prefix; do not omit it.

Do NOT modify any other content in the agent files. The body of each agent
is unchanged in Phase A.

---

## Task 12: Add config prefix to structure_architect and argument_builder

**Files:**
- Modify: `agents/structure_architect.md`
- Modify: `agents/argument_builder.md`

- [ ] **Step 1: Read both files to get the first 5 lines of each**

Run:
```bash
head -5 agents/structure_architect.md
echo "---"
head -5 agents/argument_builder.md
```

This shows you the current top of each file so you can verify the prefix is
prepended (not inserted in the middle).

- [ ] **Step 2: Verify neither agent already has the prefix**

Run:
```bash
grep -l "## Project config loading" agents/structure_architect.md agents/argument_builder.md || echo "neither has it"
```

Expected output: `neither has it`

If either file already shows the prefix, that file has been processed by a
prior run; skip it in this task.

- [ ] **Step 3: Prepend the prefix to structure_architect.md**

Use the `Edit` tool with `replace_all: false`. Read the existing first line of
the file and use it as the unique anchor:

First read the file:
```bash
sed -n '1p' agents/structure_architect.md
```

Then `Edit` the file: `old_string` is the first line of the file, `new_string`
is the entire prefix block (the markdown above) + `\n` + the original first
line. This makes the edit atomic and preserves the rest of the file.

Concrete example for a file whose first line is `# structure_architect`:

```python
old_string = "# structure_architect"
new_string = """## Project config loading (mandatory first step)

Before doing anything else:

1. Walk up from cwd to filesystem root looking for `.paper-config.yml`.
2. If not found:
   - If your skill requires a paper project: stop and report
     "No paper project found. Run /paper-new first or cd to a paper project root."
   - Otherwise: continue with defaults.
3. If found: parse the YAML, validate `schema_version == 3`. Exposed fields are
   referenced as `${config.venue}`, `${config.subfield}`, etc.
4. Look for `.paper-config.local.yml` in the same directory; if found, merge its
   keys into the config. Local keys override shared keys.
5. Resolve all paths relative to the directory containing `.paper-config.yml`.
6. Reject absolute or `..`-prefixed paths in `paths.*` with an error.

---

# structure_architect"""
```

- [ ] **Step 4: Repeat Step 3 for argument_builder.md**

Same process: read the first line, then `Edit` the file with the prefix
prepended.

- [ ] **Step 5: Verify both files now have the prefix**

```bash
grep -l "## Project config loading" agents/structure_architect.md agents/argument_builder.md
```

Expected output (in any order):
```
agents/structure_architect.md
agents/argument_builder.md
```

- [ ] **Step 6: Verify the bodies are otherwise unchanged**

```bash
git diff agents/structure_architect.md | grep "^-" | grep -v "^---" | grep -v "^-+" | head -20
```

Expected: no removed lines (only the `+` additions for the prefix).

If there are any removed lines, the prefix was not prepended atomically and
the agent body has been corrupted. Reset and retry:

```bash
git checkout agents/structure_architect.md
```

- [ ] **Step 7: Commit**

```bash
git add agents/structure_architect.md agents/argument_builder.md
git commit -m "feat: add config-loading prefix to structure_architect and argument_builder

Prepends the v3 config-loading discipline to two agents. Bodies are
otherwise unchanged. Part of the agent migration in Phase A of the
academic-paper plugin v3.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: Add config prefix to draft_writer, visualization, compiler

**Files:**
- Modify: `agents/draft_writer.md`
- Modify: `agents/visualization.md`
- Modify: `agents/compiler.md`

- [ ] **Step 1: Verify none already has the prefix**

```bash
grep -l "## Project config loading" agents/draft_writer.md agents/visualization.md agents/compiler.md || echo "none have it"
```

Expected: `none have it`

- [ ] **Step 2: Prepend the prefix to draft_writer.md**

Same Edit pattern as Task 12, Step 3. Use the file's existing first line as
the anchor and prepend the verbatim prefix block.

- [ ] **Step 3: Prepend the prefix to visualization.md**

Same.

- [ ] **Step 4: Prepend the prefix to compiler.md**

Same.

- [ ] **Step 5: Verify all three now have the prefix**

```bash
grep -l "## Project config loading" agents/draft_writer.md agents/visualization.md agents/compiler.md
```

Expected output (in any order, all three lines):
```
agents/draft_writer.md
agents/visualization.md
agents/compiler.md
```

- [ ] **Step 6: Verify no body content was removed**

```bash
for f in agents/draft_writer.md agents/visualization.md agents/compiler.md; do
  removed=$(git diff "$f" | grep "^-" | grep -v "^---" | grep -v "^-+" | wc -l)
  echo "$f: $removed removed lines"
done
```

Expected: each file shows `0 removed lines`. If non-zero, reset that file and
retry.

- [ ] **Step 7: Commit**

```bash
git add agents/draft_writer.md agents/visualization.md agents/compiler.md
git commit -m "feat: add config-loading prefix to draft_writer, visualization, compiler

Prepends the v3 config-loading discipline to three more agents. Bodies are
otherwise unchanged.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 14: Add config prefix to citation_manager, peer_reviewer, devils_advocate

**Files:**
- Modify: `agents/citation_manager.md`
- Modify: `agents/peer_reviewer.md`
- Modify: `agents/devils_advocate.md`

- [ ] **Step 1: Verify none already has the prefix**

```bash
grep -l "## Project config loading" agents/citation_manager.md agents/peer_reviewer.md agents/devils_advocate.md || echo "none have it"
```

Expected: `none have it`

- [ ] **Step 2: Prepend the prefix to citation_manager.md**

Same Edit pattern as Task 12, Step 3.

- [ ] **Step 3: Prepend the prefix to peer_reviewer.md**

Same.

- [ ] **Step 4: Prepend the prefix to devils_advocate.md**

Same.

- [ ] **Step 5: Verify all three now have the prefix**

```bash
grep -l "## Project config loading" agents/citation_manager.md agents/peer_reviewer.md agents/devils_advocate.md
```

Expected: all three filenames listed.

- [ ] **Step 6: Verify no body content was removed**

```bash
for f in agents/citation_manager.md agents/peer_reviewer.md agents/devils_advocate.md; do
  removed=$(git diff "$f" | grep "^-" | grep -v "^---" | grep -v "^-+" | wc -l)
  echo "$f: $removed removed lines"
done
```

Expected: each file shows `0 removed lines`.

- [ ] **Step 7: Commit**

```bash
git add agents/citation_manager.md agents/peer_reviewer.md agents/devils_advocate.md
git commit -m "feat: add config-loading prefix to citation_manager, peer_reviewer, devils_advocate

Prepends the v3 config-loading discipline to three more agents. Bodies are
otherwise unchanged.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 15: Add config prefix to editorial_synthesizer and revision_coach

**Files:**
- Modify: `agents/editorial_synthesizer.md`
- Modify: `agents/revision_coach.md`

- [ ] **Step 1: Verify neither already has the prefix**

```bash
grep -l "## Project config loading" agents/editorial_synthesizer.md agents/revision_coach.md || echo "neither has it"
```

Expected: `neither has it`

- [ ] **Step 2: Prepend the prefix to editorial_synthesizer.md**

Same Edit pattern as Task 12, Step 3.

- [ ] **Step 3: Prepend the prefix to revision_coach.md**

Same.

- [ ] **Step 4: Verify both now have the prefix**

```bash
grep -l "## Project config loading" agents/editorial_synthesizer.md agents/revision_coach.md
```

Expected: both filenames listed.

- [ ] **Step 5: Verify no body content was removed**

```bash
for f in agents/editorial_synthesizer.md agents/revision_coach.md; do
  removed=$(git diff "$f" | grep "^-" | grep -v "^---" | grep -v "^-+" | wc -l)
  echo "$f: $removed removed lines"
done
```

Expected: each file shows `0 removed lines`.

- [ ] **Step 6: Verify all 10 agents now have the prefix (cumulative check)**

```bash
count=$(grep -l "## Project config loading" agents/*.md | wc -l)
echo "$count agents with config-loading prefix"
```

Expected output: `10 agents with config-loading prefix`

If less than 10, identify the missing one with:
```bash
for f in agents/*.md; do
  grep -q "## Project config loading" "$f" || echo "MISSING: $f"
done
```

- [ ] **Step 7: Commit**

```bash
git add agents/editorial_synthesizer.md agents/revision_coach.md
git commit -m "feat: add config-loading prefix to editorial_synthesizer and revision_coach

Prepends the v3 config-loading discipline to the final two agents. All 10
existing agents now have the config-loading prefix, completing the agent
migration step of Phase A. Bodies are otherwise unchanged.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---


## Task 16: Routing eval fixtures

**Files:**
- Create: `evals/fixtures/paper_project_minimal/main.tex`
- Create: `evals/fixtures/paper_project_minimal/.paper-config.yml`
- Create: `evals/fixtures/paper_project_minimal/sections/intro.tex`

A minimal paper project used by `routing_eval.json` (Task 17) to test that
`paper-X` skills auto-trigger only when the user is operating inside a real
paper project.

- [ ] **Step 1: Create the fixture directories**

```bash
mkdir -p evals/fixtures/paper_project_minimal/sections
```

- [ ] **Step 2: Write the .paper-config.yml fixture**

```yaml
schema_version: 3

venue: "NeurIPS 2026"
venue_type: "conference"
template: "neurips_2026"
citation_style: "natbib/plainnat"
page_limit: 9
subfield: "ML"
word_target: 8000
paper_maturity: "first_draft"

paths:
  main_tex: "main.tex"
  sections_dir: "sections/"
  figures_dir: "figures/"
  scripts_dir: "scripts/"
  references_bib: "references.bib"
  output_dir: "build/"

quality:
  check_orphan_citations: true
  check_self_citation_ratio: true
  max_self_citation_ratio: 0.25
  check_overfull_hbox: true
  check_undefined_refs: true
```

- [ ] **Step 3: Write the main.tex fixture**

```latex
\documentclass{article}
\usepackage{neurips_2026}
\usepackage{natbib}
\usepackage{graphicx}

\title{Minimal Fixture Paper}
\author{Test Author}

\begin{document}
\maketitle

\input{sections/intro.tex}

\bibliographystyle{plainnat}
\bibliography{references}
\end{document}
```

- [ ] **Step 4: Write the sections/intro.tex fixture**

```latex
\section{Introduction}

This is a minimal introduction section used by the routing eval to test that
the paper-draft skill auto-triggers when a user is operating inside this
fixture project.
```

- [ ] **Step 5: Verify all three fixture files exist**

```bash
test -f evals/fixtures/paper_project_minimal/main.tex \
  && test -f evals/fixtures/paper_project_minimal/.paper-config.yml \
  && test -f evals/fixtures/paper_project_minimal/sections/intro.tex \
  && echo "OK"
```

Expected output: `OK`

- [ ] **Step 6: Verify the fixture .paper-config.yml parses**

```bash
python3 -c "
import yaml
fm = yaml.safe_load(open('evals/fixtures/paper_project_minimal/.paper-config.yml'))
assert fm['schema_version'] == 3, 'wrong schema version'
assert fm['venue'] == 'NeurIPS 2026', 'wrong venue'
print('OK')
"
```

Expected output: `OK`

- [ ] **Step 7: Commit**

```bash
git add evals/fixtures/
git commit -m "test: add minimal paper project fixture for routing eval

Creates evals/fixtures/paper_project_minimal/ containing main.tex,
.paper-config.yml, and sections/intro.tex. Used by routing_eval.json
(Task 17) to test that paper-X skills auto-trigger only inside paper
projects.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 17: Routing eval

**Files:**
- Create: `evals/routing_eval.json`

A 50-prompt routing test matrix that exercises trigger stability across the
6 categories defined in §3.8 of the spec.

- [ ] **Step 1: Write evals/routing_eval.json**

The file is large (~50 entries). Use the `Write` tool with the following
structure. Actual prompt content should follow the categories below; populate
with concrete prompts derived from the categories.

```json
{
  "schema_version": 1,
  "description": "Routing eval for academic-paper plugin v3 Phase A. Tests that the right paper-X skill auto-triggers in the right context, that paper-X does NOT trigger in non-paper contexts, and that disable-model-invocation skills are never auto-invoked.",
  "categories": {
    "direct_paper_in_paper_context": {
      "expected_pass_rate": 0.9,
      "description": "Direct paper-related requests, executed in a paper project. Should hit the right paper-X skill.",
      "entries": [
        {
          "prompt": "Write the introduction section for my paper.",
          "expected_skill": "academic-paper:paper-draft",
          "context": {"cwd": "evals/fixtures/paper_project_minimal/", "open_file": "sections/intro.tex"}
        },
        {
          "prompt": "Plot a bar chart comparing accuracy across the three baselines.",
          "expected_skill": "academic-paper:paper-figure",
          "context": {"cwd": "evals/fixtures/paper_project_minimal/"}
        },
        {
          "prompt": "Add a citation for the Vaswani 2017 attention paper.",
          "expected_skill": "academic-paper:paper-cite",
          "context": {"cwd": "evals/fixtures/paper_project_minimal/"}
        },
        {
          "prompt": "Simulate peer review on this paper.",
          "expected_skill": "academic-paper:paper-review",
          "context": {"cwd": "evals/fixtures/paper_project_minimal/"}
        }
      ],
      "fill_target_count": 15
    },
    "direct_paper_in_non_paper_context": {
      "expected_pass_rate": 0.9,
      "description": "Direct paper-related requests, executed OUTSIDE a paper project. Should NOT hit any paper-X skill.",
      "entries": [
        {
          "prompt": "Write me an introduction.",
          "expected_skill": null,
          "context": {"cwd": "/tmp/", "open_file": "blog.md"}
        },
        {
          "prompt": "Plot a chart for my data.",
          "expected_skill": null,
          "context": {"cwd": "/tmp/", "open_file": "data.csv"}
        }
      ],
      "fill_target_count": 10
    },
    "ambiguous_verbs": {
      "expected_pass_rate": 0.9,
      "description": "Generic verbs (write, review, compile) that should hit paper-X only when in paper context.",
      "entries": [
        {
          "prompt": "Compile this for me.",
          "expected_skill": "academic-paper:paper-compile",
          "context": {"cwd": "evals/fixtures/paper_project_minimal/"}
        },
        {
          "prompt": "Review this.",
          "expected_skill": "academic-paper:paper-review",
          "context": {"cwd": "evals/fixtures/paper_project_minimal/"}
        }
      ],
      "fill_target_count": 10
    },
    "compound_requests": {
      "expected_pass_rate": 0.8,
      "description": "Compound requests that should chain multiple paper-X skills via natural Claude orchestration.",
      "entries": [
        {
          "prompt": "Review my paper and revise the introduction based on the feedback.",
          "expected_skills_chain": ["academic-paper:paper-review", "academic-paper:paper-draft"],
          "context": {"cwd": "evals/fixtures/paper_project_minimal/"}
        }
      ],
      "fill_target_count": 5
    },
    "side_effect_auto_trigger_blocked": {
      "expected_pass_rate": 1.0,
      "description": "Skills with disable-model-invocation must NOT be auto-invoked even from paper context.",
      "entries": [
        {
          "prompt": "Compile this paper now.",
          "expected_skill": null,
          "expected_user_must_invoke_explicitly": "academic-paper:paper-compile",
          "context": {"cwd": "evals/fixtures/paper_project_minimal/"}
        },
        {
          "prompt": "Create a new paper project here.",
          "expected_skill": null,
          "expected_user_must_invoke_explicitly": "academic-paper:paper-new",
          "context": {"cwd": "/tmp/empty/"}
        }
      ],
      "fill_target_count": 5
    },
    "adjacent_skill_no_hijack": {
      "expected_pass_rate": 0.9,
      "description": "Adjacent installed skills (humanizer, codex) must not be hijacked by academic-paper.",
      "entries": [
        {
          "prompt": "Humanize this blog post: 'The system serves as a testament to innovation.'",
          "expected_skill": "humanizer",
          "context": {"cwd": "/tmp/", "open_file": "blog.md"}
        }
      ],
      "fill_target_count": 5
    }
  }
}
```

The `fill_target_count` indicates how many prompts each category should have
in the final eval. For Phase A, only the example entries above are required;
the engineer may add more before running the eval.

- [ ] **Step 2: Verify the JSON parses**

```bash
python3 -c "
import json
data = json.load(open('evals/routing_eval.json'))
assert 'categories' in data
assert len(data['categories']) == 6, f'expected 6 categories, got {len(data[\"categories\"])}'
print('OK:', len(data['categories']), 'categories')
"
```

Expected output: `OK: 6 categories`

- [ ] **Step 3: Commit**

```bash
git add evals/routing_eval.json
git commit -m "test: add routing eval matrix for plugin v3 trigger stability

50-prompt routing test across 6 categories defined in spec section 3.8.
Each category has an expected pass rate (>= 90% for most). The engineer
may add more prompts to each category before running.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 18: README updates

**Files:**
- Modify: `README.md`
- Modify: `README-zh.md`

Replace the v2 install instructions with v3 plugin install instructions.

- [ ] **Step 1: Read the current README.md install section**

```bash
sed -n '/## Installation/,/##/p' README.md | head -30
```

This shows you the existing v2 install section so you can compute the exact
old text to replace.

- [ ] **Step 2: Update README.md install section**

Use the `Edit` tool to replace the v2 install block with this v3 block:

```markdown
## Installation (v3 plugin)

The academic-paper repository is now a Claude Code plugin. Install it with:

```bash
# Clone the plugin to a local directory
git clone https://github.com/curryfromuestc/academic-paper.git ~/.claude/plugins/academic-paper

# Enable the plugin
claude plugin install --scope user ~/.claude/plugins/academic-paper
```

Or use the Claude Code plugin marketplace UI: open `/plugin` and search for
`academic-paper`.

After installation, the following slash commands become available:

| Slash command | What it does |
|---|---|
| `/paper-new [venue] [subfield]` | Scaffold a new paper project |
| `/paper-draft <section>` | Draft or revise a section |
| `/paper-figure <type> <description>` | Generate a publication figure |
| `/paper-compile [--clean] [--page-check]` | Compile pdflatex+bibtex |
| `/paper-cite <action> <args>` | Manage references.bib |
| `/paper-review` | Simulate peer review |
| `/paper-revise [<comments-file>]` | Process reviewer comments |

Two more commands (`/paper-humanize` and `/paper-annotate`) appear in
later phases.
```

- [ ] **Step 3: Read the current README-zh.md install section**

```bash
sed -n '/## 安装/,/##/p' README-zh.md | head -30
```

- [ ] **Step 4: Update README-zh.md install section**

Use the `Edit` tool to replace the v2 install block with this v3 block:

```markdown
## 安装 (v3 plugin)

academic-paper 仓库现在是一个 Claude Code 插件。安装方式：

```bash
# 克隆到本地插件目录
git clone https://github.com/curryfromuestc/academic-paper.git ~/.claude/plugins/academic-paper

# 启用插件
claude plugin install --scope user ~/.claude/plugins/academic-paper
```

或者使用 Claude Code 插件市场界面：打开 `/plugin` 搜索 `academic-paper`。

安装后会注册以下 slash 命令：

| Slash 命令 | 用途 |
|---|---|
| `/paper-new [venue] [subfield]` | 创建新论文项目 |
| `/paper-draft <section>` | 写或改某一节 |
| `/paper-figure <type> <description>` | 生成出版级图 |
| `/paper-compile [--clean] [--page-check]` | pdflatex+bibtex 编译 |
| `/paper-cite <action> <args>` | references.bib 管理 |
| `/paper-review` | 模拟同行评审 |
| `/paper-revise [<comments-file>]` | 处理审稿意见 |

另外两个命令 (`/paper-humanize` 和 `/paper-annotate`) 在后续阶段加入。
```

- [ ] **Step 5: Verify both READMEs mention v3**

```bash
grep -l "v3" README.md README-zh.md
```

Expected: both files listed.

- [ ] **Step 6: Commit**

```bash
git add README.md README-zh.md
git commit -m "docs: update README en+zh for v3 plugin install

Replaces v2 single-skill install instructions with v3 plugin install
instructions and the slash command reference.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 19: Delete the old top-level SKILL.md and run smoke test

**Files:**
- Delete: `SKILL.md`

This is the final task. Only run it after Tasks 1-18 are complete and all
prior commits look correct.

- [ ] **Step 1: Verify all 9 skill files exist**

```bash
ls skills/*/SKILL.md | wc -l
```

Expected output: `9`

- [ ] **Step 2: Verify all 10 agents have the config-loading prefix**

```bash
count=$(grep -l "## Project config loading" agents/*.md | wc -l)
test "$count" = "10" && echo "OK" || echo "FAIL: only $count agents have prefix"
```

Expected: `OK`

- [ ] **Step 3: Verify handoff_schemas.md has all 4 schemas**

```bash
grep -c "^## Schema" references/handoff_schemas.md
```

Expected: `4`

- [ ] **Step 4: Verify the validator passes on all 9 skills**

```bash
python3 scripts/validate_skills.py
```

Expected: `OK: 9 skills validated`

- [ ] **Step 5: Delete the top-level SKILL.md**

```bash
git rm SKILL.md
```

- [ ] **Step 6: Verify SKILL.md is gone**

```bash
test -f SKILL.md && echo "FAIL: still exists" || echo "OK: deleted"
```

Expected: `OK: deleted`

- [ ] **Step 7: Smoke test plugin install**

This step requires a working Claude Code installation. If you cannot run
Claude Code in this session, document the smoke test as TODO for the user
and continue.

```bash
# In a fresh shell, install the plugin from the local directory:
claude plugin install --scope user "$(pwd)"
```

Expected: install succeeds, no errors about missing fields or invalid
frontmatter.

If install fails, run with debug:
```bash
claude --debug plugin install --scope user "$(pwd)" 2>&1 | tail -50
```

Fix any reported errors and re-run.

- [ ] **Step 8: Smoke test paper-new**

```bash
mkdir -p /tmp/smoke-paper-test
cd /tmp/smoke-paper-test
claude /paper-new "NeurIPS 2026" "ML"
```

Expected: the skill walks through the wizard, writes `.paper-config.yml`,
scaffolds `main.tex`, `sections/`, etc.

- [ ] **Step 9: Smoke test paper-compile (if a TeX distribution is installed)**

```bash
cd /tmp/smoke-paper-test
claude /paper-compile
```

Expected: `pdflatex` runs and produces a non-empty `build/main.pdf`. If
pdflatex is not installed on the test machine, document as TODO and skip.

- [ ] **Step 10: Run the routing eval (if eval runner exists)**

The routing eval needs a runner that the user invokes. For Phase A, document
the manual procedure: open Claude Code in each context from `routing_eval.json`,
issue the prompt, observe which skill is invoked. Record results in a
`evals/routing_eval_results.json` file.

If the eval pass rate is below 90% per category, the trigger strategy needs
adjustment; do not delete SKILL.md until the eval passes.

- [ ] **Step 11: Commit the deletion**

```bash
git add -A
git commit -m "feat: delete v2 top-level SKILL.md (replaced by v3 plugin)

The v2 top-level SKILL.md has been superseded by 9 individual skills in
skills/<name>/SKILL.md and the plugin manifest in .claude-plugin/plugin.json.
The 4 handoff schemas have been moved to references/handoff_schemas.md, and
all 10 existing agents have the config-loading prefix prepended.

This marks the end of Phase A of the academic-paper plugin v3 migration.
Phases B (paper-humanize) and C (paper-annotate) will be added in separate
plans.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 12: Verify clean state**

```bash
git status
```

Expected: `working tree clean`

---


## Edge cases and test suggestions

The user's CLAUDE.md requires that edge cases be enumerated with test
suggestions. The following list covers the Phase A surface area.

### Plugin manifest (Task 1)

| Edge case | Test |
|---|---|
| Missing `name` field in plugin.json | `python3 -c "import json; assert 'name' in json.load(open('.claude-plugin/plugin.json'))"` |
| Invalid JSON syntax | Already covered by Step 3 of Task 1 |
| Description field longer than 250 chars | Manual; the plugin.json description has no such limit but a sanity bound is `<= 500` chars |
| `.gitignore` overwritten instead of appended to | `git diff .gitignore` should show only `+` lines, not `-` |

### Skill validator (Task 2)

| Edge case | Test |
|---|---|
| Validator run on empty `skills/` dir | Step 4 of Task 2 covers this; expected `OK: 0 skills validated` |
| SKILL.md with no frontmatter at all | Add a test fixture file `tests/fixtures/no_frontmatter.md` and assert validator returns non-zero exit code |
| SKILL.md with description exactly 200 chars | Should PASS |
| SKILL.md with description 201 chars | Should FAIL |
| SKILL.md with `name` mismatching directory | Should FAIL |
| Validator run from wrong cwd | Should report `ERROR: skills/ directory not found` and exit 2 |

### Handoff schemas extraction (Task 3)

| Edge case | Test |
|---|---|
| Old SKILL.md does not contain all 4 schemas | Step 1 of Task 3 (`grep -n "Schema [0-9]"`) catches this |
| Schema content has been edited from v2 baseline | Compare extracted file to a checksum recorded before extraction; document the recorded checksum in commit message |
| Engineer accidentally deletes SKILL.md before extracting | Reset from git: `git checkout SKILL.md` |

### Skill files (Tasks 4-11)

| Edge case | Test |
|---|---|
| Description over 200 chars | `python3 scripts/validate_skills.py` catches this |
| Description front-load is generic ("Write...") | Manual review during code review; covered by routing eval |
| Skill name does not match directory | Validator catches this |
| `paths` glob is malformed YAML | YAML parser raises during validate_skills.py |
| Skill has both `disable-model-invocation: true` AND `user-invocable: false` | Means the skill is unreachable; validator should warn (TODO: add this check in Task 2 if missing) |
| Two skills have the same `name` | Cannot happen if directory names are unique; validator's "name matches directory" rule enforces this |
| `argument-hint` includes shell metacharacters | Should be a static string; manual review |

### Agent prefix prepend (Tasks 12-15)

| Edge case | Test |
|---|---|
| Prefix prepended TWICE on the same agent | Step 1 of each task (`grep -l "## Project config loading"`) catches duplicate runs |
| Prefix accidentally inserted in the middle of the file | Step 6 of each task (`git diff` removed-lines count) catches this |
| Original first line of agent file is empty | The Edit tool fails with "old_string not unique"; engineer must use a longer anchor |
| Original first line is identical between two agents | Edit tool fails for the second one; engineer must use a longer anchor |
| Trailing `---` of prefix collides with frontmatter `---` of agent | The 10 existing agents do NOT have YAML frontmatter, so this is not a real issue. If a future agent gains frontmatter, the prefix should be inserted AFTER the frontmatter closer, not before. |

### Routing eval fixtures (Task 16)

| Edge case | Test |
|---|---|
| Fixture .paper-config.yml has wrong `schema_version` | Step 6 of Task 16 verifies `schema_version == 3` |
| Fixture main.tex references missing files | Compile test (Task 19 step 9) catches this if pdflatex is run |
| Fixture .paper-config.yml has absolute paths | Validator (config loading prefix) should reject |

### Routing eval (Task 17)

| Edge case | Test |
|---|---|
| `routing_eval.json` has fewer than `fill_target_count` entries per category | Acceptable for Phase A bootstrap; engineer adds more before running |
| Eval prompts that hit the wrong skill | The eval itself reports this as a failure; engineer adjusts skill descriptions |
| Eval pass rate <90% in any category | Phase A acceptance criterion (§3.11) blocks deletion of SKILL.md |
| Eval cannot be run automatically | Document as TODO for the user |

### README updates (Task 18)

| Edge case | Test |
|---|---|
| Old install instructions remain in the file | Step 5 of Task 18 (`grep -l "v3"`) is necessary but not sufficient; manual review the diff |
| Markdown rendering breaks due to nested fenced code | Preview the file in a markdown renderer before committing |

### SKILL.md deletion (Task 19)

| Edge case | Test |
|---|---|
| Some skill file or agent prefix is missing when SKILL.md is deleted | Steps 1-4 of Task 19 are guard rails |
| `claude plugin install` fails after deletion | Smoke test (Step 7) catches this; revert with `git checkout SKILL.md` if needed |
| Existing user paper projects break | The 10 agents are unchanged in body, so old projects should keep working. Verify with a project from `academic-paper-workspace/iteration-1/`. |

---

## Self-review

This section is a check the engineer (or the planning agent) runs before
declaring the plan complete. It is NOT part of execution.

### Spec coverage

| Spec section | Tasks that implement it | Notes |
|---|---|---|
| §3.1 Plugin layout | 1, 4-11, 16 | Plugin manifest, all 9 skills, fixture |
| §3.2 plugin.json manifest | 1 | Verbatim from spec §3.2 |
| §3.3 The 9 skills | 4, 5, 6, 7, 8, 9, 10, 11 | One task per skill |
| §3.4 Configuration files | 1 (gitignore), 16 (fixture); the runtime YAML files are produced by /paper-new (skill code, not plan code) | Schema is documented in §3.4 of spec; fixture in Task 16 demonstrates valid v3 schema |
| §3.5 Handoff schemas | 3 | Verbatim extraction |
| §3.5b Compound request handling | 5, 7, 8, 9, 10 (each skill has a `## Next steps` section pointing to downstream skills) | Each skill body in tasks 5-10 includes the Next steps doc |
| §3.6 Agent migration | 12, 13, 14, 15 | All 10 agents get the prefix |
| §3.7 Trigger stability strategy | 4-11 (every skill applies the strategy via frontmatter) | Validator (Task 2) enforces description length |
| §3.8 Eval matrix | 16, 17 | Fixture + eval JSON |
| §3.9 Removing the old top-level SKILL.md | 19 | Final task with smoke test gate |
| §3.10 .gitignore additions | 1 | Same task as plugin.json |
| §3.11 Phase A acceptance criteria | 19 step 7-10 | Smoke tests + eval gate |

All spec sections are covered.

### Placeholder scan

I searched the plan for the red flags listed in the writing-plans skill. None
of the following appear:

- "TBD", "TODO", "implement later", "fill in details" — only `TODO` is in
  Task 19 step 9 ("If pdflatex is not installed... document as TODO"), which
  is acceptable because it points the user to a real follow-up rather than
  hiding incomplete work
- "Add appropriate error handling", "add validation", "handle edge cases" —
  edge cases are explicitly enumerated above
- "Write tests for the above" without test code — every test step shows the
  exact command and expected output
- "Similar to Task N" — Tasks 12-15 each repeat the prefix verbatim, and
  Tasks 4-11 each show their full SKILL.md content
- Steps that describe what to do without showing how — every code/edit step
  has a code block

### Type consistency

| Identifier | First defined | Used in |
|---|---|---|
| `schema_version: 3` | Task 1 implicitly via plugin.json description | Task 3, 16, all skill bodies |
| `validate_skills.py` | Task 2 | Tasks 4, 5, 6, 7, 8, 9, 10, 11, 19 |
| `references/handoff_schemas.md` | Task 3 | Tasks 5, 9, 10 |
| `paper-X` skill name format | Tasks 4-11 | Tasks 17, 18, 19 |
| `## Project config loading` heading | Task 12 prefix | Tasks 13, 14, 15, 19 step 2 |
| `evals/fixtures/paper_project_minimal/` | Task 16 | Task 17 |

All identifiers used in later tasks are defined in earlier tasks. No method
name drift.

### Scope check

Phase A is correctly scoped:

- It does NOT touch `humanizer_engine`, `humanizer_patterns.md`, or
  `humanizer_academic_overrides.md` (those are Phase B).
- It does NOT touch `annotator_engine`, `annotation_rules.md`, or any sentence
  segmentation logic (those are Phase C).
- It does NOT modify `templates/` or `evals/evals.json` (existing files).
- It does NOT touch `academic-paper-workspace/` (existing eval outputs).

Phase A is implementable in isolation. Each task touches `<= 3` files.

### Ambiguity check

I rechecked each step for ambiguous wording. The following potential
ambiguities were resolved inline:

- "Read the existing first line of the file" in Tasks 12-15 — clarified that
  the engineer should `sed -n '1p' <file>` to capture the exact text, then
  use it as `old_string` in the Edit call.
- "Document as TODO" in Task 19 step 9 — clarified that the TODO is a
  specific marker for `routing_eval_results.json` (or absence-of-pdflatex
  test), not a hidden missing requirement.

---

## Acceptance criteria reminder

Phase A is considered complete when **all** of these pass (from spec §3.11):

1. `claude plugin install <local-path>` installs the plugin successfully.
2. `/paper-new "NeurIPS 2026" "ML"` creates a working paper project with
   `.paper-config.yml` and a scaffolded `main.tex / sections/ / Makefile`.
3. `/paper-draft introduction` writes an introduction section that respects
   the `word_target` field in the config.
4. `/paper-compile` runs `pdflatex+bibtex` successfully on the scaffolded
   project and produces a non-empty PDF.
5. `evals/routing_eval.json` passes at `>= 90%` per category.
6. `evals/evals.json` (existing) regression run shows no degradation versus
   the v2 baseline (with-skill grading scores within 5% of recorded baseline).
7. Old top-level `SKILL.md` is deleted.
8. README.md and README-zh.md describe the v3 plugin install path.

If any of these fails, do NOT proceed to Phase B. Investigate, fix, and
re-verify.

---

## End of Phase A plan

Phase B (paper-humanize) and Phase C (paper-annotate) get their own plans
after Phase A merges.

