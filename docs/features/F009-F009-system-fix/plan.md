# Implementation Plan: F009-system-fix

---

## Overview

- **Feature ID**: F009
- **Target Repo**: hks-meituan
- **Created**: 2026-05-09
- **Status**: Draft
  - Values: Draft | Review | Approved

---

## Tech Stack

| Category | Choice | Reason |
| -------- | ------ | ------ |
| Backend | Python 3.12 + FastAPI | Existing stack |
| State management | Thread-local + instance-level | Fix solver race condition |
| Persistence | Redis (existing `settings.REDIS_URL`) | LTM already has Redis code, just not wired |

---

## Architecture Changes

### Data Flow (Fixed)

```
用户输入
  │
  ▼
意图解析 (parse_intent → LLM 1x → returns intent + demand_vector merged)
  │
  ▼
WeightMapper (demand_vector → alpha/beta/gamma/delta/budget_strictness)
  │
  ▼
求解器 (thread-local state, dynamic_weights in both Phase 1 & Phase 2)
  │
  ▼
SSE (solver_stage callback → actual events; polish_done/step_update from main.py)
  │
  ▼
对话调整 (preserves full 5-weight set → passes to solve_route → calls record_feedback)
  │
  ▼
LTM (Redis-backed via settings, not hardcoded None)
```

### Solver State: Global → Thread-local

Replace module-level globals:
```python
# BEFORE
_current_weights = {}
_gamma_multiplier = 1.0
_progress_callback = None

# AFTER
_thread_local = threading.local()
# accessed via _get_weight() which reads _thread_local.current_weights
```

### LTM Persistence: Hardcoded None → Config-Driven

```python
# BEFORE
self.ltm = LongTermMemory(redis_url=None)

# AFTER
redis_url = settings.REDIS_URL if settings.REDIS_URL else None
self.ltm = LongTermMemory(redis_url=redis_url)
```

### LLM Calls: 2 → 1

Fold `extract_demand_vector` logic into `parse_intent`'s LLM prompt so the same LLM response includes both the structured intent and the 7-dimension demand vector. This eliminates the second LLM call entirely.

---

## File Structure Changes

```
backend/
├── services/
│   ├── solver.py           # [MODIFY] thread-local state, _evaluate_route uses _get_weight()
│   ├── intent_parser.py    # [MODIFY] merge demand vector into parse_intent LLM prompt; fix LTM key merge
│   ├── dialogue.py         # [MODIFY] pass full dynamic_weights; call record_feedback
│   ├── preference_manager.py # [MODIFY] use settings.REDIS_URL for LTM
│   ├── memory/
│   │   └── long_term.py    # [MODIFY] predict_preferences returns per-dimension values
│   ├── preference_dialogue.py # [MODIFY] remove extract_demand_vector (folded into parse_intent)
│   └── holiday_utils.py    # [MODIFY] improve weekday naming
├── main.py                 # [MODIFY] remove redundant LLM call; wire solver progress callback; emit polish_done
├── tui_app.py              # [MODIFY] fix PipelineBar phase order
```

---

## Test Strategy

- **Unit Tests**: Update solver tests to verify `_evaluate_route` uses dynamic weights; test LTM key merge
- **Integration Tests**: Test dialogue → solve_route weight propagation
- **E2E Tests**: Manual TUI verification (all SSE events fire correctly)

---

## Related Documents

- Spec: [spec.md](./spec.md)
- Decisions: [decisions.md](./decisions.md)
