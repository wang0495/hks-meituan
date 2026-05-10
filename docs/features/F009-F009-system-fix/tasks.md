# Tasks: F009-system-fix

---

## Local Tracking

- **Doc Status**: Done
- **Last Sync**: <!-- lee-spec-kit:workflow-sync 2026-05-09T12:00:00.000Z -->
- **Repo**: hks-meituan
- **Branch**: `feat/F009-system-fix`
- **Pending Change Request**: -
- **PR Review**: -

---

## Task List

### Task 1: Fix solver global state race condition [DONE]

[NON-PRD] Replace module-level globals with thread-local storage.

- **Acceptance**: ✓ Module no longer has mutable global state. `_get_weight()` reads from thread-local. Two concurrent calls with different weights work independently.
- **Checklist**:
  - [x] Replace globals with `threading.local()`
  - [x] Update `_get_weight()` and `_report_progress()` to use thread-local
  - [x] Update `solve_route()` entry to set thread-local state

---

### Task 2: Fix `_evaluate_route()` to use `_get_weight()` [DONE]

[NON-PRD] Replace hardcoded constants with dynamic weights in 2-opt scoring.

- **Acceptance**: ✓ `_evaluate_route()` uses `_get_weight()` for diversity bonus and same-type penalty. Different weights → different route output.
- **Checklist**:
  - [x] Replace hardcoded `0.5` diversity factor with `_get_weight("beta")`
  - [x] Replace hardcoded `0.3` same-type penalty with `_get_weight("delta")`
  - [x] Verify emotion_compatibility and fatigue_penalty still applied

---

### Task 3: Fix LTM prediction key mismatch [DONE]

[NON-PRD] `predict_preferences()` now returns per-dimension scores via `predicted_dimensions` key.

- **Acceptance**: ✓ `predicted_dimensions` contains culture/food/nature/social scores. `merge_user_preference()` reads from it. `preferences_source` reports `ltm_contextual` correctly.
- **Checklist**:
  - [x] Add `predicted_dimensions` to `predict_preferences()` return dict
  - [x] Fix `merge_user_preference()` to use `predicted_dimensions`
  - [x] Fix `preferences_source` tracking for preference dimensions

---

### Task 4: Fix dialogue weight retention [DONE]

[NON-PRD] All dialogue handlers pass full dynamic_weights to solve_route().

- **Acceptance**: ✓ All 6 handlers pass `state.user_intent.get("_dynamic_weights")`. `_handle_emotion_weight` preserves alpha/delta/budget_strictness.
- **Checklist**:
  - [x] `_handle_pace`: add `dynamic_weights` to `solve_route()` call
  - [x] `_handle_budget`: add `dynamic_weights` to `solve_route()` call
  - [x] `_handle_time`: add `dynamic_weights` to `solve_route()` call
  - [x] `_handle_retry`: add `dynamic_weights` to `solve_route()` call
  - [x] `_handle_emotion_weight`: preserve alpha/delta/budget_strictness
  - [x] `_handle_mood_adjust`: already passes `_dynamic_weights` correctly

---

### Task 5: Wire LTM Redis persistence [DONE]

[NON-PRD] PreferenceManager uses Redis URL from settings instead of hardcoded None.

- **Acceptance**: ✓ Redis URL built from `settings.REDIS_*`. Graceful fallback to in-memory when Redis not configured.
- **Checklist**:
  - [x] Add `_build_redis_url()` static method
  - [x] Use result instead of hardcoded `redis_url=None`

---

### Task 6: Wire `record_feedback` into dialogue flow [DONE]

[NON-PRD] After each confirmed dialogue adjustment, call `record_feedback()`.

- **Acceptance**: ✓ Both GET and POST dialogue endpoints call `record_feedback("modified")` when `changes_made` is present and `_user_id` is available.
- **Checklist**:
  - [x] Store `_user_id` in user_intent during planning
  - [x] GET `/api/dialogue`: add feedback recording
  - [x] POST `/api/dialogue/{id}`: add feedback recording

---

### Task 7: Eliminate redundant LLM call [DONE]

[NON-PRD] Merge demand vector extraction into parse_intent's LLM prompt.

- **Acceptance**: ✓ `parse_intent` LLM prompt includes 7 demand_vector dimensions. `_demand_vector` extracted from LLM response. Rule-based fallback gets default vector. Single LLM call per request.
- **Checklist**:
  - [x] Add demand_vector fields to `_SYSTEM_PROMPT`
  - [x] Extract `_demand_vector` from LLM response in `parse_intent()`
  - [x] Create default `_demand_vector` for rule-based fallback
  - [x] Remove `extract_demand_vector` call from `main.py`
  - [x] Store `_demand_vector` in user_intent for dialogue use

---

### Task 8: Wire SSE events from main.py [DONE]

[NON-PRD] `solver_stage`, `polish_done`, and `step_update` events now fire from main.py.

- **Acceptance**: ✓ Solver events collected via thread-safe list and emitted after solving. `polish_done` after narrative generation. `step_update` per step.
- **Checklist**:
  - [x] Replace `lambda: None` with `_on_solver_progress` callback
  - [x] Emit `solver_stage` events from collected list
  - [x] Emit `polish_done` after narrative generation
  - [x] Emit `step_update` after each step

---

### Task 9: Fix PipelineBar phase ordering [DONE]

[NON-PRD] Reorder phases to match actual emission order.

- **Acceptance**: ✓ Phases display as `parsing → identifying → ltm_predict → weight_mapping → searching → solving → narrating → saving`, matching emission order.
- **Checklist**:
  - [x] Reorder PipelineBar labels and iteration order
  - [x] Update `done` handler phase order
  - [x] Update `phases` reactive default dict

---

### Task 10: Fix dialogue edge cases [DONE]

[NON-PRD] Fix pace toggle, time direction, budget bounds, gamma cap, "累" routing, retry randomization.

- **Acceptance**: ✓ Three-way pace toggle (闲逛型↔平衡型↔特种兵型). "晚" shifts end time. Budget clamped [20, 10x]. Gamma capped at 3.0. "累" routes to emotion_weight. Retry shuffles candidates.
- **Checklist**:
  - [x] Fix `_handle_pace` three-way toggle
  - [x] Fix `_handle_time` "晚" → end time
  - [x] Add budget bounds (min 20, max 10x original)
  - [x] Cap gamma at 3.0
  - [x] Add "累" to `_classify_instruction` emotion_weight routing
  - [x] Add candidate shuffling for retry

---

## Completion Criteria

- [x] All tasks are `[DONE]`, and each task's `Acceptance` is verified and `Checklist` is checked
- [x] Tests executed and passing (record command/result below)
- [x] Final outcome shared and any required user confirmation recorded at the documented workflow checkpoint

### Test Run Log (Latest by Command)

| Command | Last Run (Local, YYYY-MM-DD) | Result |
| --- | --- | --- |
| `pytest tests/test_solver.py -q` | 2026-05-09 | 53/53 PASS |
| `pytest tests/test_dialogue.py -q` | 2026-05-09 | 120/120 PASS |
| `pytest tests/test_memory.py -q` | 2026-05-09 | 12/12 PASS |
| `pytest tests/test_economy.py -q` | 2026-05-09 | 7/7 PASS |
| `pytest tests/test_filters.py -q` | 2026-05-09 | 26/26 PASS |
| `pytest tests/test_perception.py -q` | 2026-05-09 | 24/24 PASS |
| **Total (affected modules)** | **2026-05-09** | **262/262 PASS** |
