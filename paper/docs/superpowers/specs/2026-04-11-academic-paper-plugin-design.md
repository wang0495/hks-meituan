---
date: 2026-04-11
status: draft
author: curryfromuestc (with Claude Opus 4.6)
supersedes: top-level SKILL.md (v2 single-skill design)
related:
  - /home/yanggl/code/humanizer (sibling general-text humanizer skill, kept as-is)
  - References: codex review (gpt-5.4:high), Claude Code official plugin docs
phases:
  - phase-a: plugin migration (this spec, implementable now)
  - phase-b: paper-humanize with academic overrides (designed here, separate plan later)
  - phase-c: bilingual annotator (designed here, separate plan later)
---

# Academic Paper Plugin v3 — design specification

## 1. Context and motivation

### 1.1 Current state (v2)

The `academic-paper` repository today is a **single Claude Code skill** consisting of:

- One top-level `SKILL.md` that routes user intent to one of 10 agents
- 10 agent files in `agents/` (structure_architect, argument_builder, draft_writer,
  visualization, compiler, citation_manager, peer_reviewer, devils_advocate,
  editorial_synthesizer, revision_coach)
- A `references/writing_quality_check.md` covering 25 AI-typical terms
- Templates (`templates/`) for LaTeX paper, review report, response letter
- An eval harness in `evals/` and recorded outputs in `academic-paper-workspace/`

### 1.2 Problems with v2

The user reports three concrete problems with v2:

1. **Trigger instability.** The single SKILL.md description packs many trigger
   phrases ("write a paper", "draft introduction", "generate figure", "review my
   paper", ...) and competes with other installed skills (`superpowers`,
   `plugin-dev`, `spml`, `humanizer`, `codex`, etc.) that own overlapping verbs.
   Claude sometimes triggers the wrong skill or fails to trigger this one at all.

2. **No "humanize" pass.** v2 has a 25-term lint in
   `references/writing_quality_check.md`, but no full removal of AI-writing
   patterns. The user wants the 28-pattern Wikipedia "Signs of AI writing" guide
   integrated, with academic-specific overrides so the rules do not destroy
   legitimate academic style.

3. **Reading gap for the user.** The user only knows basic Python and C syntax;
   reading a finished English LaTeX paper is hard. Each English sentence in the
   paper should be followed by a Chinese `%` comment that explains what it says.
   The compiled PDF must remain English-only (since `%` is stripped at compile
   time).

### 1.3 Goals of v3

- Convert the repository to a Claude Code plugin so it installs via
  `claude plugin install` and benefits from plugin namespacing.
- Fix trigger stability by combining narrow descriptions, `paths` glob filters,
  and (where appropriate) `disable-model-invocation: true`.
- Add a `paper-humanize` skill (namespaced as `academic-paper:paper-humanize`)
  that applies 28 AI-writing patterns with academic overrides.
- Add a `paper-annotate` skill that inserts sentence-level Chinese `%` comments
  into English LaTeX source files, with hash-based refresh.
- Preserve full backward compatibility for all 10 existing agents (no agent
  rewrite, only frontmatter additions and a config-loading prefix).

### 1.4 Non-goals

- Touching the existing `academic-paper-workspace/` evaluation outputs.
- Translating documents to Chinese as primary output (only `%` annotations).
- Supporting non-EECS papers (humanities, life sciences, etc.).
- Replacing the user's separate `~/code/humanizer` skill, which stays as the
  general-text humanizer.

## 2. Three-phase plan

The total surface area of v3 is large (~22 new files, ~13 modified). To control
risk, work is sequenced into three phases. Each phase is independently
shippable, independently testable, and produces a working plugin.

```
+-------------------------------------------------------------+
| Phase A: Plugin migration                                   |
|   - Create plugin manifest (.claude-plugin/plugin.json)     |
|   - Move 9 entry points into skills/                        |
|   - Add config-loading prefix to 10 existing agents         |
|   - Introduce .paper-config.yml + .paper-config.local.yml   |
|   - Move handoff schemas into references/handoff_schemas.md |
|   - Add routing eval                                        |
|   - Remove old top-level SKILL.md                           |
| Outcome: zero behavior change. Same agents, new packaging.  |
+-------------------------------------------------------------+
                            |
                            v
+-------------------------------------------------------------+
| Phase B: paper-humanize with academic overrides             |
|   - Add skills/paper-humanize/SKILL.md                      |
|   - Add agents/humanizer_engine.md                          |
|   - Add references/humanizer_patterns.md (28 patterns)      |
|   - Add references/humanizer_academic_overrides.md          |
|   - Add humanizer_regression eval                           |
| Outcome: /paper-humanize works on academic and general text |
+-------------------------------------------------------------+
                            |
                            v
+-------------------------------------------------------------+
| Phase C: Bilingual annotator                                |
|   - Add skills/paper-annotate/SKILL.md                      |
|   - Add agents/annotator_engine.md                          |
|   - Add references/annotation_rules.md                      |
|   - Add annotation_idempotence eval                         |
|   - Wire annotator into draft_writer (optional)             |
| Outcome: each English sentence gets a `% @zh[xxxx]:` line   |
+-------------------------------------------------------------+
```

The rest of this document is the **detailed Phase A design**, followed by
high-level **Phase B and Phase C designs** that will be expanded into their
own implementation specs after Phase A merges.


## 3. Phase A — plugin migration

### 3.1 Plugin layout

