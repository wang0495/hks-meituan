# hks-meituan PRD (Product Requirements Document)

## Project Overview

**Project Name**: hks-meituan (美团数据 3D 可视化平台)
**Version**: v1.0
**Date**: 2026-05-08

### Mission

构建一个基于 Mock 数据的 3D 可视化展示平台，作为后续所有软件产品的基础设施。使用 Three.js 实现交互式 3D 数据展示，后端提供统一的 LLM API 接口和数据服务。

### Target Users

- 数据分析师：查看和探索 3D 数据可视化
- 开发团队：作为后续产品的基础架构参考
- 演示/汇报：用于项目展示和技术演示

---

## Functional Requirements

### PRD-FR-001: Mock 数据加载与管理

系统支持从 JSON 文件加载 Mock 数据到内存，提供数据查询 API。

- 支持多种数据格式（JSON 文件）
- 数据热加载（修改 JSON 后无需重启）
- 内存缓存，支持快速查询

### PRD-FR-002: 3D 数据可视化展示

使用 Three.js 实现交互式 3D 数据可视化界面。

- 支持 3D 柱状图、散点图、曲面图
- 鼠标交互：旋转、缩放、平移
- 数据点悬停显示详情
- 响应式布局，适配不同屏幕

### PRD-FR-003: LLM 智能分析接口

提供统一的 LLM API 接口，支持 OpenAI API 和国产模型 API。

- 统一接口抽象，屏蔽不同模型差异
- 支持流式输出
- 数据分析问答功能

### PRD-FR-004: Web 演示页面

可在线访问的 Web 演示页面，展示 3D 可视化效果和 LLM 分析能力。

- 一键启动（README 说明）
- 页面加载时间 < 3 秒
- 支持主流浏览器（Chrome、Firefox、Edge）

### PRD-FR-005: 演示视频

3-5 分钟演示视频，展示核心功能。

---

## Non-Functional Requirements

### PRD-NFR-001: 性能要求

- 3D 渲染帧率 ≥ 30fps
- API 响应时间 < 500ms（不含 LLM 调用）
- 支持 1000+ 数据点的流畅渲染

### PRD-NFR-002: 可维护性

- 代码结构清晰，模块化设计
- README 包含一键启动说明
- 技术文档 ≤ 2 页

### PRD-NFR-003: 兼容性

- Python 3.10+
- Node.js 18+
- 现代浏览器（Chrome 90+、Firefox 88+、Edge 90+）

---

## Tech Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Backend | Python + FastAPI | 异步高性能，类型安全 |
| LLM | OpenAI API / 国产模型 API | 统一接口，灵活切换 |
| Data Storage | JSON 文件 → 内存 | 简单高效，适合 Mock 阶段 |
| Frontend 3D | Three.js (CDN) | 轻量级 3D 渲染 |
| Frontend UI | 原生 HTML/CSS/JS | 零依赖，快速开发 |

---

## Deliverables

1. 可在线访问的 Web 演示页面
2. 3-5 分钟演示视频
3. 代码仓库（含 README 一键启动说明）
4. 技术文档（≤ 2 页）

---

## Daily Standup (10 min)

- 各自 1 分钟：昨天做了什么、今天计划、有无卡点
- 卡点立刻结对解决，不隔夜
