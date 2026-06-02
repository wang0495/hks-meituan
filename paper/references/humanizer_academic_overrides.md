# Humanizer Academic Overrides

This file documents the academic-mode overrides that `paper-humanize` applies
on top of the 29 generic patterns defined in `references/humanizer_patterns.md`.
When the humanizer runs inside a LaTeX paper project, a subset of the generic
rules must be relaxed or skipped so that legitimate academic style (procedural
passive in Methods, hyphenated technical compounds, title case in NeurIPS
headings, LaTeX quoting conventions) is not flagged or destroyed.

**Parent reference:** `references/humanizer_patterns.md` (the 29-pattern
playbook, verbatim-migrated from `/home/yanggl/code/humanizer/SKILL.md`,
humanizer plugin v2.5.1, MIT).

## Operating modes

The humanizer has two modes, switched automatically based on context:

| Mode       | When                                                    | Behavior |
|------------|---------------------------------------------------------|----------|
| `academic` | `.paper-config.yml` exists in cwd ancestor chain        | Apply the 29 patterns, minus the academic overrides in this file |
| `general`  | No `.paper-config.yml` found                            | Apply all 29 patterns with no overrides (same as standalone `~/code/humanizer`) |

The mode can also be overridden by setting `humanizer.mode` in
`.paper-config.local.yml`.

## Classification summary

Of the 29 patterns in the parent reference, academic mode classifies each as:

- **KEEP** (17 patterns): applied unchanged in both modes.
- **MODIFY** (9 patterns): applied with academic-aware exceptions documented
  below.
- **SKIP-conditional** (2 patterns): entirely disabled in academic mode;
  applied normally in general mode.

| #  | Pattern                                               | Classification     |
|----|-------------------------------------------------------|--------------------|
| 1  | Undue Emphasis on Significance/Legacy                 | KEEP               |
| 2  | Undue Emphasis on Notability/Media                    | KEEP               |
| 3  | Superficial -ing Analyses                             | MODIFY             |
| 4  | Promotional Language                                  | MODIFY             |
| 5  | Vague Attributions                                    | KEEP               |
| 6  | "Challenges and Future Prospects"                     | MODIFY             |
| 7  | AI Vocabulary Words                                   | MODIFY             |
| 8  | Copula Avoidance                                      | KEEP               |
| 9  | Negative Parallelisms                                 | MODIFY             |
| 10 | Rule of Three Overuse                                 | KEEP               |
| 11 | Elegant Variation                                     | KEEP               |
| 12 | False Ranges                                          | KEEP               |
| 13 | Passive Voice and Subjectless Fragments               | MODIFY             |
| 14 | Em Dash Overuse                                       | MODIFY             |
| 15 | Boldface Mechanical Use                               | KEEP               |
| 16 | Inline-Header Vertical Lists                          | KEEP               |
| 17 | Title Case in Headings                                | SKIP-conditional   |
| 18 | Emojis                                                | KEEP               |
| 19 | Curly Quotation Marks                                 | SKIP-conditional   |
| 20 | Collaborative Communication Artifacts                 | KEEP               |
| 21 | Knowledge-Cutoff Disclaimers                          | KEEP               |
| 22 | Sycophantic Tone                                      | KEEP               |
| 23 | Filler Phrases                                        | KEEP               |
| 24 | Excessive Hedging                                     | MODIFY             |
| 25 | Generic Positive Conclusions                          | KEEP               |
| 26 | Hyphenated Word Pair Overuse                          | MODIFY             |
| 27 | Persuasive Authority Tropes                           | KEEP               |
| 28 | Signposting and Announcements                         | MODIFY             |
| 29 | Fragmented Headers                                    | KEEP               |

Totals: 17 KEEP, 9 MODIFY, 2 SKIP-conditional.

---

## MODIFY patterns

Each entry below restates the generic rule and then defines the academic
exception (when NOT to apply the rule) with concrete examples. Apply the
generic rule whenever the exception does not fire.

## Pattern 3: Superficial -ing Analyses (MODIFY)

**Original rule:** Flag present-participle ("-ing") phrases tacked onto
sentences to add fake depth (e.g., "symbolizing ...", "reflecting ...",
"highlighting ...").

**Academic exception — preserve legitimate participial clauses:** In academic
prose, participial clauses that carry real information content (definitions,
method steps, data constraints, causal linkage) are grammatically correct and
must be preserved. Only flag participial clauses that add no content beyond
rhetorical filler.

