# hks-meituan Constitution

Core principles and technical decision guidelines for this project.

---

## Project Mission

构建基于 Mock 数据的 3D 可视化展示平台，作为后续产品的基础设施。

---

## Tech Stack

### Backend

| Tech | Version | Reason |
|------|---------|--------|
| Python | 3.12 | 生态成熟，异步支持好 |
| FastAPI | latest | 异步高性能，自动 OpenAPI 文档 |
| Uvicorn | latest | ASGI 服务器 |

### Frontend

| Tech | Version | Reason |
|------|---------|--------|
| Three.js | r170+ (CDN) | 轻量级 3D 渲染引擎 |
| 原生 HTML/CSS/JS | - | 零依赖，快速开发 |

### Common

| Tech | Version | Reason |
|------|---------|--------|
| JSON | - | 数据存储格式 |
| Git | - | 版本控制 |

---

## Architecture Principles

1. **前后端分离**：后端 API + 前端静态页面，独立部署
2. **统一 LLM 接口**：抽象 LLM 调用层，支持 OpenAI 和国产模型无缝切换
3. **数据驱动**：JSON 文件 → 内存缓存 → API 查询 → 3D 渲染
4. **渐进增强**：先跑通核心流程，再优化细节

---

## Code Quality Standards

- Python: black 格式化 + ruff 检查
- 前端: 无 lint 强制要求（原生 JS）
- API: RESTful 风格，统一响应格式

---

## Security Principles

- API Key 不硬编码，使用环境变量
- LLM API 调用不暴露密钥到前端

---

## Language/Code Rules

- **Responses**: 中文
- **Code/Filenames**: English
- **Comments**: 中文/English 均可
