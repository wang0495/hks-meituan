# Tasks: F003-llm-parallel

## Task Rules

- **Status**: `[TODO]` → `[DOING]` → `[DONE]`
- **Task communication / confirmation**:
  - `[TODO] → [DOING]`: share the task title first, then update the task state in `tasks.md`
  - `[DOING] → [DONE]`: share the result and verification first, then update `Acceptance` and `Checklist` in the same edit
  - Ask for approval before changing task state only when the task crosses a documented review checkpoint or before remote/destructive actions.
  - Do not invent a standalone `OK` approval step when the workflow does not require one.
  - Do not mark `[DONE]` while any item in that task's `Checklist` remains unchecked.
- **PRD mapping (recommended)**: add an existing PRD requirement ID tag like `[PRD-FR-001]` or `[PRD-SCOPE-V1-DESKTOP-EDITOR` to each task line, or tag non-PRD tasks as `[NON-PRD]`.
  - Do not invent PRD IDs in `tasks.md`. Only reference IDs that already exist in `docs/prd` or the upstream requirements doc.
  - If this is a legacy feature without PRD IDs yet, backfill IDs in the source requirements doc first, then align `spec.md` `PRD Refs` and task tags together.
  - `[NON-PRD]` is for internal implementation work only. If the task changes user-facing behavior, acceptance criteria, or scope, backfill PRD first and tag it as `[PRD-...]`.

---
## Local Tracking
- **Doc Status**: Draft
- **Repo**: hks-meituan
- **Branch**: `feat/F003-llm-parallel`
- **Pending Change Request**: -
- **PR Review**: -
- **PR Review Evidence**: -

---
## Task List

---

### [DONE][NON-PRD] T-F003-01 SSE 流: step 提前推送 + narrate 后台化

- Date: 2026-05-09
- Acceptance: `solve_route` 完成后立即推送 step（模板文案），`generate_narrative` 作为后台 task 不阻塞 SSE ✅
- Checklist:
  - [x] `solve_route` 完成后立即遍历 step 推送到 SSE（使用 narrator 模板路径生成文案）
  - [x] `generate_narrative(LLM)` 改为 `asyncio.create_task` 后台执行，不 await
  - [x] LLM 润色完成后，通过 SSE `step_update` 事件推送更新的文案到前端
  - [x] 异常处理: narrate 超时 (`_LLM_POLISH_TIMEOUT=15s`) → 保留模板文案，SSE 正常结束

---

### [DONE][NON-PRD] T-F003-02 Narrator 模板预热

- Date: 2026-05-09
- Acceptance: `generate_narrative` 在 LLM 不可用时立即返回模板结果，不阻塞 SSE ✅
- Checklist:
  - [x] `generate_narrative` 已有 `enable_llm_polish=False` 降级路径，验证其正常工作
  - [x] LLM 调用加 `asyncio.wait_for(..., timeout=15.0)` 超时保护
  - [x] 超时时记录 WARNING 并返回模板结果

---

### [DONE][NON-PRD] T-F003-03 单元测试 + 耗时验证

- Date: 2026-05-09
- Acceptance: `pytest tests/test_llm_parallel.py -v` 通过 ✅
- Checklist:
  - [x] mock 模板+润色流程，验证 steps 先用模板推，done 不阻塞
  - [x] mock `generate_narrative` 耗时 1s，验证 done 在润色完成前推送
  - [x] mock LLM 超时，验证模板兜底正常

---

## Completion Criteria

- [x] All tasks are `[DONE]`, and each task's `Acceptance` is verified and `Checklist` is checked
- [x] Tests executed and passing (record command/result below)
- [x] Final outcome shared and any required user confirmation recorded at the documented workflow checkpoint

### Test Run Log (Latest by Command)

| Command | Last Run (Local, YYYY-MM-DD) | Result |
| --- | --- | --- |
| `pytest tests/test_llm_parallel.py -v` | `2026-05-09` | `4 passed` |