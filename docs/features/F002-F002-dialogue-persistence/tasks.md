# Tasks: F002-dialogue-persistence

## Task Rules

- **Status**: `[TODO]` → `[DOING]` → `[DONE]`
- **Task communication / confirmation**:
  - `[TODO] → [DOING]`: share the task title first, then update the task state in `tasks.md`
  - `[DOING] → [DONE]`: share the result and verification first, then update `Acceptance` and `Checklist` in the same edit
  - Ask for approval before changing task state only when the task crosses a documented review checkpoint or before remote/destructive actions.
  - Do not invent a standalone `OK` approval step when the workflow does not require one.
  - Do not mark `[DONE]` while any item in that task's `Checklist` remains unchecked.
- **PRD mapping (recommended)**: add an existing PRD requirement ID tag like `[PRD-FR-001]` or `[PRD-SCOPE-V1-DESKTOP-EDITOR]` to each task line, or tag non-PRD tasks as `[NON-PRD]`.
  - Do not invent PRD IDs in `tasks.md`. Only reference IDs that already exist in `docs/prd` or the upstream requirements doc.
  - If this is a legacy feature without PRD IDs yet, backfill IDs in the source requirements doc first, then align `spec.md` `PRD Refs` and task tags together.
  - `[NON-PRD]` is for internal implementation work only. If the task changes user-facing behavior, acceptance criteria, or scope, backfill PRD first and tag it as `[PRD-...]`.

---
## Local Tracking
- **Doc Status**: Draft
- **Repo**: hks-meituan
- **Branch**: `feat/F002-dialogue-persistence`
- **Pending Change Request**: -
- **PR Review**: -
- **PR Review Evidence**: -
- **Pending Change Request**: -

---
## Task List

---

### [DONE][NON-PRD] T-F002-01 DialogueState 序列化

- Date: 2026-05-09
- Acceptance: `DialogueState` 有 `to_dict()` / `from_dict()` 方法，双向转换无数据丢失 ✅
- Checklist:
  - [x] `DialogueState` 添加 `to_dict()` 方法 → 包含所有字段
  - [x] `DialogueState` 添加 `from_dict()` 类方法 → 完整重建对象
  - [x] 验证 roundtrip: state.to_dict() → DialogueState.from_dict() == state

---

### [DONE][NON-PRD] T-F002-02 DialogueEngine Redis 持久化

- Date: 2026-05-09
- Acceptance: 创建会话后立即写入 Redis；获取会话时从 Redis 读取 ✅
- Checklist:
  - [x] `DialogueEngine` 注入 `DialoguePersistence`（内置 Redis 客户端）
  - [x] `create_session()` 调用 Redis `setex(key, ttl, json)`
  - [x] `get_session()` 直接从 Redis `get` 并重建（不经过内存缓存，避免一致性问题）
  - [x] `process_instruction()` 每次操作后调用 `_persist_state()` 同步到 Redis
  - [x] `remove_session()` 调用 Redis `delete`

---

### [DONE][NON-PRD] T-F002-03 回退机制

- Date: 2026-05-09
- Acceptance: Redis 连接失败时使用内存模式，日志记录 WARNING ✅
- Checklist:
  - [x] `DialoguePersistence._fallback: bool` 标志
  - [x] Redis 操作加 try/except，失败时 set fallback=True，继续使用内存 dict
  - [x] 日志: `logger.warning("[DialoguePersistence] Redis 不可达，切换到内存模式")`

---

### [DONE][NON-PRD] T-F002-04 单元测试

- Date: 2026-05-09
- Acceptance: `pytest tests/test_dialogue_persistence.py -v` 全部通过 ✅
- Checklist:
  - [x] 使用 `fakeredis` mock Redis
  - [x] 测试: 创建会话 → 重启（清内存）→ 恢复会话 → 继续对话
  - [x] 测试: turn_count 连续递增（process_instruction 后持久化验证）
  - [x] 测试: Redis 不可用时回退到内存模式
  - [x] 测试: 多 session 并发操作不冲突

---

## Completion Criteria

- [x] All tasks are `[DONE]`, and each task's `Acceptance` is verified and `Checklist` is checked
- [x] Tests executed and passing (record command/result below)
- [x] Final outcome shared and any required user confirmation recorded at the documented workflow checkpoint

### Test Run Log (Latest by Command)

| Command | Last Run (Local, YYYY-MM-DD) | Result |
| --- | --- | --- |
| `pytest tests/test_dialogue_persistence.py -v` | `2026-05-09` | `11 passed` |
| `pytest tests/test_dialogue.py -v` | `2026-05-09` | `34 passed`（回归通过） |