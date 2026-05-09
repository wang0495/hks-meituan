# Feature Spec: F002-dialogue-persistence

---
## Overview

- **Feature ID**: F002
- **Feature Name**: F002-dialogue-persistence
- **Target Repo**: hks-meituan
- **Created**: 2026-05-09
- **Status**: Draft
  - Values: Draft | Review | Approved

---
## Purpose

将 `dialogue.py` 中的进程内 `dict[str, DialogueState]` 迁移到 Redis，使服务重启后对话上下文不丢失。对应架构文档 P0-2。

---
## User Stories

### US-1: 重启后继续对话

**As a** 用户
**I want** 服务重启后继续之前的对话调整
**So that** 不因服务端维护丢失已规划的路线

**Acceptance Criteria:**
- [ ] 服务重启后，`POST /api/dialogue/{session_id}` 能恢复完整的对话状态
- [ ] `session_id` 不变的情况下，`turn_count` 连续递增
- [ ] 对话历史（history）完整保留

### US-2: 分布式多实例支持

**As a** 运维人员
**I want** 多实例部署时各实例共享对话状态
**So that** 用户无论访问哪个实例都能正常对话

**Acceptance Criteria:**
- [ ] Redis 作为唯一真相来源，无进程内存依赖
- [ ] 多实例写入不冲突（TTL + 版本控制）

---
## Functional Requirements

### FR-1: 对话状态 Redis 持久化 [NON-PRD]

将 `DialogueState` 序列化后存储到 Redis Hash，key = `dialogue:{session_id}`，TTL = 1小时（可配置）。

### FR-2: 状态恢复 [NON-PRD]

服务启动时无需预加载存量会话（按需加载），但每个新请求需要从 Redis 读取/写入状态。

### FR-3: 回退机制 [NON-PRD]

Redis 不可用时回退到内存模式（仅警告日志），不影响核心规划流程。

---
## Non-Functional Requirements

- **Performance**: Redis 操作 < 10ms（单次 get/set）
- **Compatibility**: 对话引擎 API 不变，不影响上层调用方
- **Observability**: Redis 连接失败写 WARNING，不阻断业务

---
## Related Documents

- PRD: `../../prd/hks-meituan-prd.md`
- PRD Refs: - (基础设施改进，无 PRD 映射)
- Architecture: `../../architecture-and-optimization.md` §P0-2