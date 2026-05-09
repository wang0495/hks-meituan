# CityFlow API 文档

**自动生成于源码解析**

## 概览

| 指标 | 数量 |
| :--- | :--- |
| 模块数 | 166 |
| 函数数 | 395 |
| 类数 | 344 |
| API 路由数 | 68 |

## API 路由

| 方法 | 路径 | 函数 | 说明 |
| :--- | :--- | :--- | :--- |
| POST | /api/plan | plan_route | 流式规划路线 |
| GET | /api/route/{route_id} | get_route | 获取路线详情 |
| GET | /api/route/{route_id}/adjust | adjust_route | 通过指令调整路线（快捷方式） |
| POST | /api/dialogue/{session_id} | dialogue | 对话式路线调整 |
| GET | /api/health | health | 健康检查 |
| GET | /api/cache/stats | cache_stats | 缓存统计 |
| GET | /docs | custom_swagger_ui_html |  |
| GET | /redoc | custom_redoc_html |  |
| GET | /health | health | 网关健康检查 |
| GET | /logs | get_audit_logs | 查询审计日志 |
| GET | /export | export_audit_logs | 导出审计日志 |
| GET | /stats | get_audit_stats | 审计日志统计 |
| GET | /data/ | get_data | 查询数据集 |
| GET | /poi/ | get_poi | 查询城市POI数据 |
| GET | /datasets | get_datasets | 列出所有数据集 |
| GET | /order/ | get_order | 查询POI交通流量 |
| GET | /road-traffic/ | get_road_traffic | 查询道路拥堵指数 |
| GET | /health | health_check | 基础健康检查 |
| GET | /health/detailed | detailed_health | 详细健康状态 |
| POST | /chat | chat | LLM对话 |
| POST | /chat/stream | chat_stream | LLM流式对话 |
| GET | /metrics | metrics | Prometheus 指标 |
| POST | /publish/{queue} | publish_message | 发布单条消息 |
| POST | /publish/{queue}/batch | publish_batch | 批量发布消息 |
| POST | /consume/{queue} | start_consumer | 启动消费者 |
| GET | /status/{queue} | queue_status | 查询队列状态 |
| DELETE | /{queue} | clear_queue | 清空队列 |
| GET | /handlers | list_handlers | 列出已注册处理器 |
| POST | /search | search_pois | 搜索POI |
| GET | /detail/{poi_id} | get_poi_detail | 获取POI详情 |
| POST | /distance-matrix | get_distance_matrix | 计算距离矩阵 |
| POST | /register | register_service | 注册服务 |
| POST | /deregister/{service_id} | deregister_service | 注销服务 |
| POST | /heartbeat/{service_id} | heartbeat | 服务心跳 |
| GET | /services | get_services | 获取服务列表 |
| GET | /services/{service_name} | discover_service | 发现服务 |
| GET | /stats | get_stats | 注册中心统计 |
| POST | /cleanup | cleanup_unhealthy | 清理不健康实例 |
| POST | / | create_session | 创建会话 |
| GET | /stats | get_session_stats | 会话统计 |
| GET | /{session_id} | get_session | 获取会话 |
| PUT | /{session_id} | update_session | 更新会话 |
| DELETE | /{session_id} | delete_session | 删除会话 |
| POST | /{session_id}/refresh | refresh_session | 刷新会话 |
| GET | /user/{user_id}/list | get_user_sessions | 获取用户会话列表 |
| POST | /{func_name} | submit_task | 提交后台任务 |
| GET | /{task_id} | get_task_status | 查询任务状态 |
| DELETE | /{task_id} | cancel_task | 取消任务 |
| GET | / | list_tasks | 列出所有任务 |
| GET | /cityflow-error | cityflow_error |  |
| GET | /intent-error | intent_error |  |
| GET | /llm-error | llm_error |  |
| GET | /dialogue-error | dialogue_error |  |
| GET | /no-pois-error | no_pois_error |  |
| GET | /rate-limit-error | rate_limit_error |  |
| GET | /generic-error | generic_error |  |
| GET | /test | test_endpoint |  |
| PATCH |  | test_collect_returns_resource_metrics |  |
| POST | /dialogue/{session_id} | dialogue_v1 | [V1] 对话式路线调整 |
| GET | /route/{route_id} | get_route_v1 | [V1] 获取路线详情 |
| POST | /plan | plan_route_v1 | [V1] 流式规划路线 |
| POST | /poi/search | search_pois_v1 | [V1] 搜索POI |
| GET | /poi/detail/{poi_id} | get_poi_detail_v1 | [V1] 获取POI详情 |
| POST | /poi/distance-matrix | get_distance_matrix_v1 | [V1] 计算距离矩阵 |
| POST | /plan | plan_route_v2 | [V2] 流式规划路线（增强版） |
| POST | /poi/search | search_pois_v2 | [V2] 搜索POI（增强版） |
| GET | /poi/detail/{poi_id} | get_poi_detail_v2 | [V2] 获取POI详情（增强版） |
| POST | /poi/distance-matrix | get_distance_matrix_v2 | [V2] 计算距离矩阵 |

### POST /api/plan

**流式规划路线**

流式规划路线。

根据用户自然语言输入，经过意图解析、候选搜索、路线求解、文案生成四个阶段，
以 SSE 事件流的形式逐步返回结果。

返回的 `route_id` 可用于后续的 `/api/route/{route_id}` 查询和
`/api/dialogue/{session_id}` 对话调整。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| request | PlanRequest | - |

---

### GET /api/route/{route_id}

**获取路线详情**

获取已规划路线的完整数据。

路线数据保存在内存缓存中，服务重启后失效。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| route_id | str | - |

---

### GET /api/route/{route_id}/adjust

**通过指令调整路线（快捷方式）**

通过对话指令调整路线（GET快捷方式）。

自动创建对话会话（如果不存在），然后处理用户的调整指令。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| route_id | str | - |
| instruction | str | - |

---

### POST /api/dialogue/{session_id}

**对话式路线调整**

对话式路线调整。

通过POST请求发送调整指令，系统自动分类指令类型并执行相应调整。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| session_id | str | - |
| request | AdjustRequest | - |

---

### GET /api/health

**健康检查**

健康检查接口。

---

### GET /api/cache/stats

**缓存统计**

返回缓存命中率统计。

---

### GET /docs

---

### GET /redoc

---

### GET /health

**网关健康检查**

网关自身健康检查。

---

### GET /logs

**查询审计日志**

查询审计日志。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| user_id | str | None | Query(...) |
| action | AuditAction | None | Query(...) |
| resource_type | str | None | Query(...) |
| start_time | datetime | None | Query(...) |
| end_time | datetime | None | Query(...) |
| limit | int | Query(...) |
| offset | int | Query(...) |

**返回值**: `dict`

---

### GET /export

**导出审计日志**

导出审计日志。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| format | Literal['json', 'csv'] | Query(...) |
| start_time | datetime | None | Query(...) |
| end_time | datetime | None | Query(...) |
| limit | int | Query(...) |

**返回值**: `Response`

---

### GET /stats

**审计日志统计**

审计日志统计。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| start_time | datetime | None | Query(...) |
| end_time | datetime | None | Query(...) |

**返回值**: `dict`

---

### GET /data/

**查询数据集**

通用数据集查询。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| dataset | str | None | Query(...) |
| category | str | None | Query(...) |

---

### GET /poi/

**查询城市POI数据**

返回城市 POI 数据，支持城市和品类筛选。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| city | str | None | Query(...) |
| category | str | None | Query(...) |

---

### GET /datasets

**列出所有数据集**

列出所有可用数据集。

---

### GET /order/

**查询POI交通流量**

返回 POI 交通流量快照，支持按城市/品类筛选。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| city | str | None | Query(...) |
| category | str | None | Query(...) |
| day_of_year | int | None | Query(...) |
| hour | int | None | Query(...) |

---

### GET /road-traffic/

**查询道路拥堵指数**

返回道路拥堵指数快照，支持按城市/路段类型筛选。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| city | str | None | Query(...) |
| road_type | str | None | Query(...) |
| day_of_year | int | None | Query(...) |
| hour | int | None | Query(...) |

---

### GET /health

**基础健康检查**

基础健康检查 -- 轻量、快速，适合高频调用。

**返回值**: `dict`

---

### GET /health/detailed

**详细健康状态**

详细健康检查 -- 包含系统资源和依赖服务状态。

**返回值**: `dict`

---

### POST /chat

**LLM对话**

与LLM进行单轮对话。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| req | ChatRequest | - |

---

### POST /chat/stream

**LLM流式对话**

与LLM进行流式对话。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| req | ChatRequest | - |

---

### GET /metrics

**Prometheus 指标**

返回 Prometheus 指标文本。

**返回值**: `Response`

---

### POST /publish/{queue}

**发布单条消息**

发布一条消息到指定队列。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| queue | str | - |
| body | PublishRequest | - |

**返回值**: `dict[str, Any]`

---

### POST /publish/{queue}/batch

**批量发布消息**

批量发布消息到指定队列。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| queue | str | - |
| body | PublishBatchRequest | - |

**返回值**: `dict[str, Any]`

---

### POST /consume/{queue}

**启动消费者**

为指定队列启动一个后台消费者。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| queue | str | - |
| body | StartConsumerRequest | - |

**返回值**: `dict[str, str]`

---

### GET /status/{queue}

**查询队列状态**

查询指定队列的长度。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| queue | str | - |

**返回值**: `dict[str, Any]`

---

### DELETE /{queue}

**清空队列**

清空指定队列中的所有消息。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| queue | str | - |

**返回值**: `dict[str, Any]`

---

### GET /handlers

**列出已注册处理器**

列出所有已注册的消息处理器名称。

**返回值**: `dict[str, list[str]]`

---

### POST /search

**搜索POI**

搜索兴趣点。

支持按城市、类别、标签、关键词、评分、价格、地理位置等多维度筛选。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| request | SearchRequest | - |
| lat | Optional[float] | Query(...) |
| lng | Optional[float] | Query(...) |

---

### GET /detail/{poi_id}

**获取POI详情**

获取POI详情。

根据POI ID返回完整的POI信息，包括情绪标签和约束条件。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| poi_id | str | - |
| lat | Optional[float] | Query(...) |
| lng | Optional[float] | Query(...) |

---

### POST /distance-matrix

**计算距离矩阵**

计算距离矩阵。

输入POI ID列表，返回N x N的距离矩阵。距离使用haversine公式计算，
乘以1.3的道路系数，时间按30km/h估算。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| request | DistanceMatrixRequest | - |

---

### POST /register

**注册服务**

注册服务实例。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| service | ServiceInfo | - |

**返回值**: `dict[str, str]`

---

### POST /deregister/{service_id}

**注销服务**

注销服务实例。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| service_id | str | - |

**返回值**: `dict[str, str]`

---

### POST /heartbeat/{service_id}

**服务心跳**

更新服务心跳。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| service_id | str | - |

**返回值**: `dict[str, str]`

---

### GET /services

**获取服务列表**

获取服务列表。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| service_name | str | None | None |

**返回值**: `dict[str, Any]`

---

### GET /services/{service_name}

**发现服务**

发现服务实例。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| service_name | str | - |

**返回值**: `dict[str, Any]`

---

### GET /stats

**注册中心统计**

获取注册中心统计。

**返回值**: `dict[str, int]`

---

### POST /cleanup

**清理不健康实例**

清理不健康实例。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| service_name | str | None | None |

**返回值**: `dict[str, str]`

---

### POST /

**创建会话**

创建新会话，返回 session_id。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| body | CreateSessionRequest | None | None |

**返回值**: `dict[str, str]`

---

### GET /stats

**会话统计**

获取会话统计信息（总数、有用户绑定的、匿名的）。

**返回值**: `dict[str, int]`

---

### GET /{session_id}

**获取会话**

获取指定会话的完整数据。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| session_id | str | - |

**返回值**: `dict[str, Any]`

---

### PUT /{session_id}

**更新会话**

更新会话数据（合并写入）。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| session_id | str | - |
| body | UpdateSessionRequest | - |

**返回值**: `dict[str, str]`

---

### DELETE /{session_id}

**删除会话**

删除指定会话。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| session_id | str | - |

**返回值**: `dict[str, str]`

---

### POST /{session_id}/refresh

**刷新会话**

刷新会话过期时间（续期）。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| session_id | str | - |

**返回值**: `dict[str, str]`

---

### GET /user/{user_id}/list

**获取用户会话列表**

获取指定用户的所有活跃会话。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| user_id | str | - |

**返回值**: `dict[str, Any]`

---

### POST /{func_name}

**提交后台任务**

提交后台任务。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| func_name | str | - |
| request | SubmitTaskRequest | - |

---

### GET /{task_id}

**查询任务状态**

查询任务状态。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| task_id | str | - |

---

### DELETE /{task_id}

**取消任务**

取消任务。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| task_id | str | - |

---

### GET /

**列出所有任务**

列出所有任务。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| status | str | None | Query(...) |

---

### GET /cityflow-error

---

### GET /intent-error

---

### GET /llm-error

---

### GET /dialogue-error

---

### GET /no-pois-error

---

### GET /rate-limit-error

---

### GET /generic-error

---

### GET /test

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| request | Request | - |

**返回值**: `dict`

---

### PATCH 

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| mock_psutil | object | - |

**返回值**: `None`

---

### POST /dialogue/{session_id}

**[V1] 对话式路线调整**

V1 版本的对话式路线调整。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| session_id | str | - |
| request | AdjustRequestV1 | - |

---

### GET /route/{route_id}

**[V1] 获取路线详情**

V1 版本的路线详情查询。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| route_id | str | - |

---

### POST /plan

**[V1] 流式规划路线**

V1版本的路线规划（SSE流式响应）。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| request | PlanRequestV1 | - |

---

### POST /poi/search

**[V1] 搜索POI**

V1 版本的 POI 搜索。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| request | SearchRequestV1 | - |
| lat | Optional[float] | Query(...) |
| lng | Optional[float] | Query(...) |

---

### GET /poi/detail/{poi_id}

**[V1] 获取POI详情**

V1 版本的 POI 详情。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| poi_id | str | - |

---

### POST /poi/distance-matrix

**[V1] 计算距离矩阵**

V1 版本的距离矩阵计算。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| request | DistanceMatrixRequestV1 | - |

---

### POST /plan

**[V2] 流式规划路线（增强版）**

V2版本的路线规划（SSE流式响应，增强版）。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| request | PlanRequestV2 | - |

---

### POST /poi/search

**[V2] 搜索POI（增强版）**

V2 版本的 POI 搜索（增强版）。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| request | SearchRequestV2 | - |
| lat | Optional[float] | Query(...) |
| lng | Optional[float] | Query(...) |

---

### GET /poi/detail/{poi_id}

**[V2] 获取POI详情（增强版）**

V2 版本的 POI 详情（增强版）。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| poi_id | str | - |

---

### POST /poi/distance-matrix

**[V2] 计算距离矩阵**

V2 版本的距离矩阵计算。

**参数:**

| 参数名 | 类型 | 默认值 |
| :--- | :--- | :--- |
| request | DistanceMatrixRequestV2 | - |

---

## 模块详情

### backend.config

CityFlow 应用配置。

通过环境变量 / .env 文件加载配置，使用 pydantic-settings 进行校验。
支持多环境（dev / test / prod）配置，子配置按模块拆分。

#### class `Environment`

**继承**: `str`, `Enum`

运行环境枚举。

#### class `DatabaseSettings`

**继承**: `BaseSettings`

数据库配置。

#### class `RedisSettings`

**继承**: `BaseSettings`

Redis 配置。

#### class `LLMSettings`

**继承**: `BaseSettings`

LLM 服务配置。

#### class `SecuritySettings`

**继承**: `BaseSettings`

安全配置。

#### class `Settings`

**继承**: `BaseSettings`

CityFlow 主配置。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| _apply_env_defaults | - | Settings |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_settings | - | Settings | 否 |

---

### backend.config_loader

配置加载与验证。

根据 ENVIRONMENT 环境变量自动选择 .env 文件，
并在创建 Settings 实例后执行额外的业务验证。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| load_config | env | Settings | 否 |
| validate_config | config | None | 否 |
| get_config_summary | config | dict[str, str | int | bool] | 否 |

---

### backend.errors

CityFlow 统一错误码与异常体系。

错误码分段：
    1xxx - 通用错误
    2xxx - 认证/授权错误
    3xxx - 业务逻辑错误
    4xxx - 数据/输入错误
    5xxx - 外部服务错误

#### class `ErrorCode`

**继承**: `Enum`

错误码枚举。

#### class `CityFlowException`

**继承**: `Exception`

CityFlow 基础异常。

所有业务异常的基类，携带错误码、消息、可选详情和 HTTP 状态码。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | code, message, details, status_code | None |
| to_dict | - | dict[str, Any] |

#### class `IntentParseError`

**继承**: `CityFlowException`

意图解析失败。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | message, details | None |

#### class `NoPOIsFoundError`

**继承**: `CityFlowException`

未找到符合条件的 POI。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | message, details | None |

#### class `RouteSolvingError`

**继承**: `CityFlowException`

路线求解失败。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | message, details | None |

#### class `NarrativeGenerationError`

**继承**: `CityFlowException`

文案生成失败。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | message, details | None |

#### class `DialogueError`

**继承**: `CityFlowException`

对话处理失败。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | message, details | None |

#### class `LLMServiceError`

**继承**: `CityFlowException`

LLM 服务异常。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | message, details | None |

#### class `RateLimitError`

**继承**: `CityFlowException`

请求频率超限。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | message, details | None |

---

### backend.i18n

CityFlow 国际化 (i18n) 模块。

提供多语言支持，包括：
- 基于 contextvars 的线程安全 / 异步安全语言切换
- 内置 zh_CN / en_US 翻译
- 点分键访问（如 "common.success"）
- 参数插值（如 t("greeting", name="Alice")）

#### class `I18n`

国际化管理器。

每个实例持有翻译数据，语言状态通过 contextvars 管理，
天然兼容 async 并发场景。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | translations, default_locale | None |
| current_locale | - | str |
| set_locale | locale | None |
| t | key | str |
| get_translations | locale | TranslationDict |
| add_translations | locale, translations | None |
| _normalize_locale | locale | str |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| _resolve_key | data, dotted_key | str | None | 否 |
| _deep_merge | base, override | None | 否 |
| get_i18n | - | I18n | 否 |
| t | key | str | 否 |
| set_locale | locale | None | 否 |
| get_locale | - | str | 否 |

---

### backend.main

CityFlow API -- 前后端集成 + SSE 流式路线规划。

#### class `PlanRequest`

**继承**: `BaseModel`

流式规划路线的请求体。

#### class `AdjustRequest`

**继承**: `BaseModel`

对话式路线调整的请求体。

#### class `EmotionTags`

**继承**: `BaseModel`

POI情绪标签（6维，取值0~1）。

#### class `POIConstraints`

**继承**: `BaseModel`

POI约束条件。

#### class `TravelInfo`

**继承**: `BaseModel`

交通信息。

#### class `POIResponse`

**继承**: `BaseModel`

兴趣点（POI）完整信息。

#### class `RouteStep`

**继承**: `BaseModel`

路线中的单个步骤。

#### class `NarrativeStep`

**继承**: `BaseModel`

路线文案。

#### class `RouteResult`

**继承**: `BaseModel`

完整的路线规划结果。

#### class `DoneEvent`

**继承**: `BaseModel`

SSE done 事件的载荷。

#### class `DialogueResult`

**继承**: `BaseModel`

对话调整的响应。

