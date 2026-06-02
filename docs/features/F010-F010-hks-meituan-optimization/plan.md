# F010 Implementation Plan

## Architecture Overview

```
Frontend (HTML/CSS/JS)  ←→  FastAPI Backend  ←→  讯飞 API
     ↓                         ↓
  Canvas Map + SSE         agents_v3 Graph
  Agent Pipeline UI        LangGraph Nodes
  流式打字机效果            缓存 + 连接池
```

## Phase 1: 后端全面转向讯飞 API (Backend Migration)

### 1.1 更新 `.env.example`
- 将默认 LLM 配置改为讯飞 API
- 添加讯飞 API 多模型配置示例
- 更新注释说明

### 1.2 更新 `llm_service.py`
- 确保与讯飞 API 的 OpenAI 兼容接口完全兼容
- 添加流式响应的超时处理
- 优化连接池配置

### 1.3 更新 `config_loader.py`
- 确保配置加载支持讯飞 API 特定参数

## Phase 2: 前端优化 (Frontend Enhancement)

### 2.1 架构可视化
- 添加 Agent Pipeline 流程图组件
- 展示 LangGraph 节点执行状态
- 使用 Canvas/SVG 绘制架构图

### 2.2 用户体验增强
- 流式打字机效果（SSE 文本逐字显示）
- Agent 状态实时动画
- 加载状态优化（骨架屏、进度条）
- 过渡动画优化

### 2.3 Agent Pipeline 面板
- 实时展示各 Expert Agent 状态
- 展示思考过程和中间结果
- 展示 Negotiation 讨论过程

### 2.4 响应式布局
- 移动端适配
- 面板折叠/展开

## Phase 3: 前后端对接优化 (Integration)

### 3.1 SSE 事件协议
- 统一 SSE 事件格式
- 添加 agent 状态事件类型
- 优化事件频率

### 3.2 错误处理
- 前端错误降级 UI
- 超时重试机制
- 离线提示

### 3.3 性能优化
- 首 token 延迟优化
- 减少不必要的 API 调用
- 缓存策略

## Phase 4: 测试验证 (Testing)

### 4.1 基准测试
- 使用讯飞 API 运行 `test_model_bench.py`
- 记录 5 场景分数
- 对比基线分数

### 4.2 性能测试
- 测量首 token 响应时间
- 测量端到端延迟
- 负载测试

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `.env.example` | Update | 讯飞 API 配置 |
| `backend/services/llm_service.py` | Update | 讯飞 API 兼容性优化 |
| `frontend/index.html` | Update | 前端 UI 增强 |
| `frontend/js/app.js` | Update | SSE 处理 + Agent Pipeline |
| `frontend/css/main.css` | Update | 样式优化 |
| `frontend/components/pipeline.js` | Create | Agent Pipeline 组件 |
| `frontend/components/architecture.js` | Create | 架构可视化组件 |