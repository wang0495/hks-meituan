# F010 Decisions

## Decision 1: 讯飞 API 作为唯一 LLM 提供商

**Date**: 2026-06-01
**Status**: Approved

### Context
用户要求后端全部转向讯飞 API 调用。

### Decision
- 使用讯飞 API (`maas-coding-api.cn-huabei-1.xf-yun.com/v2`) 作为唯一 LLM 提供商
- 使用 `xopqwen35v35b` 作为主模型
- `.env.example` 更新为讯飞 API 配置

### Consequences
- 需要确保所有 LLM 调用兼容讯飞 API
- 需要验证基准测试分数

---

## Decision 2: 纯 HTML/CSS/JS 前端架构

**Date**: 2026-06-01
**Status**: Approved

### Context
当前前端是纯 HTML/CSS/JS，不使用框架。

### Decision
- 保持纯 HTML/CSS/JS 架构
- 使用 Canvas/SVG 实现架构可视化
- 使用原生 JavaScript 实现组件

### Consequences
- 开发效率较低，但更轻量
- 需要手动实现组件系统

---

## Decision 3: SSE 流式响应优化

**Date**: 2026-06-01
**Status**: Approved

### Context
用户要求 10 秒内输出首 token。

### Decision
- 优化 SSE 事件频率
- 减少首 token 延迟
- 使用流式打字机效果

### Consequences
- 需要优化后端 SSE 事件发送
- 需要优化前端 SSE 事件处理