#### class `DistanceMatrixItem`

**继承**: `BaseModel`

距离矩阵中的单个元素。

#### class `DistanceMatrixResponse`

**继承**: `BaseModel`

距离矩阵响应。

#### class `ErrorResponse`

**继承**: `BaseModel`

错误响应。

#### class `HealthResponse`

**继承**: `BaseModel`

健康检查响应。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| _with_timeout | coro, timeout_seconds, fallback | - | 是 |
| _generate_simplified_route | pois, count | dict[str, Any] | 否 |
| _sse | event, data_obj | str | 否 |
| plan_route | request | - | 是 |
| get_route | route_id | - | 是 |
| adjust_route | route_id, instruction | - | 是 |
| dialogue | session_id, request | - | 是 |
| startup | - | - | 是 |
| shutdown | - | - | 是 |
| health | - | - | 是 |
| cache_stats | - | - | 是 |

---

### backend.openapi

OpenAPI 元数据定义。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_openapi_metadata | - | dict[str, Any] | 否 |

---

### backend.auth.access_control

访问控制服务。

提供用户注册、权限校验，以及 FastAPI 依赖注入和装饰器两种接入方式。

#### class `AccessControl`

访问控制服务（进程内单例）。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | - | None |
| add_user | user | None |
| remove_user | user_id | bool |
| get_user | user_id | User | None |
| list_users | - | list[User] |
| check_permission | user_id, permission, resource_id | bool |
| require | permission | Callable[Ellipsis, Any] |
| require_permission | permission | Callable[Ellipsis, Any] |
| _extract_user_id | request | str | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_access_control | - | AccessControl | 否 |
| reset_access_control | - | None | 否 |

---

### backend.auth.models

角色、权限与用户模型。

#### class `Role`

**继承**: `str`, `Enum`

系统角色。

#### class `Permission`

**继承**: `str`, `Enum`

细粒度权限枚举。

#### class `User`

**继承**: `BaseModel`

系统用户。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| has_permission | permission | bool |
| get_all_permissions | - | set[Permission] |

---

### backend.auth.__init__

CityFlow 访问控制模块。

提供基于角色的访问控制（RBAC），包括：
- 角色与权限定义
- 用户模型
- 访问控制服务（单例）

Usage:
    from backend.auth import get_access_control, Permission, Role, User

    acl = get_access_control()
    acl.add_user(User(user_id="u1", username="admin", role=Role.ADMIN))
    if acl.check_permission("u1", Permission.MANAGE_USERS):
        ...

---

### backend.database.base

CityFlow 数据库引擎与会话管理。

使用 SQLAlchemy 2.0 异步引擎 + AsyncSession。
数据库连接参数从 backend.config.settings.database 读取。

#### class `Base`

**继承**: `DeclarativeBase`

SQLAlchemy 声明式基类。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_db | - | AsyncGenerator[AsyncSession, None] | 是 |

---

### backend.database.models

CityFlow 数据库 ORM 模型。

对应 PostgreSQL 表：
    users, routes, route_steps, dialogues, user_preferences

使用 SQLAlchemy 2.0 mapped_column 风格。

#### class `User`

**继承**: `Base`

用户。

#### class `Route`

**继承**: `Base`

规划路线。

#### class `RouteStep`

**继承**: `Base`

路线中的单个步骤。

#### class `Dialogue`

**继承**: `Base`

对话消息。

#### class `UserPreference`

**继承**: `Base`

用户偏好设置（按类型存储）。

#### class `AuditLog`

**继承**: `Base`

审计日志。

---

### backend.database.pool

CityFlow 数据库连接池管理。

基于 SQLAlchemy 异步引擎的连接池，提供：
- 连接池生命周期管理（启动 / 关闭）
- 连接健康检查
- 连接池统计信息

与 backend.database.base 互补：base 负责引擎和会话工厂，
本模块负责池的生命周期与监控。

#### class `PoolStats`

连接池统计快照。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| utilization | - | float |

#### class `DatabasePool`

数据库连接池。

Args:
    database_url: 异步数据库连接 URL。
    pool_size: 核心连接数。
    max_overflow: 超出 pool_size 后的最大临时连接数。
    pool_recycle: 连接回收周期（秒），避免数据库端超时断开。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| start | - | None |
| close | - | None |
| get_session | - | AsyncGenerator[AsyncSession, None] |
| ping | - | bool |
| get_stats | - | PoolStats |
| get_stats_dict | - | dict[str, Any] |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_database_pool | - | DatabasePool | 否 |

---

### backend.database.repository

CityFlow 数据访问层（Repository 模式）。

所有方法使用 AsyncSession，配合 FastAPI 的依赖注入使用。

#### class `UserRepository`

用户数据访问。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | db | None |
| create | preferences | User |
| get | user_id | User | None |
| update_preferences | user_id, preferences | User | None |

#### class `RouteRepository`

路线数据访问。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | db | None |
| create | user_input, route_data, user_id, narrative | Route |
| get | route_id | Route | None |
| get_by_user | user_id, limit, offset | Sequence[Route] |
| update | route_id, route_data, narrative | Route | None |
| update_status | route_id, status | Route | None |
| delete | route_id | bool |

#### class `RouteStepRepository`

路线步骤数据访问。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | db | None |
| bulk_create | route_id, steps | list[RouteStep] |
| get_by_route | route_id | Sequence[RouteStep] |
| replace_all | route_id, steps | list[RouteStep] |

#### class `DialogueRepository`

对话数据访问。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | db | None |
| add_message | route_id, session_id, role, content, metadata | Dialogue |
| get_session_messages | session_id, limit | Sequence[Dialogue] |
| get_route_dialogues | route_id | Sequence[Dialogue] |

#### class `UserPreferenceRepository`

用户偏好数据访问。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | db | None |
| upsert | user_id, preference_type, preference_value | UserPreference |
| get | user_id, preference_type | UserPreference | None |
| get_all | user_id | Sequence[UserPreference] |

---

### backend.database.__init__

CityFlow 数据库模块。

---

### backend.di.container

CityFlow 依赖注入容器。

支持三种注册方式：
- 实例注册：直接传入已构造的对象（可选单例）
- 工厂注册：传入 callable，每次 resolve 时调用
- 类型注册：传入类，容器自动构造（通过 inspect 解析 __init__ 参数）

#### class `DIContainer`

依赖注入容器。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | - | None |
| register | name, instance | None |
| register_factory | name, factory | None |
| register_class | name | None |
| resolve | name | Any |
| resolve_type | - | T |
| _build | - | Any |
| reset | - | None |

#### class `ServiceNotFoundError`

**继承**: `KeyError`

服务未注册时抛出。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_container | - | DIContainer | 否 |
| reset_container | - | None | 否 |
| inject | - | Callable[Ellipsis, Any] | 否 |

---

### backend.di.registry

CityFlow 服务注册表。

集中注册所有核心服务到 DI 容器。
应用启动时调用 ``register_services()`` 完成初始化。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| register_services | - | None | 否 |

---

### backend.di.__init__

CityFlow 依赖注入模块。

提供轻量级 DI 容器，用于集中管理服务实例与工厂函数。

---

### backend.docs.__init__

自定义 OpenAPI schema 生成与文档页面端点。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| custom_openapi | app | dict | 否 |
| register_docs_endpoints | app | None | 否 |

---

### backend.events.decorators

CityFlow 事件发射装饰器。

提供声明式的事件发布能力，将事件发射逻辑从业务代码中解耦。

使用示例::

    from backend.events.decorators import emit_event
    from backend.events.types import EventType

    @emit_event(EventType.ROUTE_PLANNED)
    async def plan_route(user_input: str) -> dict:
        # ... 业务逻辑 ...
        return {"route_id": "r-001", "steps": [...]}

    # 调用 plan_route 后会自动发布 route.planned 事件，
    # 事件 data 中包含 {"result": {...}, "args": [...], "kwargs": {...}}

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| emit_event | event_type | Callable[List(elts=[Name(id='F', ctx=Load())], ctx=Load()), F] | 否 |

---

### backend.events.handlers

CityFlow 事件处理器注册。

集中注册所有内置事件处理器。在应用启动时调用
:func:`setup_event_handlers` 一次即可。

新增处理器的步骤：
1. 在本模块编写 ``async def handle_xxx(event)`` 或同步函数
2. 在 :func:`setup_event_handlers` 中添加对应的订阅调用

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| setup_event_handlers | - | None | 否 |
| handle_route_planned_metrics | event | None | 否 |
| handle_route_planned_notify | event | None | 是 |
| handle_user_feedback_record | event | None | 是 |
| handle_system_error_alert | event | None | 否 |

---

### backend.events.types

CityFlow 预定义事件类型。

使用 :class:`enum.StrEnum` 统一管理事件类型字符串，避免拼写错误。
使用 :class:`dataclasses.dataclass` 定义带类型提示的事件子类。

所有事件子类继承自 :class:`~backend.services.event_bus.Event`，
可直接传入 :meth:`~backend.services.event_bus.EventBus.publish` 等方法。

使用示例::

    from backend.events.types import RoutePlannedEvent, EventType
    from backend.services.event_bus import get_event_bus

    event = RoutePlannedEvent(route_id="r-001", user_id="u-42", data={"steps": [...]})
    get_event_bus().publish(event)

    # 或使用枚举值发布通用事件
    bus.publish(Event(event_type=EventType.USER_FEEDBACK, data={...}))

#### class `EventType`

**继承**: `StrEnum`

事件类型常量。

集中管理所有事件类型的字符串标识，防止硬编码散落各处。

#### class `RoutePlannedEvent`

**继承**: `Event`

路线规划完成事件。

当路线求解器成功生成路线后发布，供通知、指标、缓存等
下游处理器消费。

#### class `RouteAdjustedEvent`

**继承**: `Event`

路线调整事件。

当用户通过对话调整已有路线后发布。

#### class `UserFeedbackEvent`

**继承**: `Event`

用户反馈事件。

当用户提交评价、纠错或其他反馈时发布。

#### class `SystemErrorEvent`

**继承**: `Event`

系统错误事件。

当系统内部发生未预期错误时发布，供告警和日志处理器消费。

---

### backend.events.__init__

CityFlow 事件系统。

提供事件驱动架构的核心组件：

- :mod:`backend.events.types`    -- 预定义事件类型
- :mod:`backend.events.handlers` -- 事件处理器注册
- :mod:`backend.events.decorators` -- 事件发射装饰器

快速开始::

    from backend.events import setup_events, EventType
    from backend.services.event_bus import get_event_bus, Event

    # 在应用启动时初始化
    setup_events()

    # 在业务代码中发布事件
    bus = get_event_bus()
    bus.publish(Event(event_type=EventType.ROUTE_PLANNED, data={"route_id": "xxx"}))

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| setup_events | - | None | 否 |

---

### backend.gateway.auth

JWT 认证中间件。

拦截请求，验证 Bearer token，将解析出的用户信息注入 ``request.state``。
白名单路径跳过认证，开发环境可配置为可选认证。

#### class `AuthMiddleware`

**继承**: `BaseHTTPMiddleware`

JWT 认证中间件。

Args:
    app: ASGI 应用。
    secret_key: JWT 签名密钥。
    algorithm: JWT 算法，默认 HS256。
    whitelist: 白名单路径集合，这些路径不校验 token。
    optional: 为 ``True`` 时缺少 token 不报错（开发模式）。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | app, secret_key, algorithm, whitelist, optional | - |
| dispatch | request, call_next | - |
| _is_whitelisted | path | bool |
| _extract_token | request | str | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| create_token | payload, secret_key, expires_in, algorithm | str | 否 |

---

### backend.gateway.main

CityFlow API 网关入口。

将请求路由转发到后端微服务（POI、路线、对话），
集成 JWT 认证和速率限制中间件。

用法::

    # 作为独立服务运行
    uvicorn backend.gateway.main:app --port 9000

    # 或在代码中创建
    from backend.gateway.main import create_gateway_app
    app = create_gateway_app()

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| create_gateway_app | - | FastAPI | 否 |
| _build_forward_headers | request | dict[str, str] | 否 |

---

### backend.gateway.rate_limit

网关级速率限制中间件。

基于客户端 IP 的滑动窗口限流，支持 X-Forwarded-For 等反向代理头。
与 ``backend.middleware.rate_limit.RateLimitMiddleware`` 功能类似，
但专为网关场景设计，响应头格式对齐网关惯例。

#### class `GatewayRateLimitMiddleware`

**继承**: `BaseHTTPMiddleware`

网关速率限制中间件。

Args:
    app: ASGI 应用。
    requests_per_minute: 每个客户端 IP 每分钟最大请求数。
    whitelist_paths: 不限流的路径前缀列表。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | app, requests_per_minute, whitelist_paths | - |
| dispatch | request, call_next | - |
| _get_client_ip | request | str |
| _maybe_cleanup | now | None |

---

### backend.gateway.router

网关路由配置。

基于前缀匹配将请求转发到对应的后端微服务。
支持精确匹配和正则模式匹配。

#### class `RouteTarget`

路由目标。

#### class `GatewayRouter`

网关路由器。

按注册顺序匹配路由，首个匹配生效。
支持两种模式：
- 精确前缀匹配（默认）：`/api/poi` 匹配 `/api/poi/xxx`
- 正则匹配：以 `^` 开头的 pattern 按正则处理

用法::

    router = GatewayRouter()
    router.register("poi", "http://localhost:8001", prefix="/api/poi")
    target = router.match("/api/poi/search?keyword=故宫", "GET")

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | - | None |
| register | service, base_url, prefix, methods, strip_prefix | None |
| match | path, method | tuple[RouteTarget, str] | None |
| get_service_url | service | str | None |
| service_names | - | list[str] |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_gateway_router | - | GatewayRouter | 否 |
| setup_default_routes | poi_url, route_url, dialogue_url | GatewayRouter | 否 |

---

### backend.gateway.__init__

CityFlow API 网关模块。

提供请求路由转发、JWT 认证授权、速率限制等网关功能。
可作为独立服务运行，也可嵌入主应用。

---

### backend.graphql.config

CityFlow GraphQL 配置 -- Schema 工厂。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| create_graphql_schema | - | strawberry.Schema | 否 |

---

### backend.graphql.resolvers

CityFlow GraphQL Resolvers -- 调用已有服务层实现查询与变更。

每个 resolver 对应 schema.py 中的一个字段，内部调用
backend.services 下的 data_service / intent_parser / solver / narrator / dialogue。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| _to_emotion_tags | raw | EmotionTags | None | 否 |
| _to_constraints | raw | POIConstraints | None | 否 |
| _to_poi | raw | POI | 否 |
| _to_travel_info | raw | TravelInfo | None | 否 |
| _to_route_step | raw | RouteStep | 否 |
| _to_narrative | raw | NarrativeStep | None | 否 |
| _to_total_cost | raw | TotalCost | None | 否 |
| _to_route | route_id, raw, user_input | Route | 否 |
| resolve_pois | region, category, limit | list[POI] | 是 |
| resolve_poi | id | Optional[POI] | 是 |
| resolve_routes | limit | list[Route] | 是 |
| resolve_route | id | Optional[Route] | 是 |
| _with_timeout | coro, timeout_seconds, fallback | Any | 是 |
| resolve_plan_route | user_input | Route | 是 |
| resolve_adjust_route | route_id, instruction | DialogueResponse | 是 |

---

### backend.graphql.schema

CityFlow GraphQL Schema -- Strawberry 类型定义。

所有类型与 backend/main.py 中的 Pydantic 响应模型保持一致。

#### class `EmotionTags`

POI 情绪标签（6维，取值 0~1）。

#### class `POIConstraints`

POI 约束条件。

#### class `TravelInfo`

交通信息。

#### class `POI`

兴趣点。

#### class `RouteStep`

路线中的单个步骤。

#### class `NarrativeStep`

路线文案。

#### class `TotalCost`

费用估算。

#### class `Route`

完整路线规划结果。

#### class `ChangeRecord`

对话调整的变更记录。

#### class `DialogueResponse`

对话调整的响应。

#### class `Query`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| pois | region, category, limit | list[POI] |
| poi | id | Optional[POI] |
| routes | limit | list[Route] |
| route | id | Optional[Route] |

#### class `Mutation`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| plan_route | user_input | Route |
| adjust_route | route_id, instruction | DialogueResponse |

---

### backend.graphql.__init__

CityFlow GraphQL 模块。

---

### backend.i18n.__init__

CityFlow 国际化（i18n）框架。

使用方式：
    from backend.i18n import t, get_i18n

    # 翻译
    msg = t("route.planning")

    # 带参数
    msg = t("route.distance", km=5.2)

    # 切换语言
    get_i18n().set_locale("en_US")

#### class `I18n`

国际化管理器。

从 JSON 翻译文件加载多语言文本，支持点分键路径和字符串格式化参数。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | locale_dir | None |
| _load_translations | - | None |
| reload | - | None |
| set_locale | locale | None |
| get_locale | - | str |
| get_available_locales | - | list[str] |
| translate | key | str |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_i18n | - | I18n | 否 |
| t | key | str | 否 |

---

### backend.middleware.compression

CityFlow HTTP 响应压缩中间件。

根据客户端 Accept-Encoding 头自动压缩响应体。
支持 gzip 和 deflate 两种压缩方式。

#### class `CompressionMiddleware`

**继承**: `BaseHTTPMiddleware`

HTTP 响应 gzip/deflate 压缩中间件。

仅在满足以下条件时压缩：
- 客户端声明支持对应编码
- 响应状态码为 2xx
- 响应体大于最小阈值
- Content-Type 不是已压缩格式

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | app, minimum_size, compresslevel | None |
| dispatch | request, call_next | Response |
| _read_body | response | bytes |
| _make_response | body, original, content_encoding | Response |

---

### backend.middleware.config

配置注入中间件。

将全局 Settings 实例挂载到 request.state.config，
方便路由/下游中间件直接读取配置，无需重复调用 get_settings()。

#### class `ConfigMiddleware`

**继承**: `BaseHTTPMiddleware`

将配置注入到 request.state.config。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| dispatch | request, call_next | - |

---

### backend.middleware.error_handler

CityFlow 全局异常处理器。

注册到 FastAPI app 后，所有 CityFlowException 和未捕获异常
都会被统一拦截并返回标准化 JSON 响应。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| cityflow_exception_handler | request, exc | JSONResponse | 是 |
| general_exception_handler | request, exc | JSONResponse | 是 |
| setup_error_handlers | app | None | 否 |

---

### backend.middleware.locale

CityFlow 本地化中间件。

从请求的 Accept-Language 头解析语言偏好，设置当前请求的语言上下文，
并在响应中添加 Content-Language 头。

#### class `LocaleMiddleware`

**继承**: `BaseHTTPMiddleware`

本地化中间件。

处理流程：
1. 从 Accept-Language 请求头解析语言偏好
2. 将语言设置到 i18n 上下文（contextvars，异步安全）
3. 将语言注入 request.state.locale 供路由使用
4. 在响应头中添加 Content-Language

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| dispatch | request, call_next | Response |
| _parse_locale | accept_language | str |

---

### backend.middleware.performance

CityFlow 性能监控中间件。

为每个请求注入唯一 ID 和耗时信息，自动记录慢请求日志。
响应头中携带 ``X-Request-ID`` 和 ``X-Response-Time``，方便前端 / 网关追踪。

#### class `PerformanceMiddleware`

**继承**: `BaseHTTPMiddleware`

请求性能监控中间件。