```
academic-paper/
+-- .claude-plugin/
|   +-- plugin.json                          # plugin manifest (Phase A)
+-- skills/
|   +-- paper-new/SKILL.md                   # Phase A: outline + scaffold project
|   +-- paper-draft/SKILL.md                 # Phase A: write/revise sections
|   +-- paper-figure/SKILL.md                # Phase A: matplotlib figures
|   +-- paper-compile/SKILL.md               # Phase A: pdflatex+bibtex
|   +-- paper-cite/SKILL.md                  # Phase A: bib management
|   +-- paper-review/SKILL.md                # Phase A: simulated peer review
|   +-- paper-revise/SKILL.md                # Phase A: handle reviewer comments
|   +-- paper-humanize/SKILL.md              # Phase B (placeholder in A)
|   +-- paper-annotate/SKILL.md              # Phase C (placeholder in A)
+-- agents/
|   +-- structure_architect.md               # Phase A: add config-loading prefix
|   +-- argument_builder.md                  # Phase A: add config-loading prefix
|   +-- draft_writer.md                      # Phase A: add config-loading prefix
|   +-- visualization.md                     # Phase A: add config-loading prefix
|   +-- compiler.md                          # Phase A: add config-loading prefix
|   +-- citation_manager.md                  # Phase A: add config-loading prefix
|   +-- peer_reviewer.md                     # Phase A: add config-loading prefix
|   +-- devils_advocate.md                   # Phase A: add config-loading prefix
|   +-- editorial_synthesizer.md             # Phase A: add config-loading prefix
|   +-- revision_coach.md                    # Phase A: add config-loading prefix
|   +-- humanizer_engine.md                  # Phase B (added later)
|   +-- annotator_engine.md                  # Phase C (added later)
+-- references/
|   +-- writing_quality_check.md             # existing, kept as-is in Phase A
|   +-- handoff_schemas.md                   # NEW Phase A: 4 schemas extracted
|   +-- humanizer_patterns.md                # Phase B
|   +-- humanizer_academic_overrides.md      # Phase B
|   +-- annotation_rules.md                  # Phase C
+-- templates/
|   +-- research_paper.tex                   # untouched
|   +-- review_report.md                     # untouched
|   +-- revision_response.md                 # untouched
+-- evals/
|   +-- evals.json                           # extended in Phase A with routing tests
|   +-- routing_eval.json                    # NEW Phase A
|   +-- annotation_idempotence.json          # Phase C
|   +-- humanizer_regression.json            # Phase B
+-- academic-paper-workspace/                # untouched
+-- README.md                                # updated to describe v3 plugin install
+-- README-zh.md                             # updated to describe v3 plugin install
+-- .gitignore                               # add .paper-config.local.yml, .codex, .humanize
```

The old top-level `SKILL.md` is **deleted** at the end of Phase A. Until then,
both the old SKILL.md and the new `skills/` entries coexist with the new ones
taking precedence (plugin-namespaced skills override top-level skills of the
same name).

### 3.2 plugin.json manifest

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

The manifest is intentionally minimal. Skills and agents auto-discover from
default `skills/` and `agents/` directories. No `commands/` section, no custom
paths.

### 3.3 The 9 skills — frontmatter and behavior

Each skill is a directory `skills/<name>/` containing a single `SKILL.md`. The
strategy for trigger stability rests on three pillars:

1. **`description` is `<= 200` characters** so the front-loaded use case is never
   truncated by the 250-char limit.
2. **`paths` glob filters** the skill to LaTeX paper projects. When the user is
   editing other files (Python, blog, README), the skill is not even visible
   to the matcher.
3. **`disable-model-invocation: true`** for skills with side effects, so they
   never auto-trigger. The user must invoke them explicitly via slash command.

Common `paths` glob used by all paper-X skills (with the exception of
`paper-humanize`, which has no `paths` filter so it works on any text):

```yaml
paths:
  - "**/main.tex"
  - "**/sections/*.tex"
  - "**/sections/**/*.tex"
  - "**/.paper-config.yml"
  - "**/references.bib"
```

#### 3.3.1 paper-new

```yaml
---
name: paper-new
description: Create and scaffold a new academic LaTeX paper project for NeurIPS, ICML, CVPR, IEEE TPAMI, ACL or EMNLP. Initializes .paper-config.yml, main.tex, sections/, Makefile.
argument-hint: "[venue] [subfield]"
disable-model-invocation: true
allowed-tools: Read Write Bash(mkdir *) Bash(touch *) Skill
---
```

`disable-model-invocation: true` because creating a new project is a deliberate
action with filesystem side effects.

#### 3.3.2 paper-draft

```yaml
---
name: paper-draft
description: Draft or revise a section of an academic LaTeX paper (abstract, intro, related work, method, experiments, results, discussion, conclusion). Uses TEEL paragraph framework and PaperConfig word budget.
argument-hint: "<section-name>"
paths: ["**/main.tex", "**/sections/*.tex", "**/sections/**/*.tex", "**/.paper-config.yml"]
allowed-tools: Read Write Edit Skill
---
```

Auto-trigger allowed: writing a section is the most common request and benefits
from natural-language matching.

#### 3.3.3 paper-figure

```yaml
---
name: paper-figure
description: Generate publication-quality matplotlib or seaborn figures for an academic LaTeX paper. 11 EECS chart types (bar, line, heatmap, ROC, ablation, scaling). Output to figures/*.pdf.
argument-hint: "<chart-type> <description>"
paths: ["**/main.tex", "**/figures/", "**/scripts/*.py", "**/.paper-config.yml"]
allowed-tools: Read Write Edit Bash(python *) Skill
---
```

#### 3.3.4 paper-compile

```yaml
---
name: paper-compile
description: Compile an academic LaTeX paper project with pdflatex and bibtex. Diagnoses LaTeX errors, checks page-limit compliance, runs bibtex, fixes undefined references and overfull-hbox warnings.
argument-hint: "[--clean] [--page-check]"
disable-model-invocation: true
paths: ["**/main.tex", "**/.paper-config.yml"]
allowed-tools: Read Bash(pdflatex *) Bash(bibtex *) Bash(make *) Bash(latexmk *) Skill
---
```

`disable-model-invocation: true` because compilation runs an external tool and
writes to `build/`.

#### 3.3.5 paper-cite

```yaml
---
name: paper-cite
description: Manage references.bib in an academic LaTeX paper project. Add bibtex entries, validate natbib citation commands, check citation compliance (orphan citations, self-citation ratio, source currency).
argument-hint: "<action> <args>"
paths: ["**/references.bib", "**/main.tex", "**/sections/*.tex", "**/.paper-config.yml"]
allowed-tools: Read Write Edit Skill
---
```

#### 3.3.6 paper-review

