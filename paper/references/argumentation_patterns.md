# High-impact argumentation patterns

These patterns distill the argumentation moves used by strong empirical EECS
papers. They are the techniques that separate papers that land (oral,
best-paper runner-up) from papers that merely get accepted.

Source inspiration: Yang Yue, Zhiqi Chen, Rui Lu, Andrew Zhao, Zhaokai Wang,
Shiji Song, Gao Huang. *Does Reinforcement Learning Really Incentivize
Reasoning Capacity in LLMs Beyond the Base Model?* NeurIPS 2025 Best Paper
Runner-up. The worked examples under each pattern below come from that
paper.

This reference is consulted by `argument_builder` (when constructing the
ArgumentBlueprint) and by `peer_reviewer` (when judging argumentation
strength). It is NOT a required template -- use the 2-3 patterns that fit
your contribution, not all 5.

---

## Pattern 1: Counterintuitive thesis against prevailing belief

**What it is.** Frame the paper around a sharp question whose answer
contradicts a widespread, unexamined assumption in the field. Readers
land on a result that forces them to update their model.

**When to use.** Use when the field has a prevailing narrative that you can
rigorously test and find wrong. Do NOT use when you merely disagree with
one prior paper -- you need an *assumption*, not a *paper*, to challenge.

**How to structure.**

1. State the prevailing belief explicitly, with 3+ citations showing it is
   widely held. Use direct phrasing such as "It is commonly believed that...".
2. Pose the paper's title as a sharp question (e.g., "Does X really do Y?").
3. Reveal the empirical answer in the abstract's last sentence.
4. Devote the body of the paper to the evidence chain that forces the
   update.

**Failure modes.**

- *Strawman.* Misrepresenting the prevailing belief. Reviewers will cite
  recent work that already expressed your nuance. Avoid by quoting the
  strongest version of the belief held by serious researchers.
- *Overclaim.* Your counterintuitive finding applies under some conditions
  but you state it universally. Fix with Pattern 4 (Scoped Limitation).

**Worked example (Yang Yue et al.).**

> "Recent breakthroughs in reasoning-capable LLMs have been attributed to
> Reinforcement Learning with Verifiable Rewards (RLVR). A growing literature
> claims RLVR teaches models to reason in ways the base model cannot. We
> test this assumption directly."

The paper's title frames it as a question -- "Does Reinforcement Learning
*Really* Incentivize Reasoning Capacity in LLMs Beyond the Base Model?" --
and the abstract resolves it with "No: at large k, the base model's
pass@k exceeds the RLVR-trained model's, meaning all RLVR-produced reasoning
paths were already within the base model's distribution."

---

## Pattern 2: Multi-angle evidence convergence

**What it is.** Use 3+ *independent* lines of evidence that all point at
the same conclusion. Independence matters: three different pass@k numbers
are ONE line of evidence; pass@k + coverage analysis + perplexity are
THREE lines.

**When to use.** Use when the claim is strong enough that a single angle
invites skepticism. Pair with Pattern 1 especially -- counterintuitive
claims need extra evidence to overcome reader priors.

**How to structure.**

1. State the claim once, precisely.
2. Evidence line 1 (e.g., sampling behavior at large k).
3. Evidence line 2 (e.g., distributional coverage / overlap).
4. Evidence line 3 (e.g., perplexity of RLVR outputs under the base model).
5. Explicit convergence paragraph: "Three orthogonal measurements agree: ...".
6. Breadth sweep: replicate across 2+ model families and 2+ algorithms so
   the result is not an artifact of one implementation.

**Failure modes.**

- *Correlated evidence masquerading as independent.* Three metrics that
  all derive from the same underlying statistic do not count as
  convergence. Test independence by asking: could metric A say yes and
  metric B say no? If no, they are not independent.
- *Evidence pile without synthesis.* Dumping 12 tables without a
  convergence paragraph leaves the reader to do the synthesis work.

**Worked example.**

The paper uses (a) pass@k with k up to 1024, (b) coverage analysis showing
RLVR outputs lie inside the base model's support, (c) perplexity of RLVR
outputs under the base model, and (d) a systematic sweep across six popular
RLVR algorithms and multiple model families. Each line could have failed
independently; all four agree.

---

## Pattern 3: Sharp metric choice as the reveal

**What it is.** Deliberately choose a metric that exposes the phenomenon
you want to reveal, and justify the choice on principled grounds (not on
outcome). Standard metrics often hide effects at the wrong scale.

**When to use.** Use when the community has converged on a metric that is
convenient but misleading for your question. Do NOT use when you are just
cherry-picking -- the metric must be defensible independent of your result.

**How to structure.**

1. Describe the standard metric and what it measures.
2. Explain why the standard metric is insufficient *for your question*
   (what it collapses, what aspect of the phenomenon it hides, or what
   confound it fails to separate).
3. Introduce your metric choice with principled justification stated
   BEFORE seeing the results, tied to what the question actually
   measures (the "What would a faithful test of this claim look like?"
   criterion).