功能：
1. 为每个请求生成唯一 ``X-Request-ID``（写入 request.state 和响应头）
2. 精确测量请求处理耗时（使用 ``time.perf_counter``）
3. 超过阈值的慢请求自动记录 WARNING 日志
4. 在响应头中注入性能指标，方便前端监控

Args:
    app: ASGI 应用。
    slow_threshold: 慢请求判定阈值（秒），默认 1.0。
    request_id_header: 自定义请求 ID 响应头名称，默认 ``X-Request-ID``。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | app, slow_threshold, request_id_header | None |
| dispatch | request, call_next | Response |

---

### backend.middleware.pipeline

CityFlow 中间件管道。

提供可编程的中间件链式执行引擎，支持：
- 动态添加/移除中间件
- 条件中间件（按请求特征决定是否执行）
- 每个中间件的性能统计（请求数、耗时、错误率、分位数）

#### class `MiddlewareHandler`

**继承**: `Protocol`

中间件处理函数签名。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __call__ | request, call_next | Response |

#### class `MiddlewareStats`

单个中间件的运行统计。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| avg_time | - | float |
| error_rate | - | float |
| percentile | p | float |
| to_dict | - | dict[str, Any] |

#### class `_MiddlewareEntry`

管道中的一个中间件条目。

#### class `MiddlewarePipeline`

可编程中间件管道。

中间件按添加顺序从外到内执行（即先添加的先执行）。
执行模型与 Starlette 的 ``add_middleware`` 一致：后添加的中间件
包裹先添加的中间件，形成洋葱模型。

用法::

    pipeline = MiddlewarePipeline()
    pipeline.add(my_auth_middleware, name="auth")
    pipeline.add(my_logging_middleware, name="logging")

    # 在 FastAPI 中使用
    @app.middleware("http")
    async def pipeline_dispatch(request: Request, call_next):
        return await pipeline.execute(request, call_next)

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | - | None |
| add | middleware, name | MiddlewarePipeline |
| remove | name | bool |
| names | - | list[str] |
| execute | request, call_next | Response |
| _record_stats | name, duration, success | None |
| get_stats | name | dict[str, Any] | None |
| get_all_stats | - | dict[str, dict[str, Any]] |
| reset_stats | - | None |
| get_stats_summary | - | dict[str, Any] |

#### class `ConditionalMiddleware`

条件中间件包装器。

根据请求特征决定是否执行内部中间件。
条件函数返回 True 时执行中间件，否则直接跳过。

用法::

    # 仅对 API 路径执行认证中间件
    auth_guard = ConditionalMiddleware(
        condition=lambda req: req.url.path.startswith("/api/"),
        middleware=auth_middleware,
    )
    pipeline.add(auth_guard, name="auth")

    # 按 HTTP 方法条件执行
    cache_mw = ConditionalMiddleware(
        condition=lambda req: req.method == "GET",
        middleware=cache_middleware,
    )
    pipeline.add(cache_mw, name="cache")

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | condition, middleware | None |
| __call__ | request, call_next | Response |

---

### backend.middleware.prometheus

Prometheus 指标采集中间件。

自动为每个 HTTP 请求记录计数和延迟，写入 Prometheus 指标。
``/metrics`` 端点自身不计入统计，避免递归干扰。

#### class `PrometheusMiddleware`

**继承**: `BaseHTTPMiddleware`

自动将每个 HTTP 请求的计数和延迟写入 Prometheus 指标。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| dispatch | request, call_next | Response |

---

### backend.middleware.rate_limit

速率限制中间件。

基于客户端 IP 的滑动窗口速率限制。使用内存存储，适合单实例部署。
如需多实例共享，应替换为 Redis 等外部存储。

#### class `RateLimitMiddleware`

**继承**: `BaseHTTPMiddleware`

滑动窗口速率限制。

Args:
    app: ASGI 应用。
    requests_per_minute: 每个 IP 每分钟允许的最大请求数。
    cleanup_interval: 清理过期记录的间隔（秒）。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | app, requests_per_minute, cleanup_interval | - |
| dispatch | request, call_next | - |
| _get_client_ip | request | str |
| _maybe_cleanup | now | None |

---

### backend.middleware.security

安全响应头中间件。

为所有 HTTP 响应注入标准安全头，防止常见浏览器端攻击。

#### class `SecurityHeadersMiddleware`

**继承**: `BaseHTTPMiddleware`

注入安全响应头。

适用于 API + 前端静态文件的混合服务场景。
如果仅提供纯 API 服务，可移除 X-Frame-Options 等与浏览器渲染相关的头。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| dispatch | request, call_next | - |

---

### backend.middleware.session

CityFlow 会话中间件。

自动为请求创建 / 注入会话，支持：
- Cookie 读取 session_id
- Header (X-Session-ID) 读取
- 无会话时自动创建
- 响应时设置 Cookie 和 Header

#### class `SessionMiddleware`

**继承**: `BaseHTTPMiddleware`

会话中间件：为每个请求注入 session_id。

优先级：Cookie > Header > 自动创建。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| dispatch | request, call_next | Response |

---

### backend.middleware.shutdown

CityFlow 停机感知中间件。

将每个 HTTP 请求的生命周期与 GracefulShutdown 管理器绑定：
- 请求进入时注册为活跃请求
- 请求结束时（无论成功/失败）注销
- 停机期间拒绝新请求，返回 503 Service Unavailable

使用方式::

    from backend.middleware.shutdown import ShutdownMiddleware

    app.add_middleware(ShutdownMiddleware)

#### class `ShutdownMiddleware`

**继承**: `BaseHTTPMiddleware`

停机感知中间件。

功能：
1. 为每个请求生成短 ID 并注册到停机管理器
2. 停机期间对新请求返回 503
3. 请求完成（成功或异常）后自动注销

在中间件链中的位置建议：靠近最外层，早于业务中间件，
以便尽早拒绝停机期间的请求。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| dispatch | request, call_next | Response |

---

### backend.middleware.validation

输入验证中间件。

在请求到达路由处理函数之前，对查询参数和请求体进行基本的安全检查。
这不是输入验证的唯一防线——路由层的 Pydantic 模型校验同样重要。

#### class `InputValidationMiddleware`

**继承**: `BaseHTTPMiddleware`

基本的注入 / XSS 检测中间件。

对查询参数和 JSON 请求体进行正则匹配，拦截明显的攻击模式。
不替代参数化查询或 Pydantic 校验，而是作为纵深防御的一层。

Args:
    app: ASGI 应用。
    max_body_size: 请求体最大字节数（默认 10 MB）。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | app, max_body_size | - |
| dispatch | request, call_next | - |
| _contains_dangerous | text | bool |

---

### backend.middleware.version

API 版本控制中间件。

#### class `APIVersionMiddleware`

**继承**: `BaseHTTPMiddleware`

API版本中间件。

支持两种版本控制方式：
1. URL路径版本控制（/api/v1/...、/api/v2/...）
2. 请求头版本控制（X-API-Version: v1）

优先级：URL路径 > 请求头 > 默认版本

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| dispatch | request, call_next | - |
| _extract_version_from_path | path | str | None |

---

### backend.middleware.__init__

CityFlow 中间件集合。

---

### backend.models.schemas

#### class `DataQuery`

**继承**: `BaseModel`

数据查询请求。

#### class `DataResponse`

**继承**: `BaseModel`

数据查询响应。

#### class `ChatRequest`

**继承**: `BaseModel`

LLM对话请求。

#### class `ChatResponse`

**继承**: `BaseModel`

LLM对话响应。

---

### backend.models.__init__

---

### backend.monitoring.error_filter

Sentry 事件过滤器。

在事件发送到 Sentry 之前进行过滤，减少噪音、降低成本。
过滤逻辑：
  - 静默 KeyboardInterrupt / SystemExit 等非业务异常
  - 静默速率限制等预期可恢复错误
  - 过滤健康检查等高频低价值事务
  - 脱敏请求头中的敏感信息

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| before_send | event, hint | dict[str, Any] | None | 否 |
| before_send_transaction | event, hint | dict[str, Any] | None | 否 |
| _sanitize_request_headers | event | None | 否 |

---

### backend.monitoring.metrics

Prometheus 指标定义与工具函数。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| track_request | method, endpoint, status, duration | None | 否 |
| track_route_planning | - | None | 否 |
| get_metrics | - | bytes | 否 |

---

### backend.monitoring.profiler

性能分析装饰器，自动将端点耗时记录到 Prometheus Histogram。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| profile_endpoint | endpoint | Callable[List(elts=[Subscript(value=Name(id='Callable', ctx=Load()), slice=Tuple(elts=[Constant(value=Ellipsis), Name(id='Any', ctx=Load())], ctx=Load()), ctx=Load())], ctx=Load()), Callable[Ellipsis, Any]] | 否 |

---

### backend.monitoring.sentry

Sentry 初始化与辅助函数。

使用方式：
    在应用启动时调用 init_sentry()，之后可直接使用
    capture_exception / capture_message 上报事件。

    环境变量：
      SENTRY_DSN      — Sentry DSN（为空则不初始化）
      ENVIRONMENT      — 环境名，默认 development
      APP_VERSION      — 应用版本号，默认 1.0.0

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| init_sentry | - | bool | 否 |
| capture_exception | error, context | str | None | 否 |
| capture_message | message, level, context | str | None | 否 |
| set_user_context | user_id, email, username | None | 否 |
| add_breadcrumb | message, category, level, data | None | 否 |
| _get_traces_sample_rate | environment | float | 否 |
| _get_profiles_sample_rate | environment | float | 否 |

---

### backend.monitoring.__init__

CityFlow 性能监控模块。

---

### backend.routers.audit

CityFlow 审计日志 API。

提供审计日志的查询和导出接口。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_audit_logs | user_id, action, resource_type, start_time, end_time, limit, offset | dict | 是 |
| export_audit_logs | format, start_time, end_time, limit | Response | 是 |
| get_audit_stats | start_time, end_time | dict | 是 |

---

### backend.routers.data

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_data | dataset, category | - | 是 |
| get_poi | city, category | - | 是 |
| get_datasets | - | - | 是 |
| get_order | city, category, day_of_year, hour | - | 是 |
| get_road_traffic | city, road_type, day_of_year, hour | - | 是 |

---

### backend.routers.graphql

CityFlow GraphQL 路由 -- 将 Strawberry GraphQL 挂载到 FastAPI。

---

### backend.routers.health

CityFlow 健康检查路由。

提供基础健康检查和详细健康状态端点，用于：
- 负载均衡器探活（Nginx health_check）
- Docker 容器健康检查（docker HEALTHCHECK）
- 运维监控（系统资源 + 依赖服务状态）

#### class `HealthResponse`

**继承**: `BaseModel`

基础健康检查响应。

#### class `SystemInfo`

**继承**: `BaseModel`

系统资源信息。

#### class `ServiceStatus`

**继承**: `BaseModel`

依赖服务状态。

#### class `DetailedHealthResponse`

**继承**: `BaseModel`

详细健康检查响应。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| health_check | - | dict | 是 |
| detailed_health | - | dict | 是 |
| _get_system_info | - | dict | 否 |
| _get_service_status | - | dict | 是 |
| _check_redis | - | str | 是 |
| _check_database | - | str | 是 |

---

### backend.routers.llm

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| chat | req | - | 是 |
| chat_stream | req | - | 是 |

---

### backend.routers.metrics

Prometheus 监控端点。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| metrics | - | Response | 是 |

---

### backend.routers.mq

CityFlow 消息队列 API。

提供消息发布、消费者管理、队列状态查询等接口。

#### class `PublishRequest`

**继承**: `BaseModel`

发布消息请求体。

#### class `PublishBatchRequest`

**继承**: `BaseModel`

批量发布请求体。

#### class `StartConsumerRequest`

**继承**: `BaseModel`

启动消费者请求体。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| publish_message | queue, body | dict[str, Any] | 是 |
| publish_batch | queue, body | dict[str, Any] | 是 |
| start_consumer | queue, body | dict[str, str] | 是 |
| queue_status | queue | dict[str, Any] | 是 |
| clear_queue | queue | dict[str, Any] | 是 |
| list_handlers | - | dict[str, list[str]] | 是 |

---

### backend.routers.poi

POI (兴趣点) 查询与距离计算接口。

#### class `SearchRequest`

**继承**: `BaseModel`

POI搜索请求体。

#### class `SearchResponse`

**继承**: `BaseModel`

POI搜索响应。

#### class `DistanceMatrixRequest`

**继承**: `BaseModel`

距离矩阵请求体。

#### class `DistanceItem`

**继承**: `BaseModel`

距离矩阵元素。

#### class `DistanceMatrixResponse`

**继承**: `BaseModel`

距离矩阵响应。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| load_pois | - | None | 否 |
| get_price_range | avg_price | str | 否 |
| enrich_poi | poi | dict | 否 |
| search_pois | request, lat, lng | - | 是 |
| get_poi_detail | poi_id, lat, lng | - | 是 |
| get_distance_matrix | request | - | 是 |

---

### backend.routers.registry

CityFlow 服务注册路由。

提供服务注册、注销、心跳和查询的 REST API。
其他微服务通过这些接口向注册中心报告自身状态。

#### class `RegistryMessage`

**继承**: `BaseModel`

注册中心通用响应。

#### class `ServiceListResponse`

**继承**: `BaseModel`

服务列表响应。

#### class `RegistryStatsResponse`

**继承**: `BaseModel`

注册中心统计。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| register_service | service | dict[str, str] | 是 |
| deregister_service | service_id | dict[str, str] | 是 |
| heartbeat | service_id | dict[str, str] | 是 |
| get_services | service_name | dict[str, Any] | 是 |
| discover_service | service_name | dict[str, Any] | 是 |
| get_stats | - | dict[str, int] | 是 |
| cleanup_unhealthy | service_name | dict[str, str] | 是 |

---

### backend.routers.session

CityFlow 会话 API。

提供会话的 CRUD 接口和统计查询。

#### class `CreateSessionRequest`

**继承**: `BaseModel`

创建会话请求。

#### class `UpdateSessionRequest`

**继承**: `BaseModel`

更新会话请求。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| create_session | body | dict[str, str] | 是 |
| get_session_stats | - | dict[str, int] | 是 |
| get_session | session_id | dict[str, Any] | 是 |
| update_session | session_id, body | dict[str, str] | 是 |
| delete_session | session_id | dict[str, str] | 是 |
| refresh_session | session_id | dict[str, str] | 是 |
| get_user_sessions | user_id | dict[str, Any] | 是 |

---

### backend.routers.tasks

CityFlow 后台任务 API。

提供任务提交、状态查询、取消、列表等接口。
通过函数白名单机制控制可执行的后台任务。

#### class `SubmitTaskRequest`

**继承**: `BaseModel`

提交任务请求体。

#### class `TaskResponse`

**继承**: `BaseModel`

任务状态响应。

#### class `TaskListResponse`

**继承**: `BaseModel`

任务列表响应。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| _resolve_function | func_name | Any | 否 |
| submit_task | func_name, request | - | 是 |
| get_task_status | task_id | - | 是 |
| cancel_task | task_id | - | 是 |
| list_tasks | status | - | 是 |

---

### backend.routers.websocket

CityFlow WebSocket 实时通信端点。

提供 WebSocket 连接入口，支持路线订阅、心跳检测等实时交互。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| websocket_endpoint | websocket, session_id | None | 是 |
| _handle_message | session_id, message | None | 是 |

---

### backend.routers.__init__

---

### backend.services.adaptive_rate_limiter

CityFlow 自适应限流器。

根据系统负载动态调整限流阈值：
- 负载低时放宽限制（提升用户体验）
- 负载高时收紧限制（保护系统稳定性）
- 支持多种负载信号：CPU、内存、响应时间、错误率

设计思路：
    系统负载 = w1*cpu + w2*memory + w3*error_rate + w4*latency
    限流倍率 = 1.0 - (负载 - threshold) * sensitivity
    最终限制 = 基础限制 * 限流倍率

用法::

    adaptive = get_adaptive_limiter()
    multiplier = adaptive.get_multiplier()
    # 将 multiplier 传给 UserRateLimiter / IPRateLimiter
    result = await user_limiter.check("user_123", "/api/v1/plan_route", multiplier)

#### class `LoadLevel`

**继承**: `str`, `Enum`

系统负载等级。

#### class `SystemMetrics`

系统运行时指标快照。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| load_score | - | float |
| level | - | LoadLevel |

#### class `MetricsCollector`

系统指标收集器。

通过 psutil 收集系统指标，如果 psutil 不可用则使用估算值。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | - | None |
| record_response | duration_ms, is_error | None |
| collect | - | SystemMetrics |
| reset | - | None |

#### class `AdaptiveRateLimiter`

自适应限流器。

根据系统负载动态计算限流倍率，供 UserRateLimiter / IPRateLimiter 使用。
支持手动覆盖和渐进式恢复。

参数:
    high_threshold: 触发收紧的负载分数阈值（默认 70）。
    critical_threshold: 触发紧急收紧的负载分数阈值（默认 90）。
    low_threshold: 触发放宽的负载分数阈值（默认 40）。
    recovery_factor: 从高负载恢复时的渐进因子（0-1，默认 0.1）。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | high_threshold, critical_threshold, low_threshold, recovery_factor | None |
| metrics | - | SystemMetrics |
| load_level | - | LoadLevel |
| get_multiplier | - | float |
| set_manual_multiplier | multiplier | None |
| record_response | duration_ms, is_error | None |
| start_monitoring | - | None |
| stop_monitoring | - | None |
| force_update | - | SystemMetrics |
| get_status | - | dict[str, Any] |
| _update_multiplier | - | None |
| _monitor_loop | - | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_adaptive_limiter | - | AdaptiveRateLimiter | 否 |

---

### backend.services.alert_notifier

CityFlow 告警通知器。

接收告警事件并分发到多个通知渠道：
- 日志记录（默认启用）
- WebSocket 广播（推送到前端仪表盘）
- 事件总线发布（供其他模块订阅）

使用示例::

    from backend.services.alert_notifier import get_alert_notifier

    notifier = get_alert_notifier()

    # 注册为资源监控回调
    from backend.services.resource_monitor import get_resource_monitor
    monitor = get_resource_monitor()
    monitor.add_callback(notifier.handle_alert_event)

    # 或者直接发送消息
    await notifier.send_warning("磁盘空间不足")

#### class `AlertNotifier`

告警通知器。

职责：
- 将告警事件记录到日志
- 通过事件总线发布，供 WebSocket 等模块订阅
- 提供便捷方法发送自定义告警消息

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | - | None |
| handle_alert | rule_name, current_value, threshold | None |
| handle_alert_event | event | None |
| send_info | message | None |
| send_warning | message | None |
| send_critical | message | None |
| notification_count | - | int |
| get_status | - | dict[str, Any] |
| _publish_event | event_type, data | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_alert_notifier | - | AlertNotifier | 否 |
| reset_alert_notifier | - | None | 否 |

---

### backend.services.audit_logger

CityFlow 审计日志服务。

提供审计日志的记录、查询和导出功能。
使用缓冲写入减少数据库压力，支持 JSON 和 CSV 导出。

#### class `AuditAction`

**继承**: `str`, `Enum`

审计动作类型。

#### class `AuditLogger`

审计日志记录器。

使用内存缓冲区批量写入数据库，减少 I/O 压力。
缓冲区满或手动调用 flush 时写入数据库。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | buffer_size | None |
| log | user_id, action, resource_type, resource_id, details, ip_address, user_agent | None |
| flush | - | None |
| query | user_id, action, resource_type, start_time, end_time, limit, offset | list[dict[str, Any]] |
| count | user_id, action, resource_type, start_time, end_time | int |
| export_json | start_time, end_time, limit | str |
| export_csv | start_time, end_time, limit | str |
| _to_dict | log | dict[str, Any] |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_audit_logger | - | AuditLogger | 否 |
| audit_log | action, resource_type | - | 否 |

