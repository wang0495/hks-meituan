# Feature Spec: F009-system-fix

> Fix data flow breaks in V2 pipeline: LTM prediction keys, solver weight propagation, dialogue weight retention, solver thread safety, LTM persistence, feedback loop closure, redundant LLM calls, and SSE event coverage.

---

## Overview

- **Feature ID**: F009
- **Feature Name**: F009-system-fix
- **Target Repo**: hks-meituan
- **Created**: 2026-05-09
- **Status**: Draft
  - Values: Draft | Review | Approved

---

## Purpose

The V2 pipeline (context-aware preference learning + memory loop) was implemented as 9 separate Feature stories (F001-F008). Integration audit revealed that several data-flow paths are broken:

1. **LTM prediction keys** don't match what `merge_user_preference()` expects → preference dimensions are never learned from history.
2. **Solver `_evaluate_route()`** ignores `dynamic_weights` → WeightMapper output only affects greedy construction, not 2-opt optimization.
3. **Solver uses module-level globals** → race condition under concurrent requests.
4. **Dialogue engine loses WeightMapper weights** → re-solve after dialogue adjustments uses default weights.
5. **LTM is always in-memory** → `redis_url=None` hardcoded, all "memory" lost on restart.
6. **`record_feedback` never called** → WeightMapper online learning never fires.
7. **Duplicate profile systems** → `intent_parser.PROFILES` and `user_profiles.USER_PROFILES` diverge.
8. **`extract_demand_vector` is redundant** → calls LLM on same input that `parse_intent` already processed.
9. **SSE solver progress, `polish_done`, `step_update` events never emitted** from main.py plan endpoint.
10. **PipelineBar phase order mismatched** → "parsing" fires first but displays 4th.

### User Stories

#### US-1: LTM learns preference dimensions

**As a** returning user
**I want** my history (sunny-day outdoor preference, rainy-day indoor preference) to actually affect the recommended POI categories
**So that** the system "remembers" what I like, not just my profile default

**Acceptance Criteria:**
- [ ] `merge_user_preference()` receives per-dimension preference values from LTM
- [ ] `preferences_source` correctly reports `ltm_contextual` for dimensions with historical data
- [ ] Integration test: LTM with history → predicted categories appear in intent preferences

#### US-2: WeightMapper weights actually affect solver output

**As a** user with personalized weights
**I want** my WeightMapper-computed alpha/beta/gamma/delta to affect the final route, not just the initial construction
**So that** personalization is reflected in the delivered plan

**Acceptance Criteria:**
- [ ] `_evaluate_route()` uses `_get_weight()` consistently with `_phase1_initialize()`
- [ ] Changing a weight value produces a different route output (tested)
- [ ] Concurrent requests don't corrupt each other's weights

#### US-3: Dialogue adjustments preserve personalization

**As a** user who adjusts pace/budget/time after planning
**I want** the re-solved route to keep my WeightMapper-personalized weights
**So that** I don't lose personalization when I tweak the plan

**Acceptance Criteria:**
- [ ] All dialogue handlers pass `dynamic_weights` to `solve_route()`
- [ ] The full 5-weight set (alpha/beta/gamma/delta/budget_strictness) is preserved
- [ ] `record_feedback` is called after each confirmed adjustment

#### US-4: Memory persists across restarts

**As an** operator
**I want** LTM data to survive server restart
**So that** the system doesn't "forget" everything on deploy

**Acceptance Criteria:**
- [ ] `PreferenceManager` receives a Redis-backed `LongTermMemory` instance
- [ ] Trip history loaded from Redis on startup

#### US-5: No redundant LLM calls

**As an** operator
**I want** the plan endpoint to make at most one LLM call per request
**So that** latency and cost are minimized

**Acceptance Criteria:**
- [ ] `extract_demand_vector` is folded into `parse_intent` response, or removed
- [ ] Plan endpoint makes 1 LLM call (intent parsing), not 2

---

## Functional Requirements

### FR-1: Fix LTM preference dimension propagation

`LongTermMemory.predict_preferences()` must return dimension-level preference values (culture/food/nature/social), not just a flat category list. `merge_user_preference()` must correctly consume these values and set `preferences_source` accurately.

### FR-2: Fix solver weight propagation

`_evaluate_route()` must use `_get_weight()` for alpha/beta/gamma/delta contributions, matching `_phase1_initialize()`. Module-level globals must be replaced with instance-level or thread-local state.

### FR-3: Fix dialogue weight retention

All dialogue handlers (`_handle_pace`, `_handle_budget`, `_handle_time`, `_handle_emotion_weight`, `_handle_mood_adjust`, `_handle_retry`) must pass the full 5-weight `dynamic_weights` dict to `solve_route()`. The WeightMapper's `record_feedback` must be called after confirmed adjustments.

### FR-4: Wire LTM Redis persistence

`PreferenceManager` must use Redis-backed `LongTermMemory` when Redis is configured. Remove the hardcoded `redis_url=None`.

### FR-5: Eliminate redundant LLM call

Merge `extract_demand_vector` into `parse_intent` or remove it. The plan endpoint should not call LLM twice on the same user input.

### FR-6: Wire SSE events that are defined but never emitted

`solver_stage` progress callback, `polish_done`, and `step_update` events must be emitted from the main plan endpoint, not just from the unused sse.py router.

### FR-7: Fix PipelineBar phase ordering

Reorder PipelineBar so "parsing" appears in its actual emission position (after identifying/ltm_predict/weight_mapping, or change emission order to match visual display).

---

## Non-Functional Requirements

- **Performance**: No additional LLM calls beyond current baseline. Solver execution time must not increase.
- **Correctness**: All existing tests must pass. New tests must cover the fixed data paths.
- **Thread safety**: Solver must not use mutable module-level state.

---

## Related Documents

- Audit findings: `docs/architecture-and-optimization.md` (disconnect section)
- Flow diagram: `docs/flow-diagram.txt`
- Agent audit reports (conversation context)
