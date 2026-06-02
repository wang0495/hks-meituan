# F010 Tasks

## Task 1: [DONE] 后端全面转向讯飞 API

**Priority**: HIGH
**Status**: DOING
**Tag**: NON-PRD

### Acceptance
- [ ] `.env.example` 默认配置改为讯飞 API
- [ ] `llm_service.py` 兼容讯飞 OpenAI 兼容接口
- [ ] 所有 LLM 调用使用讯飞 API

### Checklist
- [ ] 更新 `.env.example` 中的 LLM_BASE_URL 和 LLM_MODEL
- [ ] 更新 `.env.example` 中的注释说明
- [ ] 验证 `llm_service.py` 的流式响应兼容性
- [ ] 验证 `llm_planner.py` 的模型调用
- [ ] 验证 `intent_parser.py` 的模型调用
- [ ] 验证 `dialogue.py` 的模型调用
- [ ] 验证 `narrator.py` 的模型调用
- [ ] 运行 `test_model_bench.py` 验证

---

## Task 2: [DONE] 前端架构可视化组件

**Priority**: HIGH
**Status**: TODO
**Tag**: NON-PRD

### Acceptance
- [ ] 添加 Agent Pipeline 流程图组件
- [ ] 展示各 Agent 节点状态（idle/active/done）
- [ ] 展示 Agent 间的数据流和箭头

### Checklist
- [ ] 创建 `frontend/components/architecture.js`
- [ ] 实现 Agent Pipeline Canvas 绘制
- [ ] 集成到 `index.html`
- [ ] 添加动画效果

---

## Task 3: [DONE] 前端流式打字机效果

**Priority**: HIGH
**Status**: TODO
**Tag**: NON-PRD

### Acceptance
- [ ] SSE 文本逐字显示（打字机效果）
- [ ] Agent 状态实时动画
- [ ] 加载状态优化（骨架屏、进度条）

### Checklist
- [ ] 更新 `frontend/js/app.js` 的 SSE 处理
- [ ] 添加打字机效果函数
- [ ] 优化 Agent Pipeline 面板动画
- [ ] 添加骨架屏加载状态

---

## Task 4: [DONE] 前端 Agent Pipeline 面板

**Priority**: MEDIUM
**Status**: TODO
**Tag**: NON-PRD

### Acceptance
- [ ] 实时展示各 Expert Agent 状态
- [ ] 展示思考过程和中间结果
- [ ] 展示 Negotiation 讨论过程

### Checklist
- [ ] 创建 `frontend/components/pipeline.js`
- [ ] 实现 Agent 状态轮询/SSE 事件处理
- [ ] 集成到 `index.html`
- [ ] 添加动画效果

---

## Task 5: [DONE] 前后端 SSE 事件协议对齐

**Priority**: MEDIUM
**Status**: TODO
**Tag**: NON-PRD

### Acceptance
- [ ] SSE 事件格式统一
- [ ] 添加 agent 状态事件类型
- [ ] 优化事件频率

### Checklist
- [ ] 定义 SSE 事件类型规范
- [ ] 更新后端 SSE 事件发送
- [ ] 更新前端 SSE 事件处理
- [ ] 测试事件流

---

## Task 6: [DONE] 基准测试验证

**Priority**: HIGH
**Status**: TODO
**Tag**: NON-PRD

### Acceptance
- [ ] 使用讯飞 API 运行基准测试
- [ ] 5 场景平均分不低于基线的 90%
- [ ] 首 token 响应时间 < 10 秒

### Checklist
- [ ] 运行 `test_model_bench.py`
- [ ] 记录基准分数
- [ ] 对比基线分数
- [ ] 测量首 token 响应时间
- [ ] 记录测试结果

---

## Task 7: [TODO] `.env.example` 更新

**Priority**: MEDIUM
**Status**: TODO
**Tag**: NON-PRD

### Acceptance
- [ ] 默认配置改为讯飞 API
- [ ] 添加多模型配置示例
- [ ] 更新注释说明

### Checklist
- [ ] 更新 LLM_BASE_URL
- [ ] 更新 LLM_MODEL
- [ ] 更新 EXPERT_LLM_BASE_URL
- [ ] 更新 EXPERT_LLM_MODEL
- [ ] 添加注释说明

---

## Task 8: [TODO] 前端响应式布局优化

**Priority**: LOW
**Status**: TODO
**Tag**: NON-PRD

### Acceptance
- [ ] 移动端适配
- [ ] 面板折叠/展开

### Checklist
- [ ] 添加媒体查询
- [ ] 优化移动端布局
- [ ] 添加面板折叠功能
- [ ] 测试移动端显示

---

## Test Log

| Test | Command | Result | Notes |
|------|---------|--------|-------|
| 讯飞 API 连通性 | tests/test_xunfei_api.py | PASS (3.76s) | xopqwen35v35b 模型正常 |
| 美食型场景 E2E | tests/test_single_scene.py | PASS (103.4s, Score 129.8 S) | 首SSE事件 0.00s, 6站, 30事件 |
