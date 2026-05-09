# Decisions Log

## D001: F002-dialogue-persistence design decision (2026-05-09)

- **Context**: `DialogueState` 全在进程内存中，重启后丢失（架构文档 P0-2）
- **Constraints**: 对话引擎 API 不变；不引入新存储依赖；Redis 可用时必须用 Redis
- **Options**:
  1. 复用 `session.py` 的 `SessionManager`，把对话状态塞进 `session.data`
  2. 新建 `dialogue_redis` 模块，用独立 key `dialogue:{session_id}` 存储
  3. 把对话状态存 PostgreSQL（已有配置但未使用）
- **Decision**: 选项 2 — 独立 Redis key，与 session 分离
- **Rationale**:
  - `session.data` 是通用会话槽位，不适合存储大量结构化对话状态
  - 独立 key 可单独设置 TTL，与普通会话生命周期解耦
  - Redis 已有连接和依赖，无需引入新基础设施
  - PostgreSQL 过重，200字节的对话 JSON 不值得一张表
- **Trace**:
  - **At DOING start**: 对话状态约 200-500 字节/会话，Redis 足够
  - **Before DONE**: 确认方案2 — 独立 key，TTL=3600s
  - **Post-merge check**: -
- **Evidence**:
  - **Commit**: -
  - **PR**: -
  - **Test/Log**: -