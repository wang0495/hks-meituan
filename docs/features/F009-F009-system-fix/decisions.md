# Decisions Log

---

## D001: F009-system-fix — 求解器全局状态 → thread-local (2026-05-09)

- **Context**: `solver.py` used module-level globals (`_current_weights`, `_gamma_multiplier`, `_progress_callback`) for dynamic weights and progress reporting. Under concurrent requests, `asyncio.to_thread` runs solver in a thread pool — multiple threads would read/write the same globals, corrupting each other's state.
- **Constraints**: Must not change solver API signature. Must remain backward compatible.
- **Options**: (1) `threading.local()` — each thread gets isolated state. (2) Pass state through params to every internal function. (3) Use `contextvars`.
- **Decision**: `threading.local()` — minimal diff, zero API change, matches the existing thread-pool execution model.
- **Rationale**: Contextvars require async-aware propagation which doesn't work across `asyncio.to_thread` (solver is sync). Thread-local is the standard pattern for thread-pool workers and solves the race condition with 3 lines of infrastructure.
- **Trace**:
  - **At DOING start**: Replace `global _current_weights` assignments with `_get_tl().current_weights = ...`
  - **Before DONE**: Verified with concurrent test that weights are thread-isolated. 53 solver tests pass.
- **Evidence**:
  - **Commit**: `solver.py` — thread-local accessor `_get_tl()`, all global references replaced.

## D002: F009-system-fix — `_evaluate_route()` 使用动态权重 (2026-05-09)

- **Context**: `_evaluate_route()` (2-opt scoring) used hardcoded constants (`0.5` for diversity, `0.3` for same-type penalty) while `_phase1_initialize()` (greedy construction) used `_get_weight()`. This meant WeightMapper's personalized alpha/beta/gamma/delta only affected the initial construction — 2-opt could undo them.
- **Decision**: Replace hardcoded constants in `_evaluate_route()` with `_get_weight("beta")` and `_get_weight("delta")`.
- **Rationale**: Consistent weight application across all solver phases. Matching the Phase 1 pattern.

## D003: F009-system-fix — LTM `predicted_dimensions` 替代扁平 key 匹配 (2026-05-09)

- **Context**: `predict_preferences()` returned `predicted_categories: ["文化"]` (a list). `merge_user_preference()` iterated `["culture", "food", "nature", "social"]` checking `dim in ltm_prediction`. The list never matched the string keys, making LTM preference learning dead code.
- **Decision**: Add `predicted_dimensions: {"culture": 0.8, "food": 0.3}` to LTM output. Fix consumer to read from `predicted_dimensions`.
- **Rationale**: Structured dimension scores are more useful downstream (solver uses numeric preferences). The category→dimension mapping is deterministic.

## D004: F009-system-fix — 对话引擎保留 WeightMapper 权重 (2026-05-09)

- **Context**: All dialogue handlers (`_handle_pace`, `_handle_budget`, `_handle_time`, `_handle_retry`) called `solve_route()` without `dynamic_weights`. `_handle_emotion_weight` only passed gamma+beta, losing alpha/delta/budget_strictness.
- **Decision**: Store `_dynamic_weights` and `_demand_vector` in `user_intent` during planning. All dialogue handlers pass `state.user_intent.get("_dynamic_weights")` to `solve_route()`. Emotion weight handler preserves existing weights.
- **Rationale**: Zero new state infrastructure — user_intent already persists across planning↔dialogue.

## D005: F009-system-fix — LTM Redis 持久化 (2026-05-09)

- **Context**: `PreferenceManager._ensure_init()` hardcoded `redis_url=None`. LongTermMemory's Redis persistence code existed but was never activated for the V2 pipeline.
- **Decision**: Read Redis URL from `settings.REDIS_*` config. Graceful fallback to in-memory when Redis is not configured.
- **Rationale**: Config-driven, zero config change needed for existing deployments.

## D006: F009-system-fix — `record_feedback` 接入对话流程 (2026-05-09)

- **Context**: `PreferenceManager.record_feedback()` existed but was never called. WeightMapper deltas never learned from user behavior.
- **Decision**: Both GET and POST dialogue endpoints call `record_feedback("modified")` after successful adjustments. User intent's `_demand_vector` and `_dynamic_weights` are passed for context.
- **Rationale**: Per-endpoint hook avoids modifying the dialogue engine's internal flow.

## D007: F009-system-fix — 消除冗余 LLM 调用 (2026-05-09)

- **Context**: Plan endpoint called `parse_intent` (LLM #1) then `extract_demand_vector` (LLM #2) on identical `user_input`. The demand vector dimensions can be extracted from the same LLM response.
- **Decision**: Add 7 demand_vector fields to `parse_intent`'s `_SYSTEM_PROMPT`. Extract `_demand_vector` from LLM response. Create default vector for rule-based fallback. Remove `extract_demand_vector` call from main.py.
- **Rationale**: Single LLM call per request = half the latency, half the cost.

---

## Evidence Summary

| Change | Files Modified | Tests |
|--------|---------------|-------|
| Solver thread-local + dynamic weights | `solver.py` | 53/53 solver tests pass |
| LTM predicted_dimensions | `long_term.py`, `intent_parser.py` | Verified via integration test |
| Dialogue weight retention | `dialogue.py` | 120/120 dialogue tests pass |
| LTM Redis persistence | `preference_manager.py` | 12/12 memory tests pass |
| record_feedback wiring | `main.py` | Integration test |
| Redundant LLM call eliminated | `intent_parser.py`, `main.py` | Verified via parse_intent output |
| SSE solver_stage/polish_done/step_update | `main.py` | Code review |
| PipelineBar phase order | `tui_app.py` | Visual verification |
| Dialogue edge cases | `dialogue.py` | 120/120 dialogue tests pass |
| Total | 8 files | **231/231 tests pass** |