---

### backend.services.auto_recovery

CityFlow 自动恢复模块。

当健康检查发现服务异常时，自动执行恢复动作：
- 指数退避重试
- 冷却期控制，避免短时间内反复恢复
- 恢复历史记录，用于故障分析
- 与 HealthChecker 联动，自动响应异常

用法：
    recovery = AutoRecovery()
    recovery.register("database", recover_database)
    recovery.register("redis", recover_redis)

    # 配合 HealthChecker 自动触发
    health_checker.set_on_unhealthy(recovery.handle_unhealthy)

    # 或手动触发
    success = await recovery.attempt("database")

#### class `RecoveryStatus`

**继承**: `str`, `Enum`

恢复尝试结果状态。

#### class `RecoveryAttempt`

单次恢复尝试的记录。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | service, status, attempt, error, latency_ms | None |
| to_dict | - | dict[str, Any] |

#### class `RecoveryResult`

一组恢复尝试的汇总结果。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | attempts | None |
| to_dict | - | dict[str, Any] |

#### class `AutoRecovery`

自动恢复器。

Args:
    max_retries: 每个服务的最大连续重试次数，超过后停止尝试。
    base_delay: 重试基础延迟秒数，实际延迟 = base_delay * 2^attempt。
    max_delay: 重试延迟上限秒数。
    cooldown: 恢复成功后的冷却期秒数，期间不再重试。
    history_size: 保留最近多少条恢复记录。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | max_retries, base_delay, max_delay, cooldown, history_size | None |
| register | service, action | None |
| unregister | service | None |
| attempt | service | RecoveryAttempt |
| attempt_many | services | RecoveryResult |
| handle_unhealthy | report | RecoveryResult |
| reset_retry_count | service | None |
| reset_all | - | None |
| get_retry_count | service | int |
| history | - | list[RecoveryAttempt] |
| get_service_history | service | list[RecoveryAttempt] |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| recover_database | - | None | 是 |
| recover_redis | - | None | 是 |
| recover_llm_service | - | None | 是 |
| get_auto_recovery | - | AutoRecovery | 否 |

---

### backend.services.backup

CityFlow 数据备份服务。

提供自动备份、版本管理、备份恢复三大能力：

- **自动备份**：定时或手动创建数据快照，包含数据文件 + 配置文件 + 元数据。
- **版本管理**：每次备份生成时间戳版本，支持列出、清理旧版本。
- **备份恢复**：从指定版本恢复数据，带完整性校验。

使用方式::

    from backend.services.backup import get_backup

    backup = get_backup()

    # 创建备份
    name = await backup.create_backup()

    # 列出备份
    backups = await backup.list_backups()

    # 恢复备份
    ok = await backup.restore_backup(name)

    # 清理旧版本（默认保留 10 个）
    await backup.cleanup_old_backups(keep_count=5)

#### class `BackupError`

**继承**: `CityFlowException`

备份操作失败。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | message, details | None |

#### class `BackupNotFoundError`

**继承**: `CityFlowException`

指定备份不存在。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | backup_name, details | None |

#### class `DataBackup`

数据备份管理器。

Args:
    backup_dir: 备份存储根目录。
    data_dir: 需要备份的数据目录。
    keep_count: 自动清理时保留的备份数量。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | backup_dir, data_dir, keep_count | None |
| create_backup | name | str |
| _create_backup_sync | name | str |
| restore_backup | backup_name | bool |
| _restore_backup_sync | backup_name | bool |
| list_backups | - | list[dict[str, object]] |
| _list_backups_sync | - | list[dict[str, object]] |
| cleanup_old_backups | keep_count | int |
| _cleanup_old_backups_sync | keep_count | int |
| delete_backup | backup_name | bool |
| _delete_backup_sync | backup_name | bool |
| _compute_checksum | path | str |
| _read_checksum | backup_name | str | None |
| _dir_size | path | int |
| backup_dir | - | Path |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_backup | - | DataBackup | 否 |
| reset_backup | - | None | 否 |

---

### backend.services.cache

CityFlow 多级缓存模块。

提供三级缓存架构：
- L1: 内存缓存（MemoryCache）-- 同步，进程内，毫秒级
- L2: Redis 缓存（RedisCache）-- 异步，跨进程，亚毫秒级
- 组合层: MultiLevelCache -- L1 + L2 联合读写

同时保留原有全局缓存实例和装饰器，向后兼容。

#### class `MemoryCache`

线程安全的内存缓存，支持 TTL 过期和容量上限。

淘汰策略：TTL 过期优先，满时按 LRU 淘汰（最近最少访问）。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | max_size, ttl_seconds | None |
| get | key | Any | None |
| set | key, value | None |
| delete | key | None |
| clear | - | None |
| _evict_one | - | None |
| size | - | int |
| stats | - | dict[str, int | float] |

#### class `RedisCache`

基于 Redis 的异步缓存，支持 TTL 和按前缀批量清除。

所有键自动添加 ``cityflow:`` 前缀以避免命名冲突。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | redis_url | None |
| connect | - | None |
| get | key | Any | None |
| set | key, value, ttl | None |
| delete | key | None |
| clear_pattern | pattern | int |
| close | - | None |
| is_connected | - | bool |

#### class `MultiLevelCache`

多级缓存：L1（内存） + L2（Redis）。

读取策略：L1 命中直接返回 -> L2 命中回填 L1 -> 都未命中返回 None
写入策略：同时写入 L1 和 L2
删除策略：同时删除 L1 和 L2

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | l1, l2 | None |
| get | key | Any | None |
| set | key, value, ttl | None |
| delete | key | None |
| clear_l2_pattern | pattern | int |
| invalidate | prefix | dict[str, int] |
| stats | - | dict[str, Any] |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_multilevel_cache | - | MultiLevelCache | 否 |
| init_multilevel_cache | - | None | 是 |
| close_multilevel_cache | - | None | 是 |
| cache_key | - | str | 否 |
| cached | cache, prefix, key_builder, ttl | Callable | 否 |
| invalidate | cache, prefix | int | 否 |

---

### backend.services.cache_warmup

CityFlow 缓存预热模块。

在应用启动时将热点数据加载到缓存中，减少冷启动时的延迟抖动。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| warmup_multilevel_cache | - | None | 是 |
| warmup_memory_caches | pois | None | 否 |
| schedule_cache_refresh | interval_seconds | None | 是 |

---

### backend.services.circuit_breaker

CityFlow 熔断器模块。

实现三态熔断器（CLOSED / OPEN / HALF_OPEN），用于保护外部服务调用。
提供同步/异步装饰器和手动控制两种使用方式。

状态机：
    CLOSED  --(失败次数 >= 阈值)--> OPEN
    OPEN    --(恢复超时)----------> HALF_OPEN
    HALF_OPEN --(调用成功)--------> CLOSED
    HALF_OPEN --(调用失败)--------> OPEN

#### class `CircuitBreakerOpenError`

**继承**: `CityFlowException`

熔断器处于打开状态时抛出。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | message, details | None |

#### class `CircuitState`

**继承**: `str`, `Enum`

熔断器三态。

#### class `CircuitBreakerMetrics`

熔断器指标收集器。

默认使用简单的内存计数器。如果 prometheus_client 可用，
会自动注册 Prometheus 指标，可在 /metrics 端点暴露。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | name | None |
| record_success | - | None |
| record_failure | - | None |
| record_rejected | - | None |
| record_state_change | - | None |
| as_dict | - | dict[str, int] |

#### class `CircuitBreaker`

三态熔断器。

Args:
    failure_threshold: 连续失败次数阈值，达到后进入 OPEN 状态。
    recovery_timeout: OPEN 状态持续多少秒后进入 HALF_OPEN。
    expected_exception: 哪些异常算"失败"，默认所有 Exception。
    name: 熔断器名称，用于日志和指标。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | failure_threshold, recovery_timeout, expected_exception, name | None |
| state | - | CircuitState |
| metrics | - | CircuitBreakerMetrics |
| failure_count | - | int |
| _transition | new_state | None |
| record_success | - | None |
| record_failure | - | None |
| reject_if_open | - | None |
| reset | - | None |
| trip | - | None |
| __call__ | func | F |
| __repr__ | - | str |

---

### backend.services.config_hot_reload

CityFlow 配置热更新。

基于 watchdog 监听配置文件变更，支持：
- .env / .yaml / .json 文件变更检测
- 变更回调注册与自动触发
- 配置快照与回滚（最多保留 N 个历史版本）
- 防抖处理（避免编辑器保存产生多次事件）

#### class `ConfigReloadError`

**继承**: `Exception`

配置热更新相关错误。

#### class `ConfigSnapshot`

配置快照，用于回滚。

#### class `_DebounceState`

防抖状态追踪。

#### class `_ConfigFileHandler`

**继承**: `FileSystemEventHandler`

watchdog 文件事件处理器，桥接到 asyncio 回调。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | loop, callback, watched_extensions | None |
| on_modified | event | None |
| on_created | event | None |
| _schedule_callback | file_path | None |
| _run_callback | file_path, state | None |

#### class `ConfigHotReloader`

配置热更新器。

Args:
    config_dir: 要监听的配置文件目录。
    max_snapshots: 每个文件保留的最大快照数（用于回滚）。
    watched_extensions: 要监听的文件后缀集合，默认 .env/.yaml/.yml/.json。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | config_dir, max_snapshots, watched_extensions | None |
| start | - | None |
| stop | - | None |
| is_running | - | bool |
| register_handler | config_type, handler | None |
| unregister_handler | config_type | None |
| _on_config_change | file_path | None |
| _detect_config_type | path | str |
| _save_snapshot | file_path | None |
| rollback | file_path, steps | bool |
| get_snapshot_history | file_path | list[ConfigSnapshot] |
| get_latest_snapshot | file_path | ConfigSnapshot | None |
| clear_snapshots | file_path | None |
| __enter__ | - | ConfigHotReloader |
| __exit__ | - | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_config_reloader | - | ConfigHotReloader | 否 |

---

### backend.services.config_watcher

CityFlow 配置变更监视器。

监视 Settings 中的关键字段，当值发生变化时触发已注册的回调。
与 config_hot_reload 配合使用：hot_reload 负责文件监听，
config_watcher 负责语义层面的配置变更检测与通知。

典型用法：
    watcher = ConfigWatcher()
    watcher.watch("log_level", on_log_level_change)
    watcher.watch("rate_limit", on_rate_limit_change)

    # 在定时任务或热更新回调中调用
    await watcher.check_changes()

#### class `ConfigDiff`

单条配置变更记录。

#### class `ConfigWatcher`

配置变更监视器。

通过轮询 Settings 实例检测字段变化，
并调用已注册的异步回调通知下游。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | settings | None |
| watch | key, callback | None |
| unwatch | key | None |
| watched_keys | - | list[str] |
| check_changes | - | list[ConfigDiff] |
| change_log | - | list[ConfigDiff] |
| clear_change_log | - | None |
| refresh_snapshot | - | None |
| _take_snapshot | - | None |
| _read_current_values | - | dict[str, Any] |
| _resolve_key | key | Any |
| _trim_change_log | - | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| log_level_change_callback | key, old_value, new_value | None | 是 |
| rate_limit_change_callback | key, old_value, new_value | None | 是 |
| create_default_watcher | settings | ConfigWatcher | 否 |

---

### backend.services.data_check

POI 数据完整性验证脚本。

验证 backend/data/city_poi_db.json 中每条 POI 记录的字段存在性、类型和取值范围。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| validate_poi | poi | tuple[bool, list[str]] | 否 |
| _validate_emotion_tags | tags, errors | None | 否 |
| _validate_constraints | constraints, errors | None | 否 |
| validate_all_pois | - | dict[str, object] | 否 |
| main | - | None | 否 |

---

### backend.services.data_service

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| load_data | - | None | 否 |
| get_data | dataset, filters | Any | 否 |
| get_datasets | - | list[str] | 否 |

---

### backend.services.dialogue

CityFlow 多轮对话引擎。

支持用户对已规划路线进行调整，包括：
- 替换指令：换掉某个景点
- 节奏调整：太赶了/想轻松点
- 预算调整：太贵了/便宜一点
- 时间调整：早一点/晚一点
- 不满反馈：重新来/再想一个

#### class `DialogueState`

单个对话会话的状态管理。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | session_id, initial_route, user_intent | None |
| add_message | role, content | None |
| is_expired | - | bool |

#### class `DialogueEngine`

对话引擎：管理会话生命周期，分发指令到对应处理器。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | - | None |
| create_session | session_id, route, user_intent | DialogueState |
| get_session | session_id | DialogueState | None |
| remove_session | session_id | None |
| process_instruction | session_id, instruction | dict[str, Any] |
| _classify_instruction | instruction | str |
| _handle_replace | state, instruction | dict[str, Any] |
| _extract_poi_name | instruction, route | str | None |
| _pick_best_replacement | original, candidates | dict[str, Any] |
| _deep_copy_route | route | dict[str, Any] |
| _handle_pace | state, instruction | dict[str, Any] |
| _handle_budget | state, instruction | dict[str, Any] |
| _handle_time | state, instruction | dict[str, Any] |
| _handle_retry | state, instruction | dict[str, Any] |
| _collect_all_candidates | state | list[dict[str, Any]] |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| create_dialogue | session_id, route, user_intent | dict[str, str] | 是 |
| process_dialogue | session_id, instruction | dict[str, Any] | 是 |

---

### backend.services.discovery

CityFlow 服务发现客户端。

提供服务发现功能，支持从本地注册中心或远程注册中心获取服务实例。
支持负载均衡和故障转移。

使用方式::

    discovery = get_service_discovery()
    service_url = await discovery.discover("user-service")
    if service_url:
        # 使用 service_url 调用服务
        pass

#### class `ServiceDiscovery`

服务发现客户端。

优先从本地注册中心获取服务实例，若本地无可用实例
则尝试从远程注册中心获取。

Args:
    registry_url: 远程注册中心的 URL，为 None 时仅使用本地注册中心。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | registry_url | None |
| discover | service_name | str | None |
| _discover_remote | service_name | str | None |
| get_service_url | service_name | str |

#### class `ServiceNotFoundError`

**继承**: `Exception`

服务未找到异常。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | service_name | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_service_discovery | - | ServiceDiscovery | 否 |

---

### backend.services.emotion

CityFlow 情绪评分公共模块。

提供主导情绪判断、情绪兼容性评分、情绪曲线计算等函数，
消除 narrator.py / filters.py 中的重复实现。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_dominant_emotion | emotion_tags | str | 否 |
| emotion_compatibility | poi_a, poi_b | float | 否 |
| emotion_compatibility_with_consecutive | pois | float | 否 |
| calculate_emotion_curve | route | list[dict[str, Any]] | 否 |
| fatigue_penalty | step_count, consecutive_pois | float | 否 |

---

### backend.services.event_bus

CityFlow 事件总线。

提供同步/异步的事件发布-订阅机制，支持：
- 按事件类型注册/注销处理器
- 同步事件发布（阻塞式逐个调用）
- 异步事件发布（并发执行，异常隔离）
- 全局单例访问

使用示例::

    from backend.services.event_bus import get_event_bus, Event

    bus = get_event_bus()
    bus.subscribe("route.planned", my_handler)
    bus.publish(Event(event_type="route.planned", data={"route_id": "123"}))

#### class `Event`

事件基类。

所有事件的通用载体，包含事件类型、负载数据、时间戳和来源。

Attributes:
    event_type: 事件类型标识，如 ``"route.planned"``
    data: 事件负载数据
    timestamp: 事件发生时间（UTC），默认自动填充
    source: 事件来源标识，如模块名或服务名

#### class `EventBus`

事件总线。

维护同步和异步两套订阅者列表，发布时分别按同步阻塞 /
异步并发方式调用所有已注册的处理器。单个处理器异常不会
影响其他处理器的执行。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | - | None |
| subscribe | event_type, handler | None |
| subscribe_async | event_type, handler | None |
| unsubscribe | event_type, handler | None |
| publish | event | None |
| publish_async | event | None |
| get_subscribers | event_type | list[Callable[Ellipsis, Any]] |
| event_types | - | list[str] |
| clear | - | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_event_bus | - | EventBus | 否 |
| reset_event_bus | - | None | 否 |

---

### backend.services.fallback

CityFlow 降级策略模块。

当主函数执行失败时，自动切换到预定义的降级函数返回兜底结果。
保证用户始终能拿到一个有效响应，而不是看到错误页。

用法：
    @fallback(fallback_route_planning)
    async def plan_route(...):
        ...

    # 配合熔断器和重试使用
    @retry(max_retries=2)
    @fallback(fallback_route_planning, exceptions=(CircuitBreakerOpenError,))
    @llm_circuit_breaker
    async def plan_route(...):
        ...

#### class `FallbackError`

**继承**: `Exception`

降级函数本身也失败时抛出。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| fallback | fallback_func, exceptions | Callable[List(elts=[Name(id='F', ctx=Load())], ctx=Load()), F] | 否 |
| fallback_route_planning | - | dict[str, Any] | 是 |
| fallback_poi_search | - | dict[str, Any] | 是 |
| fallback_narrative_generation | - | dict[str, Any] | 是 |
| fallback_llm_chat | - | str | 是 |
| fallback_emotion_analysis | - | dict[str, float] | 是 |

---

### backend.services.filters

CityFlow POI过滤模块。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| _parse_queue_tolerance | hard_constraints | int | None | 否 |
| _need_accessible | hard_constraints | bool | 否 |
| _need_pet_friendly | hard_constraints | bool | 否 |
| filter_candidates | pois, user_intent | list[dict[str, Any]] | 否 |

---

### backend.services.geo

CityFlow 地理计算公共模块。

提供 haversine 距离计算、道路距离估算、旅行时间估算等函数，
消除 solver.py / poi.py / vectorized.py 中的重复实现。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| haversine | lat1, lon1, lat2, lon2 | float | 否 |
| haversine_with_road_factor | lat1, lon1, lat2, lon2, factor | float | 否 |
| estimate_travel_time | distance_m, speed_kmh | float | 否 |
| poi_distance | poi_a, poi_b | float | 否 |
| poi_travel_time | poi_a, poi_b | float | 否 |
| cache_key_distance | poi_a, poi_b | str | 否 |
| cache_key_travel_time | poi_a, poi_b | str | 否 |

---

### backend.services.graceful_shutdown

CityFlow 优雅停机管理器。

提供三阶段停机流程：
1. 信号捕获 -- 拦截 SIGINT/SIGTERM，触发停机事件
2. 请求排空 -- 等待正在处理的请求完成（带超时）
3. 资源清理 -- 按依赖顺序关闭数据库连接池、Redis、消息队列等

使用方式::

    from backend.services.graceful_shutdown import get_shutdown_manager

    manager = get_shutdown_manager()

    # 在中间件中注册请求
    manager.request_started(request_id)
    try:
        response = await handle(request)
    finally:
        manager.request_finished(request_id)

    # 在 startup 中注册信号
    manager.register_signal_handlers()

    # 在 shutdown 回调中执行清理
    await manager.shutdown()

#### class `ShutdownStats`

停机统计信息。

#### class `GracefulShutdown`

优雅停机管理器。

职责：
- 管理停机信号的捕获与分发
- 跟踪活跃请求并在停机时等待排空
- 按注册顺序依次执行资源清理回调

