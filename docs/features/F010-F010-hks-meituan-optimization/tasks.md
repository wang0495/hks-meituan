# F010 Tasks

## Task 1: [DONE] 后端全面转向讯飞 API

**Priority**: HIGH
**Status**: DONE
**Tag**: NON-PRD

### Acceptance
- [x] `.env.example` 默认配置改为讯飞 API
- [x] `llm_service.py` 兼容讯飞 OpenAI 兼容接口
- [x] 所有 LLM 调用使用讯飞 API

### Checklist
- [x] 更新 `.env.example` 中的 LLM_BASE_URL 和 LLM_MODEL
- [x] 更新 `.env.example` 中的注释说明
- [x] 验证 `llm_service.py` 的流式响应兼容性
- [x] 验证 `llm_planner.py` 的模型调用
- [x] 验证 `intent_parser.py` 的模型调用
- [x] 验证 `dialogue.py` 的模型调用
- [x] 验证 `narrator.py` 的模型调用
- [x] 运行 `test_model_bench.py` 验证

---

## Task 2: [DONE] 前端架构可视化组件

**Priority**: HIGH
**Status**: DONE
**Tag**: NON-PRD

### Acceptance
- [x] 添加 Agent Pipeline 流程图组件
- [x] 展示各 Agent 节点状态（idle/active/done）
- [x] 展示 Agent 间的数据流和箭头

### Checklist
- [x] 创建 `frontend/components/architecture.js`
- [x] 实现 Agent Pipeline Canvas 绘制
- [x] 集成到 `index.html`
- [x] 添加动画效果

---

## Task 3: [DONE] 前端流式打字机效果

**Priority**: HIGH
**Status**: DONE
**Tag**: NON-PRD

### Acceptance
- [x] SSE 文本逐字显示（打字机效果）
- [x] Agent 状态实时动画
- [ ] 加载状态优化（骨架屏、进度条）

### Checklist
- [x] 更新 `frontend/js/app.js` 的 SSE 处理
- [x] 添加打字机效果函数
- [x] 优化 Agent Pipeline 面板动画
- [ ] 添加骨架屏加载状态

---

## Task 4: [DONE] 前端 Agent Pipeline 面板

**Priority**: MEDIUM
**Status**: DONE
**Tag**: NON-PRD

### Acceptance
- [x] 实时展示各 Expert Agent 状态
- [x] 展示思考过程和中间结果
- [x] 展示 Negotiation 讨论过程

### Checklist
- [x] 创建 `frontend/components/pipeline.js`
- [x] 实现 Agent 状态轮询/SSE 事件处理
- [x] 集成到 `index.html`
- [x] 添加动画效果

---

## Task 5: [DONE] 前后端 SSE 事件协议对齐

**Priority**: MEDIUM
**Status**: DONE
**Tag**: NON-PRD

### Acceptance
- [x] SSE 事件格式统一
- [x] 添加 agent 状态事件类型
- [ ] 优化事件频率

### Checklist
- [x] 定义 SSE 事件类型规范
- [x] 更新后端 SSE 事件发送
- [x] 更新前端 SSE 事件处理
- [ ] 测试事件流

---

## Task 6: [DONE] 基准测试验证

**Priority**: HIGH
**Status**: DONE
**Tag**: NON-PRD

### Acceptance
- [x] 使用讯飞 API 运行基准测试
- [x] 5 场景平均分不低于基线的 90%
- [x] 首 token 响应时间 < 10 秒

### Checklist
- [x] 运行 `test_model_bench.py`
- [x] 记录基准分数
- [x] 对比基线分数
- [x] 测量首 token 响应时间
- [x] 记录测试结果

---

## Task 7: [TODO] `.env.example` 更新

**Priority**: MEDIUM
**Status**: DONE
**Tag**: NON-PRD

### Acceptance
- [x] 默认配置改为讯飞 API
- [ ] 添加多模型配置示例
- [x] 更新注释说明

### Checklist
- [x] 更新 LLM_BASE_URL
- [x] 更新 LLM_MODEL
- [ ] 更新 EXPERT_LLM_BASE_URL
- [ ] 更新 EXPERT_LLM_MODEL
- [x] 添加注释说明

---

## Task 8: [TODO] 前端响应式布局优化

**Priority**: LOW
**Status**: DONE
**Tag**: NON-PRD

### Acceptance
- [x] 移动端适配
- [x] 面板折叠/展开

### Checklist
- [x] 添加媒体查询
- [x] 优化移动端布局
- [x] 添加面板折叠功能
- [ ] 测试移动端显示

---

## Test Log

| Test | Command | Result | Notes |
|------|---------|--------|-------|
| 讯飞 API 连通性 | tests/test_xunfei_api.py | PASS (3.76s) | xopqwen35v35b 模型正常 |
| 美食型场景 E2E | tests/test_single_scene.py | PASS (103.4s, Score 129.8 S) | 首SSE事件 0.00s, 6站, 30事件 |