```yaml
---
name: paper-review
description: Simulate peer review on an academic LaTeX paper draft. Generates 5 reviewer personas, runs independent reviews with 5-dimension scoring, devils-advocate stress tests, editorial synthesis decision.
argument-hint: "[--sections=<list>]"
paths: ["**/main.tex", "**/sections/*.tex", "**/.paper-config.yml"]
allowed-tools: Read Skill
---
```

Auto-trigger allowed: "review my paper" is a common direct request.

#### 3.3.7 paper-revise

```yaml
---
name: paper-revise
description: Process external reviewer comments on an academic paper submission. Parses comments, classifies Major/Minor/Editorial, builds RevisionRoadmap, drafts response letter in Reviewer-Action-Change format.
argument-hint: "[<comments-file>]"
disable-model-invocation: true
paths: ["**/main.tex", "**/sections/*.tex", "**/.paper-config.yml"]
allowed-tools: Read Write Edit Skill
---
```

`disable-model-invocation: true` because revision requires external reviewer
input that the user must provide explicitly.

#### 3.3.8 paper-humanize (Phase B placeholder)

In Phase A, this file exists with only a stub frontmatter and a body that says
"Phase B not yet implemented; see Phase B spec." It is created so plugin
namespacing reserves the name and the slash command appears in the menu. The
plugin uses the name `paper-humanize` rather than `humanizer` so that the
slash command `/paper-humanize` does not collide with the user's separate
`~/code/humanizer` skill at the user level.

```yaml
---
name: paper-humanize
description: Placeholder for Phase B paper-humanize skill. Removes AI writing patterns from English text with academic-aware overrides. Currently not implemented.
disable-model-invocation: true
user-invocable: false
---
```

#### 3.3.9 paper-annotate (Phase C placeholder)

Same pattern: stub file in Phase A, real content in Phase C.

```yaml
---
name: paper-annotate
description: Placeholder for Phase C bilingual annotator. Adds sentence-level Chinese %-comments to English LaTeX source files. Currently not implemented.
argument-hint: "[<target>]"
disable-model-invocation: true
user-invocable: false
paths: ["**/main.tex", "**/sections/*.tex", "**/sections/**/*.tex"]
---
```

`user-invocable: false` hides the placeholder from the menu until Phase C.


### 3.4 Configuration files

Two YAML files. The shared file is committed to git; the local file is
gitignored.

#### 3.4.1 `.paper-config.yml` (shared, committed)

This file is a **strict superset of v2 PaperConfig**. Every v2 field keeps its
exact name and semantics so the 10 existing agents read it without modification.
New v3 fields are additive and the existing agents simply ignore them.

```yaml
# .paper-config.yml -- academic-paper plugin v3
# Created by /paper-new on YYYY-MM-DD; safe to edit by hand.

schema_version: 3

# === v2 fields, UNCHANGED for backward compatibility ===
venue: "NeurIPS 2026"
venue_type: "conference"          # conference | journal | workshop
template: "neurips_2026"          # article | neurips_2026 | IEEEtran | acmart | custom
citation_style: "natbib/plainnat" # natbib/plainnat | IEEE | acm
page_limit: 9                     # int or null
subfield: "ML"                    # ML | CV | NLP | systems | architecture | other
word_target: 8000                 # int or null
paper_maturity: "first_draft"     # first_draft | revised | pre_submission

# === v3 additive fields (existing agents safely ignore) ===
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

Validation rules (enforced by the config-loading prefix in every skill):

| Field | Rule |
|---|---|
| `schema_version` | must equal `3`; otherwise warn and offer migration |
| `venue` | non-empty string |
| `venue_type` | enum: `conference`, `journal`, `workshop` |
| `template` | string; arbitrary value allowed for `custom` |
| `citation_style` | enum or string; standard values listed above |
| `page_limit` | positive integer or null |
| `subfield` | enum: `ML`, `CV`, `NLP`, `systems`, `architecture`, `other` |
| `word_target` | positive integer or null |
| `paper_maturity` | enum: `first_draft`, `revised`, `pre_submission` |
| `paths.*` | all values must be relative; reject absolute or `..`-prefixed |
| `quality.max_self_citation_ratio` | float in `[0, 1]` |

#### 3.4.2 `.paper-config.local.yml` (per-user, gitignored)

Holds personal preferences that should not be shared between coauthors.
The reason for the split is that bilingual annotation is a single-user feature
and humanizer aggressiveness is taste.

```yaml
# .paper-config.local.yml -- per-user, NOT committed
# This file is gitignored. Each coauthor has their own.

annotation:
  enabled: true
  granularity: "sentence"        # sentence | paragraph
  skip:
    - "math"                     # math envs and inline $...$
    - "code"                     # verbatim, lstlisting, minted
    - "bibtex"                   # references.bib entries
  preserve_user_comments: true   # never overwrite non-@zh user comments

humanizer:
  mode: "academic"               # academic | general | auto
  auto_run_after_drafting: false # whether draft_writer auto-runs humanizer
                                 # NOTE: this flag has no effect in Phase A
                                 # (humanizer does not exist yet); it is
                                 # honored starting in Phase B.
```

If `.paper-config.local.yml` is missing, the system applies defaults shown
above. Local file is therefore optional. Phase A code reads and validates the
file but does not act on `humanizer.*` or `annotation.*` keys; those are
honored in Phases B and C respectively.

#### 3.4.3 Discovery rule

Both files are located by **walking up from `cwd` to filesystem root**, the
same way `git` finds `.git`. The first directory that contains
`.paper-config.yml` is the paper project root. All paths in the config are
resolved relative to that directory, not `cwd`.

If no `.paper-config.yml` is found, behavior depends on the skill:

- Skills that REQUIRE a paper project (`paper-draft`, `paper-figure`,
  `paper-compile`, `paper-cite`, `paper-review`, `paper-revise`,
  `paper-annotate`): print an error
  `"No paper project found. Run /paper-new first or cd into a paper project root."`
  and stop.
- Skills that do NOT require a paper project (`paper-new`, `paper-humanize`):
  proceed with defaults. `paper-humanize` enters general mode.

### 3.5 Handoff schemas

The 4 handoff schemas in v2 SKILL.md (StructureOutline, ArgumentBlueprint,
ReviewReport, RevisionRoadmap) move to a new file
`references/handoff_schemas.md`. Skills that participate in a multi-agent
flow document their downstream agent's handoff schema with a one-line
reference like:

```markdown
## Handoff schemas
The `revision_coach` agent produces `RevisionRoadmap` (see
references/handoff_schemas.md). Downstream `paper-draft` consumes it.
```

The schemas themselves are unchanged from v2. Quoted from the existing SKILL.md
and moved verbatim. The reason for moving them is that v2 stored them in the
top-level SKILL.md, which is being deleted.

### 3.5b Compound request handling

In v2, the top-level SKILL.md was the central router that handled compound
requests like "review my paper and then revise the introduction." In v3 there
is no router skill (per user decision in §6 of brainstorm). Compound requests
are handled by Claude itself chaining individual skills:

1. Each skill's SKILL.md has a `## Next steps` section that lists the natural
   downstream skills for a typical workflow:
   - `paper-new` -> `paper-draft`
   - `paper-draft` -> `paper-figure`, `paper-cite`, `paper-compile`
   - `paper-review` -> `paper-revise` -> `paper-draft`