Attributes:
    shutdown_timeout: 请求排空超时时间（秒），超时后强制关闭。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | shutdown_timeout | None |
| is_shutting_down | - | bool |
| wait_for_shutdown | - | None |
| request_started | request_id | None |
| request_finished | request_id | None |
| active_request_count | - | int |
| register_cleanup | name, callback | None |
| register_signal_handlers | - | None |
| _handle_signal | sig | None |
| shutdown | - | ShutdownStats |
| _drain_requests | - | None |
| _wait_until_idle | - | None |
| _run_cleanup | - | None |
| get_stats | - | dict[str, Any] |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_shutdown_manager | - | GracefulShutdown | 否 |
| reset_shutdown_manager | - | None | 否 |

---

### backend.services.health_checker

CityFlow 健康检查模块。

提供可扩展的健康检查框架，支持：
- 注册自定义检查函数（数据库、Redis、LLM 等）
- 周期性后台监控，自动检测服务异常
- 检查结果历史记录，用于趋势分析
- 与 auto_recovery 联动，异常时自动触发恢复

用法：
    checker = HealthChecker()
    checker.register("database", check_database)
    checker.register("redis", check_redis)

    # 后台启动
    await checker.start(interval=30)

    # 或手动触发
    results = await checker.run_all()

#### class `CheckStatus`

**继承**: `str`, `Enum`

单次检查结果状态。

#### class `CheckResult`

单个检查项的结果。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | name, status, latency_ms, error, details | None |
| to_dict | - | dict[str, Any] |

#### class `HealthReport`

一次完整健康检查的汇总报告。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | results, duration_ms | None |
| _compute_overall | - | CheckStatus |
| to_dict | - | dict[str, Any] |
| unhealthy_names | - | list[str] |

#### class `HealthChecker`

可扩展的健康检查器。

Args:
    history_size: 保留最近多少次检查报告。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | history_size | None |
| register | name, check_func | None |
| unregister | name | None |
| set_on_unhealthy | callback | None |
| run_check | name | CheckResult |
| run_all | - | HealthReport |
| start | interval | None |
| _monitor_loop | interval | None |
| stop | - | None |
| latest | - | HealthReport | None |
| history | - | list[HealthReport] |
| get_check_names | - | list[str] |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| check_database | - | CheckResult | 是 |
| check_redis | - | CheckResult | 是 |
| check_llm_service | - | CheckResult | 是 |
| get_health_checker | - | HealthChecker | 否 |

---

### backend.services.http_pool

CityFlow HTTP 连接池。

基于 httpx.AsyncClient 的连接池，提供：
- 可配置的最大连接数与 keep-alive 连接数
- 全生命周期管理（启动 / 关闭）
- GET / POST / PUT / PATCH / DELETE 等便捷方法
- 连接池统计信息

替代项目中散落的 ``async with httpx.AsyncClient(...) as client`` 临时连接，
复用底层 TCP 连接以降低延迟。

#### class `HTTPPoolStats`

HTTP 连接池统计快照。

#### class `HTTPPool`

HTTP 连接池。

Args:
    max_connections: 最大并发连接数。
    max_keepalive_connections: 最大 keep-alive 连接数。
    timeout: 默认请求超时（秒）。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| start | - | None |
| close | - | None |
| request | method, url | httpx.Response |
| get | url | httpx.Response |
| post | url | httpx.Response |
| put | url | httpx.Response |
| patch | url | httpx.Response |
| delete | url | httpx.Response |
| get_stats | - | HTTPPoolStats |
| get_stats_dict | - | dict[str, Any] |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_http_pool | - | HTTPPool | 否 |

---

### backend.services.intent_parser

CityFlow LLM 意图解析模块
将用户自然语言输入解析为结构化出行需求，并匹配用户画像。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| _get_client | - | AsyncOpenAI | 否 |
| _call_llm | user_input | dict | None | 是 |
| _rule_based_parse | user_input | dict | 否 |
| _match_profile | intent, available_profiles | str | 否 |
| parse_intent | user_input, available_profiles | dict | 是 |

---

### backend.services.ip_rate_limiter

CityFlow IP 级限流器。

在 middleware/rate_limit.py（全局入口 IP 限流）基础上，提供可编程的
IP 限流服务，支持：
- 按 IP + 端点维度限流
- 自动 / 手动 IP 封禁
- 可疑行为检测（短时间内大量不同端点访问）
- Redis 分布式 / 本地内存双模式

用法::

    limiter = get_ip_rate_limiter()
    result = await limiter.check("1.2.3.4", "/api/v1/plan_route")
    if not result.allowed:
        raise RateLimitExceededError(details=result.to_headers())

#### class `IPRateLimitExceededError`

**继承**: `CityFlowException`

IP 速率限制超出。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | message, details | None |

#### class `IPRateLimitResult`

IP 限流检查结果。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| to_headers | - | dict[str, str] |

#### class `_LocalWindow`

本地固定窗口计数器。

#### class `_LocalIPRateLimiter`

本地内存 IP 限流器。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | - | None |
| check | key, limit, window | tuple[bool, int, int] |
| is_banned | ip | bool |
| ban_ip | ip, duration | None |
| unban_ip | ip | None |
| track_endpoint | ip, endpoint | bool |
| cleanup | max_idle_seconds | int |

#### class `_RedisIPRateLimiter`

基于 Redis 的 IP 限流器。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | redis_client | None |
| check | key, limit, window | tuple[bool, int, int] |
| is_banned | ip | bool |
| ban_ip | ip, duration | None |
| unban_ip | ip | None |
| track_endpoint | ip, endpoint | bool |

#### class `IPRateLimiter`

IP 级速率限制器。

提供三层保护：
1. 单端点限流：每个 IP 对每个端点的请求频率限制
2. 全局限流：每个 IP 所有端点的总请求频率限制
3. 可疑行为检测：短时间内大量不同端点访问 -> 自动封禁

用法::

    limiter = IPRateLimiter(redis_client)
    result = await limiter.check("1.2.3.4", "/api/v1/plan_route")

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | redis_client, endpoint_limit, endpoint_window, global_limit, global_window, ban_duration | None |
| check | ip, endpoint, endpoint_limit, global_limit | IPRateLimitResult |
| manual_ban | ip, duration | None |
| manual_unban | ip | None |
| is_banned | ip | bool |
| backend_type | - | str |
| cleanup_local | - | int |
| _check_banned | ip | bool |
| _ban | ip, duration | None |
| _track_and_detect | ip, endpoint | bool |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_ip_rate_limiter | - | IPRateLimiter | 否 |

---

### backend.services.llm_service

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_client | - | AsyncOpenAI | 否 |
| chat_stream | message, model, system_prompt | AsyncIterator[str] | 是 |
| chat | message, model | str | 是 |

---

### backend.services.logger

CityFlow 结构化日志模块。

提供 JSON 格式的结构化日志输出，支持控制台和文件两种处理器。
所有服务模块统一通过 get_logger() 获取日志器。

#### class `JSONFormatter`

**继承**: `logging.Formatter`

将日志记录格式化为 JSON 字符串。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| format | record | str |

#### class `RequestLogger`

请求级日志记录器，封装常用的业务日志方法。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | logger | None |
| log_request | method, path, status_code, duration, user_id, session_id | None |
| log_route_planning | user_input, user_type, poi_count, duration | None |
| log_error | error, context | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| setup_logging | level | None | 否 |
| get_logger | name | logging.Logger | 否 |

---

### backend.services.log_rotation

CityFlow 日志轮转配置。

提供两种轮转策略：
- 按大小轮转：单文件 10MB，保留 5 个备份
- 按时间轮转：每天午夜轮转，保留 30 天

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| setup_log_rotation | - | tuple[RotatingFileHandler, TimedRotatingFileHandler] | 否 |

---

### backend.services.message_handlers

CityFlow 消息处理器。

注册各类业务消息的处理逻辑，供 MessageQueue 消费端调用。
处理器签名统一为 `async def handler(payload: dict) -> None`。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| handle_route_planning | payload | None | 是 |
| handle_notification | payload | None | 是 |
| handle_analytics | payload | None | 是 |
| get_handler | name | MessageHandler | None | 否 |
| start_default_consumers | - | None | 是 |

---

### backend.services.message_queue

CityFlow Redis 消息队列。

基于 Redis List 实现的生产者/消费者模型，支持：
- 多队列隔离（queue 前缀分组）
- 多消费者并发
- 优雅启停
- 全局单例访问

#### class `Message`

消息信封，封装元数据 + 业务载荷。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | queue, payload | None |
| to_json | - | str |
| from_json | data | Message |

#### class `MessageQueue`

基于 Redis List 的消息队列。

Args:
    redis_url: Redis 连接 URL，默认从配置读取。
    prefix: 所有队列键的前缀，避免 key 冲突。
    max_retries: 单条消息最大重试次数。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | redis_url, prefix, max_retries | None |
| _build_redis_url | - | str |
| _key | queue | str |
| publish | queue, payload | Message |
| publish_many | queue, payloads | list[Message] |
| consume | queue, handler | None |
| start_consumer | queue, handler | asyncio.Task |
| stop | - | None |
| queue_length | queue | int |
| clear_queue | queue | int |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_message_queue | - | MessageQueue | 否 |
| close_message_queue | - | None | 是 |

---

### backend.services.metrics

CityFlow 应用指标收集模块

提供 Prometheus 格式的指标收集，包括：
- HTTP 请求计数与延迟
- 活跃会话数
- 路线规划统计
- POI 查询统计

#### class `MetricsMiddleware`

指标收集中间件

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | app | - |
| __call__ | scope, receive, send | - |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| track_route_planning | user_type | - | 否 |
| track_poi_query | - | - | 否 |
| get_metrics | - | - | 否 |

---

### backend.services.narrator

CityFlow 路线文案引擎。

将求解器输出的路线数据转换为用户友好的文案描述。
模板驱动 + LLM 局部润色。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| _generate_opening | user_intent | str | 否 |
| _generate_step | step | str | 否 |
| _generate_closing | route_result | str | 否 |
| _extract_emotion_highlights | route_result | list[dict[str, str]] | 否 |
| _llm_polish | text, context | str | 是 |
| generate_narrative | route_result, user_intent | dict[str, Any] | 是 |

---

### backend.services.notification

CityFlow 消息推送服务。

提供路线更新、步骤变更、错误通知等实时推送能力，
供其他业务模块调用，将变更实时推送给已订阅的客户端。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| notify_route_update | route_id, update_type, data | None | 是 |
| notify_new_step | route_id, step | None | 是 |
| notify_route_complete | route_id, route | None | 是 |
| notify_route_adjusted | route_id, changes | None | 是 |
| notify_error | session_id, error | None | 是 |
| notify_personal | session_id, message | None | 是 |
| broadcast_system_message | text | None | 是 |

---

### backend.services.parallel

CityFlow 异步并行处理模块。

提供并行过滤、并行求解等并发工具。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| parallel_filter | items, filter_func, max_workers | list[T] | 是 |
| parallel_solve | solve_func, n_attempts | dict[str, Any] | 是 |
| parallel_map | items, func, max_workers | list[Any] | 是 |
| with_timeout | coro, timeout_seconds, fallback | T | None | 是 |

---

### backend.services.pool_monitor

CityFlow 连接池监控。

聚合数据库连接池与 HTTP 连接池的统计信息，提供：
- 统一的统计查询接口
- 健康检查
- 告警阈值检测（连接池使用率过高）

#### class `PoolHealthReport`

连接池健康报告。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| all_healthy | - | bool |

#### class `PoolMonitor`

连接池监控器。

Args:
    db_pool: 数据库连接池实例。
    http_pool: HTTP 连接池实例。
    utilization_warn_threshold: 使用率告警阈值（0.0 ~ 1.0）。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | db_pool, http_pool, utilization_warn_threshold | None |
| get_stats | - | dict[str, Any] |
| check_health | - | PoolHealthReport |
| report | - | dict[str, Any] |
| _collect_warnings | db_stats | list[str] |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_pool_monitor | - | PoolMonitor | 否 |

---

### backend.services.quota

CityFlow 用户配额管理服务。

提供基于 Redis 的用户配额管理，支持：
- 按用户 / 操作类型 / 时间周期的配额限制
- 配额查询与使用量递增（原子操作）
- 多周期（小时级 / 日级）同时生效
- 超额抛出统一异常

用法::

    quota = get_quota_manager()
    info = await quota.check_and_consume("user:123", "route_planning")
    if not info.within_quota:
        raise QuotaExceededError(...)

#### class `QuotaPeriod`

**继承**: `str`, `Enum`

配额统计周期。

#### class `QuotaExceededError`

**继承**: `CityFlowException`

用户配额超出限制。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | message, details | None |

#### class `QuotaInfo`

单个周期的配额信息。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| within_quota | - | bool |

#### class `QuotaCheckResult`

配额检查综合结果，包含所有周期信息。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| within_quota | - | bool |
| exceeded_periods | - | list[QuotaPeriod] |
| to_dict | - | dict[str, Any] |

#### class `QuotaManager`

用户配额管理器。

使用 Redis INCR + EXPIRE 实现原子性的配额计数。
支持同时检查多个周期（如 hourly + daily），全部通过才算在配额内。

Args:
    redis_client: Redis 异步客户端，为 None 时所有检查默认放行。
    quota_limits: 配额上限配置，默认使用模块级 ``QUOTA_LIMITS``。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | redis_client, quota_limits | None |
| get_usage | user_id, quota_type | QuotaCheckResult |
| check_and_consume | user_id, quota_type, amount | QuotaCheckResult |
| reset | user_id, quota_type, period | int |
| _make_key | user_id, quota_type, period | str |
| _get_count | user_id, quota_type, period | int |
| _increment | user_id, quota_type, period, amount | int |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_quota_manager | - | QuotaManager | 否 |

---

### backend.services.rate_limiter

CityFlow 速率限制器服务。

提供灵活的速率限制功能，支持：
- Redis 分布式滑动窗口（多实例共享）
- 本地内存固定窗口（单实例降级）
- 按用户 ID / IP / API Key 等维度限流
- 标准 RateLimit 响应头注入

与 middleware/rate_limit.py 的区别：
- middleware 层：基于 IP 的简单滑动窗口，保护全局入口
- service 层：可编程的限流器，支持自定义 key / limit / window，
  可在路由层或业务层按需调用

#### class `RateLimitExceededError`

**继承**: `CityFlowException`

速率限制超出。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | message, details | None |

#### class `RateLimitResult`

速率限制检查结果。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| to_headers | - | dict[str, str] |

#### class `_LocalWindow`

本地固定窗口计数器。

#### class `_LocalRateLimiter`

本地内存固定窗口限流器，单实例降级方案。

不支持跨进程共享，适合开发环境或 Redis 不可用时。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | - | None |
| check | key, limit, window | RateLimitResult |
| cleanup | max_idle_seconds | int |

#### class `_RedisRateLimiter`

基于 Redis Sorted Set 的滑动窗口限流器。

使用 ZREMRANGEBYSCORE + ZCARD + EXPIRE 的 pipeline 实现，
原子性强，支持多实例共享。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | redis_client | None |
| check | key, limit, window | RateLimitResult |

#### class `RateLimiter`

速率限制器统一入口。

优先使用 Redis 实现分布式限流；Redis 不可用时自动降级到本地内存。

用法::

    limiter = get_rate_limiter()
    result = await limiter.is_allowed("user:123", limit=60, window=60)
    if not result.allowed:
        raise RateLimitExceededError(details=result.to_headers())

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | redis_client | None |
| is_allowed | key, limit, window | RateLimitResult |
| backend_type | - | str |
| cleanup_local | - | int |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_rate_limiter | - | RateLimiter | 否 |

---

### backend.services.registry

CityFlow 服务注册中心。

提供服务实例的注册、注销、心跳和健康检查功能。
支持基于心跳超时的自动健康检测和随机负载均衡。

使用方式::

    registry = get_service_registry()
    await registry.start()

    # 注册
    service = ServiceInfo(...)
    await registry.register(service)

    # 发现
    svc = await registry.get_service("my-service")

#### class `ServiceInfo`

**继承**: `BaseModel`

服务实例信息。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| to_dict | - | dict[str, Any] |

#### class `ServiceRegistry`

服务注册中心。

管理所有已注册服务实例，周期性检查心跳超时，
自动将超时实例标记为 unhealthy。

Args:
    heartbeat_timeout: 心跳超时秒数，超过此时间未收到心跳则标记为不健康。
    health_check_interval: 健康检查周期（秒）。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | heartbeat_timeout, health_check_interval | None |
| register | service | None |
| deregister | service_id | bool |
| heartbeat | service_id | bool |
| get_service | service_name | ServiceInfo | None |
| get_all_services | service_name | list[ServiceInfo] |
| _check_health_loop | - | None |
| remove_unhealthy | service_name | int |
| start | - | None |
| stop | - | None |
| service_count | - | int |
| healthy_count | - | int |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_service_registry | - | ServiceRegistry | 否 |

---

### backend.services.resilient_service

CityFlow 弹性服务集成模块。

将熔断器、重试、降级策略应用到 CityFlow 的核心服务调用上。
这是实际对接业务的地方，不是示例。

设计原则：
    - 外部依赖（LLM、高德API）必须有容错
    - 内部计算（solver、narrator）不需要熔断，但可以加重试
    - 降级结果必须标记 fallback=True，前端据此提示用户

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| chat_with_resilience | message, model | str | 是 |
| plan_route_with_resilience | candidates, user_intent, start_time | dict[str, Any] | 是 |
| generate_narrative_with_resilience | route_result, user_intent | dict[str, Any] | 是 |
| get_all_circuit_breakers | - | dict[str, dict[str, Any]] | 否 |

---

### backend.services.resource_monitor

CityFlow 系统资源监控器。

提供系统级资源指标采集与告警规则引擎，包括：
- CPU / 内存 / 磁盘 / 网络指标采集
- 可配置的告警规则（阈值比较）
- 告警回调通知（异步）
- 告警冷却期（防止同一规则短时间内重复触发）

使用示例::

    from backend.services.resource_monitor import get_resource_monitor

    monitor = get_resource_monitor()
    monitor.add_rule("high_cpu", "cpu_percent", threshold=80.0)
    await monitor.start_monitoring(interval=30)

停机时调用 ``await monitor.stop_monitoring()`` 或依赖
``GracefulShutdown`` 注册的清理回调自动停止。

#### class `AlertSeverity`

**继承**: `StrEnum`

告警严重程度。

#### class `ComparisonOperator`

**继承**: `StrEnum`

阈值比较运算符。

#### class `ResourceMetrics`

系统资源快照。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| to_dict | - | dict[str, Any] |

#### class `AlertRule`

告警规则。

Attributes:
    name: 规则唯一名称，如 ``"high_cpu"``
    metric: 对应 ``ResourceMetrics`` 的字段名
    threshold: 阈值
    operator: 比较运算符，默认 ``>``（当前值大于阈值时触发）
    severity: 告警严重程度
    cooldown_seconds: 冷却期（秒），同一规则在此时间内不重复触发

#### class `AlertEvent`

告警事件。

Attributes:
    rule_name: 触发的规则名称
    metric: 指标字段名
    current_value: 当前指标值
    threshold: 阈值
    severity: 严重程度
    message: 告警消息
    timestamp: 触发时间

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| to_dict | - | dict[str, Any] |

#### class `ResourceMonitor`

系统资源监控器。

职责：
- 定期采集系统资源指标
- 按配置的告警规则评估指标
- 触发告警回调（日志 + 自定义通知）

