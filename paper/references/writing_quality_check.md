# Writing Quality Check

This reference defines five categories of writing quality checks for academic papers. Apply all five categories during self-review after completing each section.

---

## A. High-Frequency Term Warnings

The following 25 terms are statistically overrepresented in AI-generated academic text. Flag every occurrence and replace with a precise, domain-appropriate alternative.

| # | Term | Why Flagged | Better Alternatives |
|---|------|-------------|---------------------|
| 1 | delve | Overused filler verb; adds no precision | examine, investigate, analyze |
| 2 | tapestry | Cliche metaphor in academic writing | combination, mixture, collection |
| 3 | landscape | Vague metaphor for a research area | field, domain, body of work |
| 4 | pivotal | Inflated importance marker | important, key, central |
| 5 | crucial | Near-synonym of pivotal; equally overused | essential, necessary, required |
| 6 | foster | Vague causation verb | encourage, enable, support, promote |
| 7 | showcase | Informal; better suited for marketing | demonstrate, present, illustrate |
| 8 | testament | Grandiose; avoids stating the actual evidence | evidence, demonstration, indication |
| 9 | navigate | Metaphorical when literal movement is absent | address, handle, manage |
| 10 | leverage | Corporate jargon imported into academia | use, employ, exploit, apply |
| 11 | realm | Archaic metaphor for a domain | area, domain, scope |
| 12 | embark | Overly dramatic for beginning a study | begin, start, initiate, undertake |
| 13 | underscore | Used reflexively instead of stating the point | highlight, emphasize, show |
| 14 | multifaceted | Vague complexity claim without specifics | complex (specify which facets), multi-component |
| 15 | nuanced | Claims subtlety without demonstrating it | specific, detailed, fine-grained |
| 16 | comprehensive | Often unverifiable; rarely truly comprehensive | extensive, thorough, broad |
| 17 | robust | Vague strength claim (see exception below) | reliable, resilient, stable, strong |
| 18 | intricate | Vague complexity without explanation | complex (then explain the complexity) |
| 19 | cornerstone | Cliche metaphor for foundational work | foundation, basis, core component |
| 20 | paradigm | Overused outside philosophy of science | approach, framework, model |
| 21 | synergy | Corporate jargon with no precise meaning | interaction, complementary effect, combined benefit |
| 22 | holistic | Vague claim of completeness | integrated, unified, system-wide |
| 23 | streamline | Informal and imprecise in technical contexts | simplify, optimize, reduce (specify what) |
| 24 | cutting-edge | Marketing language, not academic | recent, state-of-the-art, advanced |
| 25 | groundbreaking | Hyperbolic self-promotion | novel, original, first (only if verifiably true) |

### Exception Rule

A flagged term is **acceptable** if it is standard technical terminology within the discipline. Examples:

- **"robust"** in robust optimization, robust statistics, or robustness testing is a defined technical term. Do not replace it in these contexts.
- **"paradigm"** in "programming paradigm" is standard. Do not replace it.
- **"landscape"** in "loss landscape" or "energy landscape" is a technical term. Do not replace it.

When in doubt: if the term has a formal definition in the field and you are using that definition, keep it. If it is decorative, replace it.

---

## B. Punctuation Control

### Em Dash (---)

- **Limit:** 3 or fewer per entire paper.
- **Rationale:** Em dashes break reading flow in technical prose. Use parentheses or restructure the sentence instead.
- **Fix:** Replace with parenthetical clause, a comma-delimited appositive, or a separate sentence.

### Semicolons

- **Limit:** 2 or fewer per 1000 words.
- **Rationale:** Semicolons join independent clauses but often signal a sentence that should be split.
- **Fix:** Split into two sentences, or use an explicit conjunction.

### Colon-List Sequences

- **Detection:** Flag if more than 3 colon-introduced lists appear in a single section.
- **Rationale:** Overuse creates a bullet-point feel that fragments the argument.
- **Fix:** Convert some lists into flowing prose, or use a formal `\begin{itemize}` environment for lists that truly benefit from enumeration.

---

## C. Throat-Clearing Openers

Delete these phrases on sight. They add no content and delay the real sentence.

