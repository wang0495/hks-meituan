# Implementation Plan: 3d-visualization

---

## Overview

- **Feature ID**: F001
- **Target Repo**: hks-meituan
- **Created**: 2026-05-08
- **Status**: Draft

---

## Tech Stack

| Category | Choice | Reason |
|----------|--------|--------|
| Backend Framework | FastAPI | 异步高性能，自动 OpenAPI 文档 |
| LLM Integration | httpx + OpenAI SDK | 统一接口，支持流式输出 |
| Data Storage | JSON → dict (内存) | 简单高效，适合 Mock 阶段 |
| 3D Engine | Three.js (CDN) | 轻量级，无需构建工具 |
| Frontend | 原生 HTML/CSS/JS | 零依赖，快速开发 |
| Server | Uvicorn | ASGI 服务器 |

---

## Architecture

```
┌─────────────────────────────────────────┐
│              Browser (Frontend)          │
│  ┌──────────────┐  ┌─────────────────┐  │
│  │  Three.js 3D │  │  LLM Chat UI   │  │
│  │  Visualization│  │                 │  │
│  └──────┬───────┘  └────────┬────────┘  │
│         │                   │            │
│         └─────────┬─────────┘            │
│                   │                      │
│            Fetch API calls               │
└───────────────────┼──────────────────────┘
                    │
┌───────────────────┼──────────────────────┐
│              FastAPI Backend              │
│  ┌────────────────┴────────────────┐     │
│  │         API Router              │     │
│  │  /api/data   /api/llm/chat     │     │
│  └──────┬──────────────┬──────────┘     │
│         │              │                 │
│  ┌──────┴──────┐ ┌─────┴──────────┐     │
│  │ Data Service│ │  LLM Service   │     │
│  │ (JSON→Mem)  │ │ (OpenAI/国产)  │     │
│  └─────────────┘ └────────────────┘     │
└──────────────────────────────────────────┘
```

**Data Flow:**
1. 启动时 JSON 文件加载到内存
2. 前端 Fetch 调用 `/api/data` 获取数据
3. Three.js 渲染 3D 可视化
4. 用户提问 → `/api/llm/chat` → LLM API → 返回分析结果

---

## File Structure

```
hks-meituan/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── routers/
│   │   ├── data.py          # 数据查询 API
│   │   └── llm.py           # LLM 聊天 API
│   ├── services/
│   │   ├── data_service.py  # 数据加载与查询
│   │   └── llm_service.py   # LLM 统一调用层
│   ├── models/
│   │   └── schemas.py       # Pydantic 模型
│   ├── data/
│   │   └── mock_data.json   # Mock 数据文件
│   └── requirements.txt
├── frontend/
│   ├── index.html           # 主页面
│   ├── css/
│   │   └── style.css        # 样式
│   └── js/
│       ├── app.js           # 主逻辑
│       ├── chart3d.js       # Three.js 3D 渲染
│       └── llm-chat.js      # LLM 聊天组件
├── docs/                    # lee-spec-kit 文档
├── README.md                # 一键启动说明
└── .env.example             # 环境变量模板
```

---

## Test Strategy

- **Unit Tests**: pytest 测试 data_service 和 llm_service
- **Integration Tests**: FastAPI TestClient 测试 API 端点
- **E2E Tests**: 手动浏览器验证 3D 渲染和 LLM 聊天

---

## Related Documents

- Spec: [spec.md](./spec.md)
- Decisions: [decisions.md](./decisions.md)