Args:
    disk_path: 磁盘采集路径。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | disk_path | None |
| add_rule | rule | None |
| remove_rule | name | bool |
| get_rules | - | list[AlertRule] |
| add_callback | callback | None |
| start_monitoring | interval | None |
| stop_monitoring | - | None |
| is_running | - | bool |
| latest_metrics | - | ResourceMetrics | None |
| get_current_metrics | - | ResourceMetrics |
| _monitor_loop | interval | None |
| _evaluate_rules | metrics | None |
| _fire_alert | rule, current_value | None |
| get_status | - | dict[str, Any] |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| collect_metrics | disk_path | ResourceMetrics | 否 |
| _load_default_rules | monitor | None | 否 |
| get_resource_monitor | - | ResourceMonitor | 否 |
| reset_resource_monitor | - | None | 否 |

---

### backend.services.retry

CityFlow 重试机制模块。

提供指数退避重试装饰器，支持：
- 可配置最大重试次数、初始延迟、退避倍数
- 可配置触发重试的异常类型
- 可配置最大延迟上限（防止退避时间过长）
- 同步/异步函数通用
- 每次重试前可执行自定义回调

用法：
    @retry(max_retries=3, delay=1.0, backoff=2.0)
    async def call_api(url: str) -> dict:
        ...

    # 只对特定异常重试
    @retry(max_retries=2, exceptions=(TimeoutError, ConnectionError))
    async def call_external_service():
        ...

#### class `RetryExhaustedError`

**继承**: `Exception`

所有重试用尽后抛出，保留最后一次异常。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | message, last_exception, attempts | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| retry | max_retries, delay, backoff, max_delay, jitter, exceptions, on_retry | Callable[List(elts=[Name(id='F', ctx=Load())], ctx=Load()), F] | 否 |

---

### backend.services.scheduled_backup

CityFlow 定时备份调度器。

在后台按固定间隔自动创建备份并清理旧版本。
通过 asyncio.Task 实现，支持优雅取消。

使用方式::

    from backend.services.scheduled_backup import get_scheduled_backup

    scheduler = get_scheduled_backup()

    # 启动（通常在 app startup 中调用）
    await scheduler.start()

    # 停止（通常在 app shutdown 中调用）
    await scheduler.stop()

#### class `ScheduledBackup`

定时备份调度器。

通过 asyncio.Task 在后台循环执行备份任务。
两次备份之间通过 asyncio.sleep 等待，可被 cancel 安全中断。

Args:
    interval_hours: 备份间隔（小时），默认 24。
    keep_count: 每次备份后保留的版本数量，默认 10。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | interval_hours, keep_count | None |
| start | - | None |
| stop | - | None |
| is_running | - | bool |
| run_now | - | str | None |
| _run_loop | - | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_scheduled_backup | - | ScheduledBackup | 否 |
| reset_scheduled_backup | - | None | 否 |

---

### backend.services.session

CityFlow 分布式会话管理。

基于 Redis 的会话存储，支持：
- 会话创建 / 读取 / 更新 / 删除
- 自动 TTL 过期
- 用户维度会话查询
- 过期会话清理统计

#### class `SessionManager`

基于 Redis 的会话管理器。

会话数据结构：
{
    "session_id": "uuid",
    "user_id": "optional-user-id",
    "created_at": "ISO-8601",
    "last_active": "ISO-8601",
    "data": {}
}

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | redis_url, prefix, default_ttl | None |
| connect | - | None |
| close | - | None |
| _key | session_id | str |
| _ensure_connected | - | aioredis.Redis |
| create_session | user_id | str |
| get_session | session_id | dict[str, Any] | None |
| update_session | session_id, data | bool |
| delete_session | session_id | bool |
| refresh_session | session_id | bool |
| get_user_sessions | user_id | list[dict[str, Any]] |
| get_stats | - | dict[str, int] |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_session_manager | - | SessionManager | 否 |

---

### backend.services.solver

CityFlow TSPTW 情绪混合求解器。

5阶段求解：
1. TW-Nearest Neighbor 贪心初始化（含时间窗可行性剪枝）
2. 2-opt 局部搜索改进
3. 呼吸空间插入（高兴奋POI之间插入休息节点）
4. 高潮收尾检查（确保最后一个POI情绪足够高）
5. 输出组装

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| estimate_distance | poi_a, poi_b | float | 否 |
| estimate_travel_time | poi_a, poi_b | float | 否 |
| estimate_steps | poi | int | 否 |
| _check_time_windows | route | bool | 否 |
| _recalculate_times | route, start_time | list[dict[str, Any]] | 否 |
| _evaluate_route | route, user_intent | float | 否 |
| _phase1_initialize | candidates, user_intent, start_time | list[dict[str, Any]] | 否 |
| _phase2_improve | route, user_intent, start_time, max_iterations | list[dict[str, Any]] | 否 |
| _find_rest_poi | candidates, used_ids | dict[str, Any] | None | 否 |
| _insert_rest_at | route, insert_pos, rest_poi | None | 否 |
| _phase3_breathing | route, candidates, user_intent | tuple[list[dict[str, Any]], list[dict[str, Any]]] | 否 |
| _phase4_finale | route, candidates | list[dict[str, Any]] | 否 |
| _phase5_assemble | route, candidates, breathing_spots | dict[str, Any] | 否 |
| solve_route | candidates, user_intent, start_time | dict[str, Any] | 否 |

---

### backend.services.task_queue

CityFlow 异步任务队列。

基于 asyncio.Queue 实现的内存任务队列，支持：
- 多 worker 并发执行
- 任务状态追踪（pending / running / completed / failed / cancelled）
- 任务取消
- 全局单例访问

#### class `TaskStatus`

**继承**: `str`, `Enum`

任务生命周期状态。

#### class `Task`

单个任务的状态容器。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | task_id, func, args, kwargs | None |
| to_dict | - | dict[str, Any] |

#### class `TaskQueue`

基于 asyncio.Queue 的内存任务队列。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | max_workers | None |
| start | - | None |
| stop | - | None |
| submit | func | str |
| get_task | task_id | Optional[Task] |
| cancel_task | task_id | bool |
| list_tasks | status | list[dict[str, Any]] |
| _worker | name | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_task_queue | - | TaskQueue | 否 |

---

### backend.services.template_engine

CityFlow Jinja2 模板引擎。

提供模板渲染、缓存、自定义过滤器/全局变量等功能。
模板编译结果缓存在内存中，避免重复编译开销。

#### class `TemplateRenderError`

**继承**: `CityFlowException`

模板渲染失败。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | message, details | None |

#### class `TemplateCache`

编译模板的 TTL + LRU 内存缓存。

缓存键为模板内容的 SHA256 哈希，值为编译后的 Template 对象。
文件模板以文件路径 + mtime 为键，字符串模板以内容哈希为键。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | max_size, ttl_seconds | None |
| hits | - | int |
| misses | - | int |
| size | - | int |
| get | key | Template | None |
| set | key, template | None |
| invalidate | key | bool |
| clear | - | None |

#### class `TemplateEngine`

Jinja2 模板引擎，带编译缓存。

Args:
    template_dir: 模板文件目录，默认 ``templates``。
    cache_max_size: 缓存最大条目数。
    cache_ttl: 缓存条目 TTL（秒）。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | template_dir, cache_max_size, cache_ttl | None |
| cache | - | TemplateCache |
| string_cache | - | TemplateCache |
| template_dir | - | Path |
| render | template_name, context | str |
| render_string | template_string, context | str |
| _get_file_template | template_name | Template |
| _get_string_template | template_string | Template |
| add_filter | name, func | None |
| add_global | name, value | None |
| invalidate_cache | - | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_template_engine | - | TemplateEngine | 否 |
| reset_template_engine | - | None | 否 |
| render_template | template_name, context | str | 否 |
| render_string | template_string, context | str | 否 |
| invalidate_template_cache | - | None | 否 |

---

### backend.services.time_utils

CityFlow 时间处理公共模块。

提供时间解析、格式化、营业时间解析等函数，
消除 solver.py / dialogue.py / filters.py 中的重复实现。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| parse_time | time_str | datetime | 否 |
| format_time | dt | str | 否 |
| add_minutes | time_str, minutes | str | 否 |
| time_difference | time1, time2 | int | 否 |
| is_time_in_range | time_str, start, end | bool | 否 |
| parse_opening_hours | hours_str | tuple[str, str] | 否 |
| get_poi_opening_hours | poi | tuple[datetime, datetime] | 否 |
| parse_time_window | time_info | tuple[int, int] | 否 |
| parse_hours_to_minutes | hours_str | tuple[int, int] | 否 |

---

### backend.services.user_profiles

CityFlow 用户画像定义模块
定义20组典型用户画像，用于意图匹配和路线推荐。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| _cosine_similarity | vec_a, vec_b | float | 否 |
| match_profile | intent | str | 否 |
| _infer_budget_level | budget | str | 否 |
| get_profile_by_id | profile_id | dict[str, Any] | None | 否 |
| get_all_profile_ids | - | list[str] | 否 |
| get_profiles_by_group_type | group_type | dict[str, dict[str, Any]] | 否 |

---

### backend.services.user_rate_limiter

CityFlow 用户级限流器。

在通用 RateLimiter 基础上增加：
- 按用户 ID + 端点维度限流
- 端点级自定义配额（如路线规划 10次/分钟，POI搜索 100次/分钟）
- 白名单 / VIP 用户倍率
- 与 Redis 分布式 / 本地内存双模式兼容

用法::

    limiter = get_user_rate_limiter()
    result = await limiter.check("user_abc", "/api/v1/plan_route")
    if not result.allowed:
        raise RateLimitExceededError(details=result.to_headers())

#### class `EndpointTier`

**继承**: `str`, `Enum`

端点配额等级，用于统一管理不同端点的限流策略。

#### class `UserRateLimitExceededError`

**继承**: `CityFlowException`

用户速率限制超出。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | message, details | None |

#### class `UserRateLimitResult`

用户限流检查结果。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| to_headers | - | dict[str, str] |

#### class `_LocalWindow`

本地固定窗口计数器。

#### class `_LocalUserRateLimiter`

本地内存用户限流器。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | - | None |
| check | key, limit, window | tuple[bool, int, int] |
| cleanup | max_idle_seconds | int |

#### class `_RedisUserRateLimiter`

基于 Redis Sorted Set 的用户限流器。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | redis_client | None |
| check | key, limit, window | tuple[bool, int, int] |

#### class `UserRateLimiter`

用户级速率限制器。

自动根据端点路径匹配配额等级，支持白名单用户豁免。
优先使用 Redis 分布式模式，Redis 不可用时降级到本地内存。

用法::

    limiter = UserRateLimiter(redis_client)
    result = await limiter.check("user_123", "/api/v1/plan_route")

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | redis_client | None |
| check | user_id, endpoint, multiplier | UserRateLimitResult |
| check_with_tier | user_id, endpoint, tier, multiplier | UserRateLimitResult |
| backend_type | - | str |
| cleanup_local | - | int |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| register_whitelist_user | user_id | None | 否 |
| remove_whitelist_user | user_id | None | 否 |
| resolve_endpoint_tier | endpoint | EndpointTier | 否 |
| get_user_rate_limiter | - | UserRateLimiter | 否 |

---

### backend.services.vectorized

CityFlow 向量化距离计算模块。

用 numpy 批量计算 haversine 距离矩阵，比逐对循环快 10-100 倍。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| haversine_vectorized | lat1, lon1, lat2, lon2 | NDArray[np.floating[Any]] | 否 |
| distance_matrix_vectorized | pois, road_factor | NDArray[np.floating[Any]] | 否 |
| travel_time_matrix_vectorized | pois, speed_kmh, road_factor | NDArray[np.floating[Any]] | 否 |
| distance_from_point_vectorized | lat, lng, pois, road_factor | NDArray[np.floating[Any]] | 否 |
| emotion_score_vectorized | pois, preferences | float | 否 |
| haversine_scalar | lat1, lon1, lat2, lon2 | float | 否 |

---

### backend.services.websocket

CityFlow WebSocket 连接管理器。

提供 WebSocket 连接生命周期管理、路线订阅机制和消息广播能力。

#### class `ConnectionManager`

WebSocket 连接管理器。

职责：
- 管理活跃 WebSocket 连接的生命周期
- 维护路线订阅关系（一个连接可订阅多条路线）
- 提供点对点、路线组播和全局广播三种消息推送方式

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | - | None |
| connect | websocket, session_id | None |
| disconnect | session_id | None |
| subscribe | session_id, route_id | None |
| unsubscribe | session_id, route_id | None |
| send_personal_message | session_id, message | None |
| broadcast_to_route | route_id, message | None |
| broadcast_all | message | None |
| get_connection_count | - | int |
| get_subscription_count | - | int |
| get_subscribers | route_id | Set[str] |
| is_connected | session_id | bool |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_websocket_manager | - | ConnectionManager | 否 |

---

### backend.services.__init__

---

### backend.tests.test_adaptive_rate_limiter

自适应限流器单元测试。

#### class `TestSystemMetrics`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_load_score_low | - | None |
| test_load_score_normal | - | None |
| test_load_score_high | - | None |
| test_load_score_critical | - | None |
| test_latency_factor_capped_at_1s | - | None |
| test_zero_metrics | - | None |

#### class `TestMetricsCollector`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_collect_returns_metrics | - | None |
| test_record_response_tracks_latency | - | None |
| test_record_response_tracks_errors | - | None |
| test_reset_clears_state | - | None |
| test_sliding_window_limit | - | None |

#### class `TestAdaptiveRateLimiter`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_default_multiplier_is_one | - | None |
| test_manual_multiplier_override | - | None |
| test_force_update_changes_multiplier_for_high_load | - | None |
| test_force_update_increases_multiplier_for_low_load | - | None |
| test_multiplier_clamped_to_range | - | None |
| test_record_response_updates_metrics | - | None |
| test_get_status_returns_dict | - | None |
| test_get_status_manual_mode | - | None |
| test_start_and_stop_monitoring | - | None |
| test_start_monitoring_idempotent | - | None |
| test_load_level_property | - | None |

#### class `TestGetAdaptiveLimiter`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_singleton | - | None |

---

### backend.tests.test_alert_notifier

告警通知器单元测试。

#### class `TestAlertNotifierHandleAlert`

测试 handle_alert 方法（三参数签名）。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_handle_alert_increments_count | - | None |
| test_handle_alert_publishes_event | - | None |

#### class `TestAlertNotifierHandleAlertEvent`

测试 handle_alert_event 方法（AlertEvent 对象签名）。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_handle_alert_event_increments_count | - | None |
| test_handle_critical_event_uses_critical_log | - | None |

#### class `TestConvenienceMethods`

测试 send_info / send_warning / send_critical。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_send_info | - | None |
| test_send_warning | - | None |
| test_send_critical | - | None |

#### class `TestPublishEvent`

测试事件总线发布集成。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_publish_event_calls_event_bus | - | None |
| test_publish_event_exception_does_not_raise | - | None |

#### class `TestGetStatus`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_initial_status | - | None |

#### class `TestAlertNotifierSingleton`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_singleton | - | None |
| test_reset_creates_new | - | None |

---

### backend.tests.test_audit_logger

审计日志服务单元测试。

#### class `TestAuditAction`

审计动作枚举测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_action_values | - | None |
| test_action_is_string_enum | - | None |

#### class `TestAuditLogger`

审计日志记录器测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_init_default_buffer_size | - | None |
| test_init_custom_buffer_size | - | None |
| test_log_adds_to_buffer | - | None |
| test_log_with_details | - | None |
| test_log_with_ip_and_user_agent | - | None |
| test_log_flushes_when_buffer_full | - | None |
| test_flush_clears_buffer | - | None |
| test_flush_noop_when_empty | - | None |
| test_query_calls_flush_first | - | None |
| test_export_json_format | - | None |
| test_export_csv_format | - | None |
| test_export_csv_empty | - | None |
| test_to_dict | - | None |

#### class `TestGetAuditLogger`

全局单例测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_returns_same_instance | - | None |
| test_returns_audit_logger_instance | - | None |

#### class `TestAuditLogDecorator`

审计日志装饰器测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_decorator_records_log | - | None |
| test_decorator_preserves_function_name | - | None |

---

### backend.tests.test_auto_recovery

自动恢复模块单元测试。

#### class `TestRecoveryAttempt`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_to_dict | - | None |
| test_to_dict_with_error | - | None |

#### class `TestRecoveryResult`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_all_succeeded_true | - | None |
| test_all_succeeded_false | - | None |
| test_empty_is_success | - | None |
| test_to_dict | - | None |

#### class `TestAutoRecovery`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_no_action_for_unregistered | - | None |
| test_success_on_first_try | - | None |
| test_failure_increments_retry | - | None |
| test_max_retries_skips | - | None |
| test_cooldown_skips | - | None |
| test_success_resets_retry_count | - | None |
| test_attempt_many_parallel | - | None |
| test_attempt_many_empty | - | None |
| test_attempt_many_partial_failure | - | None |
| test_handle_unhealthy | - | None |
| test_handle_unhealthy_no_registered | - | None |
| test_history_recorded | - | None |
| test_get_service_history | - | None |
| test_reset_retry_count | - | None |
| test_reset_all | - | None |
| test_unregister | - | None |

#### class `TestExponentialBackoff`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_delay_increases | - | None |

---

### backend.tests.test_backup

备份服务测试。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| backup_dir | tmp_path | Path | 否 |
| data_dir | tmp_path | Path | 否 |
| config_file | tmp_path | Path | 否 |
| backup | backup_dir, data_dir | DataBackup | 否 |
| test_create_backup_default_name | backup | None | 是 |
| test_create_backup_custom_name | backup | None | 是 |
| test_create_backup_creates_files | backup, backup_dir | None | 是 |
| test_create_backup_metadata_content | backup | None | 是 |
| test_create_backup_checksum_is_stable | backup, backup_dir | None | 是 |
| test_restore_backup | backup, data_dir | None | 是 |
| test_restore_nonexistent_backup | backup | None | 是 |
| test_restore_detects_corruption | backup, backup_dir | None | 是 |
| test_list_backups_empty | backup | None | 是 |
| test_list_backups_sorted | backup | None | 是 |
| test_cleanup_old_backups | backup | None | 是 |
| test_cleanup_nothing_to_remove | backup | None | 是 |
| test_delete_backup | backup | None | 是 |
| test_delete_nonexistent | backup | None | 是 |
| test_backup_includes_config | tmp_path, data_dir, config_file | None | 是 |
| test_get_backup_singleton | - | None | 否 |

---

### backend.tests.test_circuit_breaker

熔断器单元测试。

#### class `TestCircuitState`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_initial_state_is_closed | - | None |
| test_stays_closed_below_threshold | - | None |
| test_opens_at_threshold | - | None |
| test_open_to_half_open_after_timeout | - | None |
| test_half_open_success_closes | - | None |
| test_half_open_failure_reopens | - | None |
| test_success_resets_failure_count | - | None |

#### class `TestCircuitBreakerDecorator`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_passes_through_when_closed | - | None |
| test_records_failure_on_exception | - | None |
| test_rejects_when_open | - | None |
| test_only_catches_expected_exceptions | - | None |
| test_sync_function_support | - | None |

#### class `TestCircuitBreakerManualControl`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_reset | - | None |
| test_trip | - | None |
| test_reject_if_open | - | None |
| test_reject_if_open_noop_when_closed | - | None |

#### class `TestCircuitBreakerMetrics`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_tracks_counts | - | None |
| test_tracks_rejected | - | None |