| # | Opener | Why Delete |
|---|--------|------------|
| 1 | "In the realm of..." | Vague scene-setting; start with the specific topic instead. |
| 2 | "It's important to note that..." | If it is important, the content will show it. |
| 3 | "In today's rapidly evolving..." | Cliche temporal framing; irrelevant to the technical claim. |
| 4 | "This section will discuss..." | Meta-commentary; just discuss the topic directly. |
| 5 | "As we delve into..." | Combines two flagged patterns (delve + throat-clearing). |
| 6 | "It is worth noting that..." | Same as #2; content should speak for itself. |
| 7 | "In recent years..." | Vague temporal reference; specify the time range or omit. |
| 8 | "It has been shown that..." | Agentless passive; cite who showed it. |
| 9 | "There has been growing interest in..." | Vague trend claim; cite evidence of the trend or omit. |
| 10 | "It goes without saying that..." | If it goes without saying, do not say it. |
| 11 | "Needless to say..." | Same as #10. |
| 12 | "As previously mentioned..." | Either the reader remembers or a forward reference is clearer. |

### Meta-Commentary Warning

Avoid sentences that describe what the section does rather than doing it. For example:

- **Bad:** "This section discusses the architecture of our model."
- **Good:** "Our model consists of three components: an encoder, a fusion module, and a decoder."

### Exception: Introduction Roadmap

Sentences that describe paper organization in the Introduction are acceptable:

- "Section 3 presents our method."
- "We evaluate our approach in Section 5."

These help the reader navigate the paper and are expected by reviewers.

---

## D. Structure Pattern Warnings

### 1. Rule of Three Compulsion

- **Detection:** Every argument or list has exactly 3 sub-points, regardless of how many the evidence supports.
- **Fix:** Use as many sub-points as the evidence warrants. Two strong points are better than two strong points padded with a weak third. Four genuine contributions should not be artificially trimmed to three.

### 2. Uniform Paragraph Length

- **Detection:** All paragraphs in a section fall within a narrow word-count band (e.g., all between 140-160 words).
- **Fix:** Vary paragraph length intentionally. Use short paragraphs (2-3 sentences) for emphasis or to state a key result. Use longer paragraphs for complex arguments that require extended evidence and explanation.

### 3. Synonym Cycling

- **Detection:** The same concept is referred to by rotating synonyms (e.g., "students" -> "learners" -> "participants" -> "students") within or across paragraphs.
- **Fix:** Pick one term per concept and use it consistently within each section. If a term must change (e.g., different context), introduce the new term explicitly: "We refer to these participants as annotators in the evaluation phase."

### 4. Binary Contrast Overuse

- **Detection:** The "while X, Y" or "whereas X, Y" pattern appears more than twice in the paper.
- **Fix:** Limit to a maximum of 2 instances per paper. Replace with sequential sentences: state the first point, then state the contrasting point with "However," or "In contrast,".

### 5. Mirror Structure

- **Detection:** Every section or subsection follows an identical internal template (e.g., every related-work subsection has intro-3 papers-gap-transition).
- **Fix:** Adapt the internal structure to the content. A subsection covering a well-explored area may need more papers and a nuanced gap analysis. A subsection covering a niche area may need more background and fewer papers.

---

## E. Burstiness

Sentence length variation is a key marker of readable academic prose. Monotonous sentence length creates a robotic, list-like feel.

### Detection Rule

Flag any passage where **5 or more consecutive sentences** fall within a narrow word-count range (within **5 words** of each other). For example, five sentences of 18, 20, 19, 21, and 17 words would trigger a flag.

### Fix

- **Insert a short punchy sentence** (8-12 words) to break the pattern. Short sentences work well for stating results or transitions.
- **Combine two short sentences** into a longer compound sentence to add variety in the other direction.
- **Read the passage aloud** (mentally). If it sounds like a metronome, it needs variation.

### Per-Section Targets

| Section | Variation Target | Rationale |
|---------|-----------------|-----------|
| Abstract | Moderate | Compressed format limits variation, but avoid pure monotone. |
| Introduction | High | Must engage the reader; rhythm matters. |
| Literature Review | Moderate | Survey prose benefits from some regularity but not complete uniformity. |
| Methods | Low (acceptable) | Procedural writing is naturally more uniform. Flag only extreme monotone. |
| Results | Moderate | Alternates between data presentation and interpretation. |
| Discussion | Highest | Argumentative prose demands the most rhythmic variation. |

---

## How to Use

Apply this checklist during self-review after completing each section draft.

1. Read through the section once for each category (A through E), marking violations.
2. Count total violations across all categories.
3. Apply the scoring threshold:
   - **0 violations** = Clean. The section passes.
   - **1-3 violations** = Minor fix. Correct each flagged item individually.
   - **4+ violations** = Pattern issue. The writing approach has a systemic problem. Rewrite the section with a different stylistic strategy rather than patching individual violations.
4. **Do NOT report scores to the user.** Fix all issues silently. The user should receive a clean draft, not a diagnostic report.
5. After fixing, re-scan to confirm that fixes did not introduce new violations (e.g., replacing a flagged term with another flagged term).
