# Decisions Log

---

## D001: 3d-visualization design decision (2026-05-08)

- **Context**: 需要构建一个 3D 数据可视化平台，作为后续产品的基础设施
- **Constraints**: 快速开发、零构建工具依赖、支持 Mock 数据阶段
- **Options**:
  1. FastAPI + Three.js (CDN) + 原生 JS
  2. Django + Three.js (npm) + Vue
  3. Express + Three.js (npm) + React
- **Decision**: 选项 1 — FastAPI + Three.js (CDN) + 原生 JS
- **Rationale**:
  - FastAPI 异步高性能，自动生成 OpenAPI 文档，Python 生态丰富
  - Three.js CDN 引入无需构建工具，降低前端复杂度
  - 原生 JS 零依赖，快速开发，适合基础设施阶段
- **Trace**:
  - **At DOING start**: 用户指定技术栈为 Python + Flask/FastAPI + Three.js CDN + 原生 HTML/CSS/JS
  - **Before DONE**: -
  - **Post-merge check**: -
- **Evidence**:
  - **Commit**: -
  - **PR**: -
  - **Test/Log**: -

---

## D002: LLM 接口抽象方案 (2026-05-08)

- **Context**: 需要支持 OpenAI API 和国产模型 API，统一调用接口
- **Constraints**: 不同模型 API 格式略有差异，需要屏蔽差异
- **Options**:
  1. 直接使用 OpenAI SDK（兼容接口的国产模型可直接用）
  2. 自定义抽象层，适配不同 API
  3. 使用 LiteLLM 等第三方统一库
- **Decision**: 选项 1 — 直接使用 OpenAI SDK
- **Rationale**:
  - 多数国产模型已兼容 OpenAI API 格式
  - 减少依赖，保持简洁
  - 如有不兼容模型，再加适配层
- **Trace**:
  - **At DOING start**: 用户指定 LLM 选型为 OpenAI API / 国产模型 API（统一接口）
  - **Before DONE**: -
  - **Post-merge check**: -
- **Evidence**:
  - **Commit**: -
  - **PR**: -
  - **Test/Log**: -
