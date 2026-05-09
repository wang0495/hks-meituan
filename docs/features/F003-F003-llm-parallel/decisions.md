# Decisions Log

## D001: F003-llm-parallel design decision (2026-05-09)

- **Context**: SSE 流中两次 LLM 调用串行阻塞（P1-4），用户感知延迟高
- **Constraints**: narrate 依赖 solve 结果，不能提前；SSE 推送顺序必须按 step 顺序
- **Options**:
  1. **parse + solve 并行**: parse(LLM) 和 solve(CPU) 同时启动 → solve 完成后启动 narrate(LLM)
  2. **三段并行**: parse + solve + narrate 同时启动 → 复杂度高，且 narrate 结果可能不稳定
  3. **预取文案模板**: parse 完成后先预热模板 → 实际节省有限
- **Decision**: 选项 1 — parse + solve 并行，narrate 在 solve 完成后立即执行
- **Rationale**:
  - parse 是 LLM（慢），solve 是 CPU（中），两者无依赖可并行
  - narrate 必须等 solve 结果才能生成正确文案，串行不可避免
  - 实际节省: parse 8s + solve 10s = 18s → max(8s, 10s) + narrate 5s ≈ 15s（节省约 3s）
  - 方案 2 三段并行风险高：solve 和 narrate 如果同时失败，SSE 体验差
- **Trace**:
  - **At DOING start**: 分析 SSE 路由，发现 parse + solve 可并行
  - **Before DONE**: 确认 narrate 必须在 solve 之后
  - **Post-merge check**: -
- **Evidence**:
  - **Commit**: -
  - **PR**: -
  - **Test/Log**: -