2. When Claude completes a skill's task, it surfaces the suggested next step
   in its response, so the user can chain explicitly.
3. For compound requests like "review and revise", Claude is expected to
   invoke `paper-review`, observe the resulting `RevisionRoadmap`, then
   invoke `paper-revise` with that roadmap as input.

This natural chaining is verified in the routing eval (§3.8), which has a
"compound requests" category of 5 prompts.

### 3.6 Agent migration plan

All 10 existing agents are kept. The only change required for Phase A is a
mandatory **config-loading prefix** prepended to each agent file.

#### 3.6.1 The prefix (added verbatim to all 10 agents)

```markdown
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
```

This prefix is **added once to each of the 10 agent files**. The body of each
agent (its existing instructions) is otherwise unchanged in Phase A. No
behavioral changes, just the config-loading discipline.

#### 3.6.2 Per-agent change matrix

| Agent file | Change in Phase A |
|---|---|
| `structure_architect.md` | Prepend prefix; otherwise unchanged. |
| `argument_builder.md` | Prepend prefix; otherwise unchanged. |
| `draft_writer.md` | Prepend prefix; otherwise unchanged. |
| `visualization.md` | Prepend prefix; otherwise unchanged. |
| `compiler.md` | Prepend prefix; otherwise unchanged. |
| `citation_manager.md` | Prepend prefix; otherwise unchanged. |
| `peer_reviewer.md` | Prepend prefix; otherwise unchanged. |
| `devils_advocate.md` | Prepend prefix; otherwise unchanged. |
| `editorial_synthesizer.md` | Prepend prefix; otherwise unchanged. |
| `revision_coach.md` | Prepend prefix; otherwise unchanged. |

The 11th agent (`humanizer_engine.md`) is added in Phase B, not Phase A.
The 12th agent (`annotator_engine.md`) is added in Phase C.


### 3.7 Trigger stability strategy

Phase A is the phase that pays off the user's "skills get confused" complaint.
The strategy rests on three independent layers, ordered by strength.

#### 3.7.1 Layer 1: `paths` glob filter (strongest)

For each `paper-X` skill, the `paths` field constrains automatic invocation to
only those sessions where the user is operating on a LaTeX paper project. When
the user is editing a Python script, a blog post, or a README file, the
`paper-X` skills are **not even visible to Claude's matcher**. This is the
single most important fix.

The standard glob is:

```yaml
paths:
  - "**/main.tex"
  - "**/sections/*.tex"
  - "**/sections/**/*.tex"
  - "**/.paper-config.yml"
  - "**/references.bib"
```

Skills with `paths` set are filtered out of the candidate list before any
description matching happens. This eliminates the entire class of "wrong skill
fired on a non-paper task".

Two skills do NOT use `paths`:

- `paper-humanize`: must work on any text (academic or general); `paths`
  filtering would defeat the general-mode use case.
- `paper-new`: this skill creates a new paper project, so by definition it
  cannot require an existing one. It is `disable-model-invocation: true` and
  invoked only via slash command, so the absence of `paths` does not affect
  trigger stability.

#### 3.7.2 Layer 2: 200-character descriptions

Per official Claude Code documentation, skill descriptions over 250 characters
are truncated in the listing the matcher sees. To stay safely under, every
description in Phase A is `<= 200` characters and front-loads the most
distinctive phrase in the first 80 characters.

Each skill description in this spec is `<= 200 characters`. The exact length of
each description is verified during Phase A implementation by a build-time
linter that prints a hard error if any description exceeds 200 characters.
The 50-character buffer below the 250-char truncation limit absorbs any future
small wording adjustments without risking truncation.

Front-loaded distinctive phrases for each skill:

| Skill | Front-loaded distinctive phrase |
|---|---|
| `paper-new` | "Create and scaffold a new academic LaTeX paper project..." |
| `paper-draft` | "Draft or revise a section of an academic LaTeX paper..." |
| `paper-figure` | "Generate publication-quality matplotlib or seaborn figures..." |
| `paper-compile` | "Compile an academic LaTeX paper project with pdflatex..." |
| `paper-cite` | "Manage references.bib in an academic LaTeX paper project..." |
| `paper-review` | "Simulate peer review on an academic LaTeX paper draft..." |
| `paper-revise` | "Process external reviewer comments on an academic paper..." |

No description includes "Do NOT use for X" anti-patterns, because they would
fall after the 200-character mark and never reach the matcher.

#### 3.7.3 Layer 3: `disable-model-invocation: true` for effectful skills

Five of the nine skills are flagged manual-only because they have side effects
or require explicit user input:

| Skill | `disable-model-invocation` | Reason |
|---|---|---|
| `paper-new` | true | Creates project files; deliberate action |
| `paper-draft` | false | Common request, safe to auto-trigger |
| `paper-figure` | false | Common request |
| `paper-compile` | true | Runs pdflatex, writes build/ |
| `paper-cite` | false | Common request |
| `paper-review` | false | Direct request "review my paper" |
| `paper-revise` | true | Requires external reviewer comments |
| `paper-humanize` | true (Phase B) | Mutates text |
| `paper-annotate` | true (Phase C) | Mutates .tex |

