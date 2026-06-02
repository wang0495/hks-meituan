# F010: HKS-Meituan 全面优化

## Overview

对 hks-meituan 项目进行全面优化，涵盖三个方面：前端用户体验增强、后端全面转向讯飞 API 调用、以及前后端对接优化。目标是实现 10 秒内首 token 响应，同时保持基准测试分数在可接受范围内。

## Problem

1. **前端**: 当前前端是纯 HTML/CSS/JS 单页面应用，UI 虽有一定设计但缺少架构可视化、缺少 agent 运行状态展示、缺少丰富的交互动效
2. **后端**: LLM 服务已部分使用讯飞 API (xopqwen35v35b)，但 `.env.example` 仍以 DeepSeek 为例，需要全面统一到讯飞
3. **性能**: 需要确保首 token 响应时间 < 10s，同时基准测试分数不能大幅下降

## Scope

### In Scope

1. **前端优化**:
   - 架构设计可视化（Agent Pipeline 流程图、LangGraph 节点图）
   - 丰富用户观感（动画、过渡、粒子效果、加载状态）
   - Agent 实时运行状态面板（展示各专家 agent 的思考过程）
   - SSE 事件流的前端消费优化（渐进式渲染、流式打字机效果）
   - 响应式布局优化
   - 参考 GitHub 上类似项目的前端设计

2. **后端优化**:
   - 全面转向讯飞 API（更新 `.env.example`、`llm_service.py` 兼容性）
   - 后端架构优化（连接池、缓存策略、流式响应）
   - SSE 流式响应优化（减少首 token 延迟）

3. **前后端对接**:
   - SSE 事件协议对齐
   - 错误处理和降级机制
   - API 超时和重试策略

4. **测试**:
   - 使用讯飞 API 跑基准测试
   - 确保 5 场景平均分不低于基线的 90%

### Out of Scope

- 数据库迁移
- Docker 部署配置变更
- 移动端适配（当前仅桌面端）

## Acceptance Criteria

1. [ ] 首 token 响应时间 < 10 秒（SSE 首事件）
2. [ ] 后端所有 LLM 调用统一使用讯飞 API
3. [ ] `.env.example` 更新为讯飞 API 配置
4. [ ] 前端包含架构可视化组件
5. [ ] 前端 Agent Pipeline 面板实时展示 agent 状态
6. [ ] 基准测试 5 场景平均分不低于基线的 90%
7. [ ] 前端有流式打字机效果
8. [ ] SSE 事件处理无明显延迟

## Technical Notes

- 前端是纯 HTML/CSS/JS，不使用框架
- 后端使用 FastAPI + OpenAI 兼容 API
- 讯飞 API base_url: `https://maas-coding-api.cn-huabei-1.xf-yun.com/v2`
- 当前模型: `xopqwen35v35b`
- SSE 用于实时流式传输规划结果

## Related Documents

- Architecture: `docs/architecture.md`
- API Reference: `docs/API.md`
- Agent Architecture: `docs/agent_architecture.md`