---

### backend.tests.test_code_generator

CityFlow 代码生成器测试。

#### class `TestHelpers`

内部辅助函数测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_capitalize_snake_case | - | None |
| test_capitalize_kebab_case | - | None |
| test_capitalize_single_word | - | None |
| test_resolve_type_known | - | None |
| test_resolve_type_unknown | - | None |

#### class `TestGenerateApiEndpoint`

API 端点生成测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| generator | - | CodeGenerator |
| sample_fields | - | list[dict] |
| test_contains_router_definition | generator, sample_fields | None |
| test_contains_crud_endpoints | generator, sample_fields | None |
| test_contains_request_models | generator, sample_fields | None |
| test_optional_field_handling | generator, sample_fields | None |
| test_custom_prefix | generator, sample_fields | None |
| test_custom_tag | generator, sample_fields | None |

#### class `TestGenerateModel`

数据模型生成测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| generator | - | CodeGenerator |
| sample_fields | - | list[dict] |
| test_contains_model_class | generator, sample_fields | None |
| test_contains_id_field | generator, sample_fields | None |
| test_contains_timestamps_by_default | generator, sample_fields | None |
| test_exclude_timestamps | generator, sample_fields | None |
| test_custom_description | generator, sample_fields | None |

#### class `TestGenerateService`

服务类生成测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| generator | - | CodeGenerator |
| test_contains_service_class | generator | None |
| test_contains_crud_methods | generator | None |
| test_contains_singleton_getter | generator | None |
| test_database_mode | generator | None |
| test_non_database_mode | generator | None |

#### class `TestGenerateTest`

测试文件生成测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| generator | - | CodeGenerator |
| sample_fields | - | list[dict] |
| test_contains_test_class | generator, sample_fields | None |
| test_contains_crud_tests | generator, sample_fields | None |

#### class `TestSaveFile`

文件保存测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_save_creates_file | tmp_path | None |
| test_save_creates_parent_dirs | tmp_path | None |
| test_save_returns_absolute_path | tmp_path | None |

#### class `TestGenerateFull`

一次性生成全部文件测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| generator | - | CodeGenerator |
| sample_fields | - | list[dict] |
| test_returns_four_keys | generator, sample_fields | None |
| test_save_creates_all_files | tmp_path, sample_fields | None |

#### class `TestCLI`

CLI 入口测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_main_with_save | tmp_path, monkeypatch | None |

---

### backend.tests.test_errors

CityFlow 统一错误处理机制测试。

#### class `TestErrorCode`

错误码枚举测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_error_code_values_unique | - | - |
| test_error_code_ranges | - | - |

#### class `TestCityFlowException`

基础异常测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_basic_creation | - | - |
| test_with_details | - | - |
| test_custom_status_code | - | - |
| test_to_dict_basic | - | - |
| test_to_dict_with_details | - | - |
| test_is_exception | - | - |
| test_str_representation | - | - |

#### class `TestExceptionSubclasses`

异常子类默认值测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_intent_parse_error | - | - |
| test_no_pois_found_error | - | - |
| test_route_solving_error | - | - |
| test_narrative_generation_error | - | - |
| test_dialogue_error | - | - |
| test_llm_service_error | - | - |
| test_rate_limit_error | - | - |
| test_custom_message | - | - |
| test_custom_details | - | - |

#### class `TestGlobalErrorHandlers`

FastAPI 全局异常处理器测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| app | - | - |
| client | app | - |
| test_cityflow_exception_returns_json | client | - |
| test_intent_parse_error_status | client | - |
| test_llm_service_error_status | client | - |
| test_dialogue_error_status | client | - |
| test_no_pois_error_status | client | - |
| test_rate_limit_error_status | client | - |
| test_generic_error_returns_500 | client | - |
| test_error_response_format_consistency | client | - |

#### class `TestHandleErrorsDecorator`

handle_errors 装饰器测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_passes_through_cityflow_exception | - | - |
| test_wraps_generic_exception | - | - |
| test_success_passes_through | - | - |

#### class `TestHandleLLMErrorsDecorator`

handle_llm_errors 装饰器测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_timeout_error | - | - |
| test_generic_error | - | - |
| test_passes_through_cityflow_exception | - | - |
| test_success_passes_through | - | - |

---

### backend.tests.test_fallback

降级策略单元测试。

#### class `TestFallbackDecorator`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_no_fallback_on_success | - | None |
| test_fallback_on_exception | - | None |
| test_only_catches_specified_exceptions | - | None |
| test_fallback_receives_original_args | - | None |
| test_fallback_failure_raises | - | None |
| test_sync_function_support | - | None |

#### class `TestPredefinedFallbacks`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_fallback_route_planning_shape | - | None |
| test_fallback_poi_search_shape | - | None |
| test_fallback_narrative_generation_shape | - | None |
| test_fallback_llm_chat_returns_string | - | None |
| test_fallback_emotion_analysis_shape | - | None |

---

### backend.tests.test_health_checker

健康检查模块单元测试。

#### class `TestCheckResult`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_to_dict | - | None |
| test_to_dict_with_error | - | None |
| test_to_dict_excludes_none_fields | - | None |

#### class `TestHealthReport`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_overall_healthy_when_all_ok | - | None |
| test_overall_degraded | - | None |
| test_overall_unhealthy_on_error | - | None |
| test_overall_unhealthy_on_unhealthy | - | None |
| test_overall_healthy_when_empty | - | None |
| test_unhealthy_names | - | None |
| test_to_dict | - | None |

#### class `TestHealthChecker`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_run_all_empty | - | None |
| test_run_check_registered | - | None |
| test_run_check_unregistered | - | None |
| test_run_check_returns_false | - | None |
| test_run_check_exception | - | None |
| test_run_check_returns_check_result | - | None |
| test_run_all_aggregates | - | None |
| test_history_recorded | - | None |
| test_history_size_limit | - | None |
| test_unregister | - | None |
| test_on_unhealthy_callback | - | None |
| test_on_unhealthy_not_called_when_healthy | - | None |
| test_start_stop | - | None |
| test_start_idempotent | - | None |

---

### backend.tests.test_i18n

i18n 模块测试。

#### class `TestTranslate`

翻译功能测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_simple_key | i18n | None |
| test_nested_key | i18n | None |
| test_missing_key_returns_key | i18n | None |
| test_intermediate_key_returns_key | i18n | None |
| test_format_params | i18n | None |
| test_format_missing_param_returns_template | i18n | None |

#### class `TestLocaleSwitching`

语言切换测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_default_locale | i18n | None |
| test_switch_to_en | i18n | None |
| test_switch_back | i18n | None |
| test_invalid_locale_raises | i18n | None |
| test_get_available_locales | i18n | None |

#### class `TestEdgeCases`

边界情况测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_empty_locale_dir | tmp_path | None |
| test_nonexistent_locale_dir | tmp_path | None |
| test_malformed_json_skipped | tmp_path | None |

#### class `TestGlobalShortcut`

全局 t() 快捷函数测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_t_function | locale_dir, monkeypatch | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| locale_dir | tmp_path | Path | 否 |
| i18n | locale_dir | I18n | 否 |

---

### backend.tests.test_ip_rate_limiter

IP 限流器单元测试。

#### class `TestIPRateLimitResult`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_to_headers_basic | - | None |
| test_to_headers_with_ban | - | None |

#### class `TestLocalIPRateLimiter`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_allows_first_request | - | None |
| test_blocks_after_limit | - | None |
| test_ban_and_unban | - | None |
| test_ban_expires | - | None |
| test_track_endpoint_detects_suspicious | - | None |
| test_different_keys_independent | - | None |

#### class `TestIPRateLimiterLocal`

本地模式集成测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_backend_type_is_local | - | None |
| test_check_allows_within_limit | - | None |
| test_check_blocks_after_endpoint_limit | - | None |
| test_check_blocks_after_global_limit | - | None |
| test_manual_ban_blocks_requests | - | None |
| test_manual_unban_restores_access | - | None |
| test_is_banned | - | None |
| test_custom_limit_override | - | None |
| test_suspicious_flag_on_result | - | None |
| test_result_fields | - | None |

#### class `TestIPRateLimitExceededError`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_default_message | - | None |
| test_custom_details | - | None |

---

### backend.tests.test_locale_middleware

CityFlow 本地化中间件测试。

#### class `TestParseLocale`

Accept-Language 解析测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_empty_string | - | None |
| test_simple_en | - | None |
| test_simple_zh | - | None |
| test_en_us_full | - | None |
| test_zh_cn_full | - | None |
| test_en_gb | - | None |
| test_zh_tw | - | None |
| test_zh_hk | - | None |
| test_quality_values | - | None |
| test_quality_values_en_first | - | None |
| test_multiple_with_defaults | - | None |
| test_unknown_locale_fallback | - | None |
| test_prefix_matching | - | None |

#### class `TestLocaleMiddlewareIntegration`

中间件集成测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_default_locale_is_zh_cn | client | None |
| test_accept_language_en | client | None |
| test_accept_language_zh | client | None |
| test_content_language_header_present | client | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| app | - | FastAPI | 否 |
| client | app | TestClient | 否 |

---

### backend.tests.test_localized_response

CityFlow 本地化响应测试。

#### class `TestSuccess`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_default_message | - | None |
| test_custom_key | - | None |
| test_en_locale | - | None |

#### class `TestError`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_default_message | - | None |
| test_custom_key | - | None |
| test_en_locale | - | None |

#### class `TestData`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_basic_data | - | None |
| test_list_data | - | None |
| test_none_data | - | None |
| test_en_locale | - | None |

#### class `TestPaginated`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_basic_paginated | - | None |
| test_exact_page_count | - | None |
| test_single_page | - | None |
| test_zero_total | - | None |
| test_en_locale | - | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| _reset_locale | - | None | 否 |

---

### backend.tests.test_pool

连接池管理单元测试。

覆盖：
- DatabasePool 生命周期与统计
- HTTPPool 生命周期与统计
- PoolMonitor 健康检查与报告

#### class `TestPoolStats`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_utilization_normal | - | None |
| test_utilization_zero_pool | - | None |
| test_utilization_full | - | None |
| test_utilization_with_overflow | - | None |

#### class `TestDatabasePool`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| pool | - | DatabasePool |
| test_initial_state | pool | None |
| test_start_idempotent | pool | None |
| test_close_without_start | pool | None |
| test_close_disposes_engine | pool | None |
| test_get_session_yields_session | pool | None |
| test_get_session_rollback_on_error | pool | None |
| test_ping_success | pool | None |
| test_ping_failure | pool | None |
| test_ping_before_start | pool | None |
| test_get_stats | pool | None |
| test_get_stats_dict | pool | None |

#### class `TestHTTPPoolStats`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_create | - | None |

#### class `TestHTTPPool`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| pool | - | HTTPPool |
| test_initial_state | pool | None |
| test_start_creates_client | pool | None |
| test_start_idempotent | pool | None |
| test_close | pool | None |
| test_close_without_start | pool | None |
| test_get_stats | pool | None |
| test_get_stats_dict_closed | pool | None |
| test_get_stats_dict_started | pool | None |
| test_http_methods_delegate_to_client | pool | None |
| test_request_delegates | pool | None |

#### class `TestPoolMonitor`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| monitor | - | PoolMonitor |
| test_get_stats | monitor | None |
| test_check_health_all_ok | monitor | None |
| test_check_health_db_down | monitor | None |
| test_check_health_high_utilization_warning | monitor | None |
| test_report_no_warnings | monitor | None |
| test_report_with_warning | monitor | None |

---

### backend.tests.test_quota

配额管理器单元测试。

#### class `TestQuotaPeriod`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_hourly_value | - | None |
| test_daily_value | - | None |

#### class `TestQuotaInfo`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_within_quota_when_remaining_positive | - | None |
| test_not_within_quota_when_remaining_zero | - | None |

#### class `TestQuotaCheckResult`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_within_quota_all_periods_ok | - | None |
| test_not_within_quota_when_one_period_exceeded | - | None |
| test_to_dict | - | None |

#### class `TestQuotaManagerWithoutRedis`

测试无 Redis 时的配额管理器（默认放行）。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_get_usage_returns_zero_when_no_redis | - | None |
| test_check_and_consume_always_passes_without_redis | - | None |
| test_reset_noop_without_redis | - | None |
| test_unknown_quota_type_returns_empty_periods | - | None |

#### class `TestQuotaExceededError`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_default_message | - | None |
| test_custom_details | - | None |

#### class `TestQuotaLimits`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_route_planning_limits | - | None |
| test_poi_search_limits | - | None |
| test_dialogue_limits | - | None |
| test_all_types_have_both_periods | - | None |

---

### backend.tests.test_rate_limiter

速率限制器单元测试。

#### class `TestRateLimitResult`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_to_headers | - | None |
| test_allowed_is_true_when_within_limit | - | None |
| test_allowed_is_false_when_exceeded | - | None |

#### class `TestLocalRateLimiter`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_allows_first_request | - | None |
| test_blocks_after_limit_reached | - | None |
| test_different_keys_independent | - | None |
| test_window_reset | - | None |
| test_remaining_decrements | - | None |
| test_cleanup_removes_stale_windows | - | None |

#### class `TestRateLimiterWithoutRedis`

测试无 Redis 时的本地模式。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_uses_local_backend | - | None |
| test_is_allowed_delegates_to_local | - | None |
| test_cleanup_local_noop_for_redis_mode | - | None |

#### class `TestRateLimitExceededError`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_default_message | - | None |
| test_custom_details | - | None |

---

### backend.tests.test_registry

服务注册中心单元测试。

#### class `TestServiceInfo`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_create_with_defaults | - | None |
| test_to_dict | - | None |
| test_port_validation | - | None |

#### class `TestServiceRegistry`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| registry | - | ServiceRegistry |
| test_register_and_get | registry | None |
| test_get_nonexistent_returns_none | registry | None |
| test_deregister | registry | None |
| test_deregister_nonexistent | registry | None |
| test_heartbeat | registry | None |
| test_heartbeat_nonexistent | registry | None |
| test_get_all_services | registry | None |
| test_unhealthy_service_not_returned | registry | None |
| test_health_check_marks_unhealthy | registry | None |
| test_remove_unhealthy | registry | None |
| test_service_count_properties | registry | None |
| test_start_stop | registry | None |
| test_start_idempotent | registry | None |

#### class `TestServiceDiscovery`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| registry | - | ServiceRegistry |
| test_discover_local | registry | None |
| test_discover_not_found | registry | None |
| test_get_service_url_raises | registry | None |
| test_get_service_url_success | registry | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| _make_service | service_id, service_name, host, port | ServiceInfo | 否 |

---

### backend.tests.test_resource_monitor

资源监控器单元测试。

#### class `TestResourceMetrics`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_to_dict_rounds_values | - | None |
| test_to_dict_has_timestamp | - | None |

#### class `TestAlertEvent`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_to_dict | - | None |

#### class `TestComparisonOperator`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_comparison_operators | op, a, b, expected | None |

#### class `TestCollectMetrics`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_collect_returns_resource_metrics | mock_psutil | None |

#### class `TestResourceMonitor`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| setup_method | - | None |
| test_add_rule | - | None |
| test_add_rule_overwrites_same_name | - | None |
| test_remove_rule | - | None |
| test_remove_nonexistent_rule | - | None |
| test_add_callback | - | None |
| test_initial_state | - | None |
| test_get_status | - | None |

#### class `TestResourceMonitorEvaluateRules`

测试告警规则评估逻辑。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| setup_method | - | None |
| _record_callback | event | None |
| test_rule_triggers_when_threshold_exceeded | - | None |
| test_rule_does_not_trigger_below_threshold | - | None |
| test_cooldown_prevents_duplicate_alerts | - | None |
| test_callback_exception_does_not_block_others | - | None |
| test_multiple_rules_evaluate_independently | - | None |

#### class `TestResourceMonitorStartStop`

测试启动和停止监控循环。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_start_and_stop | - | None |
| test_double_start_is_idempotent | - | None |

#### class `TestDefaultRules`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_default_rules_loaded | - | None |
| test_singleton_returns_same_instance | - | None |
| test_reset_creates_new_instance | - | None |

---

### backend.tests.test_retry

重试机制单元测试。

#### class `TestRetryDecorator`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_no_retry_on_success | - | None |
| test_retries_on_failure | - | None |
| test_raises_after_exhaustion | - | None |
| test_only_retries_specified_exceptions | - | None |
| test_on_retry_callback | - | None |
| test_max_delay_respected | - | None |
| test_sync_function_support | - | None |
| test_zero_retries | - | None |

---

### backend.tests.test_scheduled_backup

定时备份调度器测试。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| backup_instance | tmp_path | DataBackup | 否 |
| _reset_singletons | - | None | 否 |
| test_start_and_stop | backup_instance | None | 是 |
| test_double_start | backup_instance | None | 是 |
| test_stop_when_not_running | - | None | 是 |
| test_run_now | backup_instance, tmp_path | None | 是 |
| test_run_now_failure_returns_none | monkeypatch | None | 是 |
| test_loop_runs_backup | backup_instance | None | 是 |
| test_get_scheduled_backup_singleton | - | None | 否 |

---

### backend.tests.test_user_rate_limiter

用户限流器单元测试。

#### class `TestEndpointTier`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_resolve_plan_route | - | None |
| test_resolve_search_poi | - | None |
| test_resolve_dialogue | - | None |
| test_resolve_default_for_unknown | - | None |

#### class `TestUserRateLimitResult`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_to_headers | - | None |

#### class `TestLocalUserRateLimiter`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_allows_first_request | - | None |
| test_blocks_after_limit | - | None |
| test_window_reset | - | None |
| test_different_keys_independent | - | None |

#### class `TestUserRateLimiterLocal`

本地模式集成测试。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_backend_type_is_local | - | None |
| test_check_respects_endpoint_tier | - | None |
| test_different_endpoints_independent | - | None |
| test_multiplier_reduces_limit | - | None |
| test_multiplier_increases_limit | - | None |
| test_whitelist_user_always_allowed | - | None |
| test_check_with_tier | - | None |
| test_result_contains_correct_fields | - | None |

#### class `TestUserRateLimitExceededError`

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| test_default_message | - | None |
| test_custom_details | - | None |

---

### backend.tools.changelog_generator

CityFlow 变更日志生成器。

支持两种模式：
1. 手动添加版本及变更条目
2. 从 Git 提交历史自动生成

#### class `ChangelogGenerator`

变更日志生成器。

读写 CHANGELOG.md，支持手动追加版本或从 Git 日志生成。

Parameters
----------
changelog_file : str
    变更日志文件路径，默认为当前目录下的 CHANGELOG.md。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | changelog_file | None |
| add_version | version, changes, date | None |
| generate_from_git | last_tag | list[dict[str, str]] |
| generate_from_commits | commits | list[dict[str, str]] |
| _build_section | version, date, changes | str |
| _prepend_section | section | None |
| _get_git_commits | last_tag | list[str] |
| _parse_commits | commits | list[dict[str, str]] |

---

### backend.tools.changelog_parser

CityFlow 变更日志解析器。

解析符合 Keep a Changelog 格式的 CHANGELOG.md 文件，
提取版本号、日期和变更内容。

文件格式要求：
    ## [x.y.z] - YYYY-MM-DD
    ### 新增
    - 描述内容
    ### 修复
    - 描述内容

#### class `VersionEntry`

单个版本的变更记录。

#### class `ChangelogParser`

变更日志解析器。

读取 CHANGELOG.md 文件并解析为结构化的版本列表。