Slash commands `/paper-new`, `/paper-compile`, `/paper-revise`,
`/paper-humanize`, `/paper-annotate` are the only way to trigger those skills.

### 3.8 Eval matrix (Phase A scope)

A new file `evals/routing_eval.json` contains 50 prompts that test trigger
behavior. Each entry has shape:

```json
{
  "prompt": "Write the related work section for my paper.",
  "expected_skill": "academic-paper:paper-draft",
  "context": {
    "cwd": "evals/fixtures/paper_project_minimal/",
    "open_file": "sections/related_work.tex"
  }
}
```

Categories of test prompts:

| Category | Count | Purpose |
|---|---|---|
| Direct paper requests in paper context | 15 | should hit the right paper-X skill |
| Direct paper requests in non-paper context | 10 | should NOT hit any paper-X skill |
| Ambiguous verbs (write, review, compile) | 10 | should hit paper-X only when in paper context |
| Compound requests | 5 | should chain multiple paper-X skills |
| Side-effect skills auto-trigger attempts | 5 | should be blocked by disable-model-invocation |
| Adjacent installed skills (humanizer, codex) | 5 | should not be hijacked |

The eval is run as part of Phase A acceptance. A skill is considered to have
passed routing if `>= 90%` of its category prompts route to the expected target.

The existing `evals/evals.json` is preserved unchanged for the with-skill /
without-skill comparison runs.

### 3.9 Removing the old top-level SKILL.md

The old top-level `SKILL.md` is **deleted** as the last step of Phase A, after
all 9 new skills are in place and the routing eval passes. Until then, the old
top-level skill (named `academic-paper`) and the new plugin-namespaced skills
(`academic-paper:paper-new`, `academic-paper:paper-draft`, etc.) coexist
without name collisions because they have different identifiers.

The deletion is a single git operation. The file is not preserved in any other
form because:

- The 4 handoff schemas have been moved to `references/handoff_schemas.md`.
- The "Stage Routing" table is replaced by the 9 individual skills.
- The "Project Structure Convention" content is moved into `paper-new/SKILL.md`.
- The "LaTeX Conventions" section moves into `paper-compile/SKILL.md` and
  `paper-cite/SKILL.md`.

### 3.10 .gitignore additions

Phase A adds these entries to `.gitignore`:

```
# v3 plugin per-user config
.paper-config.local.yml

# Tooling caches
.codex/
.humanize/
```

### 3.11 Phase A acceptance criteria

Phase A is considered complete when **all** of the following are true:

1. `claude plugin install <local-path>` installs the plugin successfully.
2. `/paper-new "NeurIPS 2026" "ML"` creates a working paper project with
   `.paper-config.yml` and a scaffolded `main.tex / sections/ / Makefile`.
3. `/paper-draft introduction` writes an introduction section that respects the
   `word_target` field in the config.
4. `/paper-compile` runs `pdflatex+bibtex` successfully on the scaffolded
   project and produces a non-empty PDF.
5. `evals/routing_eval.json` passes at `>= 90%` per category.
6. `evals/evals.json` (existing) regression run shows no degradation versus the
   v2 baseline (with-skill grading scores within 5% of recorded baseline).
7. Old top-level `SKILL.md` is deleted.
8. README.md and README-zh.md describe the v3 plugin install path.