- PRESERVE (legitimate, carries information):
  "We train the model using Adam with a learning rate of 1e-4, warming up
  linearly over the first 1k steps."
- PRESERVE (defining clause):
  "Let G = (V, E) be a directed graph, where each edge carries a weight
  encoding pairwise similarity."
- FLAG (rhetorical filler, no content):
  "Our method achieves state-of-the-art results, highlighting the importance
  of attention mechanisms in this domain."

## Pattern 4: Promotional and Advertisement-like Language (MODIFY)

**Original rule:** Flag promotional adjectives ("vibrant", "breathtaking",
"groundbreaking", "renowned", "nestled", "boasts", ...).

**Academic exception — preserve conventional method-descriptor vocabulary:**
The academic-paper publishing convention permits a small set of descriptors
when applied to a method, dataset, or result. Preserve:

- "novel" (as in "we propose a novel attention mechanism")
- "proposed" (as in "the proposed method outperforms ...")
- "state-of-the-art" and "SOTA"
- "principled" (as in "a principled approach to uncertainty quantification")

Still FLAG the general-purpose promotional vocabulary ("vibrant",
"breathtaking", "stunning", "must-read", "nestled", "boasts a rich history",
...) as well as stacked instances of the allowed words (e.g., "our novel,
groundbreaking, state-of-the-art method" — at most one such descriptor per
clause).

## Pattern 6: Outline-like "Challenges and Future Prospects" Sections (MODIFY)

**Original rule:** Flag formulaic "Challenges and Future Prospects" sections,
especially "Despite its ..., faces several challenges ...".

**Academic exception — allow in dedicated structural sections:** Most
empirical papers include a **Limitations** section and/or a **Future Work**
section as part of standard venue requirements (NeurIPS requires Limitations;
ACL encourages it; IEEE conferences expect Future Work). Inside those
sections, discussion of challenges and future directions is not filler — it
is the point of the section. Do not flag "Challenges"-style prose if the
enclosing heading is one of:

- Limitations
- Limitations and Future Work
- Future Work / Future Directions
- Discussion (only if the paragraph is explicitly scoped to limitations)
- Broader Impact (only if discussing societal limitations)

Still FLAG the pattern if it appears in Abstract, Introduction, Related
Work, Method, or Results sections, because there it is almost always
rhetorical filler.

## Pattern 7: Overused "AI Vocabulary" Words (MODIFY)

**Original rule:** Flag the high-frequency AI-vocabulary list (delve,
tapestry, landscape, testament, underscore, pivotal, ...).

**Academic exception — split allowlist / blocklist for academic context:**
Some words on the general-mode AI-vocab list are genuinely useful in
academic writing and should be allowed; others are not. Apply the
following split:

**Allowed in academic mode (do NOT flag):**
- "novel" (as method descriptor; see Pattern 4)
- "rigorous" (as in "a rigorous evaluation protocol")
- "robust" (as in "the method is robust to noise in the training labels")
- "non-trivial" (as in "a non-trivial extension of prior work")
- "principled" (as in "a principled Bayesian treatment")

**Still flagged in academic mode (hard blocklist):**
- delve, delving into
- tapestry (figurative)
- unleash (figurative)
- landscape (abstract, non-geographic sense)
- testament (figurative)
- pivotal (figurative)
- vibrant (figurative)
- intricate tapestry, intricate interplay
- groundbreaking (figurative, without specific quantitative justification)
- garner
- underscore (verb, figurative)

For borderline words ("enhance", "crucial", "key"), flag only when used in
filler patterns (e.g., "key role in ...", "crucial insight") and not when
referring to a concrete technical term (e.g., "a cryptographic key",
"enhanced by a factor of 2x").

## Pattern 9: Negative Parallelisms and Tailing Negations (MODIFY)

**Original rule:** Flag "not only ... but ..." and "it's not just about ...,
it's ..." constructions as overused negative parallelisms.

