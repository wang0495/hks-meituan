# CityFlow — 系统架构文档 (ARD)

> 项目: CityFlow 智能城市出行规划系统
> 版本: 1.0.0 | 框架: FastAPI + 原生JS前端
> 城市: 珠海 (2000+ POI)

---

## 1. 整体架构分层

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           用户层 (User Layer)                                │
│   浏览器 (Web UI)                      curl / Postman / 第三方客户端          │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ HTTP / SSE / WebSocket
┌────────────────────────────────┴────────────────────────────────────────────┐
│                        接入层 (Gateway Layer)                                │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  Nginx (反向代理 + 负载均衡 + 静态资源)                                │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  FastAPI 中间件栈 (由外到内):                                        │  │
│  │  CORS → ShutdownMiddleware → PrometheusMiddleware                     │  │
│  │  → RateLimitMiddleware → InputValidationMiddleware                     │  │
│  │  → SecurityHeadersMiddleware → SessionMiddleware                      │  │
│  │  → APIVersionMiddleware → ConfigMiddleware                            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ 路由分发
┌────────────────────────────────┴────────────────────────────────────────────┐
│                         路由层 (Router Layer)                                │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  v1/               v2/     (版本化 API)                              │   │
│  │  └─ plan.py        └─ plan.py                                       │   │
│  │  └─ poi.py         └─ poi.py                                        │   │
│  │  └─ dialogue.py                                                      │   │
│  │                                                                      │   │
│  │  一级路由: poi | llm | data | audit | mq | pool | session           │   │
│  │            tasks | websocket | sse | registry | health               │   │
│  │  特殊路由: graphql (Strawberry GraphQL)                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ 依赖注入
┌────────────────────────────────┴────────────────────────────────────────────┐
│                         服务层 (Service Layer)                                │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  A. 核心业务服务                                                      │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │  │
│  │  │ 意图解析  │ │ POI筛选  │ │ 路线求解  │ │ 文案生成  │ │ 对话引擎  │  │  │
│  │  │ intent_  │ │ filters  │ │ solver   │ │ narrator │ │ dialogue  │  │  │
│  │  │ parser   │ │          │ │ TSPTW    │ │ 模板+LLM │ │多轮对话   │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │  │
│  │                                                                      │  │
│  │  B. 智能增强服务                                                      │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │  │
│  │  │ 情绪引擎  │ │ 经济分析  │ │ 地理计算  │ │ 城市人格  │ │ 权重映射  │  │  │
│  │  │ emotion  │ │ economy  │ │ geo      │ │ city_    │ │weight_   │  │  │
│  │  │          │ │          │ │          │ │personality│ │mapper    │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │  │
│  │                                                                      │  │
│  │  C. 用户服务                                                          │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │  │
│  │  │ 偏好管理  │ │ 用户画像  │ │ 感知服务  │ │ 节假日   │ │ 会话管理  │  │  │
│  │  │prefer-   │ │ user_    │ │ percept- │ │ holiday_ │ │ session   │  │  │
│  │  │ence_mgr  │ │ profiles │ │ ion      │ │ utils    │ │           │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │  │
│  │                                                                      │  │
│  │  D. 基础设施服务                                                      │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │  │
│  │  │ 缓存管理  │ │ 消息队列  │ │ 任务队列  │ │ 事件总线  │ │ 服务注册  │  │  │
│  │  │ cache +  │ │ message_ │ │ task_    │ │ event_   │ │ registry  │  │  │
│  │  │warmer    │ │ queue    │ │ queue    │ │ bus      │ │           │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │  │
│  │                                                                      │  │
│  │  E. 弹性与运维                                                        │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │  │
│  │  │ 熔断器    │ │ 重试/兜底 │ │ 限流器    │ │ 审计日志  │ │优雅停机   │  │  │
│  │  │circuit_  │ │ retry+   │ │ 5种限流   │ │ audit_   │ │graceful_ │  │  │
│  │  │ breaker  │ │ fallback │ │ 策略     │ │ logger   │ │shutdown  │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────┴────────────────────────────────────────────┐
│                      AI 智能体层 (Agent Layer)                                │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  agents_v3 (MoE 混合专家架构 — C版本)                                 │  │
│  │                                                                      │  │
│  │  用户输入 → [Guard] → [Router] → 并行专家 → [Review] → [Synth] → 输出 │  │
│  │                                                                      │  │
│  │  ┌──────────────┐   ┌──────────────────────────────────────────┐    │  │
│  │  │  元规则防火墙   │   │  LangGraph 编排引擎                       │    │  │
│  │  │  meta_rule_   │   │  有向图: rule_guard → expert_router      │    │  │
│  │  │  firewall     │   │  → [8个并行专家节点] → review            │    │  │
│  │  └──────────────┘   │  → synthesizer → live_itinerary → END    │    │  │
│  │                      └──────────────────────────────────────────┘    │  │
│  │                                                                      │  │
│  │  8大领域专家:                                                        │  │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │  │
│  │  │ POI  │ │ 美食  │ │ 住宿  │ │ 交通  │ │ 天气  │ │本地   │ │预算   │  │  │
│  │  │专家  │ │专家   │ │专家   │ │专家   │ │专家   │ │向导   │ │黑客   │  │  │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘  │  │
│  │                                                                      │  │
│  │  智能体(Agent)事件通过 SSE 队列实时推送到前端                            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  Meituan Mock Server (美团模拟数据服务, 端口 8001)                     │  │
│  │  模拟美团API: 商户搜索 | 详情 | 评价 | 路线距离 | 商圈范围               │  │
│  │  Agent 通过 tool_use 调用获取原始数据                                   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────┴────────────────────────────────────────────┐
│                        持久层 (Persistence Layer)                            │
│                                                                             │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────────────────┐  │
│  │  SQLite /       │  │  Redis          │  │  文件系统                     │  │
│  │  PostgreSQL     │  │  缓存/会话/队列  │  │  JSON数据文件 + 日志          │  │
│  │  (数据库)        │  │  长期记忆        │  │  data/*.json  logs/*        │  │
│  │                 │  │  消息队列        │  │                              │  │
│  └────────────────┘  └────────────────┘  └──────────────────────────────┘  │
│                                                                             │
│  ┌───────────────┐  ┌────────────────┐  ┌──────────────────────────────┐  │
│  │  Alembic      │  │  多级缓存       │  │  Memory LTM                  │  │
│  │  数据库迁移    │  │  L1:内存 L2:Redis│  │  长期用户画像 (Redis/内存)   │  │
│  └───────────────┘  └────────────────┘  └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 模块职责详解

### 2.1 路由层 (Routers)

| 路由模块 | 端点前缀 | 功能 |
|---------|---------|------|
| `v1/plan.py` | `/api/v1/plan` | V1 路线规划 |
| `v1/dialogue.py` | `/api/v1/dialogue` | V1 对话调整 |
| `v1/poi.py` | `/api/v1/poi` | V1 POI查询 |
| `v2/plan.py` | `/api/v2/plan` | V2 路线规划 (增强版) |
| `v2/poi.py` | `/api/v2/poi` | V2 POI查询 |
| `poi.py` | `/api/poi` | POI 查询/距离矩阵 |
| `llm.py` | `/api/llm` | LLM 对话 (普通+流式) |
| `data.py` | `/api/data` | 原始数据查询 |
| `audit.py` | `/api/audit` | 审计日志 CRUD+导出 |
| `mq.py` | `/api/mq` | 消息队列管理 |
| `pool.py` | `/api/pool` | 连接池监控仪表盘 |
| `session.py` | `/api/session` | 用户会话管理 |
| `tasks.py` | `/api/tasks` | 后台任务提交/查询 |
| `websocket.py` | `/ws/{session_id}` | WebSocket 实时通信 |
| `sse.py` | `/api/sse` | SSE 流式连接管理 |
| `registry.py` | `/api/registry` | 服务注册/发现 |
| `health.py` | `/api/health` | 健康检查 |
| `metrics.py` | `/metrics` | Prometheus 指标端点 |
| `system.py` | `/api/system` | 系统管理接口 |
| `graphql.py` | `/graphql` | GraphQL 端点 |

### 2.2 核心服务层 (Services)

| 服务模块 | 职责 | 依赖 |
|---------|------|------|
| **intent_parser.py** | 用户自然语言 → 结构化意图 (LLM+规则双引擎) | emotion, user_profiles |
| **solver.py** | TSPTW 5阶段路线求解 (贪心+2-opt+呼吸空间+高潮收尾) | filters, emotion, geo, economy, time_utils, memory.psychology, poi_scenes |
| **narrator.py** | 路线文案生成 (模板+LLM润色) | economy, emotion, city_personality |
| **dialogue.py** | 多轮对话引擎 (替换/节奏/预算/时间/重规划) | solver, time_utils |
| **filters.py** | POI候选过滤 (地理/价格/类别/情绪/时间窗/感官交替) | emotion, time_utils |
| **emotion.py** | 情绪评分 (6维标签兼容性/疲劳惩罚/感官交替/情绪曲线) | — |
| **economy.py** | 经济学 enrich (体验杠杆/情绪杠杆/性价比) | — |
| **geo.py** | 地理计算 (Haversine距离/出行时间估算) | — |
| **preference_manager.py** | 偏好管理 (身份识别+LTM+上下文+WeightMapper全面整合) | memory.long_term, weight_mapper, holiday_utils |
| **weight_mapper.py** | 动态权重计算 (需求向量→求解器权重，渐进学习) | — |
| **perception.py** | 环境感知 (天气/温度/时段/季节/星期) | — |
| **user_profiles.py** | 20组预设用户画像定义 | — |
| **city_personality.py** | 城市人格 (开场白/氛围形容词) | — |
| **cache.py** | 多级缓存抽象层 (L1内存+L2 Redis) | redis |
| **cache_warmer.py** | 缓存预热 (启动预热+定时刷新) | cache |
| **template_engine.py** | 文案模板引擎 | jinja2 |
| **vectorized.py** | 向量化运算加速 | numpy |
| **parallel.py** | 并行任务执行 | asyncio |
| **memory/long_term.py** | L3长期记忆 (用户画像/Category访问/历史trip) | redis |
| **memory/short_term.py** | L1短期记忆 | — |
| **memory/working_memory.py** | L2工作记忆 | — |
| **memory/psychology.py** | 心理学规则 (认知负荷/峰终定律/曝光效应/锚定效应) | — |
| **poi_scenes.py** | POI场景标签 (节日/季节/时段/情绪) | — |
| **event_bus.py** | 事件总线 (发布/订阅) | — |
| **task_queue.py** | 异步任务队列 (白名单函数执行) | — |
| **message_queue.py** | Redis消息队列 (发布/消费) | redis |
| **message_handlers.py** | 默认消息消费者 | message_queue |
| **session.py** | 会话管理器 | redis |
| **registry.py** | 服务注册与健康检查 | — |
| **circuit_breaker.py** | 熔断器 (失败计数/半开/全开) | — |
| **retry.py** | 重试策略 (指数退避) | — |
| **fallback.py** | 兜底策略链 | — |
| **rate_limiter.py** | 通用限流器 (令牌桶) | — |
| **adaptive_rate_limiter.py** | 自适应限流 (基于系统负载) | — |
| **ip_rate_limiter.py** | IP粒度限流 | rate_limiter |
| **user_rate_limiter.py** | 用户粒度限流 | rate_limiter |
| **quota.py** | API配额管理 | — |
| **audit_logger.py** | 审计日志 (记录所有关键操作) | — |
| **graceful_shutdown.py** | 优雅停机 (排空请求→清理资源) | — |
| **auto_recovery.py** | 自动恢复机制 | — |
| **health_checker.py** | 深度健康检查 | — |
| **notification.py** | 通知推送 | — |
| **alert_notifier.py** | 告警通知 | — |
| **metrics.py** | 自定义业务指标 | prometheus |
| **logger.py** | 结构化日志 | — |
| **log_rotation.py** | 日志轮转 | — |
| **backup.py** | 数据备份 | — |
| **scheduled_backup.py** | 定时备份 | backup |
| **data_service.py** | 数据加载与访问 | — |
| **data_check.py** | 数据完整性检查 | — |
| **data_explainer.py** | 数据解释 | — |
| **discovery.py** | 服务发现 | — |
| **holiday_utils.py** | 节假日工具 (中国节假日/天气上下文) | — |
| **time_utils.py** | 时间工具 (解析/格式化/营业时间) | — |
| **http_pool.py** | HTTP连接池 | httpx |
| **pool_manager.py** | 连接池管理器 (数据库+HTTP统一管理) | pool/database, pool/http |
| **pool_monitor.py** | 连接池监控 | pool_manager |
| **llm_service.py** | LLM API封装 (OpenAI) | openai |
| **llm_planner.py** | LLM路线规划 | llm_service |
| **preference_dialogue.py** | 偏好对话 (收集用户偏好) | preference_manager |
| **websocket.py** | WebSocket连接管理 | — |
| **config_hot_reload.py** | 配置热重载 | watchdog |
| **config_watcher.py** | 配置文件监听 | — |

### 2.3 智能体层 (agents_v3 — MoE架构)

```
用户输入
    │
    ▼
┌────────────────────────────────────────────────────────────┐
│  rule_guard (意图解析 + POI加载 + 元规则检查)                │
│  └─ 输出: user_intent, candidates, meta_rules              │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│  expert_router (LLM分类场景 → 激活权重 → 选择专家)           │
│  └─ 输出: active_experts, expert_weights                    │
└────────────────────────┬───────────────────────────────────┘
                         │ Send() 动态 fan-out
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
   ┌─────────┐     ┌─────────┐     ┌─────────┐
   │ POI专家  │     │ 美食专家  │     │ 交通专家  │  ... 共8个
   │ 景点筛选  │     │ 餐饮推荐  │     │ 交通规划  │  并行执行
   │候选提案   │     │ 美食提案  │     │ 路线提案  │
   └─────────┘     └─────────┘     └─────────┘
         │               │               │
         └───────────────┼───────────────┘
                         ▼
┌────────────────────────────────────────────────────────────┐
│  review (质量审查, 冲突检测, 交叉验证)                       │
│  ┌─ 不通过 → rework (按反馈重选) ──→ review (最多2轮)       │
│  └─ 通过 → synthesizer                                      │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│  synthesizer (提案融合 → 路线组装 → 时间编排)                │
│  └─ 输出: 完整路线 + 情绪曲线                                 │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│  live_itinerary (热力图 + 决策溯源 + 最终输出)                │
│  └─ 输出: route, narrative, heatmap, decision_trace        │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼
                       END → SSE 流式推送前端
```

| 节点/专家 | 职责 | 输入 | 输出 |
|-----------|------|------|------|
| **rule_guard** | 规则守卫: 解析意图, 加载POI, 生成元规则 | user_input | user_intent, candidates, meta_rules |
| **expert_router** | 专家路由: LLM分类场景, 计算专家权重, 决定激活集 | user_intent | active_experts, expert_weights |
| **poi_expert** | POI专家: 按类别/情绪/评分筛选景点候选 | candidates | expert_candidates["poi"] |
| **food_expert** | 美食专家: 餐饮推荐, 美食路线 | candidates | expert_candidates["food"] |
| **hotel_expert** | 住宿专家: 酒店推荐 | candidates | expert_candidates["hotel"] |
| **traffic_expert** | 交通专家: 交通方式/时间估算 | candidates | expert_candidates["traffic"] |
| **weather_expert** | 天气专家: 天气影响分析 | candidates | expert_candidates["weather"] |
| **local_expert** | 本地向导: 隐藏宝藏/非标体验 | candidates | expert_candidates["local_expert"] |
| **destination_expert** | 目的地专家: 整体目的地规划 | candidates | expert_candidates["destination"] |
| **budget_hacker** | 预算黑客: 预算优化策略 | candidates | expert_candidates["budget_hacker"] |
| **review** | 质量审查: 交叉验证/冲突检测/反馈生成 | proposals | review_feedback |
| **rework** | 返工: 按反馈重选/调整 | review_feedback | reworked_proposals |
| **synthesizer** | 综合师: 融合提案→路线组装→时间编排 | proposals | route |
| **live_itinerary** | 实景行程: 热力图/决策溯源/最终输出 | route | route+narrative+heatmap |

### 2.4 中间件栈 (Middleware Pipeline)

```
请求进入 (由外到内)
    │
    ├─ ① CORSMiddleware        — CORS 预检/跨域 (最外层)
    ├─ ② ShutdownMiddleware    — 停机感知 (尽早拒绝停机中请求)
    ├─ ③ PrometheusMiddleware  — Prometheus 指标采集 (请求计数/延迟)
    ├─ ④ RateLimitMiddleware   — 速率限制 (令牌桶, 全局/分钟)
    ├─ ⑤ InputValidationMiddle — 输入验证 (请求体大小/格式)
    ├─ ⑥ SecurityHeadersMiddle — 安全响应头
    ├─ ⑦ SessionMiddleware     — 会话注入
    ├─ ⑧ APIVersionMiddleware  — API版本协商
    ├─ ⑨ ConfigMiddleware      — 配置注入
    │
    ▼ 路由匹配 → Handler执行 → 响应返回 (逆序)
```

### 2.5 缓存架构

```
┌─────────────────────────────────────────────────────────────┐
│                    多级缓存 (Multilevel Cache)                │
│                                                             │
│  L1: 内存缓存 (dict)                  L2: Redis             │
│  ┌──────────────────────┐      ┌──────────────────────┐     │
│  │ poi_cache           │      │ 持久化缓存             │     │
│  │ distance_cache      │ ◄──► │ 会话数据               │     │
│  │ route_cache (8h TTL)│      │ 长期记忆 (LTM)         │     │
│  │ profile_cache       │      │ 消息队列               │     │
│  │ general_cache       │      │                      │     │
│  └──────────────────────┘      └──────────────────────┘     │
│                                                             │
│  缓存预热 (Cache Warmer):                                    │
│  启动时 warmup_memory_caches() → 预热高频数据到 L1           │
│  后台定时 startup_warmup_with_background(3600s) → 刷新缓存   │
└─────────────────────────────────────────────────────────────┘
```

### 2.6 内存子系统 (Memory System)

```
┌────────────────────────────────────────────────────────┐
│                  记忆系统 (3层架构)                       │
│                                                         │
│  L1 短期记忆 (Short-term)                               │
│  └─ 当前对话上下文, 最近操作, 临时状态                    │
│                                                         │
│  L2 工作记忆 (Working Memory)                           │
│  └─ 当前路线, 可用候选, 用户当前需求向量                  │
│                                                         │
│  L3 长期记忆 (Long-term) — Redis/内存持久化              │
│  └─ 用户画像: preferences, category_visits,             │
│               visit_count, total_spent,                 │
│               emotion_history, trip_history,            │
│               weight_mapper                             │
│                                                         │
│  心理学规则 (Psychology Rules):                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ 认知负荷   │ │ 峰终定律  │ │ 曝光效应  │ │ 锚定效应  │  │
│  │Cognitive  │ │Peak-End  │ │Mere-     │ │Anchoring  │  │
│  │Load       │ │Rule      │ │Exposure  │ │Effect     │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
└────────────────────────────────────────────────────────┘
```

### 2.7 弹性架构 (Resilience)

```
┌─────────────────────────────────────────────────────────────┐
│                      弹性模式集合                              │
│                                                             │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ 熔断器      │  │ 重试        │  │ 超时控制    │            │
│  │ Circuit    │  │ Retry      │  │ Timeout    │            │
│  │ Breaker    │  │ 指数退避     │  │ wait_for + │            │
│  │ 3状态:     │  │ 3次 + jitter│  │ fallback   │            │
│  │ 关/半开/开  │  └────────────┘  └────────────┘            │
│  └────────────┘                                             │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ 限流器      │  │ 兜底策略    │  │ 优雅停机    │            │
│  │ Rate       │  │ Fallback   │  │ Graceful   │            │
│  │ Limiter    │  │ 链式降级    │  │ Shutdown   │            │
│  │ 4种策略    │  │ 空列表/模拟  │  │ 3阶段:     │            │
│  │ +自适应    │  │ /缓存       │  │ 排空→等待→关 │            │
│  └────────────┘  └────────────┘  └────────────┘            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ 自动恢复    │  │ 健康检查    │  │ 告警通知    │            │
│  │ Auto       │  │ Health     │  │ Alert      │            │
│  │ Recovery   │  │ Checker    │  │ Notifier   │            │
│  └────────────┘  └────────────┘  └────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 数据流 (核心链路)

### 3.1 路线规划主链路

```
用户输入 "周末一个人安静走走"
    │
    ▼
┌─────────────────────┐
│ 1. 意图解析 (8s超时)  │
│ LLM/规则 → 结构化意图  │
│ 画像匹配 → 需求向量    │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 2. 身份识别 (有user_id)│
│ LTM预测偏好 → 权重融合  │
│ WeightMapper → 动态权重│
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 3. 多智能体规划 (120s) │
│ rule_guard → expert_  │
│ router → 8个专家并行    │
│ → review → synth → out│
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 4. SSE 流式推送      │
│ 实时推送:            │
│ phase → phase → ... │
│ step → step → ...   │
│ done → route_id     │
└──────────┬──────────┘
           ▼
     前端渲染路线
```

### 3.2 对话调整链路

```
用户 "换掉第二个景点"
    │
    ▼
┌─────────────────────┐
│ 1. 指令分类          │
│ 关键词匹配 → 5种类型   │
│ 替换/节奏/预算/时间/重规划│
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 2. 执行调整          │
│ 替换: 同类目+情绪匹配  │
│ 节奏: 重设pace+重新求解 │
│ 预算: ±20%+重筛选     │
│ 时间: 调整时间窗       │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 3. 更新缓存+记录反馈   │
│ route_cache.set()    │
│ LTM.record_feedback()│
└──────────┬──────────┘
           ▼
     返回调整结果
```

---

## 4. 数据模型

### 4.1 POI (兴趣点)

```
{
  id: str,              // poi_001
  name: str,            // 名称
  category: str,        // 景点/餐厅/公园/商场/...
  city: str,            // 珠海
  rating: float,        // 0-5
  avg_price: float,     // 人均消费(元)
  avg_stay_min: int,    // 建议停留(分钟)
  lat/lng: float,       // 经纬度
  business_hours: str,  // "09:00-17:00"
  tags: [str],          // ["自然风光","拍照出片"]
  emotion_tags: {        // 6维情绪标签, 0-1
    excitement, tranquility, sociability,
    culture_depth, surprise, physical_demand
  },
  constraints: {
    accessible, pet_friendly,
    queue_time_min, opening_hours, has_restroom
  }
}
```

### 4.2 用户意图

```
{
  matched_profile_id: str,  // "P1" - "P20"
  preferred_categories: [str],
  pace: str,                // 闲逛型/平衡型/特种兵型
  budget: int,
  time_window: [start, end],
  start_location: str,
  group_type: str,          // 独居/情侣/亲子/朋友
  emotion_need: str,        // 主导情绪需求
  _demand_vector: {...},    // 6维需求向量
  _dynamic_weights: {...},  // WeightMapper计算的权重
  _user_id: str,
  _raw_input: str
}
```

### 4.3 路线结果

```
{
  route: [{               // 路线步骤
    poi: POIResponse,
    arrival_time: "09:00",
    departure_time: "11:00",
    travel_from_prev: {distance_m, time_min}
  }],
  emotion_curve: [{phase, value}],
  total_cost: {time_min, budget_used, step_estimate},
  unused_candidates: [POIResponse],
  breathing_spots: [POIResponse],
  narrative: {opening, steps, closing, emotion_highlights},
  user_intent: {...}
}
```

---

## 5. 部署架构

```
                        Internet
                           │
                        Nginx (80/443)
                       /              \
             反向代理 /                  \ 静态文件
                   /                      \
         FastAPI App (8000)          frontend/ (HTML/CSS/JS)
              │
     ┌────────┼────────┐
     │        │        │
   Redis    DB       Prometheus
   (6379)  (5432)    (9090)
     │        │        │
     └────────┼────────┘
              │
         Grafana (3000)
              │
        filebeat → ES/Kibana

Docker Compose 多服务:
  - cityflow-api (FastAPI + Uvicorn)
  - cityflow-redis
  - cityflow-db (PostgreSQL)
  - cityflow-nginx
  - cityflow-prometheus
  - cityflow-grafana
  - cityflow-filebeat
```

---

## 6. 配置体系

```
.env / .env.prod / .env.dev / .env.test

backend/config/settings.py
  ├── app: DEBUG, PORT, WORKERS
  ├── database: URL, POOL_SIZE
  ├── redis: URL, TIMEOUT
  ├── security: RATE_LIMIT, MAX_BODY, JWT_SECRET
  ├── llm: API_KEY, MODEL, TIMEOUT
  └── cache: TTL_DEFAULT, WARMUP_INTERVAL

backend/config/pool_config.py — 连接池参数
backend/config/validator.py — 配置校验
backend/config/hot_reload.py — 热重载 watchdog
```

---

## 7. 监控体系

```
┌────────────────────────────────────────────────────────────┐
│                     监控栈 (Monitoring)                       │
│                                                             │
│  Prometheus 指标:                                            │
│  ├─ http_requests_total{method, endpoint, status}         │
│  ├─ http_request_duration_seconds{method, endpoint}       │
│  ├─ rate_limit_hits_total                                  │
│  ├─ active_sessions                                        │
│  ├─ route_plan_count                                       │
│  ├─ cache_hit_ratio                                        │
│  └─ pool_connection_stats{pool_name, state}               │
│                                                             │
│  Sentry: 错误追踪 (sentry-sdk[fastapi])                      │
│                                                             │
│  Grafana Dashboard: 可视化面板                                │
│                                                             │
│  Alerts: 告警规则 (alerts.yml)                               │
│  ├─ high_error_rate → alert                                 │
│  ├─ slow_response_time → alert                              │
│  └─ pool_exhaustion → alert                                 │
│                                                             │
│  健康检查: /api/health + /api/pool/health                    │
│  深度检查: health/deep_check.py                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. 前端架构

```
frontend/
├── index.html           — 单页面入口 (Flex布局)
├── js/
│   ├── app.js           — 主控模块 (全局状态+SSE处理+UI协调)
│   ├── chart3d.js        — 3D地图可视化 (Three.js)
│   ├── l7-renderer.js    — L7 地理渲染 (蚂蚁L7)
│   └── llm-chat.js       — LLM对话组件
├── components/
│   ├── poi-list.js       — POI列表组件 (候选展示+选择)
│   └── timeline.js       — 时间轴组件 (路线步骤可视化)
├── store/
│   └── state.js          — 全局状态管理
├── api/
│   └── client.js         — HTTP API客户端
├── css/
│   ├── style.css         — 全局样式
│   └── components.css    — 组件样式
└── data/
    ├── city_poi_db.json  — POI数据副本
    └── osm_raw.json      — OSM原始数据
```

---

## 9. 测试架构

```
tests/
├── conftest.py             — 全局fixture
├── conftest_db.py          — 数据库fixture
├── factories.py             — 测试数据工厂
├── fixtures/                — 测试夹具(JSON)
│   ├── test_scenarios.json
│   ├── test_intents.json
│   └── test_pois.json
│
├── 单元测试 (services):
│   ├── test_intent.py       — 意图解析
│   ├── test_solver.py       — 路线求解
│   ├── test_narrator.py     — 文案生成
│   ├── test_dialogue.py     — 对话引擎
│   ├── test_filters.py      — POI筛选
│   ├── test_emotion_matrix.py  — 情绪矩阵
│   ├── test_economy.py      — 经济分析
│   ├── test_content_engine.py  — 内容引擎
│   ├── test_memory.py       — 记忆系统
│   ├── test_perception.py   — 环境感知
│   └── test_weight_mapper.py— 权重映射
│
│   ├── 基础设施测试:
│   ├── test_cache.py        — 缓存
│   ├── test_database.py     — 数据库
│   ├── test_message_queue.py— 消息队列
│   ├── test_task_queue.py   — 任务队列
│   ├── test_event_system.py — 事件系统
│   ├── test_config_hot_reload.py — 热重载
│   ├── test_service_infra.py— 服务基础设施
│
│   ├── 弹性测试:
│   ├── test_circuit_breaker.py  — 熔断器
│   ├── test_resilience.py      — 弹性模式
│   ├── test_retry.py           — 重试
│   └── test_fallback.py        — 兜底
│
│   ├── 安全测试:
│   ├── test_auth.py         — 认证
│   ├── test_encryption.py   — 加密
│   ├── test_security.py     — 安全
│
│   ├── 性能测试:
│   ├── test_performance.py  — 性能基线
│   ├── test_benchmark.py    — 基准测试
│   ├── test_vectorized.py   — 向量化
│   └── locustfile.py        — Locust 负载测试
│
│   ├── 集成测试:
│   ├── test_integration.py  — 服务集成
│   ├── test_e2e_routes.py   — 端到端路由
│   ├── test_graphql.py      — GraphQL
│   └── api_client.py        — API测试客户端
│
│   ├── Agent/LLM测试:
│   ├── test_llm_eval.py     — LLM评估
│   ├── test_llm_scoring.py  — LLM评分
│   ├── test_llm_parallel.py — LLM并行
│   ├── test_intent_mock.py  — 意图Mock
│   ├── test_router_cls.py   — 路由分类
│   ├── test_full_eval.py    — 全量评估
│   ├── test_score_comparison.py — 评分对比
│   └── test_targeted.py     — 定向测试
│
│   ├── 回归+C版本测试:
│   ├── test_c_version.py    — C版本测试
│   ├── test_two.py          — 双版本对比
│   ├── test_variance.py     — 方差分析
│   └── test_scenarios.py    — 场景测试
└── test_diagnose.py         — 诊断测试
```

---

## 10. 脚本工具库

```
scripts/
├── run.sh / start.sh / start_dev.sh / start_prod.sh  — 启动脚本
├── rollback.sh                                        — 回滚脚本
├── test_api.sh                                        — API测试
│
├── 数据生成:
├── gen_golden_cases.py     — 生成金标准测试用例
├── gen_golden_1000.py      — 生成1000组金标
├── gen_test_scenarios.py   — 生成测试场景
├── gen_famous_pois.py      — 知名POI生成
├── gen_niche_pois.py       — 小众POI生成
├── gen_scene_pois.py       — 场景POI生成
├── gen_special_pois.py     — 特殊POI生成
├── gen_critical_gap_pois.py— 临界缺口POI生成
├── gen_missing_cats.py     — 缺失类别生成
├── gen_ugc_reviews.py      — UGC评论生成
│
├── 文档生成:
├── generate_docx.py        — DOCX文档生成
├── generate_docx_casual.py — 非正式DOCX生成
├── write_essay.py          — 论文写作
│
├── 评估框架:
├── eval_framework.py       — 评估框架
├── run_llm_scoring.py      — LLM评分运行
├── optuna_weights.py       — Optuna权重优化
├── sync_emotion_tags.py    — 情绪标签同步
├── test_perfect_scenarios.py— 完美场景测试
│
├── 数据导入:
├── import_poi_to_db.py     — POI导入数据库
├── generate_road_traffic.py— 道路流量生成
├── generate_order.py        — 订单生成
└── run_data_gen.ps1        — 数据生成PowerShell脚本
```

---

## 11. 架构演进路线

```
V1 (原始)           →      V2 (增强)            →      V3 (当前 — C版本)
                                                             
单管线串行                 添加缓存+弹性                MoE多智能体架构
规则意图解析               Redis持久化                  LangGraph编排
TSPTW求解器               LTM长期记忆                 8个领域专家并行
基础文案生成               WeightMapper                quality review循环
20组用户画像               PreferenceManager           SSE实时推送agent事件
                          连接池管理                   元规则防火墙
                          GraphQL端点                 涌现式冲突检测
                          对话引擎V2                  热力图+决策溯源

技术债/已知局限:
  - 仅支持珠海单城市
  - 未接入美团真实API (使用Mock)
  - 缺少实时交通数据
  - 无多城市扩展
  - 前端为原生JS, 无框架
```

---

*文档生成日期: 2026-05-14*