Phase A makes **zero behavioral changes** to the agents themselves. If a v2
prompt produced output X, the same prompt in v3 must produce semantically
equivalent output X (modulo Claude's nondeterminism).


## 4. Phase B — paper-humanize with academic overrides

Phase B adds the `paper-humanize` skill (namespaced as
`academic-paper:paper-humanize`), the `humanizer_engine` agent, and two
reference files. It is implementable once Phase A merges.

### 4.1 Goal

Apply the 28 patterns from Wikipedia "Signs of AI writing" to text, with
academic-aware overrides so the rules do not destroy legitimate academic style
(passive voice in Methods, hyphenated technical compounds, etc.).

The plugin's `paper-humanize` skill **coexists with the user's separate
`~/code/humanizer` skill** (which keeps the bare name `humanizer` and handles
general-text humanization). They have different names so there is no trigger
conflict at any level.

### 4.2 Operating modes

The skill has two modes, switched automatically based on context:

| Mode | When | Behavior |
|---|---|---|
| `academic` | `.paper-config.yml` exists in cwd ancestor chain | Apply 28 patterns minus academic overrides |
| `general` | No `.paper-config.yml` found | Apply all 28 patterns (same as standalone humanizer) |

The mode is also overridable via `humanizer.mode` in `.paper-config.local.yml`.

### 4.3 Pattern classification (28 total)

| # | Pattern | Phase B classification |
|---|---|---|
| 1 | Undue Emphasis on Significance/Legacy | KEEP |
| 2 | Undue Emphasis on Notability/Media | KEEP |
| 3 | Superficial -ing Analyses | MODIFY (preserve legitimate participial clauses) |
| 4 | Promotional Language | MODIFY (preserve "novel/proposed/state-of-the-art") |
| 5 | Vague Attributions | KEEP |
| 6 | "Challenges and Future Prospects" | MODIFY (allow in Limitations and Future Work sections) |
| 7 | AI Vocabulary Words | MODIFY (split allowlist/blocklist for academic context) |
| 8 | Copula Avoidance | KEEP |
| 9 | Negative Parallelisms | MODIFY (allow "not only...but also" academic form) |
| 10 | Rule of Three Overuse | KEEP |
| 11 | Elegant Variation | KEEP |
| 12 | False Ranges | KEEP |
| 13 | Passive Voice and Subjectless Fragments | MODIFY (allow procedural passive in Methods/Results, flag evasive) |
| 14 | Em Dash Overuse | MODIFY (only flag if more than 3 per paragraph; never in math) |
| 15 | Boldface Mechanical Use | KEEP |
| 16 | Inline-Header Vertical Lists | KEEP |
| 17 | Title Case in Headings | SKIP in academic mode only (NeurIPS/IEEE/ACM require it) |
| 18 | Emojis | KEEP |
| 19 | Curly Quotation Marks | SKIP in academic mode only (LaTeX has its own conventions) |
| 20 | Collaborative Communication Artifacts | KEEP |
| 21 | Knowledge-Cutoff Disclaimers | KEEP |
| 22 | Sycophantic Tone | KEEP |
| 23 | Filler Phrases | KEEP |
| 24 | Excessive Hedging | MODIFY (allow single-layer hedge, flag stacked hedges) |
| 25 | Generic Positive Conclusions | KEEP |
| 26 | Hyphenated Word Pair Overuse | MODIFY (allow technical compounds, flag gratuitous stacking) |
| 27 | Persuasive Authority Tropes | KEEP |
| 28 | Signposting and Announcements | MODIFY (allow structural signposting like "In Section 3 we present...") |
| 29 | Fragmented Headers | KEEP |

Totals: KEEP 17, MODIFY 9, SKIP-conditional 2.

### 4.4 paper-humanize skill frontmatter

```yaml
---
name: paper-humanize
description: Remove AI writing patterns from English text with academic-aware overrides. Auto-detects LaTeX context for passive voice, hyphenated compounds, title case, curly quotes handling.
argument-hint: "[<file-or-paste>]"
disable-model-invocation: true
allowed-tools: Read Edit Skill
---
```

`disable-model-invocation: true` so it never auto-mutates content. User invokes
explicitly via `/paper-humanize`.

When `/paper-humanize` is invoked with no arguments, it asks the user to paste
text.

### 4.5 humanizer_engine agent

Phase B adds `agents/humanizer_engine.md` with frontmatter:

```yaml
---
name: humanizer_engine
description: Internal engine that applies the 28-pattern AI-writing-detection rules to a chunk of English text, respecting academic overrides when in academic mode.
model: sonnet
effort: medium
---
```

The agent body contains:

1. The full 28-pattern playbook (verbatim from `references/humanizer_patterns.md`)
2. Academic override table (verbatim from `references/humanizer_academic_overrides.md`)
3. The Wikipedia self-audit prompt loop:
   - Draft rewrite
   - Self-prompt: "What still makes this sound AI-generated in academic context?"
   - Final rewrite

### 4.6 Reference files added in Phase B

- `references/humanizer_patterns.md`: full 28-pattern definitions, prose +
  before/after examples. Migrated verbatim from `~/code/humanizer/SKILL.md`,
  with attribution preserved.
- `references/humanizer_academic_overrides.md`: the 9 MODIFY rules with their
  exact academic exceptions, plus the 2 SKIP-conditional rules.

### 4.7 Phase B eval

A new file `evals/humanizer_regression.json` contains 20 short academic English
samples (one per common section type: abstract, intro, related, method, etc.)
with expected behavior:

- `should_change_at`: list of patterns the humanizer should rewrite
- `should_preserve`: list of phrases that must survive (passive voice in
  Methods, hyphenated compounds, title case in headings, etc.)

Pass criterion: humanizer applied to each sample changes the listed patterns
and preserves all listed phrases. Eval is run as part of Phase B acceptance.

### 4.8 Phase B acceptance criteria

1. `/paper-humanize <english-text>` removes AI patterns and produces output that
   passes a self-audit ("does this still sound AI-generated?").
2. In academic mode, passive voice in Methods/Results sections is preserved.
3. In academic mode, NeurIPS/IEEE/ACM-style title case in headings is preserved.
4. In academic mode, hyphenated technical compounds (`data-driven`,
   `end-to-end`, `real-time`) are preserved.
5. In general mode (no `.paper-config.yml`), behavior is similar to (but not
   bit-identical with) the standalone `humanizer` skill in `~/code/humanizer`.
6. `evals/humanizer_regression.json` passes on all 20 samples.

## 5. Phase C — bilingual annotator

Phase C adds the `paper-annotate` skill, the `annotator_engine` agent, and one
reference file. It is implementable once Phase B merges.

### 5.1 Goal

Insert sentence-level Chinese `%` comments after each English sentence in a
LaTeX paper source file, so the user (who only knows basic Python and C
syntax) can read what each sentence says. The compiled PDF stays English-only
because LaTeX strips `%` comments.

### 5.2 Output format

```latex
We propose a graph attention mechanism for molecular property prediction.
% @zh[a3f29c4b]: 我们提出一种用于分子属性预测的图注意力机制。
Existing GNNs struggle with long-range interactions.
% @zh[7b8e2d1f]: 现有图神经网络难以捕捉长距离相互作用。
Our method introduces global attention with $O(n \log n)$ complexity.
% @zh[c1d4f7a8]: 我们的方法引入了复杂度为 $O(n \log n)$ 的全局注意力。
```

Format details:

- Each English sentence is forced onto its own physical line ("sentence per
  line" layout, common in LaTeX style guides for git-friendly diffs).
- The next line is a comment of form `% @zh[XXXXXXXX]: <chinese>` where
  `XXXXXXXX` is the **first 8 hex characters** of `SHA-1(normalized_english)`.
- Inline LaTeX commands (`\cite{}`, `\ref{}`, `$...$`, `\emph{}`) are kept
  inside the Chinese translation as-is, not translated.

### 5.3 Hash-based refresh protocol

When the user edits English text and re-runs `/paper-annotate`, the engine
detects which sentences changed and only re-translates those:

```
For each existing `% @zh[XXXXXXXX]:` line in the file:
    let prev_english = the line immediately above
    let current_hash = sha1(normalize(prev_english))[:8]
    if XXXXXXXX == current_hash:
        skip (annotation is current)
    else:
        regenerate Chinese for prev_english
        replace the comment line with a new one carrying the new hash
```

8 hex characters give 32 bits of address space (~4.3 billion), which is
overkill for any single paper file but trivially cheap to compute.

### 5.4 Sentence segmentation pipeline

Codex correctly noted that pure regex segmentation is brittle for LaTeX. Phase
C uses a **hybrid pipeline** that combines deterministic masking with
Claude-aided segmentation:

```
Input: a chunk of LaTeX source (a section file, a paragraph, etc.)
   |
   v
[1] Deterministic mask -- replace with placeholder tokens:
    - Math envs:    \begin{equation|align|gather|multline}...\end{...}
    - Inline math:  $...$, $$...$$, \(...\), \[...\]
    - Code envs:    \begin{verbatim|lstlisting|minted}...\end{...}
    - Citations:    \cite{...}, \citep{...}, \citet{...}
    - References:   \ref{...}, \label{...}, \eqref{...}
    - URLs:         \url{...}
   |
   v
[2] Hand the masked text to annotator_engine with prompt:
    "Identify all English sentences. Treat [MATH001], [CITE001] etc. as opaque
     tokens that may appear inside or between sentences. Return a JSON list of
     {start_line, start_col, end_line, end_col, sentence_text} for each sentence.
     Skip masked code/math regions entirely."
   |
   v
[3] Annotator returns segmentation JSON.
   |
   v
[4] Driver code:
    - For each segment, compute sha1[:8] of normalized English
    - Look for existing `% @zh[hash]:` comment immediately below
    - If hash matches, skip
    - Else regenerate Chinese (by feeding the sentence + neighboring context to
      annotator_engine) and replace the comment line
   |
   v
[5] Unmask placeholders back to original LaTeX content.
   |
   v
[6] Apply sentence-per-line formatting where the original had multi-sentence
    lines.
   |
   v
[7] Write the result back to the .tex file.
```

This hybrid avoids the regex brittleness Codex flagged while not requiring a
full LaTeX parser dependency.

### 5.5 Skip rules

| Region | Annotated? | Notes |
|---|---|---|
| `\begin{equation\|align\|...}...\end{...}` | NO | math env (per user decision in §6) |
| `$...$`, `$$...$$`, `\(...\)`, `\[...\]` | NO | math inline/display |
| `\begin{verbatim\|lstlisting\|minted}...\end{...}` | NO | code |
| `references.bib` | NO (skill never opens .bib) | bibtex |
| `\cite{...}, \ref{...}, \label{...}, \url{...}` | preserved inside sentence | LaTeX commands |
| `\title{...}` | YES, on next line | annotation below |
| `\section{...}, \subsection{...}` | YES, on next line | annotation below |
| `\caption{...}` | YES, comment placed BELOW the \caption{} line | per user decision |
| `\footnote{...}` | YES, comment placed BELOW the \footnote{} line | per user decision |
| `\abstract{...}` or `\begin{abstract}...\end{abstract}` | YES | each sentence annotated |
| Existing `% comment` (non-`@zh`) | preserved as-is | never overwrite user notes |

### 5.6 paper-annotate skill frontmatter

```yaml
---
name: paper-annotate
description: Add or refresh sentence-level Chinese %-comments in an English academic LaTeX paper source. Skips math, code, bibtex. Preserves LaTeX commands inside translations.
argument-hint: "[<target>]"
disable-model-invocation: true
paths: ["**/main.tex", "**/sections/*.tex", "**/sections/**/*.tex"]
allowed-tools: Read Write Edit Skill
---
```

`disable-model-invocation: true` because annotation mutates source files.

`/paper-annotate` with no arguments annotates the entire paper project. With a
target argument, annotates only that file or directory.

### 5.7 annotator_engine agent

```yaml
---
name: annotator_engine
description: Internal engine that segments English LaTeX source into sentences, translates each to Simplified Chinese with academic tone, and produces hash-tagged annotations.
model: sonnet
effort: medium
---
```

The agent body specifies:

1. The masking rules (list of regexes)
2. The segmentation prompt template
3. The translation prompt template (Chinese tone calibration: academic, no
   internet slang, preserve LaTeX inline commands as-is, Chinese full-width
   period)
4. The hash function specification (`sha1[:8]` of normalized English; whitespace
   normalized to single spaces, surrounding spaces stripped)
5. Term glossary lookup from `references/annotation_rules.md`

### 5.8 Reference file added in Phase C

`references/annotation_rules.md` contains:

1. Full abbreviation whitelist (`e.g.`, `i.e.`, `et al.`, `Fig.`, `Eq.`,
   `Sec.`, `Tab.`, `cf.`, `vs.`, `approx.`, `Dr.`, `Prof.`, ...)
2. Mask region regex definitions
3. Translation prompt template
4. Academic term glossary (~200 entries: `neural network` -> 神经网络,
   `gradient descent` -> 梯度下降, `attention mechanism` -> 注意力机制, ...)
5. Sentence-per-line formatting rules
6. Hash normalization spec

### 5.9 Phase C eval

A new file `evals/annotation_idempotence.json` exercises three properties:

| Test | Property |
|---|---|
| `idempotence` | Running `/paper-annotate` twice on the same file produces zero diff |
| `refresh_on_change` | Editing one sentence and re-running annotates ONLY that sentence |
| `no_pdf_change` | After annotation, `pdflatex` output PDF is byte-identical (modulo timestamp) to before |

The third property is the strongest correctness check: if annotation breaks the
PDF, the rule was violated.

### 5.10 Phase C acceptance criteria

1. `/paper-annotate` on a freshly drafted section produces correct sentence-
   per-sentence Chinese annotations.
2. Editing one English sentence and re-running annotates only that sentence
   (hash refresh works).
3. Compiled PDF is byte-identical (modulo timestamp) before and after
   annotation.
4. `evals/annotation_idempotence.json` passes all three tests.
5. Math environments, code blocks, and bibtex entries are never touched.


## 6. Risks and trade-offs

### 6.1 Trigger stability is empirically unverified until eval runs

The 3-layer trigger strategy (paths glob + 200-char description + manual-only
flag) is sound on paper, but its real-world effectiveness depends on how Claude
actually scores skill candidates. Phase A includes the routing eval as the
forcing function: if `>= 90%` per category does not hold, the design needs
revision before merge.

### 6.2 paths glob is opaque about why a skill did not trigger

When a `paper-X` skill does not auto-trigger, the user has no visibility into
whether it was filtered out by `paths`, by description matching, or by
`disable-model-invocation`. Mitigation: every `paper-X` skill is also a slash
command, so the user can always force-invoke. If a user expects auto-trigger
and does not get it, the workaround is `/paper-<verb>`.

### 6.3 Sentence-per-line forced layout (Phase C) changes physical formatting

Codex strongly recommended an out-of-place sidecar file instead of mutating
.tex. The user explicitly chose in-place. This means:

- `.tex` source files become significantly longer (~50-80% growth from comment
  lines)
- Git diffs after `/paper-annotate` are noisy
- Coauthors who do not have the plugin will see a `.tex` file full of
  `% @zh[xxx]:` lines and may not understand the convention

Mitigations:
- README.md clearly documents the convention so coauthors can read it
- The hash-based refresh means re-running annotation is cheap, so the noise
  cost is paid once per text change
- `git blame` on `% @zh` lines clearly identifies them as machine-generated

### 6.4 Sentence segmentation correctness depends on annotator_engine quality

Phase C trusts Claude to do the final sentence segmentation pass after
deterministic masking. If Claude misidentifies sentence boundaries (e.g.,
treating "Fig. 3" as a sentence end), the annotations will be misaligned. The
mitigation is the abbreviation whitelist in `references/annotation_rules.md`
plus the deterministic masking step.

This is a real risk because Codex flagged it as "core correctness". The Phase
C eval (`annotation_idempotence`) catches gross misalignment because
re-running on stable input must produce zero diff.

### 6.5 paper-humanize in academic mode preserves more than the standalone

Phase B's `paper-humanize` is intentionally less aggressive than the standalone
`humanizer` in `~/code/humanizer`. Some "AI-isms" that the standalone would
remove are kept by the academic version (e.g., "we propose", "this paper
presents", procedural passive voice). This is the intended design: academic
papers have legitimate stylistic constraints that general writing does not.

Risk: if the user runs `/paper-humanize` expecting the same aggressive cleanup
as the standalone humanizer, the result may feel underwhelming. Mitigation: the
skill description and README clearly explain the academic-vs-general split,
and the user can override the mode via `humanizer.mode: general` in
`.paper-config.local.yml`.

### 6.6 Backward-compat shim has a finite lifetime

The v3 schema is a strict superset of v2 PaperConfig, so existing 10 agents
work unchanged. This compatibility is a deliberate Phase A constraint. In a
hypothetical v4, the schema may break v2 compat; at that point Phase A's
backward-compat code will be removed.

For now: do not refactor the agents away from v2 field names. Do not nest
existing fields. Do not rename them.

### 6.7 The 3-phase plan extends total wall-clock time

A single big-bang rollout would have shipped in one round. Splitting into
phases A->B->C means three brainstorm-spec-plan-implement cycles. The user
explicitly accepted this trade-off after Codex's pushback in favor of staging.

## 7. Open questions

These are decisions deferred until their phase begins.

### 7.1 Phase A open questions

- Should the routing eval run in CI or only locally? (Default: local only.)
- Should `paper-new` ask the user via interactive prompts, or take all config
  via command-line arguments? (Current spec: hybrid -- arguments override
  prompts.)
- Should the plugin's plugin.json declare any `userConfig` for Phase A, or are
  config files sufficient? (Default: config files only; reserve `userConfig`
  for Phase B/C personal preferences.)

### 7.2 Phase B open questions

- Should the academic-mode AI vocabulary blocklist be a hardcoded list or
  configurable? (Current spec: hardcoded list of 28 words in
  `humanizer_academic_overrides.md`, with the option to override later.)
- Should `paper-humanize` be `context: fork` to run in a forked subagent?
  (Open; decide based on Phase A token usage observations.)

### 7.3 Phase C open questions

- Should `paper-annotate` annotate the full project at first run, or only the
  current file? (Current spec: full project unless a target is given.)
- Should `paper-annotate` integrate with `paper-draft` to auto-annotate new
  drafts? (Current spec: no, opt-in only via `humanizer.auto_run_after_drafting`
  -- which currently only refers to humanizer; an analogous flag for annotation
  may be added in Phase C.)
- Should the hash use `sha1[:8]` or `blake3[:8]`? (Default: sha1, available in
  every standard library; blake3 is faster but requires an extra dependency.)

## 8. Out of scope

- Literature search or systematic review.
- Style calibration from past papers.
- Multi-format output (DOCX, EPUB, etc.).
- Non-EECS disciplines (humanities, life sciences).
- Reference existence verification via web search.
- Auto-translating documents to Chinese as primary output (only `%`-comment
  annotations).
- Replacing the user's separate `~/code/humanizer` skill.
- Touching the `academic-paper-workspace/` evaluation outputs.

## 9. Glossary

| Term | Meaning |
|---|---|
| PaperConfig | The shared schema (v2 and v3) describing a paper's venue/template/budget |
| StructureOutline | Handoff schema from `structure_architect` to `argument_builder` and `draft_writer` |
| ArgumentBlueprint | Handoff schema from `argument_builder` to `draft_writer` |
| ReviewReport | Handoff schema from `peer_reviewer` to `editorial_synthesizer` |
| RevisionRoadmap | Handoff schema from `revision_coach` to `draft_writer` |
| paths glob | The `paths` frontmatter field that limits skill auto-activation to matching files |
| disable-model-invocation | Frontmatter flag that prevents Claude from auto-loading a skill |
| `% @zh[XXXXXXXX]:` | LaTeX comment marker for bilingual annotation; XXXXXXXX is the first 8 hex chars of SHA-1 of the English sentence |
| academic mode | humanizer mode active when `.paper-config.yml` is found; applies overrides |
| general mode | humanizer mode active otherwise; applies all 28 patterns |

## 10. References

- [Claude Code Plugins documentation](https://code.claude.com/docs/en/plugins)
- [Claude Code Plugins reference](https://code.claude.com/docs/en/plugins-reference)
- [Claude Code Skills documentation](https://code.claude.com/docs/en/skills)
- [Wikipedia: Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)
- Codex review (gpt-5.4:high) consulted on 2026-04-11; output saved at
  `.humanize/skill/2026-04-11_13-17-40-1536617-8a5d32f7/output.md`
- Sibling repository: `~/code/humanizer` (general-text humanizer skill, not
  superseded by this plugin)