4. Show both metrics on the same data. The reveal is that standard
   metric says A, your metric says B, and the gap is the mechanism.

**Failure modes.**

- *Outcome-motivated metric selection.* If your only justification for the
  metric is "it shows my result," reviewers will call it p-hacking.
  Principled justifications appear BEFORE seeing the numbers.
- *Metric the community will reject.* A metric that's "better" but nobody
  else uses becomes its own battle. Bias toward metrics with 1+ prior use
  in a related context.

**Worked example.**

Prior work on RLVR used pass@1 or pass@8, which rewards peaked distributions.
The paper argues pass@k at large k (k=128, 512, 1024) measures breadth
of reasoning capacity more faithfully: if a base model can, with enough
samples, produce a correct solution, it *has* that reasoning path. This
metric was defensible before the results were in.

---

## Pattern 4: Scoped limitation (steelmanning)

**What it is.** Acknowledge precisely what the target technique DOES
achieve before precisely scoping what it does NOT. The result is a claim
that cannot be dismissed as polemic.

**When to use.** Use whenever your paper critiques a technique, a prior
method, or a common practice. Always. Unconditional critiques are easy
targets.

**How to structure.**

1. One paragraph: "Technique X IS effective for Y". Quote the best
   argument *for* X with the same rigor you would use to argue against it.
2. One paragraph: "However, X does NOT achieve Z", where Z is the claim
   your paper disputes.
3. One paragraph: "The boundary is here: [precise]". Identify the exact
   line that separates Y from Z.

**Failure modes.**

- *Hedging collapse.* Concede so much that the thesis becomes trivial
  ("well, X works in some cases"). The scope must still be a real
  disagreement.
- *Concession without precision.* "X has some benefits" is not a
  steelman; it's a sigh. Name the benefit concretely.

**Worked example.**

The paper does NOT claim RLVR is useless. It claims: "RLVR does improve
sampling efficiency (the model hits a correct answer with fewer samples)
but does NOT expand the set of reasoning paths the model can produce.
The boundary is at the support of the base model's distribution: RLVR
reweights within the support, it does not extend it."

This scoped claim is much harder to attack than "RLVR is overhyped".

---

## Pattern 5: Falsifiable prediction

**What it is.** State the paper's central claim as a testable prediction:
under specific conditions, a specific metric will cross a specific threshold.
The prediction is falsifiable because a reader with the resources could
attempt to disprove it.

**When to use.** Use for the core contribution claim of the paper. Use
sparingly for sub-claims (not every sentence needs to be a prediction).

**How to structure.**

1. Name the conditions explicitly (model family, size, training data,
   evaluation benchmark).
2. Name the metric and the threshold the prediction commits to.
3. Name the counterfactual: what result would falsify the claim.
4. Report the actual result against that counterfactual.

**Failure modes.**

- *Unfalsifiable hedging.* "Our method may, in some cases, improve
  performance" commits to nothing. Reviewers will flag it.
- *Overcommitted prediction.* "Our method always beats baselines by 10%"
  is unlikely to survive. Pick a threshold you can defend.

**Worked example.**

The paper predicts: "For base models in the 7B-70B parameter range,
trained with six common RLVR algorithms on verifiable-reward math and code
benchmarks, pass@k at k >= 256 of the base model will equal or exceed the
RLVR-trained model." The counterfactual is straightforward: find a base
model / RLVR pair where this is not true. The paper's systematic sweep is
an attempt to exhaust the counterfactual.

---

## How to use this reference

### When writing a new paper (argument_builder)

1. List your contribution claims. For each, ask: which pattern would make
   this claim land hardest?
2. Target 2-3 patterns. More than 3 usually dilutes focus.
3. For each chosen pattern, verify the failure modes do not apply to your
   version.
4. If Pattern 1 is chosen, pair with Pattern 2 or 5 (evidence needs to be
   strong enough to support the counterintuitive framing).

### When reviewing a paper (peer_reviewer)

Add the following checks to the reviewer's **Argument Coherence**,
**Methodological Rigor**, and **Evidence Sufficiency** dimensions:

- Does the paper identify a counterintuitive finding and support it with
  multi-angle evidence (Patterns 1+2)?
- If it critiques prior work, does it scope the critique precisely
  (Pattern 4)?
- Are the central claims stated as falsifiable predictions (Pattern 5)?
- Is the choice of evaluation metric justified on principled grounds
  (Pattern 3)?

A paper that exhibits 2-3 of these patterns is likely punching above its
weight. A paper that exhibits none is likely safe but unmemorable.

---

## Cross-references

- `references/handoff_schemas.md` -- Schema 2 (ArgumentBlueprint) produced
  by `argument_builder` should note which of these patterns it targets.
- `references/writing_quality_check.md` -- writing quality operates at the
  sentence/paragraph level; this reference operates at the thesis/section
  level. They complement each other.