Parameters
----------
changelog_file : str
    变更日志文件路径，默认为当前目录下的 CHANGELOG.md。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | changelog_file | None |
| parse | - | list[VersionEntry] |
| get_latest_version | - | VersionEntry | None |
| get_version | version | VersionEntry | None |
| get_changes_by_type | version | dict[str, list[str]] |
| _parse_content | content | list[VersionEntry] |
| _extract_sections | content | dict[str, list[str]] |

---

### backend.tools.code_generator

CityFlow 代码生成工具。

根据字段定义自动生成符合项目规范的 API 端点、数据模型和服务类代码。
生成的代码遵循 CityFlow 项目的编码风格：
- 使用 `from __future__ import annotations`
- Pydantic v2 BaseModel + Field
- 统一的注释分隔线风格
- 类型注解完整

#### class `CodeGenerator`

代码生成器。

根据字段定义生成 FastAPI 端点、Pydantic 模型、异步服务类的代码，
并可选择直接写入文件。

Parameters
----------
output_dir : str
    输出根目录，默认 ``"backend"``。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | output_dir | None |
| _build_field_lines | fields | list[str] |
| _build_sample_payload | fields | list[str] |
| generate_api_endpoint | name, fields | str |
| generate_model | name, fields | str |
| generate_service | name | str |
| generate_test | name, fields | str |
| save_file | filename, content | Path |
| generate_full | name, fields | dict[str, str] |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| _resolve_type | raw | str | 否 |
| _capitalize | name | str | 否 |
| main | - | None | 否 |

---

### backend.tools.doc_generator

CityFlow 文档自动生成工具。

从 Python 源码中提取 API 文档、SDK 文档和使用指南。
支持解析 FastAPI 路由、Pydantic 模型、服务类等模块，
自动生成结构化的 Markdown 文档。

Features:
    - 基于 AST 解析，无需运行代码即可提取文档
    - 支持函数、类、方法的 docstring 提取
    - 自动生成参数表格和返回值说明
    - 支持 FastAPI 路由端点的 HTTP 方法和路径识别

#### class `DocType`

**继承**: `Enum`

文档类型枚举。

#### class `ParamInfo`

函数参数信息。

#### class `ReturnInfo`

函数返回值信息。

#### class `FunctionDoc`

函数/方法文档信息。

#### class `ClassDoc`

类文档信息。

#### class `ModuleDoc`

模块文档信息。

#### class `RouteInfo`

FastAPI 路由信息。

#### class `_AstParser`

AST 解析辅助类，从 Python 源码中提取文档信息。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| parse_annotation | node | str |
| parse_default | node | str |
| extract_params | func_node | list[ParamInfo] |
| extract_return | func_node | ReturnInfo |
| extract_decorators | node | list[str] |
| extract_route_info | decorators | tuple[str, str] | None |

#### class `DocGenerator`

文档生成器。

从 Python 源码目录中提取文档信息，生成 API 文档、SDK 文档和使用指南。

Parameters
----------
source_dir : str
    源码目录路径，默认 ``"backend"``。
project_name : str
    项目名称，默认 ``"CityFlow"``。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | source_dir, project_name | None |
| parse | - | None |
| _parse_module | tree, file_path | ModuleDoc |
| _parse_function | node | FunctionDoc |
| _parse_class | node | ClassDoc |
| _extract_routes | tree, file_path | None |
| generate_api_docs | - | dict[str, Any] |
| generate_api_docs_markdown | - | str |
| generate_sdk_docs | - | str |
| generate_usage_guide | - | str |
| save_docs | output_dir | dict[str, Path] |
| _format_param | param | str |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| main | - | None | 否 |

---

### backend.tools.markdown_generator

CityFlow Markdown 文档生成工具。

提供 Markdown 内容的构建块，包括表格、代码块、目录、
列表等常用结构的生成方法。

设计为无状态工具类，所有方法均为纯函数，便于组合使用。

#### class `MarkdownGenerator`

Markdown 内容生成器。

提供生成常见 Markdown 结构的工具方法，
所有方法返回纯字符串，可直接拼接使用。

Examples
--------
>>> md = MarkdownGenerator()
>>> table = md.generate_table(
...     headers=["名称", "值"],
...     rows=[["A", "1"], ["B", "2"]],
... )
>>> print(table)
| 名称 | 值 |
| --- | --- |
| A | 1 |
| B | 2 |

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| generate_table | headers, rows | str |
| generate_code_block | code, language | str |
| generate_inline_code | text | str |
| generate_toc | headings | str |
| generate_unordered_list | items | str |
| generate_ordered_list | items | str |
| generate_heading | text, level | str |
| generate_horizontal_rule | - | str |
| generate_link | text, url | str |
| generate_image | alt, url | str |
| generate_blockquote | text | str |
| generate_key_value_pairs | data | str |
| generate_details_block | summary, content | str |
| _slugify | text | str |

---

### backend.tools.__init__

CityFlow 开发工具集。

---

### backend.utils.cpu_profiler

CityFlow CPU 分析器。

基于 cProfile 提供 CPU 级别的函数调用分析，
支持按累计耗时 / 自身耗时 / 调用次数排序。

#### class `FunctionStat`

单个函数的 CPU 统计。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| to_dict | - | dict[str, Any] |

#### class `CPUProfileResult`

一次 CPU 分析的结果。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| to_dict | - | dict[str, Any] |

#### class `CPUProfiler`

CPU 分析器。

用法::

    cpu_profiler = CPUProfiler()

    # 方式 1: 上下文管理器
    with cpu_profiler.run("my_block"):
        do_heavy_work()

    # 方式 2: 装饰器
    @cpu_profiler.profile("my_func")
    def my_func():
        ...

    # 方式 3: 手动启停
    cpu_profiler.start()
    do_work()
    result = cpu_profiler.stop("work_label")

    # 查看结果
    print(cpu_profiler.get_top_functions(limit=20))

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | - | None |
| enabled | - | bool |
| start | - | None |
| stop | label | CPUProfileResult |
| run | label | _CPURunContext |
| profile | name | Any |
| get_top_functions | limit, label, sort_by | list[dict[str, Any]] |
| get_pstats_text | label, sort_by | str |
| get_all_labels | - | list[str] |
| remove_result | label | bool |
| reset | - | None |
| _get_result | label | CPUProfileResult | None |
| _build_result | label | CPUProfileResult |

#### class `_CPURunContext`

CPUProfiler.run() 返回的上下文管理器。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | profiler, label | None |
| __enter__ | - | _CPURunContext |
| __exit__ | exc_type, exc_val, exc_tb | None |

---

### backend.utils.encryption

CityFlow 数据加密工具。

基于 Fernet 对称加密，使用 PBKDF2 派生密钥。
用于加密数据库中的敏感字段（如用户手机号、API Key 等）。

#### class `EncryptionError`

**继承**: `Exception`

加密/解密操作失败。

#### class `DataEncryptor`

Fernet 对称加密器。

Parameters
----------
key:
    用户提供的原始密钥字符串。如果为 ``None``，
    则依次尝试 ``ENCRYPTION_KEY`` 环境变量、
    ``ENCRYPTION_KEY_FILE`` 指向的文件。
    三者均不可用时抛出 ``EncryptionError``。
salt:
    PBKDF2 盐值，默认 ``b"cityflow-salt-v1"``。
iterations:
    PBKDF2 迭代次数，默认 480 000。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | key, salt, iterations | None |
| encrypt | data | str |
| decrypt | encrypted_data | str |
| encrypt_dict | data | str |
| decrypt_dict | encrypted_data | dict[str, Any] |
| _resolve_key | key | str |
| _build_fernet | raw_key, salt, iterations | Fernet |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_encryptor | - | DataEncryptor | 否 |
| reset_encryptor | - | None | 否 |
| encrypt_sensitive_data | data | str | 否 |
| decrypt_sensitive_data | encrypted_data | str | 否 |

---

### backend.utils.error_handler

CityFlow 错误处理装饰器。

为 service 层函数提供统一的异常包装，把底层异常
转换为 CityFlowException 子类，避免在每个函数里重复 try/except。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| handle_errors | default_message | Callable | 否 |
| handle_llm_errors | func | Callable | 否 |

---

### backend.utils.field_encryption

CityFlow 字段加密装饰器。

为 service 层函数提供透明的字段加解密，
支持对返回字典中的指定字段自动加密/解密。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| encrypt_field | field_name | Callable | 否 |
| decrypt_field | field_name | Callable | 否 |
| encrypt_fields | - | Callable | 否 |
| decrypt_fields | - | Callable | 否 |
| _encrypt_result_field | result, field_name | Any | 否 |
| _decrypt_result_field | result, field_name | Any | 否 |
| _encrypt_result_fields | result, field_names | Any | 否 |
| _decrypt_result_fields | result, field_names | Any | 否 |
| encrypt_value | value | str | 否 |
| decrypt_value | value | str | 否 |

---

### backend.utils.localized_response

CityFlow 本地化响应工具。

提供统一的 API 响应格式，所有消息通过 i18n 翻译后返回。

#### class `LocalizedResponse`

本地化 API 响应构建器。

所有方法返回字典，可直接由 FastAPI 序列化为 JSON。
消息键默认使用 "common.*" 下的翻译。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| success | message_key | dict[str, Any] |
| error | message_key | dict[str, Any] |
| data | data, message_key | dict[str, Any] |
| paginated | data, total, page, page_size, message_key | dict[str, Any] |

---

### backend.utils.memory_profiler

CityFlow 内存分析器。

基于 tracemalloc 提供内存分配追踪能力，
支持快照对比、Top N 排查、增量分析。

#### class `AllocationInfo`

单条内存分配记录。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| to_dict | - | dict[str, Any] |

#### class `SnapshotInfo`

快照摘要。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| to_dict | - | dict[str, Any] |

#### class `MemoryProfiler`

内存分析器。

用法::

    mem_profiler = MemoryProfiler()
    mem_profiler.start()

    # ... 执行代码 ...

    snapshot = mem_profiler.take_snapshot("after_load")
    print(mem_profiler.get_top_allocations(limit=10))

    # 对比两次快照
    mem_profiler.take_snapshot("after_process")
    diff = mem_profiler.compare_snapshots("after_load", "after_process")

    mem_profiler.stop()

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | nframes | None |
| enabled | - | bool |
| start | nframes | None |
| stop | - | None |
| take_snapshot | label | SnapshotInfo | None |
| get_top_allocations | limit, label | list[dict[str, Any]] |
| compare_snapshots | label_before, label_after, limit | list[dict[str, Any]] |
| get_snapshot_labels | - | list[str] |
| remove_snapshot | label | bool |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| _human_size | size_bytes | str | 否 |

---

### backend.utils.profiler

CityFlow 性能分析器。

提供函数耗时统计功能，包括装饰器和手动记录两种方式。
支持全局统计与慢函数告警。

#### class `ProfilerStats`

单个函数的统计数据。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | - | None |
| record | duration | None |
| avg | - | float |
| to_dict | - | dict[str, Any] |

#### class `Profiler`

性能分析器。

用法::

    profiler = get_profiler()

    # 方式 1: 装饰器
    @profile("my_func")
    async def my_func():
        ...

    # 方式 2: 手动记录
    start = time.time()
    ...
    profiler.record("my_func", time.time() - start)

    # 查看统计
    print(profiler.get_stats())

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| __init__ | slow_threshold | None |
| enabled | - | bool |
| enable | - | None |
| disable | - | None |
| set_slow_threshold | seconds | None |
| record | name, duration | None |
| get_stats | - | dict[str, dict[str, Any]] |
| get_slow_functions | - | list[dict[str, Any]] |
| reset | - | None |
| log_summary | - | None |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| get_profiler | - | Profiler | 否 |
| profile | name | Callable | 否 |

---

### backend.utils.serialization

CityFlow 高效 JSON 序列化工具。

使用 orjson 实现高性能序列化，可选 gzip 压缩。

#### class `FastJSONSerializer`

基于 orjson 的高性能 JSON 序列化器。

orjson 比标准库 json 快 5-10 倍，
且原生支持 numpy 类型和非字符串 key。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| dumps | obj, compress | bytes |
| loads | data, compressed | Any |
| dumps_str | obj | str |
| loads_str | data | Any |

#### class `CompressedJSONSerializer`

基于标准库 json + gzip 的压缩序列化器。

用于不依赖 orjson 的场景（如脚本、迁移工具）。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| dumps | obj | bytes |
| loads | data | Any |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| serialize_response | data, compress | bytes | 否 |
| deserialize_request | data, compressed | Any | 否 |

---

### backend.utils.serializers

CityFlow 序列化装饰器。

为函数/路由提供自动序列化/反序列化能力。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| serialize_output | compress | Callable[List(elts=[Name(id='F', ctx=Load())], ctx=Load()), F] | 否 |
| deserialize_input | compressed | Callable[List(elts=[Name(id='F', ctx=Load())], ctx=Load()), F] | 否 |
| _deserialize_args | args, compressed | list[Any] | 否 |

---

### backend.utils.version_compat

API 版本兼容性处理工具。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| convert_v1_to_v2_request | v1_request | dict[str, Any] | 否 |
| convert_v2_to_v1_response | v2_response | dict[str, Any] | 否 |
| convert_v2_to_v1_poi | poi | dict[str, Any] | 否 |
| get_version_from_request | request | str | 否 |
| is_v1_request | request | bool | 否 |
| is_v2_request | request | bool | 否 |

---

### backend.utils.__init__

CityFlow 工具集。

---

### backend.validators.base

CityFlow 数据校验框架。

提供请求/响应数据的校验基类和业务校验器。
基于 Pydantic v2，与项目已有的错误体系 (CityFlowException) 对接。

#### class `BaseValidator`

**继承**: `BaseModel`

基础校验器 — 所有业务校验器的基类。

#### class `RequestValidator`

**继承**: `BaseValidator`

请求校验基类 — 自动清理所有字符串字段。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| sanitize_all_strings | data | Any |

#### class `EmotionTagsValidator`

**继承**: `BaseValidator`

POI 情绪标签校验（6 维，取值 0~1）。

#### class `ConstraintsValidator`

**继承**: `BaseValidator`

POI 约束条件校验。

#### class `POIValidator`

**继承**: `RequestValidator`

POI 数据校验器 — 匹配 city_poi_db.json 的实际字段。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| validate_id | v | str |
| validate_business_hours | v | str |

#### class `POISearchValidator`

**继承**: `RequestValidator`

POI 搜索请求校验器 — 匹配 SearchRequest 模型。

#### class `RouteStepValidator`

**继承**: `BaseValidator`

路线步骤校验器。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| validate_time_format | v | str | None |

#### class `RouteValidator`

**继承**: `RequestValidator`

路线校验器 — 用于校验完整的路线数据。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| validate_route_not_empty | v | list[dict] |

#### class `PlanRequestValidator`

**继承**: `RequestValidator`

V1 路线规划请求校验器 — 匹配 PlanRequestV1。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| validate_user_input | v | str |

#### class `DialogueRequestValidator`

**继承**: `RequestValidator`

对话调整请求校验器 — 匹配 AdjustRequestV1。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| validate_instruction | v | str |

#### class `DistanceMatrixValidator`

**继承**: `RequestValidator`

距离矩阵请求校验器 — 匹配 DistanceMatrixRequest。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| validate_poi_ids | v | list[str] |

#### class `ChatRequestValidator`

**继承**: `RequestValidator`

LLM 对话请求校验器 — 匹配 ChatRequest。

| 方法 | 参数 | 返回值 |
| :--- | :--- | :--- |
| validate_message | v | str |

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| sanitize_string | value | str | 否 |
| check_injection | value | None | 否 |

---

### backend.validators.decorators

校验装饰器。

为 FastAPI 路由函数提供声明式的数据校验能力：
- validate_request: 在函数执行前校验请求参数
- validate_response: 在函数执行后校验返回值

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| validate_request | model | Any | 否 |
| validate_response | model | Any | 否 |

---

### backend.validators.__init__

CityFlow 数据校验框架。

使用方式::

    from backend.validators import POIValidator, validate_request

    # 直接校验数据
    poi = POIValidator(**raw_data)

    # 装饰器方式
    @validate_request(PlanRequestValidator)
    async def plan_route(user_input: str): ...

---

### backend.routers.v1.dialogue

V1 对话式路线调整接口。

#### class `AdjustRequestV1`

**继承**: `BaseModel`

V1 对话调整请求。

#### class `DialogueResultV1`

**继承**: `BaseModel`

V1 对话调整响应。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| dialogue_v1 | session_id, request | - | 是 |
| get_route_v1 | route_id | - | 是 |

---

### backend.routers.v1.plan

V1 路线规划接口。

#### class `PlanRequestV1`

**继承**: `BaseModel`

V1 路线规划请求。

#### class `PlanResponseV1`

**继承**: `BaseModel`

V1 路线规划响应。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| _with_timeout | coro, timeout_seconds, fallback | - | 是 |
| _generate_simplified_route | pois, count | dict[str, Any] | 否 |
| _sse | event, data_obj | str | 否 |
| plan_route_v1 | request | - | 是 |

---

### backend.routers.v1.poi

V1 POI 查询接口。

#### class `SearchRequestV1`

**继承**: `BaseModel`

V1 POI 搜索请求。

#### class `DistanceMatrixRequestV1`

**继承**: `BaseModel`

V1 距离矩阵请求。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| load_pois | - | None | 否 |
| get_price_range | avg_price | str | 否 |
| haversine | lat1, lon1, lat2, lon2 | float | 否 |
| enrich_poi | poi | dict | 否 |
| search_pois_v1 | request, lat, lng | - | 是 |
| get_poi_detail_v1 | poi_id | - | 是 |
| get_distance_matrix_v1 | request | - | 是 |

---

### backend.routers.v1.__init__

CityFlow API v1 路由。

---

### backend.routers.v2.plan

V2 路线规划接口（增强版）。

#### class `PlanRequestV2`

**继承**: `BaseModel`

V2 路线规划请求（增强版，支持约束和节奏）。

#### class `EmotionCurvePoint`

**继承**: `BaseModel`

情绪曲线数据点。

#### class `RouteMetadata`

**继承**: `BaseModel`

路线元数据。

#### class `PlanResponseV2`

**继承**: `BaseModel`

V2 路线规划响应（增强版，包含情绪曲线和元数据）。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| _with_timeout | coro, timeout_seconds, fallback | - | 是 |
| _generate_simplified_route | pois, count | dict[str, Any] | 否 |
| _build_emotion_curve | route_result | list[dict] | 否 |
| _build_metadata | route_result, request | dict | 否 |
| _sse | event, data_obj | str | 否 |
| plan_route_v2 | request | - | 是 |

---

### backend.routers.v2.poi

V2 POI 查询接口（增强版）。

#### class `SearchRequestV2`

**继承**: `BaseModel`

V2 POI 搜索请求（增强版，支持约束过滤）。

#### class `DistanceMatrixRequestV2`

**继承**: `BaseModel`

V2 距离矩阵请求。

#### 函数

| 函数 | 参数 | 返回值 | 异步 |
| :--- | :--- | :--- | :--- |
| load_pois | - | None | 否 |
| get_price_range | avg_price | str | 否 |
| haversine | lat1, lon1, lat2, lon2 | float | 否 |
| enrich_poi | poi | dict | 否 |
| search_pois_v2 | request, lat, lng | - | 是 |
| get_poi_detail_v2 | poi_id | - | 是 |
| get_distance_matrix_v2 | request | - | 是 |

---

### backend.routers.v2.__init__

CityFlow API v2 路由（增强版）。

---
