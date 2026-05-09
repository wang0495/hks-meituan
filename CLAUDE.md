# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CityFlow** — 智能城市出行规划系统。基于情绪感知的个性化城市路线规划，核心流程：自然语言意图解析 → POI筛选 → TSPTW路线求解 → 文案生成。覆盖珠海2000+ POI。

## Commands

### Development

```bash
# 启动开发服务器（热重载）
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 或使用脚本
./scripts/start_dev.sh
```

### Testing

```bash
# 运行全部测试
pytest

# 运行单个测试文件
pytest tests/test_solver.py

# 运行单个测试用例
pytest tests/test_solver.py::test_2opt_optimization

# 覆盖率报告
pytest --cov=backend --cov-report=html

# 并行测试
pytest -n auto

# 排除慢速测试
pytest -m "not slow"
```

### Code Quality

```bash
black backend/ tests/
ruff check backend/ tests/
mypy backend/
```

### Environment

```bash
cp .env.example .env
# 必填: SECURITY_ENCRYPTION_KEY
# 可选: OPENAI_API_KEY（有规则降级，不影响核心功能）
```

环境变量通过 `pydantic-settings` 加载，支持 `.env` 文件，前缀拆分见 `backend/config/settings.py` 的各子配置类（`DB_`, `REDIS_`, `LLM_`, `SECURITY_`）。

## Architecture

### Request Pipeline (backend/main.py)

```
客户端 → CORS → ShutdownMiddleware → PrometheusMiddleware → RateLimitMiddleware
     → InputValidationMiddleware → SecurityHeadersMiddleware → SessionMiddleware
     → APIVersionMiddleware → ConfigMiddleware → Router → Response
```

中间件按添加顺序从外到内执行。

### Core Flow: `/api/plan` (SSE streaming)

1. **意图解析** (`services/intent_parser.py`) — 自然语言 → 结构化意图 + 匹配用户画像
2. **POI筛选** (`services/filters.py`) — 约束过滤（时间窗、预算、体力等）
3. **路线求解** (`services/solver.py`) — 5阶段混合算法：贪心初始化 → 2-opt改进 → 呼吸空间插入 → 高潮收尾 → 输出组装
4. **文案生成** (`services/narrator.py`) — 路线描述 + 情绪曲线（LLM或规则降级）

每阶段通过SSE `phase` 事件推送进度，`step` 事件逐站返回，`done` 事件返回完整结果。

### Key Services

| 模块 | 职责 |
|------|------|
| `services/dialogue.py` | 多轮对话引擎，支持替换/节奏/预算/时间调整指令 |
| `services/user_profiles.py` | 20组预设用户画像（P1-P20） |
| `services/emotion.py` | 6维情绪标签计算 |
| `services/cache.py` | 多级缓存（L1内存 + L2 Redis） |
| `services/solver.py` | TSPTW路线求解器，运行在线程池中 |
| `services/data_service.py` | POI数据加载（JSON文件） |

### API Versioning

路由分版本：`routers/v1/` 和 `routers/v2/`，通过 `APIVersionMiddleware` 控制。

### Frontend

原生JS单页应用，`frontend/index.html` 通过FastAPI的 `StaticFiles` 挂载在 `/`（**必须在所有API路由之后**，否则会拦截API请求）。JS文件在 `frontend/js/`，含L7地图渲染和LLM聊天。

### Testing

- pytest配置在 `pytest.ini`：`asyncio_mode = auto`，标记 `slow` 和 `integration`
- 测试fixtures在 `tests/conftest.py` 和 `tests/conftest_db.py`
- 使用 `fakeredis` 做Redis mock，`aiosqlite` 做异步DB测试

### Key Patterns

- 配置热更新：`services/config_hot_reload.py` + `watchdog`
- 优雅停机：`services/graceful_shutdown.py` 三阶段（排空→清理→退出）
- 弹性设计：`services/circuit_breaker.py`, `services/retry.py`, `services/resilient_service.py`
- 消息队列：`services/message_queue.py` 基于Redis，支持异步任务分发
- GraphQL端点：`routers/graphql.py` 使用 `strawberry-graphql`

## lee-spec-kit

项目使用 lee-spec-kit 文档工作流。相关配置在 `AGENTS.md`。需要时运行 `npx lee-spec-kit detect --json` 检测。
