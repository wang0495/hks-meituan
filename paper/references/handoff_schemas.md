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

See also: `references/argumentation_patterns.md` for the 5 high-impact
argumentation patterns referenced by the `patterns_used` field.

```
central_thesis:   string
sub_arguments:    list of {claim, evidence, reasoning, counter, rebuttal_strategy}
patterns_used:    list of int (pattern IDs 1-5 from argumentation_patterns.md)
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
