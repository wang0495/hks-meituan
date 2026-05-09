# Implementation Plan: F003-llm-parallel

---
## Overview

- **Feature ID**: F003
- **Target Repo**: hks-meituan
- **Created**: 2026-05-09
- **Status**: Draft

---
## Tech Stack

| Category | Choice | Reason |
|----------|--------|--------|
| 并发 | asyncio.gather | 已有 asyncio 基础 |
| 超时 | asyncio.wait_for | 5s LLM 超时兜底已有 |
| 降级 | 模板引擎 | narrator.py 已有模板逻辑 |

---
## Architecture (优化前 vs 优化后)

```
优化前（串行）:
  parse_intent(LLM) → get_data(内存) → solve_route(CPU) → generate_narrative(LLM) → SSE steps
         8s               0.01s               10s                    5s               = 23s
                          ↑ 不可并行                                           ↑ 用户等5s才看到step

优化后（步骤提前推送 + narrate 后台执行）:
  parse_intent(LLM) → filter → solve_route(CPU) → SSE step (模板文案先推)
         8s               0.01s        10s             0.1s
                                                      │
                                          generate_narrative(LLM) ────→ SSE update (润色文案)
                                              5s (后台 task 不阻塞)         异步推更新
                                      
  用户感知: solve 完成后 0.1s 就见到 step，不用等 narrate 5s
  架构改动: narrate 改为 asyncio.create_task，用回调推更新
```

**为什么不能做 parse+solve 并行？**
`solve_route(candidates, intent)` 需要 `intent` 作为参数，而 intent 来自 `parse_intent()` 的输出。这是数据依赖，无法绕过。

**真正能优化的点：**
1. `get_data("city_poi_db")` 是内存读取（<10ms），没必要并行
2. `generate_narrative` 当前阻塞 SSE 推送——改为后台 task
3. step 先用模板文案推送，narrate(LLM) 完成后推 `step_update` 事件润色

---
## File Structure

```
backend/
├── routers/sse.py            # 修改: 并行化 orchestrator
├── services/
│   ├── intent_parser.py      # 改动: parse_intent 返回更完整上下文
│   ├── narrator.py           # 改动: generate_narrative 支持预热模板
│   └── llm_service.py        # 无改动（复用）
tests/
├── test_llm_parallel.py              # 新增
```

---
## Test Strategy

- **Unit Tests**: `test_llm_parallel.py` — mock 两次 LLM 调用，验证并行执行
- **Integration Tests**: 用 `aioresponses` mock LLM API，测量总耗时
- **Manual**: 用 curl 观察 SSE 事件时间戳

---
## Related Documents

- Spec: [spec.md](./spec.md)
- Decisions: [decisions.md](./decisions.md)