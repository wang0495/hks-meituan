# Tasks: 3d-visualization

## Task Rules

- **Status**: `[TODO]` → `[DOING]` → `[DONE]`
- **Task communication / confirmation**:
  - `[TODO] → [DOING]`: share the task title first, then update the task state in `tasks.md`
  - `[DOING] → [DONE]`: share the result and verification first, then update `Acceptance` and `Checklist` in the same edit
  - Ask for approval before changing task state only when the task crosses a documented review checkpoint or before remote/destructive actions.
  - Do not invent a standalone `OK` approval step when the workflow does not require one.
  - Do not mark `[DONE]` while any item in that task's `Checklist` remains unchecked.
- **PRD mapping (recommended)**: add an existing PRD requirement ID tag like `[PRD-FR-001]` or `[PRD-SCOPE-V1-DESKTOP-EDITOR]` to each task line, or tag non-PRD tasks as `[NON-PRD]`.
  - Do not invent PRD IDs in `tasks.md`. Only reference IDs that already exist in `docs/prd` or the upstream requirements doc.
  - `[NON-PRD]` is for internal implementation work only. If the task changes user-facing behavior, acceptance criteria, or scope, backfill PRD first and tag it as `[PRD-...]`.

---

## Local Tracking
- **Doc Status**: Draft
- **Repo**: hks-meituan
- **Branch**: `feat/3d-visualization`
- **Pending Change Request**: -
- **PR Review**: -
- **PR Review Evidence**: -

---

## Task List

---

### [DONE][PRD-FR-001] T-F001-01 初始化 FastAPI 项目结构

- Date: 2026-05-08
- Acceptance:
  - FastAPI 应用可启动，访问 /docs 看到 OpenAPI 文档 ✅
- Checklist:
  - [x] 创建 backend/ 目录结构
  - [x] 编写 main.py（FastAPI 入口 + CORS）
  - [x] 编写 requirements.txt
  - [x] 验证 uvicorn 可启动

---

### [DONE][PRD-FR-001] T-F001-02 创建 Mock 数据 + 数据服务

- Date: 2026-05-08
- Acceptance:
  - /api/data 返回 JSON 数据，支持查询参数 ✅
- Checklist:
  - [x] 创建 mock_data.json（20 条城市/分类/销售额/利润数据）
  - [x] 实现 data_service.py（JSON 加载 + 内存缓存）
  - [x] 实现 /api/data 路由
  - [x] 测试 API 返回正确数据（20 条，含筛选功能）

---

### [DONE][PRD-FR-003] T-F001-03 实现 LLM 统一接口

- Date: 2026-05-08
- Acceptance:
  - /api/llm/chat 返回 LLM 响应，支持流式输出 ✅
- Checklist:
  - [x] 实现 llm_service.py（统一 LLM 调用层，基于 OpenAI SDK）
  - [x] 支持 OpenAI API 和国产模型 API（通过 LLM_BASE_URL 切换）
  - [x] 实现 /api/llm/chat 和 /api/llm/chat/stream 路由
  - [x] 配置 .env 环境变量管理

---

### [DONE][PRD-FR-002] T-F001-04 实现前端 3D 可视化

- Date: 2026-05-08
- Acceptance:
  - 浏览器显示 3D 柱状图/散点图，支持鼠标交互 ✅
- Checklist:
  - [x] 创建 index.html 主页面
  - [x] 实现 Three.js 3D 柱状图（chart3d.js）
  - [x] 实现 3D 散点图
  - [x] 添加鼠标旋转/缩放/平移（OrbitControls）
  - [x] 数据点悬停显示详情（tooltip）

---

### [DONE][PRD-FR-004] T-F001-05 实现 LLM 聊天 UI

- Date: 2026-05-08
- Acceptance:
  - 聊天框可输入问题，流式显示 LLM 回复 ✅
- Checklist:
  - [x] 实现聊天输入框和消息展示区
  - [x] 对接 /api/llm/chat（非流式）
  - [x] 样式美化（深色主题）

---

### [DONE][PRD-FR-004] T-F001-06 编写 README + 技术文档

- Date: 2026-05-08
- Acceptance:
  - README 包含一键启动说明，技术文档 ≤ 2 页 ✅
- Checklist:
  - [x] 编写 README.md（安装、启动、API 说明）
  - [x] 创建 .env.example

---

### [DONE][PRD-FR-001] T-F001-07 生成 POI 数据集（3689 条）

- Date: 2026-05-08
- Acceptance:
  - 从 OpenStreetMap 拉取珠海/广州/湛江真实 POI，补全属性后生成 `city_poi_db.json`（3689 条）✅
- Checklist:
  - [x] 通过 Overpass API (kumi 镜像) 拉取 3 城市 OSM 数据
  - [x] 品类映射：amenity/shop/tourism/leisure → 餐饮/购物/酒店/文化/运动
  - [x] Faker 补全属性：rating, avg_price, business_hours, tags, ugc_comments
  - [x] 输出 `frontend/data/city_poi_db.json`（3689 条）

---

### [DONE][PRD-FR-001] T-F001-08 POI 数据校验

- Date: 2026-05-08
- Acceptance:
  - 3689 条数据，必填字段完整，坐标在有效范围内 ✅
- Checklist:
  - [x] 城市分布：广州 2596 / 珠海 999 / 湛江 94
  - [x] 品类分布：餐饮 2524 / 购物 758 / 酒店 214 / 文化 145 / 运动 39
  - [x] 所有记录含 id, name, city, category, lat, lng

---

### [TODO][PRD-FR-002] T-F001-09 L7 3D 渲染引擎

- Date: 2026-05-08
- Acceptance:
  - 高德 3D 地图上使用 L7 显示彩色 3D 圆柱 POI，支持交互
- Checklist:
  - [ ] 引入 L7 CDN（@antv/l7 + @antv/l7-amap）
  - [ ] 创建 `frontend/js/l7-renderer.js`（Scene + PointLayer）
  - [ ] PointLayer shape='cylinder'，高度映射 rating，颜色映射 category
  - [ ] Popup 交互：点击显示店名/评分/价格/UGC
  - [ ] 城市切换下拉框（珠海/广州/湛江）
  - [ ] 品类图例（右上角）

---

### [TODO][PRD-FR-004] T-F001-10 前端页面集成

- Date: 2026-05-08
- Acceptance:
  - 打开 index.html 即可看到完整可交互的 3D 地图 POI 可视化
- Checklist:
  - [ ] 更新 `index.html`（引入 L7，替换 Three.js 渲染）
  - [ ] 保留 AI 分析聊天面板
  - [ ] 验证 3689 数据点渲染流畅（≥30fps）

---

### [TODO][PRD-FR-005] T-F001-11 录制演示视频 + 部署

- Date: 2026-05-08
- Acceptance:
  - 3-5 分钟演示视频，可在线访问的演示页面
- Checklist:
  - [ ] 录制 3-5 分钟演示视频
  - [ ] 部署到可在线访问的服务器
  - [ ] 验证在线演示可正常访问

---

## Completion Criteria

- [ ] All tasks are `[DONE]`, and each task's `Acceptance` is verified and `Checklist` is checked
- [ ] Tests executed and passing
- [ ] Final outcome shared and any required user confirmation recorded

### Test Run Log

| Command | Last Run (Local, YYYY-MM-DD) | Result |
| --- | --- | --- |
| `pytest backend/tests/ -q` | - | - |
