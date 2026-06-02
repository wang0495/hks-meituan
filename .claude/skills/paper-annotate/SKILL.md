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
