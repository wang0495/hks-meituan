# Feature Spec: F003-llm-parallel

---
## Overview

- **Feature ID**: F003
- **Feature Name**: F003-llm-parallel
- **Target Repo**: hks-meituan
- **Created**: 2026-05-09
- **Status**: Draft

---
## Purpose

将 `/api/plan/stream` 中 `parse_intent`（LLM）+ `generate_narrative`（LLM）两次串行 LLM 调用改为并行执行，在 `solve_route`（CPU）运行期间提前生成文案模板，减少 SSE 端到端延迟。对应架构文档 P1-4。

---
## User Stories

### US-1: 加速 SSE 响应

**As a** 用户
**I want** 路线规划更快看到第一步结果
**So that** 减少等待焦虑，提升体验

**Acceptance Criteria:**
- [ ] 两次 LLM 调用总耗时 ≤ max(parse, narrate)（并行）
- [ ] SSE 推送第一阶段 "parsing" 后，快速推进到 "solving"

### US-2: 部分结果提前推送

**As a** 前端
**I want** 在 solver 运行期间就能拿到文案模板
**So that** 减少前端等待，提升感知速度

**Acceptance Criteria:**
- [ ] `solve_route` 完成后立即吐出结果，无需等待 narrate 完成
- [ ] narrate 失败时，已生成的 step 数据仍可返回

---
## Functional Requirements

### FR-1: LLM 调用并行化 [NON-PRD]

在 `solve` 完成后启动 `narrate`，两者并行（`asyncio.gather`）。若 `narrate` 超时则用模板兜底。

### FR-2: 模板降级 [NON-PRD]

当 LLM 润色不可用时，`generate_narrative` 返回纯模板结果，不阻断流程。

### FR-3: 分阶段 SSE 推送优化 [NON-PRD]

文案生成完成后才推送 step 详情（避免前后端数据不一致）。

---
## Non-Functional Requirements

- **Performance**: LLM 阶段总耗时减少 30-50%（并行节省一次串行等待）
- **Reliability**: LLM 失败有模板兜底，SSE 不会中断

---
## Related Documents

- PRD: `../../prd/hks-meituan-prd.md`
- PRD Refs: -
- Architecture: `../../architecture-and-optimization.md` §P1-4