**Academic exception — allow a single "not only ... but also" per section:**
The "not only X but also Y" construction is a standard academic device to
signal that a contribution covers two orthogonal dimensions (e.g., "we
evaluate not only on ImageNet but also on 15 out-of-distribution benchmarks").
Allow one occurrence per major section (one per Abstract, one per
Introduction, one per Method, etc.). Flag a second occurrence within the
same section, and always flag the clipped tailing-negation variant ("no
guessing", "no wasted motion") because that one has no academic justification.

## Pattern 13: Passive Voice and Subjectless Fragments (MODIFY)

**Original rule:** Flag passive voice and subjectless fragments as hiding the
actor.

**Academic exception — allow procedural passive in Methods/Results, flag
evasive passive everywhere:** In academic writing, the "procedural passive"
is the standard voice for describing experimental procedure, because the
identity of the experimenter is irrelevant and foregrounding the procedure
is more informative than foregrounding "we". Apply the following rule:

- PRESERVE in Methods / Experimental Setup / Results sections:
  "The model was trained for 100 epochs on 8 A100 GPUs."
  "Samples were drawn from the validation split with stratified sampling."
  "Hyperparameters were selected via 5-fold cross-validation."
- PRESERVE in formal problem statements:
  "Let x be drawn from a distribution P over R^d."
- FLAG anywhere (evasive passive — hides a controversial claim):
  "It has been argued that our approach is superior to prior work."
  (Rewrite to: "We argue that our approach improves on prior work because
  ...")
- FLAG anywhere (subjectless fragments that aren't formal problem
  statements): "No configuration file needed." "Automatically handled."

Rule of thumb: procedural passive describing what was done = KEEP; evasive
passive hiding who is making a claim = FLAG.

## Pattern 14: Em Dash Overuse (MODIFY)

**Original rule:** Flag em dashes (—) as over-punctuated "punchy sales writing".

**Academic exception — density threshold and math context:** Em dashes are
used less often in academic writing than in LLM prose, but they are legitimate
in short parenthetical insertions and in author attribution lines. Apply:

- Only flag a paragraph if it contains **more than 3 em dashes**. A paragraph
  with 1 or 2 em dashes is fine.
- Never flag em dashes inside inline math or LaTeX math environments
  (`$...$`, `\\( ... \\)`, `\\[ ... \\]`, `equation`, `align`, etc.), because
  they are likely minus signs being rendered as em dashes by the font.
- Never flag em dashes inside `\\caption{...}`, `\\title{...}`, or `\\author{...}`,
  where they are used for metadata separation ("A — B" style).

If a paragraph crosses the density threshold, suggest replacing the excess
em dashes with commas, periods, or parentheses (the generic rewrite from
the parent reference).

## Pattern 24: Excessive Hedging (MODIFY)

**Original rule:** Flag over-qualified statements ("could potentially
possibly be argued that ... might have some effect on ...").

**Academic exception — allow single-layer hedge, flag stacked hedges:** In
academic writing, a single hedge is not just allowed but often required for
epistemic honesty. A statement with one layer of hedging ("we suggest that
...", "this evidence is consistent with ...", "our results indicate that ...")
should be preserved.

Flag only when two or more hedge markers stack on the same claim:

- PRESERVE (single-layer):
  "We suggest that attention heads specialize during fine-tuning."
  "The results indicate a statistically significant effect (p < 0.01)."
- FLAG (stacked):
  "We tentatively suggest that perhaps attention heads may possibly
  specialize during fine-tuning, although this could potentially also be
  explained by ..."

The hedge-marker categories to count are: (1) epistemic verbs ("suggest",
"indicate", "appear", "seem"), (2) modal verbs ("may", "might", "could"),
(3) adverbs ("perhaps", "possibly", "tentatively", "potentially"),
(4) conditional framings ("it could be argued that"). Two or more from
any combination of categories, modifying the same clause, is a stacked hedge.

## Pattern 26: Hyphenated Word Pair Overuse (MODIFY)

**Original rule:** Flag consistent hyphenation of word pairs (data-driven,
end-to-end, real-time, ...). The generic rule rewrites them without hyphens.

**Academic exception — preserve technical compound modifiers:** Several
hyphenated compounds are standard in computer-science and EECS prose and
must be preserved exactly:

- `data-driven`
- `end-to-end`
- `real-time`
- `long-tailed`
- `out-of-distribution`
- `in-context` (as in "in-context learning")
- `state-of-the-art`
- `self-supervised`
- `cross-entropy`
- `large-scale`
- `fine-tuning`
- `zero-shot`, `few-shot`, `one-shot`

Flag only when hyphens are being stacked gratuitously inside the same
sentence for rhetorical effect:

- PRESERVE: "We train a self-supervised, data-driven model on long-tailed
  visual recognition benchmarks."
- FLAG (gratuitous stacking of non-technical hyphens): "The cross-functional,
  client-facing, decision-making team produced a well-known, high-quality
  report."

The heuristic: count the non-technical hyphenated compounds (not on the
preservation list above) in a single sentence. If the count is 3 or more,
flag the sentence and suggest de-hyphenating the non-technical compounds.

## Pattern 28: Signposting and Announcements (MODIFY)

**Original rule:** Flag meta-commentary like "let's dive in", "here's what
you need to know", "let's explore", "let's break this down", "now let's
look at ...".

**Academic exception — allow structural signposting that references section
numbers or figure/table numbers:** Academic papers legitimately use
structural signposts to guide the reader through the paper's organization.
Preserve sentences that refer to a specific numbered section, figure, or
table:

- PRESERVE: "In Section 3 we present our graph attention mechanism."
- PRESERVE: "Section 4 reports ablation studies on the query encoder."
- PRESERVE: "Table 2 summarizes the per-task accuracy scores."
- PRESERVE: "We defer the proof of Theorem 1 to Appendix A."

Still flag generic signposting that does NOT reference a specific
numbered element:

- FLAG: "Let's dive into our method."
- FLAG: "Here's what you need to know about the results."
- FLAG: "In this section, we will now explore ..." (filler version, no
  structural payload).

The test is whether removing the signpost would lose information about
where something lives in the paper. "In Section 3 we present ..." = keep
(tells reader where to look). "Let's dive into our method" = flag (tells
reader nothing new).

---

## SKIP-conditional patterns

These two patterns are entirely disabled in academic mode. They are applied
normally in general mode.

## Pattern 17: Title Case in Headings (SKIP in academic mode)

**Generic rule:** Rewrite headings from Title Case to sentence case.

**Why skipped in academic mode:** The three dominant conference template
families (NeurIPS, IEEE, ACM) all **require** title case in section
headings:

- NeurIPS (`neurips_2024.sty`): section headings are rendered in bold with
  initial caps on each content word. Changing "Experimental Setup" to
  "Experimental setup" would make the paper non-compliant with the template
  and risk desk rejection.
- IEEE (`IEEEtran.cls`): `\\section{}` macros expect title case per the IEEE
  Editorial Style Manual (e.g., "Related Work", "Proposed Method",
  "Numerical Results").
- ACM (`acmart.cls`): the standard ACM template also requires title case in
  top-level headings.

In academic mode the humanizer skips this pattern entirely and leaves
section headings untouched. (If the user has an unusual venue that requires
sentence case, they can still re-enable the rule by setting
`humanizer.patterns.17: enabled` in `.paper-config.local.yml`.)

## Pattern 19: Curly Quotation Marks (SKIP in academic mode)

**Generic rule:** Replace curly quotes (“...”) with straight quotes ("...").

**Why skipped in academic mode:** LaTeX has its own established conventions
for producing typographically correct quote marks at compile time, and
those conventions are incompatible with both straight ASCII quotes and
curly Unicode quotes in the source:

- Opening quote: two backticks (`` `` ``)
- Closing quote: two apostrophes (`''`)
- Single-quote equivalents: `` ` `` and `'`

A LaTeX source file using "straight quotes" will compile to left-and-right
double-straight glyphs in the PDF (typographically wrong). A LaTeX source
file using curly quotes may also render wrong depending on the font encoding
package. The correct answer is to use the backtick-apostrophe convention
and let LaTeX render proper curly quotes at compile time.

Because rewriting quotes in academic mode would either corrupt existing
backtick-apostrophe sequences or introduce the wrong Unicode form, the
humanizer leaves all quote marks untouched when in academic mode and
defers the decision to the LaTeX engine and the user.

---

## Cross-references

- `references/humanizer_patterns.md` — the 29-pattern playbook (parent
  reference). Read this first; the overrides in this file layer on top of
  those patterns.
- `references/argumentation_patterns.md` — argumentation and rhetorical
  templates for academic drafting. The humanizer does not apply these, but
  the paper-draft agent does, and they should be read together when editing
  manuscript prose.
- Spec: `docs/superpowers/specs/2026-04-11-academic-paper-plugin-design.md`
  section 4.3 — the source of the KEEP/MODIFY/SKIP-conditional classification
  tabulated above.
