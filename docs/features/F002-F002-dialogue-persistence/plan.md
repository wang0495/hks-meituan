# Implementation Plan: F002-dialogue-persistence

---
## Overview

- **Feature ID**: F002
- **Target Repo**: hks-meituan
- **Created**: 2026-05-09
- **Status**: Draft

---
## Tech Stack

| Category | Choice | Reason |
|----------|--------|--------|
| 序列化 | json.dumps / json.loads | 已有依赖，足够简单 |
| Redis 客户端 | redis.asyncio (复用现有) | 与 session.py 一致 |
| 回退 | 内存 dict 兜底 | 不阻断业务 |

---
## Architecture

```
dialogue.py                      Redis
┌─────────────────────┐          ┌──────────────────────────┐
│ DialogueEngine      │  get    │  dialogue:{session_id}   │
│ .sessions[session_id]│─────────▶│  JSON: DialogueState     │
│ (内存, 仅读缓存)     │  set    │  TTL: 3600s              │
└─────────────────────┘          └──────────────────────────┘
```

**关键决策**：
- 不改 `DialogueEngine` 对外 API
- `DialogueState` 不改类定义，加 `to_dict()` / `from_dict()` 方法
- Redis 作为唯一持久存储，每次读写直连 Redis（无内存缓存层——Redis 亚毫秒响应，缓存层只会引入不一致性）
- `DialogueEngine.sessions` 保留为读缓存优化，但 TTL=0（每次强制从 Redis 读，写时双写）

---
## File Structure

```
backend/services/
├── dialogue.py          # 修改: DialogueEngine 加持久化
│
tests/
├── test_dialogue_persistence.py   # 新增: 持久化 + 恢复测试
```

**仅修改 1 个核心文件**，最小改动。

---
## Test Strategy

- **Unit Tests**: `test_dialogue_persistence.py` — 模拟 Redis，验证序列化/反序列化、TTL、并发
- **Integration Tests**: 用 `fakeredis` 跑 pytest，验证完整流程
- **Manual**: 重启服务后用 `curl` 验证会话可恢复

---
## Data Schema (Redis)

Key: `dialogue:{session_id}`

```json
{
  "session_id": "uuid",
  "route": { ... },
  "user_intent": { ... },
  "history": [ { "role": "user|assistant", "content": "...", "timestamp": "..." } ],
  "pending_changes": [ ... ],
  "turn_count": 3,
  "max_turns": 10,
  "created_at": "...",
  "last_active": "..."
}
```

---
## Related Documents

- Spec: [spec.md](./spec.md)
- Decisions: [decisions.md](./decisions.md)