# CityFlow SDK 文档

本文档自动生成，涵盖所有可公开使用的服务类、工具类和辅助函数。

## 目录

  - [backend.config](#backendconfig)
  - [backend.config_loader](#backendconfigloader)
  - [backend.errors](#backenderrors)
  - [backend.i18n](#backendi18n)
  - [backend.main](#backendmain)
  - [backend.openapi](#backendopenapi)
  - [backend.auth.access_control](#backendauthaccesscontrol)
  - [backend.auth.models](#backendauthmodels)
  - [backend.database.base](#backenddatabasebase)
  - [backend.database.models](#backenddatabasemodels)
  - [backend.database.pool](#backenddatabasepool)
  - [backend.database.repository](#backenddatabaserepository)
  - [backend.di.container](#backenddicontainer)
  - [backend.di.registry](#backenddiregistry)
  - [backend.docs.__init__](#backenddocsinit)
  - [backend.events.decorators](#backendeventsdecorators)
  - [backend.events.handlers](#backendeventshandlers)
  - [backend.events.types](#backendeventstypes)
  - [backend.events.__init__](#backendeventsinit)
  - [backend.gateway.auth](#backendgatewayauth)
  - [backend.gateway.main](#backendgatewaymain)
  - [backend.gateway.rate_limit](#backendgatewayratelimit)
  - [backend.gateway.router](#backendgatewayrouter)
  - [backend.graphql.config](#backendgraphqlconfig)
  - [backend.graphql.resolvers](#backendgraphqlresolvers)
  - [backend.graphql.schema](#backendgraphqlschema)
  - [backend.i18n.__init__](#backendi18ninit)
  - [backend.middleware.compression](#backendmiddlewarecompression)
  - [backend.middleware.config](#backendmiddlewareconfig)
  - [backend.middleware.error_handler](#backendmiddlewareerrorhandler)
  - [backend.middleware.locale](#backendmiddlewarelocale)
  - [backend.middleware.performance](#backendmiddlewareperformance)
  - [backend.middleware.pipeline](#backendmiddlewarepipeline)
  - [backend.middleware.prometheus](#backendmiddlewareprometheus)
  - [backend.middleware.rate_limit](#backendmiddlewareratelimit)
  - [backend.middleware.security](#backendmiddlewaresecurity)
  - [backend.middleware.session](#backendmiddlewaresession)
  - [backend.middleware.shutdown](#backendmiddlewareshutdown)
  - [backend.middleware.validation](#backendmiddlewarevalidation)
  - [backend.middleware.version](#backendmiddlewareversion)
  - [backend.models.schemas](#backendmodelsschemas)
  - [backend.monitoring.error_filter](#backendmonitoringerrorfilter)
  - [backend.monitoring.metrics](#backendmonitoringmetrics)
  - [backend.monitoring.profiler](#backendmonitoringprofiler)
  - [backend.monitoring.sentry](#backendmonitoringsentry)
  - [backend.routers.audit](#backendroutersaudit)
  - [backend.routers.data](#backendroutersdata)
  - [backend.routers.health](#backendroutershealth)
  - [backend.routers.llm](#backendroutersllm)
  - [backend.routers.metrics](#backendroutersmetrics)
  - [backend.routers.mq](#backendroutersmq)
  - [backend.routers.poi](#backendrouterspoi)
  - [backend.routers.registry](#backendroutersregistry)
  - [backend.routers.session](#backendrouterssession)
  - [backend.routers.tasks](#backendrouterstasks)
  - [backend.routers.websocket](#backendrouterswebsocket)
  - [backend.services.adaptive_rate_limiter](#backendservicesadaptiveratelimiter)
  - [backend.services.alert_notifier](#backendservicesalertnotifier)
  - [backend.services.audit_logger](#backendservicesauditlogger)
  - [backend.services.auto_recovery](#backendservicesautorecovery)
  - [backend.services.backup](#backendservicesbackup)
  - [backend.services.cache](#backendservicescache)
  - [backend.services.cache_warmup](#backendservicescachewarmup)
  - [backend.services.circuit_breaker](#backendservicescircuitbreaker)
  - [backend.services.config_hot_reload](#backendservicesconfighotreload)
  - [backend.services.config_watcher](#backendservicesconfigwatcher)
  - [backend.services.data_check](#backendservicesdatacheck)
  - [backend.services.data_service](#backendservicesdataservice)
  - [backend.services.dialogue](#backendservicesdialogue)
  - [backend.services.discovery](#backendservicesdiscovery)
  - [backend.services.emotion](#backendservicesemotion)
  - [backend.services.event_bus](#backendserviceseventbus)
  - [backend.services.fallback](#backendservicesfallback)
  - [backend.services.filters](#backendservicesfilters)
  - [backend.services.geo](#backendservicesgeo)
  - [backend.services.graceful_shutdown](#backendservicesgracefulshutdown)
  - [backend.services.health_checker](#backendserviceshealthchecker)
  - [backend.services.http_pool](#backendserviceshttppool)
  - [backend.services.intent_parser](#backendservicesintentparser)
  - [backend.services.ip_rate_limiter](#backendservicesipratelimiter)
  - [backend.services.llm_service](#backendservicesllmservice)
  - [backend.services.logger](#backendserviceslogger)
  - [backend.services.log_rotation](#backendserviceslogrotation)
  - [backend.services.message_handlers](#backendservicesmessagehandlers)
  - [backend.services.message_queue](#backendservicesmessagequeue)
  - [backend.services.metrics](#backendservicesmetrics)
  - [backend.services.narrator](#backendservicesnarrator)
  - [backend.services.notification](#backendservicesnotification)
  - [backend.services.parallel](#backendservicesparallel)
  - [backend.services.pool_monitor](#backendservicespoolmonitor)
  - [backend.services.quota](#backendservicesquota)
  - [backend.services.rate_limiter](#backendservicesratelimiter)
  - [backend.services.registry](#backendservicesregistry)
  - [backend.services.resilient_service](#backendservicesresilientservice)
  - [backend.services.resource_monitor](#backendservicesresourcemonitor)
  - [backend.services.retry](#backendservicesretry)
  - [backend.services.scheduled_backup](#backendservicesscheduledbackup)
  - [backend.services.session](#backendservicessession)
  - [backend.services.solver](#backendservicessolver)
  - [backend.services.task_queue](#backendservicestaskqueue)
  - [backend.services.template_engine](#backendservicestemplateengine)
  - [backend.services.time_utils](#backendservicestimeutils)
  - [backend.services.user_profiles](#backendservicesuserprofiles)
  - [backend.services.user_rate_limiter](#backendservicesuserratelimiter)
  - [backend.services.vectorized](#backendservicesvectorized)
  - [backend.services.websocket](#backendserviceswebsocket)
  - [backend.tests.test_adaptive_rate_limiter](#backendteststestadaptiveratelimiter)
  - [backend.tests.test_alert_notifier](#backendteststestalertnotifier)
  - [backend.tests.test_audit_logger](#backendteststestauditlogger)
  - [backend.tests.test_auto_recovery](#backendteststestautorecovery)
  - [backend.tests.test_backup](#backendteststestbackup)
  - [backend.tests.test_circuit_breaker](#backendteststestcircuitbreaker)
  - [backend.tests.test_code_generator](#backendteststestcodegenerator)
  - [backend.tests.test_errors](#backendteststesterrors)
  - [backend.tests.test_fallback](#backendteststestfallback)
  - [backend.tests.test_health_checker](#backendteststesthealthchecker)
  - [backend.tests.test_i18n](#backendteststesti18n)
  - [backend.tests.test_ip_rate_limiter](#backendteststestipratelimiter)
  - [backend.tests.test_locale_middleware](#backendteststestlocalemiddleware)
  - [backend.tests.test_localized_response](#backendteststestlocalizedresponse)
  - [backend.tests.test_pool](#backendteststestpool)
  - [backend.tests.test_quota](#backendteststestquota)
  - [backend.tests.test_rate_limiter](#backendteststestratelimiter)
  - [backend.tests.test_registry](#backendteststestregistry)
  - [backend.tests.test_resource_monitor](#backendteststestresourcemonitor)
  - [backend.tests.test_retry](#backendteststestretry)
  - [backend.tests.test_scheduled_backup](#backendteststestscheduledbackup)
  - [backend.tests.test_user_rate_limiter](#backendteststestuserratelimiter)
  - [backend.tools.changelog_generator](#backendtoolschangeloggenerator)
  - [backend.tools.changelog_parser](#backendtoolschangelogparser)
  - [backend.tools.code_generator](#backendtoolscodegenerator)
  - [backend.tools.doc_generator](#backendtoolsdocgenerator)
  - [backend.tools.markdown_generator](#backendtoolsmarkdowngenerator)
  - [backend.utils.cpu_profiler](#backendutilscpuprofiler)
  - [backend.utils.encryption](#backendutilsencryption)
  - [backend.utils.error_handler](#backendutilserrorhandler)
  - [backend.utils.field_encryption](#backendutilsfieldencryption)
  - [backend.utils.localized_response](#backendutilslocalizedresponse)
  - [backend.utils.memory_profiler](#backendutilsmemoryprofiler)
  - [backend.utils.profiler](#backendutilsprofiler)
  - [backend.utils.serialization](#backendutilsserialization)
  - [backend.utils.serializers](#backendutilsserializers)
  - [backend.utils.version_compat](#backendutilsversioncompat)
  - [backend.validators.base](#backendvalidatorsbase)
  - [backend.validators.decorators](#backendvalidatorsdecorators)
  - [backend.routers.v1.dialogue](#backendroutersv1dialogue)
  - [backend.routers.v1.plan](#backendroutersv1plan)
  - [backend.routers.v1.poi](#backendroutersv1poi)
  - [backend.routers.v2.plan](#backendroutersv2plan)
  - [backend.routers.v2.poi](#backendroutersv2poi)

## backend.config

**文件**: `backend\config.py`

CityFlow 应用配置。

通过环境变量 / .env 文件加载配置，使用 pydantic-settings 进行校验。
支持多环境（dev / test / prod）配置，子配置按模块拆分。

### class `Environment`

**继承**: `str`, `Enum`

运行环境枚举。

### class `DatabaseSettings`

**继承**: `BaseSettings`

数据库配置。

### class `RedisSettings`

**继承**: `BaseSettings`

Redis 配置。

### class `LLMSettings`

**继承**: `BaseSettings`

LLM 服务配置。

### class `SecuritySettings`

**继承**: `BaseSettings`

安全配置。

### class `Settings`

**继承**: `BaseSettings`

CityFlow 主配置。

### `get_settings()`

获取全局配置实例。

**Returns**: `Settings`

---

## backend.config_loader

**文件**: `backend\config_loader.py`

配置加载与验证。

根据 ENVIRONMENT 环境变量自动选择 .env 文件，
并在创建 Settings 实例后执行额外的业务验证。

### `load_config(env: Environment | None = None)`

加载并验证配置。

Args:
    env: 指定环境。为 None 时从 ENVIRONMENT 环境变量读取，默认 dev。

Returns:
    经过验证的 Settings 实例。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| env | Environment | None | None | - |

**Returns**: `Settings`

---

### `validate_config(config: Settings)`

业务层面的配置校验。

Raises:
    ValueError: 配置不合法时抛出。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| config | Settings | - | - |

**Returns**: `None`

---

### `get_config_summary(config: Settings)`

获取配置摘要（隐藏敏感信息）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| config | Settings | - | - |

**Returns**: `dict[str, str | int | bool]`

---

## backend.errors

**文件**: `backend\errors.py`

CityFlow 统一错误码与异常体系。

错误码分段：
    1xxx - 通用错误
    2xxx - 认证/授权错误
    3xxx - 业务逻辑错误
    4xxx - 数据/输入错误
    5xxx - 外部服务错误

### class `ErrorCode`

**继承**: `Enum`

错误码枚举。

### class `CityFlowException`

**继承**: `Exception`

CityFlow 基础异常。

所有业务异常的基类，携带错误码、消息、可选详情和 HTTP 状态码。

#### `CityFlowException.__init__(code: ErrorCode, message: str, details: dict[str, Any] | None = None, status_code: int | None = None)`

**Returns**: `None`


#### `CityFlowException.to_dict()`

转换为 API 响应字典。

**Returns**: `dict[str, Any]`


### class `IntentParseError`

**继承**: `CityFlowException`

意图解析失败。

#### `IntentParseError.__init__(message: str = '意图解析失败', details: dict[str, Any] | None = None)`

**Returns**: `None`


### class `NoPOIsFoundError`

**继承**: `CityFlowException`

未找到符合条件的 POI。

#### `NoPOIsFoundError.__init__(message: str = '未找到符合条件的POI', details: dict[str, Any] | None = None)`

**Returns**: `None`


### class `RouteSolvingError`

**继承**: `CityFlowException`

路线求解失败。

#### `RouteSolvingError.__init__(message: str = '路线求解失败', details: dict[str, Any] | None = None)`

**Returns**: `None`


### class `NarrativeGenerationError`

**继承**: `CityFlowException`

文案生成失败。

#### `NarrativeGenerationError.__init__(message: str = '文案生成失败', details: dict[str, Any] | None = None)`

**Returns**: `None`


### class `DialogueError`

**继承**: `CityFlowException`

对话处理失败。

#### `DialogueError.__init__(message: str = '对话处理失败', details: dict[str, Any] | None = None)`

**Returns**: `None`


### class `LLMServiceError`

**继承**: `CityFlowException`

LLM 服务异常。

#### `LLMServiceError.__init__(message: str = 'LLM服务异常', details: dict[str, Any] | None = None)`

**Returns**: `None`


### class `RateLimitError`

**继承**: `CityFlowException`

请求频率超限。

#### `RateLimitError.__init__(message: str = '请求过于频繁', details: dict[str, Any] | None = None)`

**Returns**: `None`


## backend.i18n

**文件**: `backend\i18n.py`

CityFlow 国际化 (i18n) 模块。

提供多语言支持，包括：
- 基于 contextvars 的线程安全 / 异步安全语言切换
- 内置 zh_CN / en_US 翻译
- 点分键访问（如 "common.success"）
- 参数插值（如 t("greeting", name="Alice")）

### class `I18n`

国际化管理器。

每个实例持有翻译数据，语言状态通过 contextvars 管理，
天然兼容 async 并发场景。

#### `I18n.__init__(translations: dict[str, TranslationDict] | None = None, default_locale: str = DEFAULT_LOCALE)`

**Returns**: `None`


#### `I18n.current_locale()`

获取当前语言。

**Returns**: `str`


#### `I18n.set_locale(locale: str)`

设置当前请求的语言。

Args:
    locale: 语言代码，如 "zh_CN"、"en_US"。

**Returns**: `None`


#### `I18n.t(key: str)`

翻译指定键。

Args:
    key: 点分翻译键，如 "common.success"。
    **kwargs: 插值参数，如 t("greeting", name="Alice")。

Returns:
    翻译后的字符串；找不到时返回键本身。

**Returns**: `str`


#### `I18n.get_translations(locale: str)`

获取指定语言的完整翻译字典。

**Returns**: `TranslationDict`


#### `I18n.add_translations(locale: str, translations: TranslationDict)`

动态添加翻译数据（深度合并）。

Args:
    locale: 语言代码。
    translations: 要合并的翻译字典。

**Returns**: `None`


### `get_i18n()`

获取全局 I18n 单例。

**Returns**: `I18n`

---

### `t(key: str)`

全局翻译快捷函数。

等价于 ``get_i18n().t(key, **kwargs)``。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| key | str | - | - |

**Returns**: `str`

---

### `set_locale(locale: str)`

全局设置语言快捷函数。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| locale | str | - | - |

**Returns**: `None`

---

### `get_locale()`

获取当前语言快捷函数。

**Returns**: `str`

---

## backend.main

**文件**: `backend\main.py`

CityFlow API -- 前后端集成 + SSE 流式路线规划。

### class `PlanRequest`

**继承**: `BaseModel`

流式规划路线的请求体。

### class `AdjustRequest`

**继承**: `BaseModel`

对话式路线调整的请求体。

### class `EmotionTags`

**继承**: `BaseModel`

POI情绪标签（6维，取值0~1）。

### class `POIConstraints`

**继承**: `BaseModel`

POI约束条件。

### class `TravelInfo`

**继承**: `BaseModel`

交通信息。

### class `POIResponse`

**继承**: `BaseModel`

兴趣点（POI）完整信息。

### class `RouteStep`

**继承**: `BaseModel`

路线中的单个步骤。

### class `NarrativeStep`

**继承**: `BaseModel`

路线文案。

### class `RouteResult`

**继承**: `BaseModel`

完整的路线规划结果。

### class `DoneEvent`

**继承**: `BaseModel`

SSE done 事件的载荷。

### class `DialogueResult`

**继承**: `BaseModel`

对话调整的响应。

### class `DistanceMatrixItem`

**继承**: `BaseModel`

距离矩阵中的单个元素。

### class `DistanceMatrixResponse`

**继承**: `BaseModel`

距离矩阵响应。

### class `ErrorResponse`

**继承**: `BaseModel`

错误响应。

### class `HealthResponse`

**继承**: `BaseModel`

健康检查响应。

### `async plan_route(request: PlanRequest)`

流式规划路线。

根据用户自然语言输入，经过意图解析、候选搜索、路线求解、文案生成四个阶段，
以 SSE 事件流的形式逐步返回结果。

返回的 `route_id` 可用于后续的 `/api/route/{route_id}` 查询和
`/api/dialogue/{session_id}` 对话调整。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| request | PlanRequest | - | - |

---

### `async get_route(route_id: str)`

获取已规划路线的完整数据。

路线数据保存在内存缓存中，服务重启后失效。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| route_id | str | - | - |

---

### `async adjust_route(route_id: str, instruction: str)`

通过对话指令调整路线（GET快捷方式）。

自动创建对话会话（如果不存在），然后处理用户的调整指令。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| route_id | str | - | - |
| instruction | str | - | - |

---

### `async dialogue(session_id: str, request: AdjustRequest)`

对话式路线调整。

通过POST请求发送调整指令，系统自动分类指令类型并执行相应调整。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| session_id | str | - | - |
| request | AdjustRequest | - | - |

---

### `async startup()`

---

### `async shutdown()`

---

### `async health()`

健康检查接口。

---

### `async cache_stats()`

返回缓存命中率统计。

---

## backend.openapi

**文件**: `backend\openapi.py`

OpenAPI 元数据定义。

### `get_openapi_metadata()`

返回 OpenAPI 规范的顶层元数据。

**Returns**: `dict[str, Any]`

---

## backend.auth.access_control

**文件**: `backend\auth\access_control.py`

访问控制服务。

提供用户注册、权限校验，以及 FastAPI 依赖注入和装饰器两种接入方式。

### class `AccessControl`

访问控制服务（进程内单例）。

#### `AccessControl.__init__()`

**Returns**: `None`


#### `AccessControl.add_user(user: User)`

注册 / 更新用户。

**Returns**: `None`


#### `AccessControl.remove_user(user_id: str)`

移除用户，返回是否成功。

**Returns**: `bool`


#### `AccessControl.get_user(user_id: str)`

根据 user_id 获取用户。

**Returns**: `User | None`


#### `AccessControl.list_users()`

列出所有用户。

**Returns**: `list[User]`


#### `AccessControl.check_permission(user_id: str, permission: Permission, resource_id: str | None = None)`

检查用户是否拥有指定权限。

Args:
    user_id: 用户 ID。
    permission: 需要的权限。
    resource_id: 可选的资源 ID（预留，用于未来细粒度资源控制）。

Returns:
    True 表示放行，False 表示拒绝。

**Returns**: `bool`


#### `AccessControl.require(permission: Permission)`

返回一个 FastAPI Depends 可用的权限校验函数。

用法::

    @router.get("/admin/users")
    async def list_users(
        _perm: None = Depends(acl.require(Permission.VIEW_USERS)),
    ):
        ...

**Returns**: `Callable[Ellipsis, Any]`


#### `AccessControl.require_permission(permission: Permission)`

装饰器版本的权限校验（用于非 FastAPI 场景）。

用法::

    @acl.require_permission(Permission.MANAGE_SYSTEM)
    async def do_admin_work(user_id: str):
        ...

**Returns**: `Callable[Ellipsis, Any]`


### `get_access_control()`

获取全局 AccessControl 实例（懒初始化）。

**Returns**: `AccessControl`

---

### `reset_access_control()`

重置全局实例（仅供测试使用）。

**Returns**: `None`

---

## backend.auth.models

**文件**: `backend\auth\models.py`

角色、权限与用户模型。

### class `Role`

**继承**: `str`, `Enum`

系统角色。

### class `Permission`

**继承**: `str`, `Enum`

细粒度权限枚举。

### class `User`

**继承**: `BaseModel`

系统用户。

#### `User.has_permission(permission: Permission)`

检查用户是否拥有指定权限。

权限来源（任一满足即为拥有）：
1. 角色默认权限
2. 额外授予的权限

**Returns**: `bool`


#### `User.get_all_permissions()`

获取用户的有效权限集合。

**Returns**: `set[Permission]`


## backend.database.base

**文件**: `backend\database\base.py`

CityFlow 数据库引擎与会话管理。

使用 SQLAlchemy 2.0 异步引擎 + AsyncSession。
数据库连接参数从 backend.config.settings.database 读取。

### class `Base`

**继承**: `DeclarativeBase`

SQLAlchemy 声明式基类。

### `async get_db()`

FastAPI 依赖：为每个请求提供一个 AsyncSession。

**Returns**: `AsyncGenerator[AsyncSession, None]`

---

## backend.database.models

**文件**: `backend\database\models.py`

CityFlow 数据库 ORM 模型。

对应 PostgreSQL 表：
    users, routes, route_steps, dialogues, user_preferences

使用 SQLAlchemy 2.0 mapped_column 风格。

### class `User`

**继承**: `Base`

用户。

### class `Route`

**继承**: `Base`

规划路线。

### class `RouteStep`

**继承**: `Base`

路线中的单个步骤。

### class `Dialogue`

**继承**: `Base`

对话消息。

### class `UserPreference`

**继承**: `Base`

用户偏好设置（按类型存储）。

### class `AuditLog`

**继承**: `Base`

审计日志。

## backend.database.pool

**文件**: `backend\database\pool.py`

CityFlow 数据库连接池管理。

基于 SQLAlchemy 异步引擎的连接池，提供：
- 连接池生命周期管理（启动 / 关闭）
- 连接健康检查
- 连接池统计信息

与 backend.database.base 互补：base 负责引擎和会话工厂，
本模块负责池的生命周期与监控。

### class `PoolStats`

连接池统计快照。

#### `PoolStats.utilization()`

连接池使用率（0.0 ~ 1.0）。

**Returns**: `float`


### class `DatabasePool`

数据库连接池。

Args:
    database_url: 异步数据库连接 URL。
    pool_size: 核心连接数。
    max_overflow: 超出 pool_size 后的最大临时连接数。
    pool_recycle: 连接回收周期（秒），避免数据库端超时断开。

#### `async DatabasePool.start()`

初始化引擎与会话工厂。幂等，重复调用无副作用。

**Returns**: `None`


#### `async DatabasePool.close()`

关闭连接池，释放所有连接。幂等。

**Returns**: `None`


#### `async DatabasePool.get_session()`

获取数据库会话（上下文管理器）。

用法::

    async for session in pool.get_session():
        ...

**Returns**: `AsyncGenerator[AsyncSession, None]`


#### `async DatabasePool.ping()`

执行轻量级查询验证连接可用性。

**Returns**: `bool`


#### `DatabasePool.get_stats()`

获取连接池统计快照。

**Returns**: `PoolStats`


#### `DatabasePool.get_stats_dict()`

以字典形式返回统计信息。

**Returns**: `dict[str, Any]`


### `get_database_pool()`

获取全局数据库连接池单例。

**Returns**: `DatabasePool`

---

## backend.database.repository

**文件**: `backend\database\repository.py`

CityFlow 数据访问层（Repository 模式）。

所有方法使用 AsyncSession，配合 FastAPI 的依赖注入使用。

### class `UserRepository`

用户数据访问。

#### `UserRepository.__init__(db: AsyncSession)`

**Returns**: `None`


#### `async UserRepository.create(preferences: dict | None = None)`

创建用户，返回 User 对象。

**Returns**: `User`


#### `async UserRepository.get(user_id: uuid.UUID)`

按 ID 获取用户。

**Returns**: `User | None`


#### `async UserRepository.update_preferences(user_id: uuid.UUID, preferences: dict)`

更新用户偏好。

**Returns**: `User | None`


### class `RouteRepository`

路线数据访问。

#### `RouteRepository.__init__(db: AsyncSession)`

**Returns**: `None`


#### `async RouteRepository.create(user_input: str, route_data: dict, user_id: uuid.UUID | None = None, narrative: dict | None = None)`

创建路线。

**Returns**: `Route`


#### `async RouteRepository.get(route_id: uuid.UUID)`

按 ID 获取路线（含步骤和对话）。

**Returns**: `Route | None`


#### `async RouteRepository.get_by_user(user_id: uuid.UUID, limit: int = 10, offset: int = 0)`

获取用户的路线列表（按创建时间倒序）。

**Returns**: `Sequence[Route]`


#### `async RouteRepository.update(route_id: uuid.UUID, route_data: dict, narrative: dict | None = None)`

更新路线数据。

**Returns**: `Route | None`


#### `async RouteRepository.update_status(route_id: uuid.UUID, status: str)`

更新路线状态（active/archived/deleted）。

**Returns**: `Route | None`


#### `async RouteRepository.delete(route_id: uuid.UUID)`

删除路线（级联删除步骤和对话）。

**Returns**: `bool`


### class `RouteStepRepository`

路线步骤数据访问。

#### `RouteStepRepository.__init__(db: AsyncSession)`

**Returns**: `None`


#### `async RouteStepRepository.bulk_create(route_id: uuid.UUID, steps: list[dict])`

批量创建路线步骤。

steps 中每个 dict 应包含：
    step_index, poi_id, poi_name, arrival_time,
    departure_time, travel_from_prev

**Returns**: `list[RouteStep]`


#### `async RouteStepRepository.get_by_route(route_id: uuid.UUID)`

获取路线的所有步骤（按 step_index 排序）。

**Returns**: `Sequence[RouteStep]`


#### `async RouteStepRepository.replace_all(route_id: uuid.UUID, steps: list[dict])`

替换路线的全部步骤（先删后插）。

**Returns**: `list[RouteStep]`


### class `DialogueRepository`

对话数据访问。

#### `DialogueRepository.__init__(db: AsyncSession)`

**Returns**: `None`


#### `async DialogueRepository.add_message(route_id: uuid.UUID, session_id: str, role: str, content: str, metadata: dict | None = None)`

添加一条对话消息。

**Returns**: `Dialogue`


#### `async DialogueRepository.get_session_messages(session_id: str, limit: int = 100)`

获取会话的全部消息（按时间排序）。

**Returns**: `Sequence[Dialogue]`


#### `async DialogueRepository.get_route_dialogues(route_id: uuid.UUID)`

获取路线关联的所有对话。

**Returns**: `Sequence[Dialogue]`


### class `UserPreferenceRepository`

用户偏好数据访问。

#### `UserPreferenceRepository.__init__(db: AsyncSession)`

**Returns**: `None`


#### `async UserPreferenceRepository.upsert(user_id: uuid.UUID, preference_type: str, preference_value: dict)`

插入或更新用户偏好。

**Returns**: `UserPreference`


#### `async UserPreferenceRepository.get(user_id: uuid.UUID, preference_type: str)`

获取指定类型的偏好。

**Returns**: `UserPreference | None`


#### `async UserPreferenceRepository.get_all(user_id: uuid.UUID)`

获取用户的全部偏好。

**Returns**: `Sequence[UserPreference]`


## backend.di.container

**文件**: `backend\di\container.py`

CityFlow 依赖注入容器。

支持三种注册方式：
- 实例注册：直接传入已构造的对象（可选单例）
- 工厂注册：传入 callable，每次 resolve 时调用
- 类型注册：传入类，容器自动构造（通过 inspect 解析 __init__ 参数）

### class `DIContainer`

依赖注入容器。

#### `DIContainer.__init__()`

**Returns**: `None`


#### `DIContainer.register(name: str, instance: Any)`

注册一个已构造的服务实例。

Parameters
----------
name:
    服务名称，resolve 时使用。
instance:
    服务实例。
singleton:
    若为 True，实例存入单例池，多次 resolve 返回同一对象。

**Returns**: `None`


#### `DIContainer.register_factory(name: str, factory: Callable[Ellipsis, Any])`

注册工厂函数。

每次 resolve 时都会调用 factory()，适合需要短生命周期的对象
（如数据库会话、HTTP 客户端）。

**Returns**: `None`


#### `DIContainer.register_class(name: str)`

注册一个类，容器在 resolve 时自动构造。

构造参数通过递归解析 __init__ 的类型注解自动注入。

**Returns**: `None`


#### `DIContainer.resolve(name: str)`

按名称解析服务。

查找顺序：单例 -> 实例 -> 工厂 -> 类型自动构造。

**Returns**: `Any`


#### `DIContainer.resolve_type()`

按类型解析服务（使用类名作为键）。

**Returns**: `T`


#### `DIContainer.reset()`

清空所有注册（用于测试）。

**Returns**: `None`


### class `ServiceNotFoundError`

**继承**: `KeyError`

服务未注册时抛出。

### `get_container()`

获取全局 DI 容器（懒初始化）。

**Returns**: `DIContainer`

---

### `reset_container()`

重置全局容器（用于测试）。

**Returns**: `None`

---

### `inject()`

注入装饰器：自动从容器中解析服务并传入函数。

用法::

    @inject("intent_parser", "route_solver")
    async def plan_route(intent_parser, route_solver, user_input: str):
        ...

装饰后调用 ``plan_route(user_input="...")`` 即可，
intent_parser 和 route_solver 会自动注入。

**Returns**: `Callable[Ellipsis, Any]`

---

## backend.di.registry

**文件**: `backend\di\registry.py`

CityFlow 服务注册表。

集中注册所有核心服务到 DI 容器。
应用启动时调用 ``register_services()`` 完成初始化。

### `register_services()`

注册所有核心服务到 DI 容器。

- 单例服务：IntentParser, RouteSolver, NarrativeGenerator
- 工厂服务：db_session, http_pool（每次 resolve 创建新实例）

**Returns**: `None`

---

## backend.docs.__init__

**文件**: `backend\docs\__init__.py`

自定义 OpenAPI schema 生成与文档页面端点。

### `custom_openapi(app: FastAPI)`

生成带自定义扩展字段的 OpenAPI schema（带缓存）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| app | FastAPI | - | - |

**Returns**: `dict`

---

### `register_docs_endpoints(app: FastAPI)`

注册 /docs 和 /redoc 自定义端点（需先禁用默认端点）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| app | FastAPI | - | - |

**Returns**: `None`

---

## backend.events.decorators

**文件**: `backend\events\decorators.py`

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

### `emit_event(event_type: str)`

事件发射装饰器。

被装饰的函数执行完毕后，自动向全局事件总线发布一条事件。
支持同步和异步函数。

Args:
    event_type: 要发布的事件类型字符串
    data_fn: 可选的自定义数据提取函数，签名
        ``(result, *args, **kwargs) -> dict``。
        如果不提供，使用默认的 ``{"result": result}``
        作为事件数据。

Returns:
    装饰后的函数，签名和行为与原函数一致。

Example::

    @emit_event(EventType.ROUTE_PLANNED)
    async def plan_route(user_input: str) -> dict:
        return {"route_id": "r-001"}

    # 自定义数据提取
    def extract_route_data(result, *args, **kwargs):
        return {"route_id": result["route_id"], "user_input": args[0]}

    @emit_event(EventType.ROUTE_PLANNED, data_fn=extract_route_data)
    async def plan_route_v2(user_input: str) -> dict:
        return {"route_id": "r-001"}

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| event_type | str | - | - |

**Returns**: `Callable[List(elts=[Name(id='F', ctx=Load())], ctx=Load()), F]`

---

## backend.events.handlers

**文件**: `backend\events\handlers.py`

CityFlow 事件处理器注册。

集中注册所有内置事件处理器。在应用启动时调用
:func:`setup_event_handlers` 一次即可。

新增处理器的步骤：
1. 在本模块编写 ``async def handle_xxx(event)`` 或同步函数
2. 在 :func:`setup_event_handlers` 中添加对应的订阅调用

### `setup_event_handlers()`

注册所有内置事件处理器。

应在应用启动时调用一次。处理器分为两类：

- **同步处理器**：用于轻量级操作（日志、指标记录）
- **异步处理器**：用于 I/O 密集操作（通知推送、数据持久化）

**Returns**: `None`

---

### `handle_route_planned_metrics(event: Event)`

路线规划完成 -> 记录指标（同步）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| event | Event | - | - |

**Returns**: `None`

---

### `async handle_route_planned_notify(event: Event)`

路线规划完成 -> 推送通知（异步）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| event | Event | - | - |

**Returns**: `None`

---

### `async handle_user_feedback_record(event: Event)`

用户反馈 -> 持久化记录（异步）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| event | Event | - | - |

**Returns**: `None`

---

### `handle_system_error_alert(event: Event)`

系统错误 -> 发送告警（同步）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| event | Event | - | - |

**Returns**: `None`

---

## backend.events.types

**文件**: `backend\events\types.py`

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

### class `EventType`

**继承**: `StrEnum`

事件类型常量。

集中管理所有事件类型的字符串标识，防止硬编码散落各处。

### class `RoutePlannedEvent`

**继承**: `Event`

路线规划完成事件。

当路线求解器成功生成路线后发布，供通知、指标、缓存等
下游处理器消费。

### class `RouteAdjustedEvent`

**继承**: `Event`

路线调整事件。

当用户通过对话调整已有路线后发布。

### class `UserFeedbackEvent`

**继承**: `Event`

用户反馈事件。

当用户提交评价、纠错或其他反馈时发布。

### class `SystemErrorEvent`

**继承**: `Event`

系统错误事件。

当系统内部发生未预期错误时发布，供告警和日志处理器消费。

## backend.events.__init__

**文件**: `backend\events\__init__.py`

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

### `setup_events()`

初始化事件系统：注册所有内置事件处理器。

应在 FastAPI 应用启动时调用一次。

**Returns**: `None`

---

## backend.gateway.auth

**文件**: `backend\gateway\auth.py`

JWT 认证中间件。

拦截请求，验证 Bearer token，将解析出的用户信息注入 ``request.state``。
白名单路径跳过认证，开发环境可配置为可选认证。

### class `AuthMiddleware`

**继承**: `BaseHTTPMiddleware`

JWT 认证中间件。

Args:
    app: ASGI 应用。
    secret_key: JWT 签名密钥。
    algorithm: JWT 算法，默认 HS256。
    whitelist: 白名单路径集合，这些路径不校验 token。
    optional: 为 ``True`` 时缺少 token 不报错（开发模式）。

#### `AuthMiddleware.__init__(app, secret_key: str = 'change-me-in-production', algorithm: str = 'HS256', whitelist: set[str] | None = None, optional: bool = False)`


#### `async AuthMiddleware.dispatch(request: Request, call_next)`


### `create_token(payload: dict[str, Any], secret_key: str, expires_in: int = 3600, algorithm: str = 'HS256')`

生成 JWT token（辅助函数）。

Args:
    payload: token 载荷，需包含 ``sub`` 或 ``user_id``。
    secret_key: 签名密钥。
    expires_in: 过期时间（秒），默认 1 小时。
    algorithm: 算法。

Returns:
    编码后的 JWT 字符串。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| payload | dict[str, Any] | - | - |
| secret_key | str | - | - |
| expires_in | int | 3600 | - |
| algorithm | str | 'HS256' | - |

**Returns**: `str`

---

## backend.gateway.main

**文件**: `backend\gateway\main.py`

CityFlow API 网关入口。

将请求路由转发到后端微服务（POI、路线、对话），
集成 JWT 认证和速率限制中间件。

用法::

    # 作为独立服务运行
    uvicorn backend.gateway.main:app --port 9000

    # 或在代码中创建
    from backend.gateway.main import create_gateway_app
    app = create_gateway_app()

### `create_gateway_app()`

创建网关 FastAPI 应用。

Args:
    router: 自定义路由器，为 ``None`` 时使用默认配置。
    jwt_secret: JWT 签名密钥。
    auth_optional: 认证是否可选（开发模式为 ``True``）。
    rate_limit: 每分钟最大请求数。

Returns:
    配置好的 FastAPI 实例。

**Returns**: `FastAPI`

---

## backend.gateway.rate_limit

**文件**: `backend\gateway\rate_limit.py`

网关级速率限制中间件。

基于客户端 IP 的滑动窗口限流，支持 X-Forwarded-For 等反向代理头。
与 ``backend.middleware.rate_limit.RateLimitMiddleware`` 功能类似，
但专为网关场景设计，响应头格式对齐网关惯例。

### class `GatewayRateLimitMiddleware`

**继承**: `BaseHTTPMiddleware`

网关速率限制中间件。

Args:
    app: ASGI 应用。
    requests_per_minute: 每个客户端 IP 每分钟最大请求数。
    whitelist_paths: 不限流的路径前缀列表。

#### `GatewayRateLimitMiddleware.__init__(app, requests_per_minute: int = 60, whitelist_paths: list[str] | None = None)`


#### `async GatewayRateLimitMiddleware.dispatch(request: Request, call_next)`


## backend.gateway.router

**文件**: `backend\gateway\router.py`

网关路由配置。

基于前缀匹配将请求转发到对应的后端微服务。
支持精确匹配和正则模式匹配。

### class `RouteTarget`

路由目标。

### class `GatewayRouter`

网关路由器。

按注册顺序匹配路由，首个匹配生效。
支持两种模式：
- 精确前缀匹配（默认）：`/api/poi` 匹配 `/api/poi/xxx`
- 正则匹配：以 `^` 开头的 pattern 按正则处理

用法::

    router = GatewayRouter()
    router.register("poi", "http://localhost:8001", prefix="/api/poi")
    target = router.match("/api/poi/search?keyword=故宫", "GET")

#### `GatewayRouter.__init__()`

**Returns**: `None`


#### `GatewayRouter.register(service: str, base_url: str, prefix: str = '', methods: list[str] | None = None, strip_prefix: bool = True)`

注册后端服务。

Args:
    service: 服务名称（如 ``poi``）。
    base_url: 服务基础 URL（如 ``http://localhost:8001``）。
    prefix: URL 前缀（如 ``/api/poi``）。
    methods: 允许的 HTTP 方法，默认全部。
    strip_prefix: 转发时是否剥离前缀。

**Returns**: `None`


#### `GatewayRouter.match(path: str, method: str)`

匹配路由，返回 (目标, 转发路径)。

Args:
    path: 请求路径（如 ``/api/poi/search``）。
    method: HTTP 方法。

Returns:
    匹配成功返回 ``(RouteTarget, 转发后路径)``，否则 ``None``。

**Returns**: `tuple[RouteTarget, str] | None`


#### `GatewayRouter.get_service_url(service: str)`

获取服务的基础 URL。

**Returns**: `str | None`


#### `GatewayRouter.service_names()`

已注册的服务名列表。

**Returns**: `list[str]`


### `get_gateway_router()`

获取默认网关路由器实例。

根据环境变量或配置注册后端服务。可在启动时调用
``router.register(...)`` 添加更多服务。

**Returns**: `GatewayRouter`

---

### `setup_default_routes(poi_url: str = 'http://localhost:8001', route_url: str = 'http://localhost:8002', dialogue_url: str = 'http://localhost:8003')`

用默认地址配置路由。

Args:
    poi_url: POI 服务地址。
    route_url: 路线服务地址。
    dialogue_url: 对话服务地址。

Returns:
    配置好的路由器实例。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi_url | str | 'http://localhost:8001' | - |
| route_url | str | 'http://localhost:8002' | - |
| dialogue_url | str | 'http://localhost:8003' | - |

**Returns**: `GatewayRouter`

---

## backend.graphql.config

**文件**: `backend\graphql\config.py`

CityFlow GraphQL 配置 -- Schema 工厂。

### `create_graphql_schema()`

创建并返回 GraphQL Schema 实例。

启用 auto_camel_case 使得 Python 的 snake_case 字段名
在 GraphQL 端自动转为 camelCase（如 avg_price -> avgPrice）。

**Returns**: `strawberry.Schema`

---

## backend.graphql.resolvers

**文件**: `backend\graphql\resolvers.py`

CityFlow GraphQL Resolvers -- 调用已有服务层实现查询与变更。

每个 resolver 对应 schema.py 中的一个字段，内部调用
backend.services 下的 data_service / intent_parser / solver / narrator / dialogue。

### `async resolve_pois(region: Optional[str] = None, category: Optional[str] = None, limit: int = 10)`

查询 POI 列表。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| region | Optional[str] | None | - |
| category | Optional[str] | None | - |
| limit | int | 10 | - |

**Returns**: `list[POI]`

---

### `async resolve_poi(id: str)`

查询单个 POI。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| id | str | - | - |

**Returns**: `Optional[POI]`

---

### `async resolve_routes(limit: int = 10)`

查询已缓存的路线列表。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| limit | int | 10 | - |

**Returns**: `list[Route]`

---

### `async resolve_route(id: str)`

查询单条已缓存路线。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| id | str | - | - |

**Returns**: `Optional[Route]`

---

### `async resolve_plan_route(user_input: str)`

规划路线 -- 调用 intent_parser -> filters -> solver -> narrator 完整流程。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| user_input | str | - | - |

**Returns**: `Route`

---

### `async resolve_adjust_route(route_id: str, instruction: str)`

调整路线 -- 调用 dialogue engine。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| route_id | str | - | - |
| instruction | str | - | - |

**Returns**: `DialogueResponse`

---

## backend.graphql.schema

**文件**: `backend\graphql\schema.py`

CityFlow GraphQL Schema -- Strawberry 类型定义。

所有类型与 backend/main.py 中的 Pydantic 响应模型保持一致。

### class `EmotionTags`

POI 情绪标签（6维，取值 0~1）。

### class `POIConstraints`

POI 约束条件。

### class `TravelInfo`

交通信息。

### class `POI`

兴趣点。

### class `RouteStep`

路线中的单个步骤。

### class `NarrativeStep`

路线文案。

### class `TotalCost`

费用估算。

### class `Route`

完整路线规划结果。

### class `ChangeRecord`

对话调整的变更记录。

### class `DialogueResponse`

对话调整的响应。

### class `Query`

#### `async Query.pois(region: Optional[str] = None, category: Optional[str] = None, limit: int = 10)`

**Returns**: `list[POI]`


#### `async Query.poi(id: str)`

**Returns**: `Optional[POI]`


#### `async Query.routes(limit: int = 10)`

**Returns**: `list[Route]`


#### `async Query.route(id: str)`

**Returns**: `Optional[Route]`


### class `Mutation`

#### `async Mutation.plan_route(user_input: str)`

**Returns**: `Route`


#### `async Mutation.adjust_route(route_id: str, instruction: str)`

**Returns**: `DialogueResponse`


## backend.i18n.__init__

**文件**: `backend\i18n\__init__.py`

CityFlow 国际化（i18n）框架。

使用方式：
    from backend.i18n import t, get_i18n

    # 翻译
    msg = t("route.planning")

    # 带参数
    msg = t("route.distance", km=5.2)

    # 切换语言
    get_i18n().set_locale("en_US")

### class `I18n`

国际化管理器。

从 JSON 翻译文件加载多语言文本，支持点分键路径和字符串格式化参数。

#### `I18n.__init__(locale_dir: str | Path | None = None)`

**Returns**: `None`


#### `I18n.reload()`

重新加载所有翻译文件（热更新用）。

**Returns**: `None`


#### `I18n.set_locale(locale: str)`

设置当前语言。

Args:
    locale: 语言代码，如 "zh_CN"、"en_US"。

Raises:
    ValueError: 如果 locale 不在已加载的翻译中。

**Returns**: `None`


#### `I18n.get_locale()`

获取当前语言代码。

**Returns**: `str`


#### `I18n.get_available_locales()`

获取所有已加载的语言代码列表。

**Returns**: `list[str]`


#### `I18n.translate(key: str)`

翻译指定 key。

使用点分路径访问嵌套字典，如 "route.planning"。
支持 str.format() 参数插值。

Args:
    key: 点分翻译键，如 "common.success"。
    **kwargs: 格式化参数。

Returns:
    翻译后的字符串；如果找不到则返回 key 本身。

**Returns**: `str`


### `get_i18n()`

获取全局 I18n 单例。

**Returns**: `I18n`

---

### `t(key: str)`

翻译快捷函数。

等价于 ``get_i18n().translate(key, **kwargs)``。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| key | str | - | - |

**Returns**: `str`

---

## backend.middleware.compression

**文件**: `backend\middleware\compression.py`

CityFlow HTTP 响应压缩中间件。

根据客户端 Accept-Encoding 头自动压缩响应体。
支持 gzip 和 deflate 两种压缩方式。

### class `CompressionMiddleware`

**继承**: `BaseHTTPMiddleware`

HTTP 响应 gzip/deflate 压缩中间件。

仅在满足以下条件时压缩：
- 客户端声明支持对应编码
- 响应状态码为 2xx
- 响应体大于最小阈值
- Content-Type 不是已压缩格式

#### `CompressionMiddleware.__init__(app: Callable, minimum_size: int = _MIN_COMPRESS_SIZE, compresslevel: int = 6)`

**Returns**: `None`


#### `async CompressionMiddleware.dispatch(request: Request, call_next: Callable)`

拦截响应，按需压缩。

**Returns**: `Response`


## backend.middleware.config

**文件**: `backend\middleware\config.py`

配置注入中间件。

将全局 Settings 实例挂载到 request.state.config，
方便路由/下游中间件直接读取配置，无需重复调用 get_settings()。

### class `ConfigMiddleware`

**继承**: `BaseHTTPMiddleware`

将配置注入到 request.state.config。

#### `async ConfigMiddleware.dispatch(request: Request, call_next)`


## backend.middleware.error_handler

**文件**: `backend\middleware\error_handler.py`

CityFlow 全局异常处理器。

注册到 FastAPI app 后，所有 CityFlowException 和未捕获异常
都会被统一拦截并返回标准化 JSON 响应。

### `async cityflow_exception_handler(request: Request, exc: CityFlowException)`

处理 CityFlowException -- 业务异常。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| request | Request | - | - |
| exc | CityFlowException | - | - |

**Returns**: `JSONResponse`

---

### `async general_exception_handler(request: Request, exc: Exception)`

兜底处理未预期异常，不向客户端暴露内部细节。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| request | Request | - | - |
| exc | Exception | - | - |

**Returns**: `JSONResponse`

---

### `setup_error_handlers(app: FastAPI)`

将异常处理器注册到 FastAPI 应用。

调用一次即可，放在 app 创建之后、路由注册之前或之后均可。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| app | FastAPI | - | - |

**Returns**: `None`

---

## backend.middleware.locale

**文件**: `backend\middleware\locale.py`

CityFlow 本地化中间件。

从请求的 Accept-Language 头解析语言偏好，设置当前请求的语言上下文，
并在响应中添加 Content-Language 头。

### class `LocaleMiddleware`

**继承**: `BaseHTTPMiddleware`

本地化中间件。

处理流程：
1. 从 Accept-Language 请求头解析语言偏好
2. 将语言设置到 i18n 上下文（contextvars，异步安全）
3. 将语言注入 request.state.locale 供路由使用
4. 在响应头中添加 Content-Language

#### `async LocaleMiddleware.dispatch(request: Request, call_next: Callable)`

**Returns**: `Response`


## backend.middleware.performance

**文件**: `backend\middleware\performance.py`

CityFlow 性能监控中间件。

为每个请求注入唯一 ID 和耗时信息，自动记录慢请求日志。
响应头中携带 ``X-Request-ID`` 和 ``X-Response-Time``，方便前端 / 网关追踪。

### class `PerformanceMiddleware`

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

#### `PerformanceMiddleware.__init__(app, slow_threshold: float = _DEFAULT_SLOW_THRESHOLD, request_id_header: str = 'X-Request-ID')`

**Returns**: `None`


#### `async PerformanceMiddleware.dispatch(request: Request, call_next)`

拦截请求，注入性能信息。

**Returns**: `Response`


## backend.middleware.pipeline

**文件**: `backend\middleware\pipeline.py`

CityFlow 中间件管道。

提供可编程的中间件链式执行引擎，支持：
- 动态添加/移除中间件
- 条件中间件（按请求特征决定是否执行）
- 每个中间件的性能统计（请求数、耗时、错误率、分位数）

### class `MiddlewareHandler`

**继承**: `Protocol`

中间件处理函数签名。

### class `MiddlewareStats`

单个中间件的运行统计。

#### `MiddlewareStats.avg_time()`

平均耗时（秒）。

**Returns**: `float`


#### `MiddlewareStats.error_rate()`

错误率。

**Returns**: `float`


#### `MiddlewareStats.percentile(p: float)`

计算第 p 分位数（p 取 0~100）。

**Returns**: `float`


#### `MiddlewareStats.to_dict()`

导出为字典。

**Returns**: `dict[str, Any]`


### class `_MiddlewareEntry`

管道中的一个中间件条目。

### class `MiddlewarePipeline`

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

#### `MiddlewarePipeline.__init__()`

**Returns**: `None`


#### `MiddlewarePipeline.add(middleware: MiddlewareHandler, name: str | None = None)`

添加中间件到管道末尾。

Args:
    middleware: 中间件处理函数，签名为 ``(request, call_next) -> Response``。
    name: 中间件名称（用于统计展示），默认使用函数名。

Returns:
    self，支持链式调用。

**Returns**: `MiddlewarePipeline`


#### `MiddlewarePipeline.remove(name: str)`

按名称移除中间件。

Args:
    name: 要移除的中间件名称。

Returns:
    是否成功移除。

**Returns**: `bool`


#### `MiddlewarePipeline.names()`

当前管道中所有中间件的名称（按执行顺序）。

**Returns**: `list[str]`


#### `async MiddlewarePipeline.execute(request: Request, call_next: Callable[Ellipsis, Any])`

执行中间件管道。

中间件从后向前组装，从前往后执行，形成洋葱模型。
每个中间件的签名必须为 ``(request, call_next) -> Response``。

Args:
    request: 当前 HTTP 请求。
    call_next: 最终处理函数（通常是路由处理器）。

Returns:
    HTTP 响应。

**Returns**: `Response`


#### `MiddlewarePipeline.get_stats(name: str)`

获取单个中间件的统计信息。

**Returns**: `dict[str, Any] | None`


#### `MiddlewarePipeline.get_all_stats()`

获取所有中间件的统计信息。

**Returns**: `dict[str, dict[str, Any]]`


#### `MiddlewarePipeline.reset_stats()`

重置所有统计信息。

**Returns**: `None`


#### `MiddlewarePipeline.get_stats_summary()`

获取管道整体统计摘要。

Returns:
    包含管道总请求数、总错误数、最慢中间件等信息的字典。

**Returns**: `dict[str, Any]`


### class `ConditionalMiddleware`

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

#### `ConditionalMiddleware.__init__(condition: Callable[List(elts=[Name(id='Request', ctx=Load())], ctx=Load()), bool], middleware: MiddlewareHandler)`

**Returns**: `None`


## backend.middleware.prometheus

**文件**: `backend\middleware\prometheus.py`

Prometheus 指标采集中间件。

自动为每个 HTTP 请求记录计数和延迟，写入 Prometheus 指标。
``/metrics`` 端点自身不计入统计，避免递归干扰。

### class `PrometheusMiddleware`

**继承**: `BaseHTTPMiddleware`

自动将每个 HTTP 请求的计数和延迟写入 Prometheus 指标。

#### `async PrometheusMiddleware.dispatch(request: Request, call_next)`

**Returns**: `Response`


## backend.middleware.rate_limit

**文件**: `backend\middleware\rate_limit.py`

速率限制中间件。

基于客户端 IP 的滑动窗口速率限制。使用内存存储，适合单实例部署。
如需多实例共享，应替换为 Redis 等外部存储。

### class `RateLimitMiddleware`

**继承**: `BaseHTTPMiddleware`

滑动窗口速率限制。

Args:
    app: ASGI 应用。
    requests_per_minute: 每个 IP 每分钟允许的最大请求数。
    cleanup_interval: 清理过期记录的间隔（秒）。

#### `RateLimitMiddleware.__init__(app, requests_per_minute: int = 60, cleanup_interval: int = 300)`


#### `async RateLimitMiddleware.dispatch(request: Request, call_next)`


## backend.middleware.security

**文件**: `backend\middleware\security.py`

安全响应头中间件。

为所有 HTTP 响应注入标准安全头，防止常见浏览器端攻击。

### class `SecurityHeadersMiddleware`

**继承**: `BaseHTTPMiddleware`

注入安全响应头。

适用于 API + 前端静态文件的混合服务场景。
如果仅提供纯 API 服务，可移除 X-Frame-Options 等与浏览器渲染相关的头。

#### `async SecurityHeadersMiddleware.dispatch(request: Request, call_next)`


## backend.middleware.session

**文件**: `backend\middleware\session.py`

CityFlow 会话中间件。

自动为请求创建 / 注入会话，支持：
- Cookie 读取 session_id
- Header (X-Session-ID) 读取
- 无会话时自动创建
- 响应时设置 Cookie 和 Header

### class `SessionMiddleware`

**继承**: `BaseHTTPMiddleware`

会话中间件：为每个请求注入 session_id。

优先级：Cookie > Header > 自动创建。

#### `async SessionMiddleware.dispatch(request: Request, call_next)`

**Returns**: `Response`


## backend.middleware.shutdown

**文件**: `backend\middleware\shutdown.py`

CityFlow 停机感知中间件。

将每个 HTTP 请求的生命周期与 GracefulShutdown 管理器绑定：
- 请求进入时注册为活跃请求
- 请求结束时（无论成功/失败）注销
- 停机期间拒绝新请求，返回 503 Service Unavailable

使用方式::

    from backend.middleware.shutdown import ShutdownMiddleware

    app.add_middleware(ShutdownMiddleware)

### class `ShutdownMiddleware`

**继承**: `BaseHTTPMiddleware`

停机感知中间件。

功能：
1. 为每个请求生成短 ID 并注册到停机管理器
2. 停机期间对新请求返回 503
3. 请求完成（成功或异常）后自动注销

在中间件链中的位置建议：靠近最外层，早于业务中间件，
以便尽早拒绝停机期间的请求。

#### `async ShutdownMiddleware.dispatch(request: Request, call_next)`

**Returns**: `Response`


## backend.middleware.validation

**文件**: `backend\middleware\validation.py`

输入验证中间件。

在请求到达路由处理函数之前，对查询参数和请求体进行基本的安全检查。
这不是输入验证的唯一防线——路由层的 Pydantic 模型校验同样重要。

### class `InputValidationMiddleware`

**继承**: `BaseHTTPMiddleware`

基本的注入 / XSS 检测中间件。

对查询参数和 JSON 请求体进行正则匹配，拦截明显的攻击模式。
不替代参数化查询或 Pydantic 校验，而是作为纵深防御的一层。

Args:
    app: ASGI 应用。
    max_body_size: 请求体最大字节数（默认 10 MB）。

#### `InputValidationMiddleware.__init__(app, max_body_size: int = ...)`


#### `async InputValidationMiddleware.dispatch(request: Request, call_next)`


## backend.middleware.version

**文件**: `backend\middleware\version.py`

API 版本控制中间件。

### class `APIVersionMiddleware`

**继承**: `BaseHTTPMiddleware`

API版本中间件。

支持两种版本控制方式：
1. URL路径版本控制（/api/v1/...、/api/v2/...）
2. 请求头版本控制（X-API-Version: v1）

优先级：URL路径 > 请求头 > 默认版本

#### `async APIVersionMiddleware.dispatch(request: Request, call_next)`


## backend.models.schemas

**文件**: `backend\models\schemas.py`

### class `DataQuery`

**继承**: `BaseModel`

数据查询请求。

### class `DataResponse`

**继承**: `BaseModel`

数据查询响应。

### class `ChatRequest`

**继承**: `BaseModel`

LLM对话请求。

### class `ChatResponse`

**继承**: `BaseModel`

LLM对话响应。

## backend.monitoring.error_filter

**文件**: `backend\monitoring\error_filter.py`

Sentry 事件过滤器。

在事件发送到 Sentry 之前进行过滤，减少噪音、降低成本。
过滤逻辑：
  - 静默 KeyboardInterrupt / SystemExit 等非业务异常
  - 静默速率限制等预期可恢复错误
  - 过滤健康检查等高频低价值事务
  - 脱敏请求头中的敏感信息

### `before_send(event: dict[str, Any], hint: dict[str, Any])`

Sentry before_send 回调 — 过滤异常事件。

返回 None 表示丢弃该事件，返回 event 表示正常上报。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| event | dict[str, Any] | - | - |
| hint | dict[str, Any] | - | - |

**Returns**: `dict[str, Any] | None`

---

### `before_send_transaction(event: dict[str, Any], hint: dict[str, Any])`

Sentry before_send_transaction 回调 — 过滤事务事件。

过滤健康检查等高频低价值路径。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| event | dict[str, Any] | - | - |
| hint | dict[str, Any] | - | - |

**Returns**: `dict[str, Any] | None`

---

## backend.monitoring.metrics

**文件**: `backend\monitoring\metrics.py`

Prometheus 指标定义与工具函数。

### `track_request(method: str, endpoint: str, status: int, duration: float)`

记录一次 HTTP 请求的指标。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| method | str | - | - |
| endpoint | str | - | - |
| status | int | - | - |
| duration | float | - | - |

**Returns**: `None`

---

### `track_route_planning()`

路线规划完成时调用，计数 +1。

**Returns**: `None`

---

### `get_metrics()`

返回当前所有 Prometheus 指标的文本表示（供 /metrics 端点使用）。

**Returns**: `bytes`

---

## backend.monitoring.profiler

**文件**: `backend\monitoring\profiler.py`

性能分析装饰器，自动将端点耗时记录到 Prometheus Histogram。

### `profile_endpoint(endpoint: str)`

性能分析装饰器 —— 自动记录被装饰异步端点的执行耗时。

用法::

    @profile_endpoint("/api/plan")
    async def plan_route(request):
        ...

Args:
    endpoint: 端点路径标签，写入 Prometheus label。

Returns:
    装饰后的异步函数。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| endpoint | str | - | - |

**Returns**: `Callable[List(elts=[Subscript(value=Name(id='Callable', ctx=Load()), slice=Tuple(elts=[Constant(value=Ellipsis), Name(id='Any', ctx=Load())], ctx=Load()), ctx=Load())], ctx=Load()), Callable[Ellipsis, Any]]`

---

## backend.monitoring.sentry

**文件**: `backend\monitoring\sentry.py`

Sentry 初始化与辅助函数。

使用方式：
    在应用启动时调用 init_sentry()，之后可直接使用
    capture_exception / capture_message 上报事件。

    环境变量：
      SENTRY_DSN      — Sentry DSN（为空则不初始化）
      ENVIRONMENT      — 环境名，默认 development
      APP_VERSION      — 应用版本号，默认 1.0.0

### `init_sentry()`

初始化 Sentry SDK。

Returns:
    True 表示初始化成功，False 表示未配置 DSN 而跳过。

**Returns**: `bool`

---

### `capture_exception(error: Exception, context: dict[str, Any] | None = None)`

上报异常到 Sentry。

Args:
    error: 要上报的异常实例。
    context: 附加上下文信息，会写入 Sentry extra 字段。

Returns:
    Sentry event_id，未初始化时返回 None。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| error | Exception | - | - |
| context | dict[str, Any] | None | None | - |

**Returns**: `str | None`

---

### `capture_message(message: str, level: str = 'info', context: dict[str, Any] | None = None)`

上报消息到 Sentry。

Args:
    message: 消息内容。
    level: 日志级别 (debug/info/warning/error/fatal)。
    context: 附加上下文信息。

Returns:
    Sentry event_id，未初始化时返回 None。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| message | str | - | - |
| level | str | 'info' | - |
| context | dict[str, Any] | None | None | - |

**Returns**: `str | None`

---

### `set_user_context(user_id: str, email: str | None = None, username: str | None = None)`

设置当前请求的用户上下文。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| user_id | str | - | - |
| email | str | None | None | - |
| username | str | None | None | - |

**Returns**: `None`

---

### `add_breadcrumb(message: str, category: str = 'default', level: str = 'info', data: dict[str, Any] | None = None)`

添加面包屑（调试线索）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| message | str | - | - |
| category | str | 'default' | - |
| level | str | 'info' | - |
| data | dict[str, Any] | None | None | - |

**Returns**: `None`

---

## backend.routers.audit

**文件**: `backend\routers\audit.py`

CityFlow 审计日志 API。

提供审计日志的查询和导出接口。

### `async get_audit_logs(user_id: str | None = Query(...), action: AuditAction | None = Query(...), resource_type: str | None = Query(...), start_time: datetime | None = Query(...), end_time: datetime | None = Query(...), limit: int = Query(...), offset: int = Query(...))`

查询审计日志。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| user_id | str | None | Query(...) | - |
| action | AuditAction | None | Query(...) | - |
| resource_type | str | None | Query(...) | - |
| start_time | datetime | None | Query(...) | - |
| end_time | datetime | None | Query(...) | - |
| limit | int | Query(...) | - |
| offset | int | Query(...) | - |

**Returns**: `dict`

---

### `async export_audit_logs(format: Literal['json', 'csv'] = Query(...), start_time: datetime | None = Query(...), end_time: datetime | None = Query(...), limit: int = Query(...))`

导出审计日志。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| format | Literal['json', 'csv'] | Query(...) | - |
| start_time | datetime | None | Query(...) | - |
| end_time | datetime | None | Query(...) | - |
| limit | int | Query(...) | - |

**Returns**: `Response`

---

### `async get_audit_stats(start_time: datetime | None = Query(...), end_time: datetime | None = Query(...))`

审计日志统计。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| start_time | datetime | None | Query(...) | - |
| end_time | datetime | None | Query(...) | - |

**Returns**: `dict`

---

## backend.routers.data

**文件**: `backend\routers\data.py`

### `async get_data(dataset: str | None = Query(...), category: str | None = Query(...))`

通用数据集查询。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| dataset | str | None | Query(...) | - |
| category | str | None | Query(...) | - |

---

### `async get_poi(city: str | None = Query(...), category: str | None = Query(...))`

返回城市 POI 数据，支持城市和品类筛选。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| city | str | None | Query(...) | - |
| category | str | None | Query(...) | - |

---

### `async get_datasets()`

列出所有可用数据集。

---

### `async get_order(city: str | None = Query(...), category: str | None = Query(...), day_of_year: int | None = Query(...), hour: int | None = Query(...))`

返回 POI 交通流量快照，支持按城市/品类筛选。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| city | str | None | Query(...) | - |
| category | str | None | Query(...) | - |
| day_of_year | int | None | Query(...) | - |
| hour | int | None | Query(...) | - |

---

### `async get_road_traffic(city: str | None = Query(...), road_type: str | None = Query(...), day_of_year: int | None = Query(...), hour: int | None = Query(...))`

返回道路拥堵指数快照，支持按城市/路段类型筛选。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| city | str | None | Query(...) | - |
| road_type | str | None | Query(...) | - |
| day_of_year | int | None | Query(...) | - |
| hour | int | None | Query(...) | - |

---

## backend.routers.health

**文件**: `backend\routers\health.py`

CityFlow 健康检查路由。

提供基础健康检查和详细健康状态端点，用于：
- 负载均衡器探活（Nginx health_check）
- Docker 容器健康检查（docker HEALTHCHECK）
- 运维监控（系统资源 + 依赖服务状态）

### class `HealthResponse`

**继承**: `BaseModel`

基础健康检查响应。

### class `SystemInfo`

**继承**: `BaseModel`

系统资源信息。

### class `ServiceStatus`

**继承**: `BaseModel`

依赖服务状态。

### class `DetailedHealthResponse`

**继承**: `BaseModel`

详细健康检查响应。

### `async health_check()`

基础健康检查 -- 轻量、快速，适合高频调用。

**Returns**: `dict`

---

### `async detailed_health()`

详细健康检查 -- 包含系统资源和依赖服务状态。

**Returns**: `dict`

---

## backend.routers.llm

**文件**: `backend\routers\llm.py`

### `async chat(req: ChatRequest)`

与LLM进行单轮对话。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| req | ChatRequest | - | - |

---

### `async chat_stream(req: ChatRequest)`

与LLM进行流式对话。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| req | ChatRequest | - | - |

---

## backend.routers.metrics

**文件**: `backend\routers\metrics.py`

Prometheus 监控端点。

### `async metrics()`

返回 Prometheus 指标文本。

**Returns**: `Response`

---

## backend.routers.mq

**文件**: `backend\routers\mq.py`

CityFlow 消息队列 API。

提供消息发布、消费者管理、队列状态查询等接口。

### class `PublishRequest`

**继承**: `BaseModel`

发布消息请求体。

### class `PublishBatchRequest`

**继承**: `BaseModel`

批量发布请求体。

### class `StartConsumerRequest`

**继承**: `BaseModel`

启动消费者请求体。

### `async publish_message(queue: str, body: PublishRequest)`

发布一条消息到指定队列。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| queue | str | - | - |
| body | PublishRequest | - | - |

**Returns**: `dict[str, Any]`

---

### `async publish_batch(queue: str, body: PublishBatchRequest)`

批量发布消息到指定队列。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| queue | str | - | - |
| body | PublishBatchRequest | - | - |

**Returns**: `dict[str, Any]`

---

### `async start_consumer(queue: str, body: StartConsumerRequest)`

为指定队列启动一个后台消费者。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| queue | str | - | - |
| body | StartConsumerRequest | - | - |

**Returns**: `dict[str, str]`

---

### `async queue_status(queue: str)`

查询指定队列的长度。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| queue | str | - | - |

**Returns**: `dict[str, Any]`

---

### `async clear_queue(queue: str)`

清空指定队列中的所有消息。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| queue | str | - | - |

**Returns**: `dict[str, Any]`

---

### `async list_handlers()`

列出所有已注册的消息处理器名称。

**Returns**: `dict[str, list[str]]`

---

## backend.routers.poi

**文件**: `backend\routers\poi.py`

POI (兴趣点) 查询与距离计算接口。

### class `SearchRequest`

**继承**: `BaseModel`

POI搜索请求体。

### class `SearchResponse`

**继承**: `BaseModel`

POI搜索响应。

### class `DistanceMatrixRequest`

**继承**: `BaseModel`

距离矩阵请求体。

### class `DistanceItem`

**继承**: `BaseModel`

距离矩阵元素。

### class `DistanceMatrixResponse`

**继承**: `BaseModel`

距离矩阵响应。

### `load_pois()`

**Returns**: `None`

---

### `get_price_range(avg_price: float)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| avg_price | float | - | - |

**Returns**: `str`

---

### `enrich_poi(poi: dict)`

为 POI 补充 emotion_tags、constraints、price_range 字段。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi | dict | - | - |

**Returns**: `dict`

---

### `async search_pois(request: SearchRequest, lat: Optional[float] = Query(...), lng: Optional[float] = Query(...))`

搜索兴趣点。

支持按城市、类别、标签、关键词、评分、价格、地理位置等多维度筛选。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| request | SearchRequest | - | - |
| lat | Optional[float] | Query(...) | - |
| lng | Optional[float] | Query(...) | - |

---

### `async get_poi_detail(poi_id: str, lat: Optional[float] = Query(...), lng: Optional[float] = Query(...))`

获取POI详情。

根据POI ID返回完整的POI信息，包括情绪标签和约束条件。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi_id | str | - | - |
| lat | Optional[float] | Query(...) | - |
| lng | Optional[float] | Query(...) | - |

---

### `async get_distance_matrix(request: DistanceMatrixRequest)`

计算距离矩阵。

输入POI ID列表，返回N x N的距离矩阵。距离使用haversine公式计算，
乘以1.3的道路系数，时间按30km/h估算。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| request | DistanceMatrixRequest | - | - |

---

## backend.routers.registry

**文件**: `backend\routers\registry.py`

CityFlow 服务注册路由。

提供服务注册、注销、心跳和查询的 REST API。
其他微服务通过这些接口向注册中心报告自身状态。

### class `RegistryMessage`

**继承**: `BaseModel`

注册中心通用响应。

### class `ServiceListResponse`

**继承**: `BaseModel`

服务列表响应。

### class `RegistryStatsResponse`

**继承**: `BaseModel`

注册中心统计。

### `async register_service(service: ServiceInfo)`

注册服务实例。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| service | ServiceInfo | - | - |

**Returns**: `dict[str, str]`

---

### `async deregister_service(service_id: str)`

注销服务实例。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| service_id | str | - | - |

**Returns**: `dict[str, str]`

---

### `async heartbeat(service_id: str)`

更新服务心跳。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| service_id | str | - | - |

**Returns**: `dict[str, str]`

---

### `async get_services(service_name: str | None = None)`

获取服务列表。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| service_name | str | None | None | - |

**Returns**: `dict[str, Any]`

---

### `async discover_service(service_name: str)`

发现服务实例。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| service_name | str | - | - |

**Returns**: `dict[str, Any]`

---

### `async get_stats()`

获取注册中心统计。

**Returns**: `dict[str, int]`

---

### `async cleanup_unhealthy(service_name: str | None = None)`

清理不健康实例。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| service_name | str | None | None | - |

**Returns**: `dict[str, str]`

---

## backend.routers.session

**文件**: `backend\routers\session.py`

CityFlow 会话 API。

提供会话的 CRUD 接口和统计查询。

### class `CreateSessionRequest`

**继承**: `BaseModel`

创建会话请求。

### class `UpdateSessionRequest`

**继承**: `BaseModel`

更新会话请求。

### `async create_session(body: CreateSessionRequest | None = None)`

创建新会话，返回 session_id。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| body | CreateSessionRequest | None | None | - |

**Returns**: `dict[str, str]`

---

### `async get_session_stats()`

获取会话统计信息（总数、有用户绑定的、匿名的）。

**Returns**: `dict[str, int]`

---

### `async get_session(session_id: str)`

获取指定会话的完整数据。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| session_id | str | - | - |

**Returns**: `dict[str, Any]`

---

### `async update_session(session_id: str, body: UpdateSessionRequest)`

更新会话数据（合并写入）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| session_id | str | - | - |
| body | UpdateSessionRequest | - | - |

**Returns**: `dict[str, str]`

---

### `async delete_session(session_id: str)`

删除指定会话。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| session_id | str | - | - |

**Returns**: `dict[str, str]`

---

### `async refresh_session(session_id: str)`

刷新会话过期时间（续期）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| session_id | str | - | - |

**Returns**: `dict[str, str]`

---

### `async get_user_sessions(user_id: str)`

获取指定用户的所有活跃会话。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| user_id | str | - | - |

**Returns**: `dict[str, Any]`

---

## backend.routers.tasks

**文件**: `backend\routers\tasks.py`

CityFlow 后台任务 API。

提供任务提交、状态查询、取消、列表等接口。
通过函数白名单机制控制可执行的后台任务。

### class `SubmitTaskRequest`

**继承**: `BaseModel`

提交任务请求体。

### class `TaskResponse`

**继承**: `BaseModel`

任务状态响应。

### class `TaskListResponse`

**继承**: `BaseModel`

任务列表响应。

### `async submit_task(func_name: str, request: SubmitTaskRequest)`

提交后台任务。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| func_name | str | - | - |
| request | SubmitTaskRequest | - | - |

---

### `async get_task_status(task_id: str)`

查询任务状态。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| task_id | str | - | - |

---

### `async cancel_task(task_id: str)`

取消任务。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| task_id | str | - | - |

---

### `async list_tasks(status: str | None = Query(...))`

列出所有任务。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| status | str | None | Query(...) | - |

---

## backend.routers.websocket

**文件**: `backend\routers\websocket.py`

CityFlow WebSocket 实时通信端点。

提供 WebSocket 连接入口，支持路线订阅、心跳检测等实时交互。

### `async websocket_endpoint(websocket: WebSocket, session_id: str)`

WebSocket 实时通信端点。

客户端通过 `ws://host/ws/{session_id}` 建立连接后，
可发送 JSON 消息进行交互。

支持的消息类型：

| type | 说明 | 额外字段 |
|------|------|----------|
| subscribe | 订阅路线更新 | route_id |
| unsubscribe | 取消订阅 | route_id |
| ping | 心跳检测 | - |

服务端推送的消息类型：

| type | 说明 |
|------|------|
| subscribed | 订阅成功确认 |
| unsubscribed | 取消订阅确认 |
| pong | 心跳响应 |
| route_update | 路线更新通知 |
| error | 错误通知 |

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| websocket | WebSocket | - | - |
| session_id | str | - | - |

**Returns**: `None`

---

## backend.services.adaptive_rate_limiter

**文件**: `backend\services\adaptive_rate_limiter.py`

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

### class `LoadLevel`

**继承**: `str`, `Enum`

系统负载等级。

### class `SystemMetrics`

系统运行时指标快照。

#### `SystemMetrics.load_score()`

计算综合负载分数 (0-100)。

加权公式：
    score = 0.3*cpu + 0.2*memory + 0.3*error_rate*100 + 0.2*latency_factor
    latency_factor = min(avg_response_ms / 1000, 1) * 100

**Returns**: `float`


#### `SystemMetrics.level()`

根据负载分数判定等级。

阈值说明（满载 100 分）：
- LOW: < 30  （系统空闲）
- NORMAL: 30 - 60  （正常负载）
- HIGH: 60 - 85  （高负载，需收紧）
- CRITICAL: >= 85  （过载，紧急收紧）

**Returns**: `LoadLevel`


### class `MetricsCollector`

系统指标收集器。

通过 psutil 收集系统指标，如果 psutil 不可用则使用估算值。

#### `MetricsCollector.__init__()`

**Returns**: `None`


#### `MetricsCollector.record_response(duration_ms: float, is_error: bool = False)`

记录一次请求的响应。

**Returns**: `None`


#### `MetricsCollector.collect()`

收集当前系统指标。

**Returns**: `SystemMetrics`


#### `MetricsCollector.reset()`

重置所有指标。

**Returns**: `None`


### class `AdaptiveRateLimiter`

自适应限流器。

根据系统负载动态计算限流倍率，供 UserRateLimiter / IPRateLimiter 使用。
支持手动覆盖和渐进式恢复。

参数:
    high_threshold: 触发收紧的负载分数阈值（默认 70）。
    critical_threshold: 触发紧急收紧的负载分数阈值（默认 90）。
    low_threshold: 触发放宽的负载分数阈值（默认 40）。
    recovery_factor: 从高负载恢复时的渐进因子（0-1，默认 0.1）。

#### `AdaptiveRateLimiter.__init__(high_threshold: float = 70.0, critical_threshold: float = 90.0, low_threshold: float = 40.0, recovery_factor: float = 0.1)`

**Returns**: `None`


#### `AdaptiveRateLimiter.metrics()`

当前系统指标快照。

**Returns**: `SystemMetrics`


#### `AdaptiveRateLimiter.load_level()`

当前负载等级。

**Returns**: `LoadLevel`


#### `AdaptiveRateLimiter.get_multiplier()`

获取当前限流倍率。

Returns:
    限流倍率。>1 表示放宽，<1 表示收紧，1.0 表示正常。

**Returns**: `float`


#### `AdaptiveRateLimiter.set_manual_multiplier(multiplier: float | None)`

设置手动倍率覆盖。

Args:
    multiplier: 倍率值，None 则恢复自动模式。

**Returns**: `None`


#### `AdaptiveRateLimiter.record_response(duration_ms: float, is_error: bool = False)`

记录请求响应（供中间件调用）。

**Returns**: `None`


#### `async AdaptiveRateLimiter.start_monitoring()`

启动后台指标监控。

**Returns**: `None`


#### `async AdaptiveRateLimiter.stop_monitoring()`

停止后台指标监控。

**Returns**: `None`


#### `AdaptiveRateLimiter.force_update()`

立即更新指标并重新计算倍率。

**Returns**: `SystemMetrics`


#### `AdaptiveRateLimiter.get_status()`

获取自适应限流器状态。

**Returns**: `dict[str, Any]`


### `get_adaptive_limiter()`

获取全局自适应限流器单例。

**Returns**: `AdaptiveRateLimiter`

---

## backend.services.alert_notifier

**文件**: `backend\services\alert_notifier.py`

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

### class `AlertNotifier`

告警通知器。

职责：
- 将告警事件记录到日志
- 通过事件总线发布，供 WebSocket 等模块订阅
- 提供便捷方法发送自定义告警消息

#### `AlertNotifier.__init__()`

**Returns**: `None`


#### `async AlertNotifier.handle_alert(rule_name: str, current_value: float, threshold: float)`

处理资源监控器触发的告警。

适配 ``ResourceMonitor.add_callback`` 的签名：
``(rule_name: str, value: float, threshold: float) -> None``

Args:
    rule_name: 告警规则名称。
    current_value: 当前指标值。
    threshold: 阈值。

**Returns**: `None`


#### `async AlertNotifier.handle_alert_event(event: Any)`

处理 ``AlertEvent`` 对象。

适配 ``ResourceMonitor`` 发出的结构化告警事件。

Args:
    event: ``AlertEvent`` 实例，需具有 ``to_dict`` 方法。

**Returns**: `None`


#### `async AlertNotifier.send_info(message: str)`

发送 INFO 级别通知。

Args:
    message: 通知内容。
    **extra: 附加数据。

**Returns**: `None`


#### `async AlertNotifier.send_warning(message: str)`

发送 WARNING 级别通知。

Args:
    message: 通知内容。
    **extra: 附加数据。

**Returns**: `None`


#### `async AlertNotifier.send_critical(message: str)`

发送 CRITICAL 级别通知。

Args:
    message: 通知内容。
    **extra: 附加数据。

**Returns**: `None`


#### `AlertNotifier.notification_count()`

累计通知次数。

**Returns**: `int`


#### `AlertNotifier.get_status()`

返回通知器状态。

**Returns**: `dict[str, Any]`


### `get_alert_notifier()`

获取全局告警通知器单例。

**Returns**: `AlertNotifier`

---

### `reset_alert_notifier()`

重置全局告警通知器（仅用于测试）。

**Returns**: `None`

---

## backend.services.audit_logger

**文件**: `backend\services\audit_logger.py`

CityFlow 审计日志服务。

提供审计日志的记录、查询和导出功能。
使用缓冲写入减少数据库压力，支持 JSON 和 CSV 导出。

### class `AuditAction`

**继承**: `str`, `Enum`

审计动作类型。

### class `AuditLogger`

审计日志记录器。

使用内存缓冲区批量写入数据库，减少 I/O 压力。
缓冲区满或手动调用 flush 时写入数据库。

#### `AuditLogger.__init__(buffer_size: int = 100)`

**Returns**: `None`


#### `async AuditLogger.log(user_id: str, action: AuditAction, resource_type: str, resource_id: str | None = None, details: dict[str, Any] | None = None, ip_address: str | None = None, user_agent: str | None = None)`

记录一条审计日志。

Args:
    user_id: 操作用户 ID。
    action: 审计动作类型。
    resource_type: 资源类型（如 route、poi、user）。
    resource_id: 资源 ID。
    details: 附加详情。
    ip_address: 客户端 IP。
    user_agent: 客户端 User-Agent。

**Returns**: `None`


#### `async AuditLogger.flush()`

将缓冲区写入数据库。

**Returns**: `None`


#### `async AuditLogger.query(user_id: str | None = None, action: AuditAction | None = None, resource_type: str | None = None, start_time: datetime | None = None, end_time: datetime | None = None, limit: int = 100, offset: int = 0)`

查询审计日志。

Args:
    user_id: 按用户 ID 过滤。
    action: 按动作类型过滤。
    resource_type: 按资源类型过滤。
    start_time: 起始时间（含）。
    end_time: 结束时间（含）。
    limit: 返回条数上限。
    offset: 偏移量。

Returns:
    审计日志列表。

**Returns**: `list[dict[str, Any]]`


#### `async AuditLogger.count(user_id: str | None = None, action: AuditAction | None = None, resource_type: str | None = None, start_time: datetime | None = None, end_time: datetime | None = None)`

统计符合条件的审计日志总数。

**Returns**: `int`


#### `async AuditLogger.export_json(start_time: datetime | None = None, end_time: datetime | None = None, limit: int = 10000)`

导出审计日志为 JSON 字符串。

**Returns**: `str`


#### `async AuditLogger.export_csv(start_time: datetime | None = None, end_time: datetime | None = None, limit: int = 10000)`

导出审计日志为 CSV 字符串。

**Returns**: `str`


### `get_audit_logger()`

获取全局审计日志记录器单例。

**Returns**: `AuditLogger`

---

### `audit_log(action: AuditAction, resource_type: str)`

审计日志装饰器。

自动记录被装饰函数的调用为审计日志。
函数的第一个参数应为 user_id (str)，或从 kwargs 中获取。

用法::

    @audit_log(AuditAction.PLAN_ROUTE, "route")
    async def plan_route(user_id: str, ...):
        ...

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| action | AuditAction | - | - |
| resource_type | str | - | - |

---

## backend.services.auto_recovery

**文件**: `backend\services\auto_recovery.py`

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

### class `RecoveryStatus`

**继承**: `str`, `Enum`

恢复尝试结果状态。

### class `RecoveryAttempt`

单次恢复尝试的记录。

#### `RecoveryAttempt.__init__(service: str, status: RecoveryStatus, attempt: int = 0, error: str | None = None, latency_ms: float = 0.0)`

**Returns**: `None`


#### `RecoveryAttempt.to_dict()`

**Returns**: `dict[str, Any]`


### class `RecoveryResult`

一组恢复尝试的汇总结果。

#### `RecoveryResult.__init__(attempts: list[RecoveryAttempt])`

**Returns**: `None`


#### `RecoveryResult.to_dict()`

**Returns**: `dict[str, Any]`


### class `AutoRecovery`

自动恢复器。

Args:
    max_retries: 每个服务的最大连续重试次数，超过后停止尝试。
    base_delay: 重试基础延迟秒数，实际延迟 = base_delay * 2^attempt。
    max_delay: 重试延迟上限秒数。
    cooldown: 恢复成功后的冷却期秒数，期间不再重试。
    history_size: 保留最近多少条恢复记录。

#### `AutoRecovery.__init__(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0, cooldown: float = 30.0, history_size: int = 200)`

**Returns**: `None`


#### `AutoRecovery.register(service: str, action: RecoveryFunc)`

注册一个恢复动作。

Args:
    service: 服务名称，需与 HealthChecker 中的检查名对应。
    action: 异步恢复函数，无参数，失败时抛异常。

**Returns**: `None`


#### `AutoRecovery.unregister(service: str)`

注销一个恢复动作。

**Returns**: `None`


#### `async AutoRecovery.attempt(service: str)`

尝试恢复单个服务。

按以下顺序检查：
1. 是否有注册的恢复动作
2. 是否在冷却期内
3. 是否超过最大重试次数
4. 执行恢复动作（带指数退避等待）

Args:
    service: 服务名称。

Returns:
    RecoveryAttempt 记录。

**Returns**: `RecoveryAttempt`


#### `async AutoRecovery.attempt_many(services: list[str])`

并行恢复多个服务。

Args:
    services: 需要恢复的服务名称列表。

Returns:
    RecoveryResult 汇总。

**Returns**: `RecoveryResult`


#### `async AutoRecovery.handle_unhealthy(report: Any)`

HealthChecker 的 on_unhealthy 回调入口。

从健康报告中提取不健康的服务，自动触发恢复。

Args:
    report: HealthReport 实例，需有 unhealthy_names 属性。

Returns:
    RecoveryResult 汇总。

**Returns**: `RecoveryResult`


#### `AutoRecovery.reset_retry_count(service: str)`

手动重置某个服务的重试计数。

**Returns**: `None`


#### `AutoRecovery.reset_all()`

重置所有服务的重试计数。

**Returns**: `None`


#### `AutoRecovery.get_retry_count(service: str)`

获取某个服务当前的连续重试次数。

**Returns**: `int`


#### `AutoRecovery.history()`

**Returns**: `list[RecoveryAttempt]`


#### `AutoRecovery.get_service_history(service: str)`

获取某个服务的恢复历史。

**Returns**: `list[RecoveryAttempt]`


### `async recover_database()`

恢复数据库连接池。

策略：关闭旧引擎，创建新引擎。

**Returns**: `None`

---

### `async recover_redis()`

恢复 Redis 连接。

策略：关闭旧连接，重新 ping 验证。

**Returns**: `None`

---

### `async recover_llm_service()`

恢复 LLM 服务客户端。

策略：重置全局客户端实例，强制下次调用重新创建。

**Returns**: `None`

---

### `get_auto_recovery()`

获取全局 AutoRecovery 单例。

**Returns**: `AutoRecovery`

---

## backend.services.backup

**文件**: `backend\services\backup.py`

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

### class `BackupError`

**继承**: `CityFlowException`

备份操作失败。

#### `BackupError.__init__(message: str = '备份操作失败', details: dict[str, object] | None = None)`

**Returns**: `None`


### class `BackupNotFoundError`

**继承**: `CityFlowException`

指定备份不存在。

#### `BackupNotFoundError.__init__(backup_name: str, details: dict[str, object] | None = None)`

**Returns**: `None`


### class `DataBackup`

数据备份管理器。

Args:
    backup_dir: 备份存储根目录。
    data_dir: 需要备份的数据目录。
    keep_count: 自动清理时保留的备份数量。

#### `DataBackup.__init__(backup_dir: str = 'backups', data_dir: str = 'backend/data', keep_count: int = 10)`

**Returns**: `None`


#### `async DataBackup.create_backup(name: str | None = None)`

创建一个完整备份。

在后台线程中执行文件 IO，不阻塞事件循环。

Args:
    name: 自定义备份名称，默认使用时间戳。

Returns:
    备份名称，可用于后续恢复。

Raises:
    BackupError: 备份创建过程中发生错误。

**Returns**: `str`


#### `async DataBackup.restore_backup(backup_name: str)`

从指定备份恢复数据。

恢复前会校验备份完整性（SHA-256），校验失败则拒绝恢复。

Args:
    backup_name: 备份名称（目录名）。

Returns:
    恢复成功返回 True。

Raises:
    BackupNotFoundError: 备份不存在。
    BackupError: 恢复失败或完整性校验不通过。

**Returns**: `bool`


#### `async DataBackup.list_backups()`

列出所有备份，按时间倒序排列。

Returns:
    备份元数据列表，每项包含 name / timestamp / total_size_bytes 等字段。

**Returns**: `list[dict[str, object]]`


#### `async DataBackup.cleanup_old_backups(keep_count: int | None = None)`

清理旧版本备份，保留最近 N 个。

Args:
    keep_count: 保留数量，默认使用初始化时的 keep_count。

Returns:
    删除的备份数量。

**Returns**: `int`


#### `async DataBackup.delete_backup(backup_name: str)`

删除指定备份。

Args:
    backup_name: 备份名称。

Returns:
    删除成功返回 True。

Raises:
    BackupNotFoundError: 备份不存在。

**Returns**: `bool`


#### `DataBackup.backup_dir()`

备份存储目录。

**Returns**: `Path`


### `get_backup()`

获取全局备份管理器实例。

**Returns**: `DataBackup`

---

### `reset_backup()`

重置全局备份管理器（仅用于测试）。

**Returns**: `None`

---

## backend.services.cache

**文件**: `backend\services\cache.py`

CityFlow 多级缓存模块。

提供三级缓存架构：
- L1: 内存缓存（MemoryCache）-- 同步，进程内，毫秒级
- L2: Redis 缓存（RedisCache）-- 异步，跨进程，亚毫秒级
- 组合层: MultiLevelCache -- L1 + L2 联合读写

同时保留原有全局缓存实例和装饰器，向后兼容。

### class `MemoryCache`

线程安全的内存缓存，支持 TTL 过期和容量上限。

淘汰策略：TTL 过期优先，满时按 LRU 淘汰（最近最少访问）。

#### `MemoryCache.__init__(max_size: int = 1000, ttl_seconds: int = 300)`

**Returns**: `None`


#### `MemoryCache.get(key: str)`

获取缓存值，过期则删除并返回 None。命中时更新访问时间（LRU）。

**Returns**: `Any | None`


#### `MemoryCache.set(key: str, value: Any)`

写入缓存，满时按 LRU 淘汰。

**Returns**: `None`


#### `MemoryCache.delete(key: str)`

删除指定缓存条目。

**Returns**: `None`


#### `MemoryCache.clear()`

清空全部缓存。

**Returns**: `None`


#### `MemoryCache.size()`

当前缓存条目数。

**Returns**: `int`


#### `MemoryCache.stats()`

返回命中率统计。

**Returns**: `dict[str, int | float]`


### class `RedisCache`

基于 Redis 的异步缓存，支持 TTL 和按前缀批量清除。

所有键自动添加 ``cityflow:`` 前缀以避免命名冲突。

#### `RedisCache.__init__(redis_url: str = 'redis://localhost:6379')`

**Returns**: `None`


#### `async RedisCache.connect()`

建立 Redis 连接。幂等，已连接时跳过。

**Returns**: `None`


#### `async RedisCache.get(key: str)`

从 Redis 获取缓存值。未连接时直接返回 None。

**Returns**: `Any | None`


#### `async RedisCache.set(key: str, value: Any, ttl: int = 3600)`

写入 Redis 缓存，默认 1 小时过期。

**Returns**: `None`


#### `async RedisCache.delete(key: str)`

删除指定键。

**Returns**: `None`


#### `async RedisCache.clear_pattern(pattern: str)`

按通配符批量删除，返回删除数量。

**Returns**: `int`


#### `async RedisCache.close()`

关闭 Redis 连接。

**Returns**: `None`


#### `RedisCache.is_connected()`

**Returns**: `bool`


### class `MultiLevelCache`

多级缓存：L1（内存） + L2（Redis）。

读取策略：L1 命中直接返回 -> L2 命中回填 L1 -> 都未命中返回 None
写入策略：同时写入 L1 和 L2
删除策略：同时删除 L1 和 L2

#### `MultiLevelCache.__init__(l1: MemoryCache | None = None, l2: RedisCache | None = None)`

**Returns**: `None`


#### `async MultiLevelCache.get(key: str)`

获取缓存值（L1 -> L2 -> None）。

**Returns**: `Any | None`


#### `async MultiLevelCache.set(key: str, value: Any, ttl: int = 3600)`

同时写入 L1 和 L2。L2 使用指定 TTL（默认 1 小时）。

**Returns**: `None`


#### `async MultiLevelCache.delete(key: str)`

同时删除 L1 和 L2。

**Returns**: `None`


#### `async MultiLevelCache.clear_l2_pattern(pattern: str)`

清除 L2 中匹配模式的键。返回删除数量。

**Returns**: `int`


#### `async MultiLevelCache.invalidate(prefix: str)`

按前缀同时清除 L1 和 L2 中的缓存条目。

Returns:
    {"l1_deleted": int, "l2_deleted": int}

**Returns**: `dict[str, int]`


#### `MultiLevelCache.stats()`

返回 L1 统计 + L2 连接状态。

**Returns**: `dict[str, Any]`


### `get_multilevel_cache()`

获取全局多级缓存单例。首次调用时根据配置创建。

**Returns**: `MultiLevelCache`

---

### `async init_multilevel_cache()`

初始化多级缓存的 L2（Redis）连接。应用启动时调用。

**Returns**: `None`

---

### `async close_multilevel_cache()`

关闭多级缓存的 L2 连接。应用关闭时调用。

**Returns**: `None`

---

### `cache_key()`

根据参数生成稳定的 MD5 缓存键。

**Returns**: `str`

---

### `cached(cache: MemoryCache | MultiLevelCache, prefix: str = '', key_builder: Callable[Ellipsis, str] | None = None, ttl: int = 3600)`

通用缓存装饰器，同时支持同步和异步函数。

Args:
    cache: MemoryCache（同步）或 MultiLevelCache（异步）实例
    prefix: 缓存键前缀
    key_builder: 自定义键生成函数，默认使用 cache_key
    ttl: MultiLevelCache 的 L2 TTL 秒数，默认 3600

Returns:
    装饰后的函数

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| cache | MemoryCache | MultiLevelCache | - | - |
| prefix | str | '' | - |
| key_builder | Callable[Ellipsis, str] | None | None | - |
| ttl | int | 3600 | - |

**Returns**: `Callable`

---

### `invalidate(cache: MemoryCache, prefix: str = '')`

清除指定前缀的所有缓存条目，返回删除数量。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| cache | MemoryCache | - | - |
| prefix | str | '' | - |

**Returns**: `int`

---

## backend.services.cache_warmup

**文件**: `backend\services\cache_warmup.py`

CityFlow 缓存预热模块。

在应用启动时将热点数据加载到缓存中，减少冷启动时的延迟抖动。

### `async warmup_multilevel_cache()`

将热点数据预热到多级缓存（L1 + L2）。

**Returns**: `None`

---

### `warmup_memory_caches(pois: list[dict[str, Any]] | None = None)`

将热点数据预热到全局 MemoryCache 实例（同步）。

在 startup 中 ``load_data()`` 之后调用。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| pois | list[dict[str, Any]] | None | None | - |

**Returns**: `None`

---

### `async schedule_cache_refresh(interval_seconds: int = 3600)`

定时刷新多级缓存中的预热数据。

在后台任务中运行，每 ``interval_seconds`` 秒刷新一次。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| interval_seconds | int | 3600 | - |

**Returns**: `None`

---

## backend.services.circuit_breaker

**文件**: `backend\services\circuit_breaker.py`

CityFlow 熔断器模块。

实现三态熔断器（CLOSED / OPEN / HALF_OPEN），用于保护外部服务调用。
提供同步/异步装饰器和手动控制两种使用方式。

状态机：
    CLOSED  --(失败次数 >= 阈值)--> OPEN
    OPEN    --(恢复超时)----------> HALF_OPEN
    HALF_OPEN --(调用成功)--------> CLOSED
    HALF_OPEN --(调用失败)--------> OPEN

### class `CircuitBreakerOpenError`

**继承**: `CityFlowException`

熔断器处于打开状态时抛出。

#### `CircuitBreakerOpenError.__init__(message: str = '服务暂时不可用（熔断器已打开）', details: dict[str, Any] | None = None)`

**Returns**: `None`


### class `CircuitState`

**继承**: `str`, `Enum`

熔断器三态。

### class `CircuitBreakerMetrics`

熔断器指标收集器。

默认使用简单的内存计数器。如果 prometheus_client 可用，
会自动注册 Prometheus 指标，可在 /metrics 端点暴露。

#### `CircuitBreakerMetrics.__init__(name: str)`

**Returns**: `None`


#### `CircuitBreakerMetrics.record_success()`

**Returns**: `None`


#### `CircuitBreakerMetrics.record_failure()`

**Returns**: `None`


#### `CircuitBreakerMetrics.record_rejected()`

**Returns**: `None`


#### `CircuitBreakerMetrics.record_state_change()`

**Returns**: `None`


#### `CircuitBreakerMetrics.as_dict()`

**Returns**: `dict[str, int]`


### class `CircuitBreaker`

三态熔断器。

Args:
    failure_threshold: 连续失败次数阈值，达到后进入 OPEN 状态。
    recovery_timeout: OPEN 状态持续多少秒后进入 HALF_OPEN。
    expected_exception: 哪些异常算"失败"，默认所有 Exception。
    name: 熔断器名称，用于日志和指标。

#### `CircuitBreaker.__init__(failure_threshold: int = 5, recovery_timeout: float = 30.0, expected_exception: type[BaseException] | tuple[type[BaseException], Ellipsis] = Exception, name: str = 'default')`

**Returns**: `None`


#### `CircuitBreaker.state()`

获取当前状态，OPEN 超时后自动转 HALF_OPEN。

**Returns**: `CircuitState`


#### `CircuitBreaker.metrics()`

**Returns**: `CircuitBreakerMetrics`


#### `CircuitBreaker.failure_count()`

**Returns**: `int`


#### `CircuitBreaker.record_success()`

记录一次成功调用，重置失败计数并关闭熔断器。

**Returns**: `None`


#### `CircuitBreaker.record_failure()`

记录一次失败调用，达到阈值时打开熔断器。

**Returns**: `None`


#### `CircuitBreaker.reject_if_open()`

如果熔断器已打开，直接抛出异常。

**Returns**: `None`


#### `CircuitBreaker.reset()`

手动重置熔断器到 CLOSED 状态。

**Returns**: `None`


#### `CircuitBreaker.trip()`

手动触发熔断器到 OPEN 状态。

**Returns**: `None`


## backend.services.config_hot_reload

**文件**: `backend\services\config_hot_reload.py`

CityFlow 配置热更新。

基于 watchdog 监听配置文件变更，支持：
- .env / .yaml / .json 文件变更检测
- 变更回调注册与自动触发
- 配置快照与回滚（最多保留 N 个历史版本）
- 防抖处理（避免编辑器保存产生多次事件）

### class `ConfigReloadError`

**继承**: `Exception`

配置热更新相关错误。

### class `ConfigSnapshot`

配置快照，用于回滚。

### class `_DebounceState`

防抖状态追踪。

### class `_ConfigFileHandler`

**继承**: `FileSystemEventHandler`

watchdog 文件事件处理器，桥接到 asyncio 回调。

#### `_ConfigFileHandler.__init__(loop: asyncio.AbstractEventLoop, callback: Callable[List(elts=[Name(id='str', ctx=Load())], ctx=Load()), Coroutine[Any, Any, None]], watched_extensions: set[str])`

**Returns**: `None`


#### `_ConfigFileHandler.on_modified(event: FileSystemEvent)`

**Returns**: `None`


#### `_ConfigFileHandler.on_created(event: FileSystemEvent)`

新建配置文件也触发更新。

**Returns**: `None`


### class `ConfigHotReloader`

配置热更新器。

Args:
    config_dir: 要监听的配置文件目录。
    max_snapshots: 每个文件保留的最大快照数（用于回滚）。
    watched_extensions: 要监听的文件后缀集合，默认 .env/.yaml/.yml/.json。

#### `ConfigHotReloader.__init__(config_dir: str = '.', max_snapshots: int = 10, watched_extensions: set[str] | None = None)`

**Returns**: `None`


#### `ConfigHotReloader.start()`

启动文件监听。

**Returns**: `None`


#### `ConfigHotReloader.stop()`

停止文件监听。

**Returns**: `None`


#### `ConfigHotReloader.is_running()`

**Returns**: `bool`


#### `ConfigHotReloader.register_handler(config_type: str, handler: Callable[List(elts=[Name(id='str', ctx=Load())], ctx=Load()), Coroutine[Any, Any, None]])`

注册配置变更处理器。

Args:
    config_type: 配置类型标识（env / yaml / json / 自定义）。
    handler: 异步回调，接收文件路径参数。

**Returns**: `None`


#### `ConfigHotReloader.unregister_handler(config_type: str)`

移除配置变更处理器。

**Returns**: `None`


#### `ConfigHotReloader.rollback(file_path: str, steps: int = 1)`

回滚配置文件到指定历史版本。

Args:
    file_path: 要回滚的文件路径。
    steps: 回滚步数（1 = 上一个版本）。

Returns:
    是否回滚成功。

Raises:
    ConfigReloadError: 无可用快照或步数超出范围。

**Returns**: `bool`


#### `ConfigHotReloader.get_snapshot_history(file_path: str)`

获取文件的快照历史（从新到旧）。

**Returns**: `list[ConfigSnapshot]`


#### `ConfigHotReloader.get_latest_snapshot(file_path: str)`

获取文件的最新快照。

**Returns**: `ConfigSnapshot | None`


#### `ConfigHotReloader.clear_snapshots(file_path: str | None = None)`

清空快照。file_path 为 None 时清空全部。

**Returns**: `None`


### `get_config_reloader()`

获取全局配置热更新器（懒初始化）。

**Returns**: `ConfigHotReloader`

---

## backend.services.config_watcher

**文件**: `backend\services\config_watcher.py`

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

### class `ConfigDiff`

单条配置变更记录。

### class `ConfigWatcher`

配置变更监视器。

通过轮询 Settings 实例检测字段变化，
并调用已注册的异步回调通知下游。

#### `ConfigWatcher.__init__(settings: Settings | None = None)`

**Returns**: `None`


#### `ConfigWatcher.watch(key: str, callback: ConfigChangeCallback)`

注册配置变更回调。

Args:
    key: 配置字段名（支持点分路径，如 "security.rate_limit_per_minute"）。
    callback: 异步回调，签名 async def cb(key, old_value, new_value)。

**Returns**: `None`


#### `ConfigWatcher.unwatch(key: str)`

取消监视。

**Returns**: `None`


#### `ConfigWatcher.watched_keys()`

当前监视的配置键列表。

**Returns**: `list[str]`


#### `async ConfigWatcher.check_changes()`

检查配置变更并触发回调。

Returns:
    本次检测到的变更列表。

**Returns**: `list[ConfigDiff]`


#### `ConfigWatcher.change_log()`

获取最近的变更日志。

**Returns**: `list[ConfigDiff]`


#### `ConfigWatcher.clear_change_log()`

清空变更日志。

**Returns**: `None`


#### `ConfigWatcher.refresh_snapshot()`

强制刷新快照（不触发回调）。

**Returns**: `None`


### `async log_level_change_callback(key: str, old_value: Any, new_value: Any)`

日志级别变更回调：动态调整 root logger 级别。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| key | str | - | - |
| old_value | Any | - | - |
| new_value | Any | - | - |

**Returns**: `None`

---

### `async rate_limit_change_callback(key: str, old_value: Any, new_value: Any)`

限流配置变更回调：记录变更（实际限流组件需自行监听）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| key | str | - | - |
| old_value | Any | - | - |
| new_value | Any | - | - |

**Returns**: `None`

---

### `create_default_watcher(settings: Settings | None = None)`

创建带有默认监视项的 ConfigWatcher。

默认监视:
- log_level -> 动态调整日志级别
- security.rate_limit_per_minute -> 记录变更

Args:
    settings: Settings 实例，为 None 时使用全局单例。

Returns:
    配置好的 ConfigWatcher 实例。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| settings | Settings | None | None | - |

**Returns**: `ConfigWatcher`

---

## backend.services.data_check

**文件**: `backend\services\data_check.py`

POI 数据完整性验证脚本。

验证 backend/data/city_poi_db.json 中每条 POI 记录的字段存在性、类型和取值范围。

### `validate_poi(poi: dict)`

验证单个 POI 记录。

Returns:
    (是否有效, 错误信息列表)

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi | dict | - | - |

**Returns**: `tuple[bool, list[str]]`

---

### `validate_all_pois()`

验证所有 POI 数据，返回验证结果与统计信息。

**Returns**: `dict[str, object]`

---

### `main()`

命令行入口：运行验证并打印报告。

**Returns**: `None`

---

## backend.services.data_service

**文件**: `backend\services\data_service.py`

### `load_data()`

**Returns**: `None`

---

### `get_data(dataset: Optional[str] = None, filters: Optional[dict] = None)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| dataset | Optional[str] | None | - |
| filters | Optional[dict] | None | - |

**Returns**: `Any`

---

### `get_datasets()`

**Returns**: `list[str]`

---

## backend.services.dialogue

**文件**: `backend\services\dialogue.py`

CityFlow 多轮对话引擎。

支持用户对已规划路线进行调整，包括：
- 替换指令：换掉某个景点
- 节奏调整：太赶了/想轻松点
- 预算调整：太贵了/便宜一点
- 时间调整：早一点/晚一点
- 不满反馈：重新来/再想一个

### class `DialogueState`

单个对话会话的状态管理。

#### `DialogueState.__init__(session_id: str, initial_route: dict[str, Any], user_intent: dict[str, Any])`

**Returns**: `None`


#### `DialogueState.add_message(role: str, content: str)`

添加消息到对话历史。

**Returns**: `None`


#### `DialogueState.is_expired()`

对话轮次是否已达上限。

**Returns**: `bool`


### class `DialogueEngine`

对话引擎：管理会话生命周期，分发指令到对应处理器。

#### `DialogueEngine.__init__()`

**Returns**: `None`


#### `DialogueEngine.create_session(session_id: str, route: dict[str, Any], user_intent: dict[str, Any])`

创建新会话并注册。

**Returns**: `DialogueState`


#### `DialogueEngine.get_session(session_id: str)`

获取已有会话。

**Returns**: `DialogueState | None`


#### `DialogueEngine.remove_session(session_id: str)`

删除会话。

**Returns**: `None`


#### `async DialogueEngine.process_instruction(session_id: str, instruction: str)`

处理用户指令的主入口。

Returns:
    {"reply": str, "route": dict, "changes_made": list}

Raises:
    DialogueError: 会话不存在或对话轮次已达上限

**Returns**: `dict[str, Any]`


### `async create_dialogue(session_id: str, route: dict[str, Any], user_intent: dict[str, Any])`

创建新对话会话。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| session_id | str | - | - |
| route | dict[str, Any] | - | - |
| user_intent | dict[str, Any] | - | - |

**Returns**: `dict[str, str]`

---

### `async process_dialogue(session_id: str, instruction: str)`

处理对话指令。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| session_id | str | - | - |
| instruction | str | - | - |

**Returns**: `dict[str, Any]`

---

## backend.services.discovery

**文件**: `backend\services\discovery.py`

CityFlow 服务发现客户端。

提供服务发现功能，支持从本地注册中心或远程注册中心获取服务实例。
支持负载均衡和故障转移。

使用方式::

    discovery = get_service_discovery()
    service_url = await discovery.discover("user-service")
    if service_url:
        # 使用 service_url 调用服务
        pass

### class `ServiceDiscovery`

服务发现客户端。

优先从本地注册中心获取服务实例，若本地无可用实例
则尝试从远程注册中心获取。

Args:
    registry_url: 远程注册中心的 URL，为 None 时仅使用本地注册中心。

#### `ServiceDiscovery.__init__(registry_url: str | None = None)`

**Returns**: `None`


#### `async ServiceDiscovery.discover(service_name: str)`

发现服务，返回服务的基础 URL（如 ``http://host:port``）。

优先使用本地注册中心，若无可用实例则尝试远程注册中心。
找不到时返回 None。

**Returns**: `str | None`


#### `async ServiceDiscovery.get_service_url(service_name: str)`

获取服务 URL，找不到时抛出异常。

Raises:
    ServiceNotFoundError: 服务不存在或无可用实例。

**Returns**: `str`


### class `ServiceNotFoundError`

**继承**: `Exception`

服务未找到异常。

#### `ServiceNotFoundError.__init__(service_name: str)`

**Returns**: `None`


### `get_service_discovery()`

获取全局服务发现客户端单例。

**Returns**: `ServiceDiscovery`

---

## backend.services.emotion

**文件**: `backend\services\emotion.py`

CityFlow 情绪评分公共模块。

提供主导情绪判断、情绪兼容性评分、情绪曲线计算等函数，
消除 narrator.py / filters.py 中的重复实现。

### `get_dominant_emotion(emotion_tags: dict[str, float])`

获取主导情绪类型。

强度 > 0.6 的最高情绪标签为主导情绪，否则返回 "default"。

Args:
    emotion_tags: 情绪标签字典，键为情绪类型，值为 0-1 的强度

Returns:
    主导情绪名称

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| emotion_tags | dict[str, float] | - | - |

**Returns**: `str`

---

### `emotion_compatibility(poi_a: dict[str, Any], poi_b: dict[str, Any])`

计算两个 POI 之间的情绪兼容性评分。

规则：
- 两个 POI 兴奋度都 > 0.8 -> -0.5（过载惩罚）
- 同 category -> -0.3（连续同类惩罚）
- 文化 >= 0.7 后面跟宁静 >= 0.7 -> +0.4（增强型）
- 兴奋 >= 0.7 后面跟宁静 >= 0.7 -> +0.3（反差型）
- 其他 -> 0.0

Args:
    poi_a: 前一个 POI
    poi_b: 后一个 POI

Returns:
    -1.0 到 1.0 的兼容性评分

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi_a | dict[str, Any] | - | - |
| poi_b | dict[str, Any] | - | - |

**Returns**: `float`

---

### `emotion_compatibility_with_consecutive(pois: list[dict[str, Any]])`

计算 POI 序列的总情绪兼容性，处理连续同类惩罚升级。

Args:
    pois: 按顺序排列的 POI 列表

Returns:
    总兼容性评分

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| pois | list[dict[str, Any]] | - | - |

**Returns**: `float`

---

### `calculate_emotion_curve(route: list[dict[str, Any]])`

计算情绪曲线。

Args:
    route: 路线步骤列表，每步需含 poi.emotion_tags 和 arrival_time

Returns:
    情绪曲线数据列表

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| route | list[dict[str, Any]] | - | - |

**Returns**: `list[dict[str, Any]]`

---

### `fatigue_penalty(step_count: int, consecutive_pois: int)`

根据步数和连续 POI 数量计算疲劳惩罚。

Args:
    step_count: 当前步数
    consecutive_pois: 连续访问的 POI 数量

Returns:
    疲劳惩罚系数（0 表示无惩罚，-999 表示强制休息）

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| step_count | int | - | - |
| consecutive_pois | int | - | - |

**Returns**: `float`

---

## backend.services.event_bus

**文件**: `backend\services\event_bus.py`

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

### class `Event`

事件基类。

所有事件的通用载体，包含事件类型、负载数据、时间戳和来源。

Attributes:
    event_type: 事件类型标识，如 ``"route.planned"``
    data: 事件负载数据
    timestamp: 事件发生时间（UTC），默认自动填充
    source: 事件来源标识，如模块名或服务名

### class `EventBus`

事件总线。

维护同步和异步两套订阅者列表，发布时分别按同步阻塞 /
异步并发方式调用所有已注册的处理器。单个处理器异常不会
影响其他处理器的执行。

#### `EventBus.__init__()`

**Returns**: `None`


#### `EventBus.subscribe(event_type: str, handler: SyncHandler)`

注册同步事件处理器。

Args:
    event_type: 要监听的事件类型
    handler: 同步回调 ``(event: Event) -> None``

**Returns**: `None`


#### `EventBus.subscribe_async(event_type: str, handler: AsyncHandler)`

注册异步事件处理器。

Args:
    event_type: 要监听的事件类型
    handler: 异步回调 ``(event: Event) -> Coroutine``

**Returns**: `None`


#### `EventBus.unsubscribe(event_type: str, handler: Callable[Ellipsis, Any])`

取消注册事件处理器。

同时在同步和异步订阅者列表中查找并移除。如果 handler
不在列表中，静默忽略。

Args:
    event_type: 事件类型
    handler: 要移除的处理器

**Returns**: `None`


#### `EventBus.publish(event: Event)`

同步发布事件。

逐个调用所有已注册的同步处理器，单个处理器的异常会被
捕获并记录，不影响后续处理器。

Args:
    event: 要发布的事件

**Returns**: `None`


#### `async EventBus.publish_async(event: Event)`

异步发布事件。

并发执行所有已注册的异步处理器，使用 ``asyncio.gather``
的 ``return_exceptions=True`` 保证单个处理器失败不影响
其他处理器。处理完毕后逐条记录异常。

注册到异步列表中的处理器如果实际是同步函数，会被自动
包装为协程执行。

Args:
    event: 要发布的事件

**Returns**: `None`


#### `EventBus.get_subscribers(event_type: str)`

获取指定事件类型的所有订阅者（同步 + 异步）。

**Returns**: `list[Callable[Ellipsis, Any]]`


#### `EventBus.event_types()`

返回所有已注册事件类型的列表（去重）。

**Returns**: `list[str]`


#### `EventBus.clear()`

清空所有订阅（主要用于测试）。

**Returns**: `None`


### `get_event_bus()`

获取全局事件总线单例。

**Returns**: `EventBus`

---

### `reset_event_bus()`

重置全局事件总线（仅用于测试）。

**Returns**: `None`

---

## backend.services.fallback

**文件**: `backend\services\fallback.py`

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

### class `FallbackError`

**继承**: `Exception`

降级函数本身也失败时抛出。

### `fallback(fallback_func: Callable[Ellipsis, Any], exceptions: type[BaseException] | tuple[type[BaseException], Ellipsis] = Exception)`

降级装饰器。

当被装饰的函数抛出指定异常时，调用 fallback_func 代替。

Args:
    fallback_func: 降级函数，签名应与被装饰函数兼容。
    exceptions: 触发降级的异常类型，默认所有 Exception。

Returns:
    装饰器。

Example::

    @fallback(my_fallback, exceptions=(TimeoutError, ConnectionError))
    async def call_external_api(url: str) -> dict:
        ...

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| fallback_func | Callable[Ellipsis, Any] | - | - |
| exceptions | type[BaseException] | tuple[type[BaseException], Ellipsis] | Exception | - |

**Returns**: `Callable[List(elts=[Name(id='F', ctx=Load())], ctx=Load()), F]`

---

### `async fallback_route_planning()`

路线规划降级：返回空路线，提示稍后重试。

**Returns**: `dict[str, Any]`

---

### `async fallback_poi_search()`

POI 搜索降级：返回空列表。

**Returns**: `dict[str, Any]`

---

### `async fallback_narrative_generation()`

文案生成降级：返回简洁模板文案。

**Returns**: `dict[str, Any]`

---

### `async fallback_llm_chat()`

LLM 对话降级：返回固定提示。

**Returns**: `str`

---

### `async fallback_emotion_analysis()`

情绪分析降级：返回中性情绪值。

**Returns**: `dict[str, float]`

---

## backend.services.filters

**文件**: `backend\services\filters.py`

CityFlow POI过滤模块。

### `filter_candidates(pois: list[dict[str, Any]], user_intent: dict[str, Any])`

根据用户意图过滤POI候选列表。

过滤规则：
- 时间窗：POI营业时间必须覆盖用户出行时段
- 排队：poi排队时间 <= 用户排队容忍度
- 无障碍：需要时过滤掉不支持的POI
- 宠物友好：需要时过滤掉不支持的POI
- 预算：avg_price 不超过 per_person 的1.2倍

Args:
    pois: POI列表
    user_intent: 用户意图

Returns:
    过滤后的POI列表

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| pois | list[dict[str, Any]] | - | - |
| user_intent | dict[str, Any] | - | - |

**Returns**: `list[dict[str, Any]]`

---

## backend.services.geo

**文件**: `backend\services\geo.py`

CityFlow 地理计算公共模块。

提供 haversine 距离计算、道路距离估算、旅行时间估算等函数，
消除 solver.py / poi.py / vectorized.py 中的重复实现。

### `haversine(lat1: float, lon1: float, lat2: float, lon2: float)`

计算两点间的球面距离（米）。

Args:
    lat1: 第一个点的纬度
    lon1: 第一个点的经度
    lat2: 第二个点的纬度
    lon2: 第二个点的经度

Returns:
    距离（米）

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| lat1 | float | - | - |
| lon1 | float | - | - |
| lat2 | float | - | - |
| lon2 | float | - | - |

**Returns**: `float`

---

### `haversine_with_road_factor(lat1: float, lon1: float, lat2: float, lon2: float, factor: float = _ROAD_FACTOR)`

计算两点间的实际道路距离（米）。

Args:
    lat1: 第一个点的纬度
    lon1: 第一个点的经度
    lat2: 第二个点的纬度
    lon2: 第二个点的经度
    factor: 道路系数（默认 1.3）

Returns:
    实际道路距离（米）

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| lat1 | float | - | - |
| lon1 | float | - | - |
| lat2 | float | - | - |
| lon2 | float | - | - |
| factor | float | _ROAD_FACTOR | - |

**Returns**: `float`

---

### `estimate_travel_time(distance_m: float, speed_kmh: float = _AVG_SPEED_KMH)`

估算旅行时间（分钟）。

Args:
    distance_m: 距离（米）
    speed_kmh: 速度（千米/小时，默认 30）

Returns:
    时间（分钟）

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| distance_m | float | - | - |
| speed_kmh | float | _AVG_SPEED_KMH | - |

**Returns**: `float`

---

### `poi_distance(poi_a: dict[str, Any] | None, poi_b: dict[str, Any] | None)`

计算两个 POI 间的实际道路距离（米）。None 安全。

Args:
    poi_a: 第一个 POI 字典（需含 lat, lng）
    poi_b: 第二个 POI 字典（需含 lat, lng）

Returns:
    道路距离（米），任一输入为 None 时返回 0.0

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi_a | dict[str, Any] | None | - | - |
| poi_b | dict[str, Any] | None | - | - |

**Returns**: `float`

---

### `poi_travel_time(poi_a: dict[str, Any] | None, poi_b: dict[str, Any] | None)`

估算两个 POI 间的旅行时间（分钟）。None 安全。

Args:
    poi_a: 第一个 POI 字典
    poi_b: 第二个 POI 字典

Returns:
    旅行时间（分钟），任一输入为 None 时返回 0.0

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi_a | dict[str, Any] | None | - | - |
| poi_b | dict[str, Any] | None | - | - |

**Returns**: `float`

---

### `cache_key_distance(poi_a: dict[str, Any], poi_b: dict[str, Any])`

生成距离缓存键。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi_a | dict[str, Any] | - | - |
| poi_b | dict[str, Any] | - | - |

**Returns**: `str`

---

### `cache_key_travel_time(poi_a: dict[str, Any], poi_b: dict[str, Any])`

生成旅行时间缓存键。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi_a | dict[str, Any] | - | - |
| poi_b | dict[str, Any] | - | - |

**Returns**: `str`

---

## backend.services.graceful_shutdown

**文件**: `backend\services\graceful_shutdown.py`

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

### class `ShutdownStats`

停机统计信息。

### class `GracefulShutdown`

优雅停机管理器。

职责：
- 管理停机信号的捕获与分发
- 跟踪活跃请求并在停机时等待排空
- 按注册顺序依次执行资源清理回调

Attributes:
    shutdown_timeout: 请求排空超时时间（秒），超时后强制关闭。

#### `GracefulShutdown.__init__(shutdown_timeout: float = 30.0)`

**Returns**: `None`


#### `GracefulShutdown.is_shutting_down()`

是否正在停机。

**Returns**: `bool`


#### `async GracefulShutdown.wait_for_shutdown()`

等待停机信号。

在需要阻塞当前任务直到停机时使用，例如后台轮询循环。

**Returns**: `None`


#### `GracefulShutdown.request_started(request_id: str)`

注册一个活跃请求。

Args:
    request_id: 请求唯一标识。

**Returns**: `None`


#### `GracefulShutdown.request_finished(request_id: str)`

注销一个已完成的请求。

Args:
    request_id: 请求唯一标识。

**Returns**: `None`


#### `GracefulShutdown.active_request_count()`

当前活跃请求数。

**Returns**: `int`


#### `GracefulShutdown.register_cleanup(name: str, callback: CleanupCallback)`

注册资源清理回调。

回调按注册顺序依次执行（非并发），单个回调异常不影响后续执行。

Args:
    name: 清理步骤名称（用于日志）。
    callback: 异步无参函数，执行资源释放。

**Returns**: `None`


#### `GracefulShutdown.register_signal_handlers()`

注册操作系统信号处理器。

- Linux/macOS: SIGINT 和 SIGTERM
- Windows: 仅 SIGINT（SIGTERM 不被 loop.add_signal_handler 支持）

幂等，重复调用无副作用。

**Returns**: `None`


#### `async GracefulShutdown.shutdown()`

执行三阶段优雅停机。

1. 设置停机事件，拒绝新请求
2. 等待活跃请求完成（超时则强制继续）
3. 按注册顺序执行清理回调

Returns:
    停机统计信息。

**Returns**: `ShutdownStats`


#### `GracefulShutdown.get_stats()`

返回当前状态字典。

**Returns**: `dict[str, Any]`


### `get_shutdown_manager()`

获取全局优雅停机管理器单例。

**Returns**: `GracefulShutdown`

---

### `reset_shutdown_manager()`

重置全局停机管理器（仅用于测试）。

**Returns**: `None`

---

## backend.services.health_checker

**文件**: `backend\services\health_checker.py`

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

### class `CheckStatus`

**继承**: `str`, `Enum`

单次检查结果状态。

### class `CheckResult`

单个检查项的结果。

#### `CheckResult.__init__(name: str, status: CheckStatus, latency_ms: float = 0.0, error: str | None = None, details: dict[str, Any] | None = None)`

**Returns**: `None`


#### `CheckResult.to_dict()`

**Returns**: `dict[str, Any]`


### class `HealthReport`

一次完整健康检查的汇总报告。

#### `HealthReport.__init__(results: list[CheckResult], duration_ms: float = 0.0)`

**Returns**: `None`


#### `HealthReport.to_dict()`

**Returns**: `dict[str, Any]`


#### `HealthReport.unhealthy_names()`

**Returns**: `list[str]`


### class `HealthChecker`

可扩展的健康检查器。

Args:
    history_size: 保留最近多少次检查报告。

#### `HealthChecker.__init__(history_size: int = 100)`

**Returns**: `None`


#### `HealthChecker.register(name: str, check_func: HealthCheckFunc)`

注册一个健康检查函数。

Args:
    name: 检查项名称，如 "database"、"redis"。
    check_func: 异步检查函数，返回 bool 或 CheckResult。

**Returns**: `None`


#### `HealthChecker.unregister(name: str)`

注销一个健康检查。

**Returns**: `None`


#### `HealthChecker.set_on_unhealthy(callback: Callable[List(elts=[Name(id='HealthReport', ctx=Load())], ctx=Load()), Coroutine[Any, Any, None]])`

设置异常回调，每次检测到 unhealthy 时触发。

典型用途：触发 auto_recovery。

**Returns**: `None`


#### `async HealthChecker.run_check(name: str)`

运行单个检查。

**Returns**: `CheckResult`


#### `async HealthChecker.run_all()`

并行运行所有已注册的检查，返回汇总报告。

**Returns**: `HealthReport`


#### `async HealthChecker.start(interval: int = 30)`

启动后台周期性健康检查。

Args:
    interval: 检查间隔秒数，默认 30 秒。

**Returns**: `None`


#### `HealthChecker.stop()`

停止后台监控。

**Returns**: `None`


#### `HealthChecker.latest()`

最近一次检查报告。

**Returns**: `HealthReport | None`


#### `HealthChecker.history()`

**Returns**: `list[HealthReport]`


#### `HealthChecker.get_check_names()`

返回所有已注册的检查名称。

**Returns**: `list[str]`


### `async check_database()`

检查数据库连接。

**Returns**: `CheckResult`

---

### `async check_redis()`

检查 Redis 连接。

**Returns**: `CheckResult`

---

### `async check_llm_service()`

检查 LLM 服务可用性（轻量级，只验证连通性）。

**Returns**: `CheckResult`

---

### `get_health_checker()`

获取全局 HealthChecker 单例。

**Returns**: `HealthChecker`

---

## backend.services.http_pool

**文件**: `backend\services\http_pool.py`

CityFlow HTTP 连接池。

基于 httpx.AsyncClient 的连接池，提供：
- 可配置的最大连接数与 keep-alive 连接数
- 全生命周期管理（启动 / 关闭）
- GET / POST / PUT / PATCH / DELETE 等便捷方法
- 连接池统计信息

替代项目中散落的 ``async with httpx.AsyncClient(...) as client`` 临时连接，
复用底层 TCP 连接以降低延迟。

### class `HTTPPoolStats`

HTTP 连接池统计快照。

### class `HTTPPool`

HTTP 连接池。

Args:
    max_connections: 最大并发连接数。
    max_keepalive_connections: 最大 keep-alive 连接数。
    timeout: 默认请求超时（秒）。

#### `async HTTPPool.start()`

初始化 HTTP 客户端。幂等。

**Returns**: `None`


#### `async HTTPPool.close()`

关闭连接池。幂等。

**Returns**: `None`


#### `async HTTPPool.request(method: str, url: str)`

发送 HTTP 请求。

Args:
    method: HTTP 方法（GET / POST / ...）。
    url: 目标 URL。
    **kwargs: 传递给 httpx.AsyncClient.request 的其余参数。

**Returns**: `httpx.Response`


#### `async HTTPPool.get(url: str)`

GET 请求。

**Returns**: `httpx.Response`


#### `async HTTPPool.post(url: str)`

POST 请求。

**Returns**: `httpx.Response`


#### `async HTTPPool.put(url: str)`

PUT 请求。

**Returns**: `httpx.Response`


#### `async HTTPPool.patch(url: str)`

PATCH 请求。

**Returns**: `httpx.Response`


#### `async HTTPPool.delete(url: str)`

DELETE 请求。

**Returns**: `httpx.Response`


#### `HTTPPool.get_stats()`

获取连接池配置快照。

**Returns**: `HTTPPoolStats`


#### `HTTPPool.get_stats_dict()`

以字典形式返回统计信息。

**Returns**: `dict[str, Any]`


### `get_http_pool()`

获取全局 HTTP 连接池单例。

**Returns**: `HTTPPool`

---

## backend.services.intent_parser

**文件**: `backend\services\intent_parser.py`

CityFlow LLM 意图解析模块
将用户自然语言输入解析为结构化出行需求，并匹配用户画像。

### `async parse_intent(user_input: str, available_profiles: dict | None = None)`

将用户自然语言输入解析为结构化出行需求。

参数:
    user_input: 用户的自然语言出行需求
    available_profiles: 画像字典，默认使用内置 PROFILES

返回:
    结构化意图字典，包含 time/budget/group/preferences/pace/hard_constraints/matched_profile_id

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| user_input | str | - | - |
| available_profiles | dict | None | None | - |

**Returns**: `dict`

---

## backend.services.ip_rate_limiter

**文件**: `backend\services\ip_rate_limiter.py`

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

### class `IPRateLimitExceededError`

**继承**: `CityFlowException`

IP 速率限制超出。

#### `IPRateLimitExceededError.__init__(message: str = '请求过于频繁，请稍后再试', details: dict[str, Any] | None = None)`

**Returns**: `None`


### class `IPRateLimitResult`

IP 限流检查结果。

#### `IPRateLimitResult.to_headers()`

转换为标准 RateLimit 响应头。

**Returns**: `dict[str, str]`


### class `_LocalWindow`

本地固定窗口计数器。

### class `_LocalIPRateLimiter`

本地内存 IP 限流器。

#### `_LocalIPRateLimiter.__init__()`

**Returns**: `None`


#### `async _LocalIPRateLimiter.check(key: str, limit: int, window: int)`

检查限流，返回 (allowed, remaining, reset_ts)。

**Returns**: `tuple[bool, int, int]`


#### `_LocalIPRateLimiter.is_banned(ip: str)`

检查 IP 是否被封禁。

**Returns**: `bool`


#### `_LocalIPRateLimiter.ban_ip(ip: str, duration: int = _BAN_DURATION)`

封禁 IP。

**Returns**: `None`


#### `_LocalIPRateLimiter.unban_ip(ip: str)`

解封 IP。

**Returns**: `None`


#### `_LocalIPRateLimiter.track_endpoint(ip: str, endpoint: str)`

记录端点访问，返回是否触发可疑行为。

**Returns**: `bool`


#### `_LocalIPRateLimiter.cleanup(max_idle_seconds: int = 600)`

清理过期记录。

**Returns**: `int`


### class `_RedisIPRateLimiter`

基于 Redis 的 IP 限流器。

#### `_RedisIPRateLimiter.__init__(redis_client: aioredis.Redis)`

**Returns**: `None`


#### `async _RedisIPRateLimiter.check(key: str, limit: int, window: int)`

检查限流，返回 (allowed, remaining, reset_ts)。

**Returns**: `tuple[bool, int, int]`


#### `async _RedisIPRateLimiter.is_banned(ip: str)`

检查 IP 是否被封禁。

**Returns**: `bool`


#### `async _RedisIPRateLimiter.ban_ip(ip: str, duration: int = _BAN_DURATION)`

封禁 IP。

**Returns**: `None`


#### `async _RedisIPRateLimiter.unban_ip(ip: str)`

解封 IP。

**Returns**: `None`


#### `async _RedisIPRateLimiter.track_endpoint(ip: str, endpoint: str)`

记录端点访问，返回是否触发可疑行为。

**Returns**: `bool`


### class `IPRateLimiter`

IP 级速率限制器。

提供三层保护：
1. 单端点限流：每个 IP 对每个端点的请求频率限制
2. 全局限流：每个 IP 所有端点的总请求频率限制
3. 可疑行为检测：短时间内大量不同端点访问 -> 自动封禁

用法::

    limiter = IPRateLimiter(redis_client)
    result = await limiter.check("1.2.3.4", "/api/v1/plan_route")

#### `IPRateLimiter.__init__(redis_client: aioredis.Redis | None = None, endpoint_limit: int = _DEFAULT_ENDPOINT_LIMIT, endpoint_window: int = _DEFAULT_ENDPOINT_WINDOW, global_limit: int = _DEFAULT_GLOBAL_LIMIT, global_window: int = _DEFAULT_GLOBAL_WINDOW, ban_duration: int = _BAN_DURATION)`

**Returns**: `None`


#### `async IPRateLimiter.check(ip: str, endpoint: str, endpoint_limit: int | None = None, global_limit: int | None = None)`

检查 IP 对指定端点的限流。

Args:
    ip: 客户端 IP 地址。
    endpoint: API 端点路径。
    endpoint_limit: 覆盖单端点限制（可选）。
    global_limit: 覆盖全局限制（可选）。

Returns:
    IPRateLimitResult 包含限流判定和配额信息。

**Returns**: `IPRateLimitResult`


#### `async IPRateLimiter.manual_ban(ip: str, duration: int | None = None)`

手动封禁 IP。

**Returns**: `None`


#### `async IPRateLimiter.manual_unban(ip: str)`

手动解封 IP。

**Returns**: `None`


#### `async IPRateLimiter.is_banned(ip: str)`

检查 IP 是否被封禁。

**Returns**: `bool`


#### `IPRateLimiter.backend_type()`

当前后端类型：``"redis"`` 或 ``"local"``。

**Returns**: `str`


#### `async IPRateLimiter.cleanup_local()`

清理本地内存中的过期记录。仅本地模式有效。

**Returns**: `int`


### `get_ip_rate_limiter()`

获取全局 IP 限流器单例。

**Returns**: `IPRateLimiter`

---

## backend.services.llm_service

**文件**: `backend\services\llm_service.py`

### `get_client()`

**Returns**: `AsyncOpenAI`

---

### `async chat_stream(message: str, model: str = 'gpt-4o-mini', system_prompt: str = '你是一个数据分析助手，简洁地回答用户问题。')`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| message | str | - | - |
| model | str | 'gpt-4o-mini' | - |
| system_prompt | str | '你是一个数据分析助手，简洁地回答用户问题。' | - |

**Returns**: `AsyncIterator[str]`

---

### `async chat(message: str, model: str = 'gpt-4o-mini')`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| message | str | - | - |
| model | str | 'gpt-4o-mini' | - |

**Returns**: `str`

---

## backend.services.logger

**文件**: `backend\services\logger.py`

CityFlow 结构化日志模块。

提供 JSON 格式的结构化日志输出，支持控制台和文件两种处理器。
所有服务模块统一通过 get_logger() 获取日志器。

### class `JSONFormatter`

**继承**: `logging.Formatter`

将日志记录格式化为 JSON 字符串。

#### `JSONFormatter.format(record: logging.LogRecord)`

**Returns**: `str`


### class `RequestLogger`

请求级日志记录器，封装常用的业务日志方法。

#### `RequestLogger.__init__(logger: logging.Logger)`

**Returns**: `None`


#### `RequestLogger.log_request(method: str, path: str, status_code: int, duration: float, user_id: Optional[str] = None, session_id: Optional[str] = None)`

记录 HTTP 请求日志。

**Returns**: `None`


#### `RequestLogger.log_route_planning(user_input: str, user_type: str, poi_count: int, duration: float)`

记录路线规划日志。

**Returns**: `None`


#### `RequestLogger.log_error(error: Exception, context: str)`

记录错误日志。

**Returns**: `None`


### `setup_logging(level: str = 'INFO')`

初始化全局日志配置。

- 控制台输出 JSON 格式
- 文件输出到 logs/cityflow.log（全量）
- 文件输出到 logs/error.log（仅 ERROR 及以上）

Args:
    level: 根日志器级别，如 "DEBUG" / "INFO" / "WARNING"

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| level | str | 'INFO' | - |

**Returns**: `None`

---

### `get_logger(name: str)`

获取指定名称的日志器。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| name | str | - | - |

**Returns**: `logging.Logger`

---

## backend.services.log_rotation

**文件**: `backend\services\log_rotation.py`

CityFlow 日志轮转配置。

提供两种轮转策略：
- 按大小轮转：单文件 10MB，保留 5 个备份
- 按时间轮转：每天午夜轮转，保留 30 天

### `setup_log_rotation()`

创建并返回两个轮转文件处理器。

Returns:
    (size_handler, time_handler) -- 调用方自行挂载到日志器上

**Returns**: `tuple[RotatingFileHandler, TimedRotatingFileHandler]`

---

## backend.services.message_handlers

**文件**: `backend\services\message_handlers.py`

CityFlow 消息处理器。

注册各类业务消息的处理逻辑，供 MessageQueue 消费端调用。
处理器签名统一为 `async def handler(payload: dict) -> None`。

### `async handle_route_planning(payload: dict[str, Any])`

处理路线规划消息。

payload 结构::

    {
        "session_id": "abc123",
        "user_input": "带女朋友逛商场",
        "callback_url": "https://xxx/callback"  # 可选
    }

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| payload | dict[str, Any] | - | - |

**Returns**: `None`

---

### `async handle_notification(payload: dict[str, Any])`

处理通知消息。

payload 结构::

    {
        "session_id": "abc123",
        "content": "您的路线已更新",
        "msg_type": "info"  # info / warning / error
    }

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| payload | dict[str, Any] | - | - |

**Returns**: `None`

---

### `async handle_analytics(payload: dict[str, Any])`

处理分析事件，记录用户行为。

payload 结构::

    {
        "event_type": "route_planned",
        "user_id": "u_001",
        "data": {"city": "成都", "poi_count": 5}
    }

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| payload | dict[str, Any] | - | - |

**Returns**: `None`

---

### `get_handler(name: str)`

根据名称获取已注册的处理器。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| name | str | - | - |

**Returns**: `MessageHandler | None`

---

### `async start_default_consumers()`

启动所有已注册处理器的默认消费者（用于应用启动时调用）。

队列名与处理器名一一对应：
- route_planning -> cityflow:mq:route_planning
- notification   -> cityflow:mq:notification
- analytics      -> cityflow:mq:analytics

**Returns**: `None`

---

## backend.services.message_queue

**文件**: `backend\services\message_queue.py`

CityFlow Redis 消息队列。

基于 Redis List 实现的生产者/消费者模型，支持：
- 多队列隔离（queue 前缀分组）
- 多消费者并发
- 优雅启停
- 全局单例访问

### class `Message`

消息信封，封装元数据 + 业务载荷。

#### `Message.__init__(queue: str, payload: dict[str, Any])`

**Returns**: `None`


#### `Message.to_json()`

序列化为 JSON 字符串，用于写入 Redis。

**Returns**: `str`


#### `Message.from_json(data: str | bytes)`

从 Redis 读取的 JSON 反序列化。

**Returns**: `Message`


### class `MessageQueue`

基于 Redis List 的消息队列。

Args:
    redis_url: Redis 连接 URL，默认从配置读取。
    prefix: 所有队列键的前缀，避免 key 冲突。
    max_retries: 单条消息最大重试次数。

#### `MessageQueue.__init__(redis_url: str | None = None, prefix: str = 'cityflow:mq:', max_retries: int = 3)`

**Returns**: `None`


#### `async MessageQueue.publish(queue: str, payload: dict[str, Any])`

发布一条消息到指定队列。

Args:
    queue: 队列名称。
    payload: 业务消息体。

Returns:
    已发布的 Message 对象（含 message_id）。

**Returns**: `Message`


#### `async MessageQueue.publish_many(queue: str, payloads: list[dict[str, Any]])`

批量发布消息，使用 pipeline 减少 RTT。

**Returns**: `list[Message]`


#### `async MessageQueue.consume(queue: str, handler: MessageHandler)`

阻塞消费循环（应作为后台 task 运行）。

Args:
    queue: 队列名称。
    handler: 异步消息处理函数。
    timeout: BLPOP 超时秒数，到时自动重试。

**Returns**: `None`


#### `MessageQueue.start_consumer(queue: str, handler: MessageHandler)`

启动一个后台消费者 task。

Args:
    queue: 队列名称。
    handler: 异步消息处理函数。

Returns:
    消费者 asyncio.Task。

**Returns**: `asyncio.Task`


#### `async MessageQueue.stop()`

停止所有消费者并关闭 Redis 连接。

**Returns**: `None`


#### `async MessageQueue.queue_length(queue: str)`

查询队列长度。

**Returns**: `int`


#### `async MessageQueue.clear_queue(queue: str)`

清空指定队列，返回删除的消息数。

**Returns**: `int`


### `get_message_queue()`

获取全局消息队列实例（懒初始化）。

**Returns**: `MessageQueue`

---

### `async close_message_queue()`

关闭全局消息队列（用于 FastAPI shutdown 事件）。

**Returns**: `None`

---

## backend.services.metrics

**文件**: `backend\services\metrics.py`

CityFlow 应用指标收集模块

提供 Prometheus 格式的指标收集，包括：
- HTTP 请求计数与延迟
- 活跃会话数
- 路线规划统计
- POI 查询统计

### class `MetricsMiddleware`

指标收集中间件

#### `MetricsMiddleware.__init__(app)`


### `track_route_planning(user_type: str)`

记录路线规划

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| user_type | str | - | - |

---

### `track_poi_query()`

记录POI查询

---

### `get_metrics()`

获取 Prometheus 格式的指标数据

---

## backend.services.narrator

**文件**: `backend\services\narrator.py`

CityFlow 路线文案引擎。

将求解器输出的路线数据转换为用户友好的文案描述。
模板驱动 + LLM 局部润色。

### `async generate_narrative(route_result: dict[str, Any], user_intent: dict[str, Any])`

生成路线文案。

将 solver.solve_route() 的输出转换为用户友好的文案描述。

Args:
    route_result: solver.solve_route() 的返回值，包含 route 列表。
    user_intent: 用户意图字典，包含 group、preferences 等。
    enable_llm_polish: 是否启用 LLM 润色（默认关闭，测试时可关闭）。

Returns:
    包含 opening、steps、closing、emotion_highlights 的文案字典。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| route_result | dict[str, Any] | - | - |
| user_intent | dict[str, Any] | - | - |

**Returns**: `dict[str, Any]`

---

## backend.services.notification

**文件**: `backend\services\notification.py`

CityFlow 消息推送服务。

提供路线更新、步骤变更、错误通知等实时推送能力，
供其他业务模块调用，将变更实时推送给已订阅的客户端。

### `async notify_route_update(route_id: str, update_type: str, data: dict[str, Any])`

通知路线订阅者：路线发生了变更。

Args:
    route_id: 路线 ID
    update_type: 变更类型（new_step / complete / adjusted / removed）
    data: 变更的具体数据

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| route_id | str | - | - |
| update_type | str | - | - |
| data | dict[str, Any] | - | - |

**Returns**: `None`

---

### `async notify_new_step(route_id: str, step: dict[str, Any])`

通知路线新增了一个步骤（用于 SSE 流式规划过程中的实时推送）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| route_id | str | - | - |
| step | dict[str, Any] | - | - |

**Returns**: `None`

---

### `async notify_route_complete(route_id: str, route: dict[str, Any])`

通知路线规划完成。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| route_id | str | - | - |
| route | dict[str, Any] | - | - |

**Returns**: `None`

---

### `async notify_route_adjusted(route_id: str, changes: list[dict[str, Any]])`

通知路线已被对话调整。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| route_id | str | - | - |
| changes | list[dict[str, Any]] | - | - |

**Returns**: `None`

---

### `async notify_error(session_id: str, error: str)`

向单个客户端发送错误通知。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| session_id | str | - | - |
| error | str | - | - |

**Returns**: `None`

---

### `async notify_personal(session_id: str, message: dict[str, Any])`

向单个客户端发送自定义消息。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| session_id | str | - | - |
| message | dict[str, Any] | - | - |

**Returns**: `None`

---

### `async broadcast_system_message(text: str)`

向所有在线客户端广播系统消息（维护通知、公告等）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| text | str | - | - |

**Returns**: `None`

---

## backend.services.parallel

**文件**: `backend\services\parallel.py`

CityFlow 异步并行处理模块。

提供并行过滤、并行求解等并发工具。

### `async parallel_filter(items: list[T], filter_func: Callable[List(elts=[Name(id='T', ctx=Load())], ctx=Load()), Coroutine[Any, Any, bool]], max_workers: int = 4)`

并行过滤列表。

Args:
    items: 待过滤列表
    filter_func: 异步过滤函数，返回 True 保留
    max_workers: 最大并发数

Returns:
    过滤后的列表（保持原顺序）

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| items | list[T] | - | - |
| filter_func | Callable[List(elts=[Name(id='T', ctx=Load())], ctx=Load()), Coroutine[Any, Any, bool]] | - | - |
| max_workers | int | 4 | - |

**Returns**: `list[T]`

---

### `async parallel_solve(solve_func: Callable[List(elts=[], ctx=Load()), Coroutine[Any, Any, dict[str, Any]]], n_attempts: int = 3)`

并行运行多次求解，返回评分最高的结果。

Args:
    solve_func: 无参异步求解函数，返回带 'score' 字段的字典
    n_attempts: 并行尝试次数

Returns:
    评分最高的结果

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| solve_func | Callable[List(elts=[], ctx=Load()), Coroutine[Any, Any, dict[str, Any]]] | - | - |
| n_attempts | int | 3 | - |

**Returns**: `dict[str, Any]`

---

### `async parallel_map(items: list[T], func: Callable[List(elts=[Name(id='T', ctx=Load())], ctx=Load()), Coroutine[Any, Any, Any]], max_workers: int = 4)`

并行映射函数到列表，保持顺序。

Args:
    items: 输入列表
    func: 异步映射函数
    max_workers: 最大并发数

Returns:
    与输入等长的结果列表

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| items | list[T] | - | - |
| func | Callable[List(elts=[Name(id='T', ctx=Load())], ctx=Load()), Coroutine[Any, Any, Any]] | - | - |
| max_workers | int | 4 | - |

**Returns**: `list[Any]`

---

### `async with_timeout(coro: Coroutine[Any, Any, T], timeout_seconds: float = 10.0, fallback: T | None = None)`

给协程加超时保护。

Args:
    coro: 待执行协程
    timeout_seconds: 超时秒数
    fallback: 超时时返回的默认值

Returns:
    协程结果或 fallback

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| coro | Coroutine[Any, Any, T] | - | - |
| timeout_seconds | float | 10.0 | - |
| fallback | T | None | None | - |

**Returns**: `T | None`

---

## backend.services.pool_monitor

**文件**: `backend\services\pool_monitor.py`

CityFlow 连接池监控。

聚合数据库连接池与 HTTP 连接池的统计信息，提供：
- 统一的统计查询接口
- 健康检查
- 告警阈值检测（连接池使用率过高）

### class `PoolHealthReport`

连接池健康报告。

#### `PoolHealthReport.all_healthy()`

**Returns**: `bool`


### class `PoolMonitor`

连接池监控器。

Args:
    db_pool: 数据库连接池实例。
    http_pool: HTTP 连接池实例。
    utilization_warn_threshold: 使用率告警阈值（0.0 ~ 1.0）。

#### `PoolMonitor.__init__(db_pool: DatabasePool, http_pool: HTTPPool, utilization_warn_threshold: float = _UTILIZATION_WARN_THRESHOLD)`

**Returns**: `None`


#### `async PoolMonitor.get_stats()`

获取全部连接池统计信息。

**Returns**: `dict[str, Any]`


#### `async PoolMonitor.check_health()`

执行全面健康检查，返回报告。

**Returns**: `PoolHealthReport`


#### `PoolMonitor.report()`

生成快速报告（不做网络调用，纯内存读取）。

**Returns**: `dict[str, Any]`


### `get_pool_monitor()`

获取全局连接池监控器单例。

**Returns**: `PoolMonitor`

---

## backend.services.quota

**文件**: `backend\services\quota.py`

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

### class `QuotaPeriod`

**继承**: `str`, `Enum`

配额统计周期。

### class `QuotaExceededError`

**继承**: `CityFlowException`

用户配额超出限制。

#### `QuotaExceededError.__init__(message: str = '已达到使用上限，请稍后再试', details: dict[str, Any] | None = None)`

**Returns**: `None`


### class `QuotaInfo`

单个周期的配额信息。

#### `QuotaInfo.within_quota()`

是否在配额范围内。

**Returns**: `bool`


### class `QuotaCheckResult`

配额检查综合结果，包含所有周期信息。

#### `QuotaCheckResult.within_quota()`

所有周期是否都在配额范围内。

**Returns**: `bool`


#### `QuotaCheckResult.exceeded_periods()`

已超限的周期列表。

**Returns**: `list[QuotaPeriod]`


#### `QuotaCheckResult.to_dict()`

转换为 API 响应字典。

**Returns**: `dict[str, Any]`


### class `QuotaManager`

用户配额管理器。

使用 Redis INCR + EXPIRE 实现原子性的配额计数。
支持同时检查多个周期（如 hourly + daily），全部通过才算在配额内。

Args:
    redis_client: Redis 异步客户端，为 None 时所有检查默认放行。
    quota_limits: 配额上限配置，默认使用模块级 ``QUOTA_LIMITS``。

#### `QuotaManager.__init__(redis_client: aioredis.Redis | None = None, quota_limits: dict[str, dict[str, int]] | None = None)`

**Returns**: `None`


#### `async QuotaManager.get_usage(user_id: str, quota_type: str)`

查询用户当前配额使用情况（不消耗配额）。

Args:
    user_id: 用户标识。
    quota_type: 操作类型，须在 ``QUOTA_LIMITS`` 中注册。

Returns:
    QuotaCheckResult 包含各周期的使用详情。

**Returns**: `QuotaCheckResult`


#### `async QuotaManager.check_and_consume(user_id: str, quota_type: str, amount: int = 1)`

检查配额并消耗一次。原子操作。

如果任一周期已超限，不会递增计数，直接返回当前状态。

Args:
    user_id: 用户标识。
    quota_type: 操作类型。
    amount: 消耗量，默认 1。

Returns:
    QuotaCheckResult，``within_quota`` 为 False 表示已超限。

**Returns**: `QuotaCheckResult`


#### `async QuotaManager.reset(user_id: str, quota_type: str, period: QuotaPeriod | None = None)`

重置用户配额计数。

Args:
    user_id: 用户标识。
    quota_type: 操作类型。
    period: 指定周期，为 None 时重置所有周期。

Returns:
    删除的 key 数量。

**Returns**: `int`


### `get_quota_manager()`

获取全局配额管理器单例。

首次调用时根据配置自动创建。Redis 不可用时配额检查默认放行。

**Returns**: `QuotaManager`

---

## backend.services.rate_limiter

**文件**: `backend\services\rate_limiter.py`

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

### class `RateLimitExceededError`

**继承**: `CityFlowException`

速率限制超出。

#### `RateLimitExceededError.__init__(message: str = '请求过于频繁，请稍后再试', details: dict[str, Any] | None = None)`

**Returns**: `None`


### class `RateLimitResult`

速率限制检查结果。

#### `RateLimitResult.to_headers()`

转换为标准 RateLimit 响应头。

**Returns**: `dict[str, str]`


### class `_LocalWindow`

本地固定窗口计数器。

### class `_LocalRateLimiter`

本地内存固定窗口限流器，单实例降级方案。

不支持跨进程共享，适合开发环境或 Redis 不可用时。

#### `_LocalRateLimiter.__init__()`

**Returns**: `None`


#### `async _LocalRateLimiter.check(key: str, limit: int, window: int)`

**Returns**: `RateLimitResult`


#### `_LocalRateLimiter.cleanup(max_idle_seconds: int = 600)`

清理长时间无活动的窗口，返回清理数量。

**Returns**: `int`


### class `_RedisRateLimiter`

基于 Redis Sorted Set 的滑动窗口限流器。

使用 ZREMRANGEBYSCORE + ZCARD + EXPIRE 的 pipeline 实现，
原子性强，支持多实例共享。

#### `_RedisRateLimiter.__init__(redis_client: aioredis.Redis)`

**Returns**: `None`


#### `async _RedisRateLimiter.check(key: str, limit: int, window: int)`

**Returns**: `RateLimitResult`


### class `RateLimiter`

速率限制器统一入口。

优先使用 Redis 实现分布式限流；Redis 不可用时自动降级到本地内存。

用法::

    limiter = get_rate_limiter()
    result = await limiter.is_allowed("user:123", limit=60, window=60)
    if not result.allowed:
        raise RateLimitExceededError(details=result.to_headers())

#### `RateLimiter.__init__(redis_client: aioredis.Redis | None = None)`

**Returns**: `None`


#### `async RateLimiter.is_allowed(key: str, limit: int, window: int = 60)`

检查是否允许请求。

Args:
    key: 限制维度键，如 ``"user:123"``、``"ip:1.2.3.4"``。
    limit: 时间窗口内允许的最大请求数。
    window: 时间窗口大小（秒），默认 60。

Returns:
    RateLimitResult 包含是否允许、剩余配额、重置时间。

**Returns**: `RateLimitResult`


#### `RateLimiter.backend_type()`

当前后端类型：``"redis"`` 或 ``"local"``。

**Returns**: `str`


#### `async RateLimiter.cleanup_local()`

清理本地内存中的过期窗口。仅本地模式有效。

**Returns**: `int`


### `get_rate_limiter()`

获取全局速率限制器单例。

首次调用时根据配置自动创建。如配置了 Redis 则使用分布式模式，
否则降级到本地内存。

**Returns**: `RateLimiter`

---

## backend.services.registry

**文件**: `backend\services\registry.py`

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

### class `ServiceInfo`

**继承**: `BaseModel`

服务实例信息。

#### `ServiceInfo.to_dict()`

序列化为字典（用于 API 响应）。

**Returns**: `dict[str, Any]`


### class `ServiceRegistry`

服务注册中心。

管理所有已注册服务实例，周期性检查心跳超时，
自动将超时实例标记为 unhealthy。

Args:
    heartbeat_timeout: 心跳超时秒数，超过此时间未收到心跳则标记为不健康。
    health_check_interval: 健康检查周期（秒）。

#### `ServiceRegistry.__init__(heartbeat_timeout: int = 30, health_check_interval: int = 10)`

**Returns**: `None`


#### `async ServiceRegistry.register(service: ServiceInfo)`

注册一个服务实例。

**Returns**: `None`


#### `async ServiceRegistry.deregister(service_id: str)`

注销一个服务实例。返回是否确实存在并被移除。

**Returns**: `bool`


#### `async ServiceRegistry.heartbeat(service_id: str)`

更新服务心跳。返回服务是否存在。

**Returns**: `bool`


#### `async ServiceRegistry.get_service(service_name: str)`

获取指定服务的一个健康实例（随机负载均衡）。

**Returns**: `ServiceInfo | None`


#### `async ServiceRegistry.get_all_services(service_name: str | None = None)`

获取所有服务实例，可按服务名过滤。

**Returns**: `list[ServiceInfo]`


#### `async ServiceRegistry.remove_unhealthy(service_name: str | None = None)`

移除所有不健康的实例。返回移除数量。

**Returns**: `int`


#### `async ServiceRegistry.start()`

启动健康检查后台任务。

**Returns**: `None`


#### `async ServiceRegistry.stop()`

停止健康检查后台任务。

**Returns**: `None`


#### `ServiceRegistry.service_count()`

当前注册的服务实例总数。

**Returns**: `int`


#### `ServiceRegistry.healthy_count()`

当前健康的服务实例数。

**Returns**: `int`


### `get_service_registry()`

获取全局服务注册中心单例。

**Returns**: `ServiceRegistry`

---

## backend.services.resilient_service

**文件**: `backend\services\resilient_service.py`

CityFlow 弹性服务集成模块。

将熔断器、重试、降级策略应用到 CityFlow 的核心服务调用上。
这是实际对接业务的地方，不是示例。

设计原则：
    - 外部依赖（LLM、高德API）必须有容错
    - 内部计算（solver、narrator）不需要熔断，但可以加重试
    - 降级结果必须标记 fallback=True，前端据此提示用户

### `async chat_with_resilience(message: str, model: str = 'gpt-4o-mini')`

带容错的 LLM 对话。

调用链：retry -> fallback -> circuit_breaker -> 实际调用
1. circuit_breaker: 检查熔断状态，失败计数
2. fallback: 熔断器打开时返回降级文案
3. retry: 超时/连接错误时自动重试

Args:
    message: 用户消息。
    model: 模型名称。

Returns:
    LLM 回复文本，熔断时返回降级文案。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| message | str | - | - |
| model | str | 'gpt-4o-mini' | - |

**Returns**: `str`

---

### `async plan_route_with_resilience(candidates: list[dict[str, Any]], user_intent: dict[str, Any], start_time: str = '09:00')`

带容错的路线规划。

solver 本身是 CPU 计算，不会超时。但如果上游调用链
中有任何网络调用失败（如距离矩阵 API），这里兜底。

Args:
    candidates: 候选 POI 列表。
    user_intent: 用户意图。
    start_time: 出发时间。

Returns:
    路线规划结果，降级时返回空路线 + fallback=True。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| candidates | list[dict[str, Any]] | - | - |
| user_intent | dict[str, Any] | - | - |
| start_time | str | '09:00' | - |

**Returns**: `dict[str, Any]`

---

### `async generate_narrative_with_resilience(route_result: dict[str, Any], user_intent: dict[str, Any])`

带容错的文案生成。

文案生成中 LLM 润色部分可能超时，降级为纯模板文案。

Args:
    route_result: solver 输出。
    user_intent: 用户意图。
    enable_llm_polish: 是否启用 LLM 润色。

Returns:
    文案字典，降级时返回简洁模板 + fallback=True。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| route_result | dict[str, Any] | - | - |
| user_intent | dict[str, Any] | - | - |

**Returns**: `dict[str, Any]`

---

### `get_all_circuit_breakers()`

获取所有熔断器的状态和指标，供监控端点使用。

Returns:
    {name: {state, failure_count, metrics}} 的字典。

**Returns**: `dict[str, dict[str, Any]]`

---

## backend.services.resource_monitor

**文件**: `backend\services\resource_monitor.py`

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

### class `AlertSeverity`

**继承**: `StrEnum`

告警严重程度。

### class `ComparisonOperator`

**继承**: `StrEnum`

阈值比较运算符。

### class `ResourceMetrics`

系统资源快照。

#### `ResourceMetrics.to_dict()`

转换为字典。

**Returns**: `dict[str, Any]`


### class `AlertRule`

告警规则。

Attributes:
    name: 规则唯一名称，如 ``"high_cpu"``
    metric: 对应 ``ResourceMetrics`` 的字段名
    threshold: 阈值
    operator: 比较运算符，默认 ``>``（当前值大于阈值时触发）
    severity: 告警严重程度
    cooldown_seconds: 冷却期（秒），同一规则在此时间内不重复触发

### class `AlertEvent`

告警事件。

Attributes:
    rule_name: 触发的规则名称
    metric: 指标字段名
    current_value: 当前指标值
    threshold: 阈值
    severity: 严重程度
    message: 告警消息
    timestamp: 触发时间

#### `AlertEvent.to_dict()`

转换为字典。

**Returns**: `dict[str, Any]`


### class `ResourceMonitor`

系统资源监控器。

职责：
- 定期采集系统资源指标
- 按配置的告警规则评估指标
- 触发告警回调（日志 + 自定义通知）

Args:
    disk_path: 磁盘采集路径。

#### `ResourceMonitor.__init__(disk_path: str = '/')`

**Returns**: `None`


#### `ResourceMonitor.add_rule(rule: AlertRule)`

添加告警规则。

如果已存在同名规则，会被覆盖。

Args:
    rule: 告警规则实例。

**Returns**: `None`


#### `ResourceMonitor.remove_rule(name: str)`

移除告警规则。

Args:
    name: 规则名称。

Returns:
    是否成功移除（规则不存在返回 False）。

**Returns**: `bool`


#### `ResourceMonitor.get_rules()`

获取所有告警规则列表。

**Returns**: `list[AlertRule]`


#### `ResourceMonitor.add_callback(callback: AlertCallback)`

注册告警回调。

回调将在告警触发时被异步调用，单个回调异常不影响其他回调。

Args:
    callback: 异步回调 ``(event: AlertEvent) -> None``

**Returns**: `None`


#### `async ResourceMonitor.start_monitoring(interval: int = 60)`

启动后台监控循环。

以 ``asyncio.create_task`` 方式启动，不阻塞调用方。
重复调用不会创建多个任务。

Args:
    interval: 采集间隔（秒），默认 60。

**Returns**: `None`


#### `async ResourceMonitor.stop_monitoring()`

停止后台监控循环。

**Returns**: `None`


#### `ResourceMonitor.is_running()`

监控是否正在运行。

**Returns**: `bool`


#### `ResourceMonitor.latest_metrics()`

最近一次采集的指标快照。

**Returns**: `ResourceMetrics | None`


#### `ResourceMonitor.get_current_metrics()`

立即采集一次指标并返回。

**Returns**: `ResourceMetrics`


#### `ResourceMonitor.get_status()`

返回监控器当前状态。

**Returns**: `dict[str, Any]`


### `collect_metrics(disk_path: str = '/')`

采集当前系统资源指标。

Args:
    disk_path: 磁盘挂载路径（Windows 下无效，使用所有磁盘）。

Returns:
    系统资源快照。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| disk_path | str | '/' | - |

**Returns**: `ResourceMetrics`

---

### `get_resource_monitor()`

获取全局资源监控器单例。

首次调用时自动加载预定义告警规则。

**Returns**: `ResourceMonitor`

---

### `reset_resource_monitor()`

重置全局资源监控器（仅用于测试）。

**Returns**: `None`

---

## backend.services.retry

**文件**: `backend\services\retry.py`

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

### class `RetryExhaustedError`

**继承**: `Exception`

所有重试用尽后抛出，保留最后一次异常。

#### `RetryExhaustedError.__init__(message: str, last_exception: BaseException | None = None, attempts: int = 0)`

**Returns**: `None`


### `retry(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0, max_delay: float = 60.0, jitter: bool = True, exceptions: type[BaseException] | tuple[type[BaseException], Ellipsis] = Exception, on_retry: Callable[List(elts=[Name(id='int', ctx=Load()), Name(id='BaseException', ctx=Load())], ctx=Load()), None] | None = None)`

指数退避重试装饰器。

Args:
    max_retries: 最大重试次数（不含首次调用）。0 表示不重试。
    delay: 首次重试前的等待秒数。
    backoff: 每次重试的延迟倍数。
    max_delay: 延迟上限秒数，防止退避过长。
    jitter: 是否添加随机抖动（防止雪崩）。
    exceptions: 触发重试的异常类型。
    on_retry: 重试前的回调函数，接收 (attempt_number, exception)。

Returns:
    装饰器。

Example::

    @retry(max_retries=2, delay=0.5, exceptions=(TimeoutError,))
    async def fetch_data(url: str) -> bytes:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                return await resp.read()

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| max_retries | int | 3 | - |
| delay | float | 1.0 | - |
| backoff | float | 2.0 | - |
| max_delay | float | 60.0 | - |
| jitter | bool | True | - |
| exceptions | type[BaseException] | tuple[type[BaseException], Ellipsis] | Exception | - |
| on_retry | Callable[List(elts=[Name(id='int', ctx=Load()), Name(id='BaseException', ctx=Load())], ctx=Load()), None] | None | None | - |

**Returns**: `Callable[List(elts=[Name(id='F', ctx=Load())], ctx=Load()), F]`

---

## backend.services.scheduled_backup

**文件**: `backend\services\scheduled_backup.py`

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

### class `ScheduledBackup`

定时备份调度器。

通过 asyncio.Task 在后台循环执行备份任务。
两次备份之间通过 asyncio.sleep 等待，可被 cancel 安全中断。

Args:
    interval_hours: 备份间隔（小时），默认 24。
    keep_count: 每次备份后保留的版本数量，默认 10。

#### `ScheduledBackup.__init__(interval_hours: int = 24, keep_count: int = 10)`

**Returns**: `None`


#### `async ScheduledBackup.start()`

启动定时备份调度器。

如果已经在运行则忽略重复调用。

**Returns**: `None`


#### `async ScheduledBackup.stop()`

停止定时备份调度器。

取消后台任务并等待其完成。

**Returns**: `None`


#### `ScheduledBackup.is_running()`

调度器是否正在运行。

**Returns**: `bool`


#### `async ScheduledBackup.run_now()`

立即执行一次备份（不等待定时周期）。

Returns:
    备份名称，失败返回 None。

**Returns**: `str | None`


### `get_scheduled_backup()`

获取全局定时备份调度器实例。

**Returns**: `ScheduledBackup`

---

### `reset_scheduled_backup()`

重置全局定时备份调度器（仅用于测试）。

**Returns**: `None`

---

## backend.services.session

**文件**: `backend\services\session.py`

CityFlow 分布式会话管理。

基于 Redis 的会话存储，支持：
- 会话创建 / 读取 / 更新 / 删除
- 自动 TTL 过期
- 用户维度会话查询
- 过期会话清理统计

### class `SessionManager`

基于 Redis 的会话管理器。

会话数据结构：
{
    "session_id": "uuid",
    "user_id": "optional-user-id",
    "created_at": "ISO-8601",
    "last_active": "ISO-8601",
    "data": {}
}

#### `SessionManager.__init__(redis_url: str = 'redis://localhost:6379', prefix: str = 'session:', default_ttl: int = 3600)`

**Returns**: `None`


#### `async SessionManager.connect()`

建立 Redis 连接。幂等，已连接时跳过。

**Returns**: `None`


#### `async SessionManager.close()`

关闭 Redis 连接。

**Returns**: `None`


#### `async SessionManager.create_session(user_id: str | None = None)`

创建新会话，返回 session_id。

**Returns**: `str`


#### `async SessionManager.get_session(session_id: str)`

获取会话数据，不存在或已过期返回 None。

**Returns**: `dict[str, Any] | None`


#### `async SessionManager.update_session(session_id: str, data: dict[str, Any])`

更新会话数据，返回是否成功。

**Returns**: `bool`


#### `async SessionManager.delete_session(session_id: str)`

删除会话，返回是否存在并被删除。

**Returns**: `bool`


#### `async SessionManager.refresh_session(session_id: str)`

刷新会话过期时间（续期），返回是否成功。

**Returns**: `bool`


#### `async SessionManager.get_user_sessions(user_id: str)`

获取指定用户的所有活跃会话。

**Returns**: `list[dict[str, Any]]`


#### `async SessionManager.get_stats()`

获取会话统计信息。

**Returns**: `dict[str, int]`


### `get_session_manager()`

获取全局会话管理器（懒初始化）。

**Returns**: `SessionManager`

---

## backend.services.solver

**文件**: `backend\services\solver.py`

CityFlow TSPTW 情绪混合求解器。

5阶段求解：
1. TW-Nearest Neighbor 贪心初始化（含时间窗可行性剪枝）
2. 2-opt 局部搜索改进
3. 呼吸空间插入（高兴奋POI之间插入休息节点）
4. 高潮收尾检查（确保最后一个POI情绪足够高）
5. 输出组装

### `estimate_distance(poi_a: dict[str, Any] | None, poi_b: dict[str, Any] | None)`

估算两点间实际道路距离（米）。None 安全。带缓存。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi_a | dict[str, Any] | None | - | - |
| poi_b | dict[str, Any] | None | - | - |

**Returns**: `float`

---

### `estimate_travel_time(poi_a: dict[str, Any] | None, poi_b: dict[str, Any] | None)`

估算两点间旅行时间（分钟）。None 安全。带缓存。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi_a | dict[str, Any] | None | - | - |
| poi_b | dict[str, Any] | None | - | - |

**Returns**: `float`

---

### `estimate_steps(poi: dict[str, Any])`

根据停留时间和体力需求估算步数。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi | dict[str, Any] | - | - |

**Returns**: `int`

---

### `solve_route(candidates: list[dict[str, Any]], user_intent: dict[str, Any], start_time: str = '09:00')`

求解最优路线。

Args:
    candidates: 候选 POI 列表（已经过 filter_candidates 过滤）
    user_intent: 用户意图字典
    start_time: 出发时间，格式 "HH:MM"

Returns:
    包含 route, emotion_curve, total_cost, unused_candidates, breathing_spots 的字典

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| candidates | list[dict[str, Any]] | - | - |
| user_intent | dict[str, Any] | - | - |
| start_time | str | '09:00' | - |

**Returns**: `dict[str, Any]`

---

## backend.services.task_queue

**文件**: `backend\services\task_queue.py`

CityFlow 异步任务队列。

基于 asyncio.Queue 实现的内存任务队列，支持：
- 多 worker 并发执行
- 任务状态追踪（pending / running / completed / failed / cancelled）
- 任务取消
- 全局单例访问

### class `TaskStatus`

**继承**: `str`, `Enum`

任务生命周期状态。

### class `Task`

单个任务的状态容器。

#### `Task.__init__(task_id: str, func: Callable[Ellipsis, Any], args: tuple, kwargs: dict)`

**Returns**: `None`


#### `Task.to_dict()`

序列化为 API 响应字典。

**Returns**: `dict[str, Any]`


### class `TaskQueue`

基于 asyncio.Queue 的内存任务队列。

#### `TaskQueue.__init__(max_workers: int = 5)`

**Returns**: `None`


#### `async TaskQueue.start()`

启动所有 worker 协程。

**Returns**: `None`


#### `async TaskQueue.stop()`

停止所有 worker，等待正在执行的任务完成。

**Returns**: `None`


#### `async TaskQueue.submit(func: Callable[Ellipsis, Any])`

提交一个异步任务，返回 task_id。

**Returns**: `str`


#### `async TaskQueue.get_task(task_id: str)`

根据 task_id 获取任务对象。

**Returns**: `Optional[Task]`


#### `async TaskQueue.cancel_task(task_id: str)`

取消一个尚未开始执行的任务。

Returns:
    True 表示取消成功，False 表示任务不存在或已在执行。

**Returns**: `bool`


#### `async TaskQueue.list_tasks(status: Optional[TaskStatus] = None)`

列出所有任务，可按状态过滤。

**Returns**: `list[dict[str, Any]]`


### `get_task_queue()`

获取全局任务队列实例（懒初始化）。

**Returns**: `TaskQueue`

---

## backend.services.template_engine

**文件**: `backend\services\template_engine.py`

CityFlow Jinja2 模板引擎。

提供模板渲染、缓存、自定义过滤器/全局变量等功能。
模板编译结果缓存在内存中，避免重复编译开销。

### class `TemplateRenderError`

**继承**: `CityFlowException`

模板渲染失败。

#### `TemplateRenderError.__init__(message: str = '模板渲染失败', details: dict[str, Any] | None = None)`

**Returns**: `None`


### class `TemplateCache`

编译模板的 TTL + LRU 内存缓存。

缓存键为模板内容的 SHA256 哈希，值为编译后的 Template 对象。
文件模板以文件路径 + mtime 为键，字符串模板以内容哈希为键。

#### `TemplateCache.__init__(max_size: int = 256, ttl_seconds: int = 600)`

**Returns**: `None`


#### `TemplateCache.hits()`

**Returns**: `int`


#### `TemplateCache.misses()`

**Returns**: `int`


#### `TemplateCache.size()`

**Returns**: `int`


#### `TemplateCache.get(key: str)`

获取缓存的编译模板，过期则删除并返回 None。

**Returns**: `Template | None`


#### `TemplateCache.set(key: str, template: Template)`

写入缓存，满时淘汰最旧条目。

**Returns**: `None`


#### `TemplateCache.invalidate(key: str)`

删除指定缓存条目。

**Returns**: `bool`


#### `TemplateCache.clear()`

清空缓存。

**Returns**: `None`


### class `TemplateEngine`

Jinja2 模板引擎，带编译缓存。

Args:
    template_dir: 模板文件目录，默认 ``templates``。
    cache_max_size: 缓存最大条目数。
    cache_ttl: 缓存条目 TTL（秒）。

#### `TemplateEngine.__init__(template_dir: str = 'templates', cache_max_size: int = 256, cache_ttl: int = 600)`

**Returns**: `None`


#### `TemplateEngine.cache()`

暴露缓存实例，便于监控和测试。

**Returns**: `TemplateCache`


#### `TemplateEngine.string_cache()`

字符串模板缓存实例。

**Returns**: `TemplateCache`


#### `TemplateEngine.template_dir()`

**Returns**: `Path`


#### `TemplateEngine.render(template_name: str, context: dict[str, Any] | None = None)`

渲染文件模板。

Args:
    template_name: 模板文件名（相对于 template_dir）。
    context: 模板上下文变量。

Returns:
    渲染后的字符串。

Raises:
    TemplateRenderError: 模板加载或渲染失败。

**Returns**: `str`


#### `TemplateEngine.render_string(template_string: str, context: dict[str, Any] | None = None)`

渲染模板字符串（带缓存）。

Args:
    template_string: Jinja2 模板字符串。
    context: 模板上下文变量。

Returns:
    渲染后的字符串。

Raises:
    TemplateRenderError: 模板编译或渲染失败。

**Returns**: `str`


#### `TemplateEngine.add_filter(name: str, func: Any)`

注册自定义 Jinja2 过滤器。

**Returns**: `None`


#### `TemplateEngine.add_global(name: str, value: Any)`

注册全局模板变量。

**Returns**: `None`


#### `TemplateEngine.invalidate_cache()`

清空所有缓存。

**Returns**: `None`


### `get_template_engine()`

获取全局模板引擎单例。

**Returns**: `TemplateEngine`

---

### `reset_template_engine()`

重置全局单例（测试用）。

**Returns**: `None`

---

### `render_template(template_name: str, context: dict[str, Any] | None = None)`

渲染模板（使用全局引擎）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| template_name | str | - | - |
| context | dict[str, Any] | None | None | - |

**Returns**: `str`

---

### `render_string(template_string: str, context: dict[str, Any] | None = None)`

渲染模板字符串（使用全局引擎）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| template_string | str | - | - |
| context | dict[str, Any] | None | None | - |

**Returns**: `str`

---

### `invalidate_template_cache()`

清空全局模板缓存（使用全局引擎）。

**Returns**: `None`

---

## backend.services.time_utils

**文件**: `backend\services\time_utils.py`

CityFlow 时间处理公共模块。

提供时间解析、格式化、营业时间解析等函数，
消除 solver.py / dialogue.py / filters.py 中的重复实现。

### `parse_time(time_str: str)`

解析 HH:MM 时间字符串为 datetime 对象（基准日 2000-01-01）。

Args:
    time_str: 时间字符串，格式 "HH:MM"

Returns:
    datetime 对象

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| time_str | str | - | - |

**Returns**: `datetime`

---

### `format_time(dt: datetime)`

格式化 datetime 为 HH:MM 字符串。

Args:
    dt: datetime 对象

Returns:
    时间字符串，格式 "HH:MM"

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| dt | datetime | - | - |

**Returns**: `str`

---

### `add_minutes(time_str: str, minutes: int)`

时间加分钟。

Args:
    time_str: 时间字符串
    minutes: 分钟数

Returns:
    新的时间字符串

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| time_str | str | - | - |
| minutes | int | - | - |

**Returns**: `str`

---

### `time_difference(time1: str, time2: str)`

计算时间差（分钟）。

Args:
    time1: 起始时间
    time2: 结束时间

Returns:
    时间差（分钟），正数表示 time2 晚于 time1

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| time1 | str | - | - |
| time2 | str | - | - |

**Returns**: `int`

---

### `is_time_in_range(time_str: str, start: str, end: str)`

检查时间是否在范围内。

Args:
    time_str: 时间字符串
    start: 开始时间
    end: 结束时间

Returns:
    是否在范围内

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| time_str | str | - | - |
| start | str | - | - |
| end | str | - | - |

**Returns**: `bool`

---

### `parse_opening_hours(hours_str: str)`

解析营业时间字符串为 (开始, 结束) 时间元组。

Args:
    hours_str: 营业时间字符串，格式 "HH:MM-HH:MM"

Returns:
    (开始时间, 结束时间) 字符串元组

Raises:
    ValueError: 格式不合法时

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| hours_str | str | - | - |

**Returns**: `tuple[str, str]`

---

### `get_poi_opening_hours(poi: dict[str, Any])`

获取 POI 的营业开始/结束时间。

优先读 constraints.opening_hours，回退到 business_hours，
最终回退到 "00:00-23:59"。

Args:
    poi: POI 字典

Returns:
    (开门时间, 关门时间) datetime 元组

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi | dict[str, Any] | - | - |

**Returns**: `tuple[datetime, datetime]`

---

### `parse_time_window(time_info: dict[str, str])`

将时间信息字典转为 (start_minutes, end_minutes)。

Args:
    time_info: 包含 "start" 和 "end" 键的字典，值为 "HH:MM" 格式

Returns:
    (起始分钟数, 结束分钟数)

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| time_info | dict[str, str] | - | - |

**Returns**: `tuple[int, int]`

---

### `parse_hours_to_minutes(hours_str: str)`

将营业时间字符串转为分钟数。

Args:
    hours_str: 营业时间字符串，格式 "HH:MM-HH:MM"

Returns:
    (开门分钟数, 关门分钟数)

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| hours_str | str | - | - |

**Returns**: `tuple[int, int]`

---

## backend.services.user_profiles

**文件**: `backend\services\user_profiles.py`

CityFlow 用户画像定义模块
定义20组典型用户画像，用于意图匹配和路线推荐。

### `match_profile(intent: dict[str, Any])`

根据用户意图匹配最相似的画像ID。

计算逻辑：
1. 偏好向量余弦相似度（权重 0.4）
2. 社交倾向距离（权重 0.2）
3. 群体类型匹配（权重 0.2）
4. 节奏偏好匹配（权重 0.1）
5. 预算水平距离（权重 0.1）

参数:
    intent: 用户意图字典，包含 group, preferences, pace, budget 等字段

返回:
    最匹配的画像 ID（P1-P20）

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| intent | dict[str, Any] | - | - |

**Returns**: `str`

---

### `get_profile_by_id(profile_id: str)`

根据画像 ID 获取画像详情。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| profile_id | str | - | - |

**Returns**: `dict[str, Any] | None`

---

### `get_all_profile_ids()`

获取所有画像 ID 列表。

**Returns**: `list[str]`

---

### `get_profiles_by_group_type(group_type: str)`

根据群体类型筛选画像。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| group_type | str | - | - |

**Returns**: `dict[str, dict[str, Any]]`

---

## backend.services.user_rate_limiter

**文件**: `backend\services\user_rate_limiter.py`

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

### class `EndpointTier`

**继承**: `str`, `Enum`

端点配额等级，用于统一管理不同端点的限流策略。

### class `UserRateLimitExceededError`

**继承**: `CityFlowException`

用户速率限制超出。

#### `UserRateLimitExceededError.__init__(message: str = '请求过于频繁，请稍后再试', details: dict[str, Any] | None = None)`

**Returns**: `None`


### class `UserRateLimitResult`

用户限流检查结果。

#### `UserRateLimitResult.to_headers()`

转换为标准 RateLimit 响应头。

**Returns**: `dict[str, str]`


### class `_LocalWindow`

本地固定窗口计数器。

### class `_LocalUserRateLimiter`

本地内存用户限流器。

#### `_LocalUserRateLimiter.__init__()`

**Returns**: `None`


#### `async _LocalUserRateLimiter.check(key: str, limit: int, window: int)`

检查限流，返回 (allowed, remaining, reset_ts)。

**Returns**: `tuple[bool, int, int]`


#### `_LocalUserRateLimiter.cleanup(max_idle_seconds: int = 600)`

清理长时间无活动的窗口。

**Returns**: `int`


### class `_RedisUserRateLimiter`

基于 Redis Sorted Set 的用户限流器。

#### `_RedisUserRateLimiter.__init__(redis_client: aioredis.Redis)`

**Returns**: `None`


#### `async _RedisUserRateLimiter.check(key: str, limit: int, window: int)`

检查限流，返回 (allowed, remaining, reset_ts)。

**Returns**: `tuple[bool, int, int]`


### class `UserRateLimiter`

用户级速率限制器。

自动根据端点路径匹配配额等级，支持白名单用户豁免。
优先使用 Redis 分布式模式，Redis 不可用时降级到本地内存。

用法::

    limiter = UserRateLimiter(redis_client)
    result = await limiter.check("user_123", "/api/v1/plan_route")

#### `UserRateLimiter.__init__(redis_client: aioredis.Redis | None = None)`

**Returns**: `None`


#### `async UserRateLimiter.check(user_id: str, endpoint: str, multiplier: float = 1.0)`

检查用户对指定端点的限流。

Args:
    user_id: 用户 ID。
    endpoint: API 端点路径，如 ``"/api/v1/plan_route"``。
    multiplier: 配额倍率，>1 放宽限制，<1 收紧限制。

Returns:
    UserRateLimitResult 包含限流判定和配额信息。

**Returns**: `UserRateLimitResult`


#### `async UserRateLimiter.check_with_tier(user_id: str, endpoint: str, tier: EndpointTier, multiplier: float = 1.0)`

使用指定配额等级检查限流（跳过自动解析）。

适用于需要手动覆盖端点配额等级的场景。

**Returns**: `UserRateLimitResult`


#### `UserRateLimiter.backend_type()`

当前后端类型：``"redis"`` 或 ``"local"``。

**Returns**: `str`


#### `async UserRateLimiter.cleanup_local()`

清理本地内存中的过期窗口。仅本地模式有效。

**Returns**: `int`


### `register_whitelist_user(user_id: str)`

注册白名单用户。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| user_id | str | - | - |

**Returns**: `None`

---

### `remove_whitelist_user(user_id: str)`

移除白名单用户。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| user_id | str | - | - |

**Returns**: `None`

---

### `resolve_endpoint_tier(endpoint: str)`

根据端点路径解析配额等级。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| endpoint | str | - | - |

**Returns**: `EndpointTier`

---

### `get_user_rate_limiter()`

获取全局用户限流器单例。

**Returns**: `UserRateLimiter`

---

## backend.services.vectorized

**文件**: `backend\services\vectorized.py`

CityFlow 向量化距离计算模块。

用 numpy 批量计算 haversine 距离矩阵，比逐对循环快 10-100 倍。

### `haversine_vectorized(lat1: NDArray[np.floating[Any]], lon1: NDArray[np.floating[Any]], lat2: NDArray[np.floating[Any]], lon2: NDArray[np.floating[Any]])`

向量化 haversine 距离计算（米）。

所有输入应为同 shape 的 numpy 数组，支持广播。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| lat1 | NDArray[np.floating[Any]] | - | - |
| lon1 | NDArray[np.floating[Any]] | - | - |
| lat2 | NDArray[np.floating[Any]] | - | - |
| lon2 | NDArray[np.floating[Any]] | - | - |

**Returns**: `NDArray[np.floating[Any]]`

---

### `distance_matrix_vectorized(pois: list[dict[str, Any]], road_factor: float = _ROAD_FACTOR)`

向量化计算 POI 间距离矩阵（米，含道路系数）。

Args:
    pois: POI 列表，每个需含 lat, lng 字段
    road_factor: 道路弯曲系数

Returns:
    shape (n, n) 的距离矩阵

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| pois | list[dict[str, Any]] | - | - |
| road_factor | float | _ROAD_FACTOR | - |

**Returns**: `NDArray[np.floating[Any]]`

---

### `travel_time_matrix_vectorized(pois: list[dict[str, Any]], speed_kmh: float = _AVG_SPEED_KMH, road_factor: float = _ROAD_FACTOR)`

向量化计算 POI 间旅行时间矩阵（分钟）。

Args:
    pois: POI 列表
    speed_kmh: 平均速度 km/h
    road_factor: 道路弯曲系数

Returns:
    shape (n, n) 的时间矩阵（分钟）

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| pois | list[dict[str, Any]] | - | - |
| speed_kmh | float | _AVG_SPEED_KMH | - |
| road_factor | float | _ROAD_FACTOR | - |

**Returns**: `NDArray[np.floating[Any]]`

---

### `distance_from_point_vectorized(lat: float, lng: float, pois: list[dict[str, Any]], road_factor: float = _ROAD_FACTOR)`

计算一个点到多个 POI 的距离数组（米）。

Args:
    lat: 起点纬度
    lng: 起点经度
    pois: 目标 POI 列表
    road_factor: 道路系数

Returns:
    shape (n,) 的距离数组

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| lat | float | - | - |
| lng | float | - | - |
| pois | list[dict[str, Any]] | - | - |
| road_factor | float | _ROAD_FACTOR | - |

**Returns**: `NDArray[np.floating[Any]]`

---

### `emotion_score_vectorized(pois: list[dict[str, Any]], preferences: dict[str, float])`

批量计算 POI 列表的情绪偏好总分。

Args:
    pois: POI 列表
    preferences: 用户偏好权重 {key: weight}

Returns:
    总分

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| pois | list[dict[str, Any]] | - | - |
| preferences | dict[str, float] | - | - |

**Returns**: `float`

---

### `haversine_scalar(lat1: float, lon1: float, lat2: float, lon2: float)`

标量 haversine（米），用于少量点对的场景。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| lat1 | float | - | - |
| lon1 | float | - | - |
| lat2 | float | - | - |
| lon2 | float | - | - |

**Returns**: `float`

---

## backend.services.websocket

**文件**: `backend\services\websocket.py`

CityFlow WebSocket 连接管理器。

提供 WebSocket 连接生命周期管理、路线订阅机制和消息广播能力。

### class `ConnectionManager`

WebSocket 连接管理器。

职责：
- 管理活跃 WebSocket 连接的生命周期
- 维护路线订阅关系（一个连接可订阅多条路线）
- 提供点对点、路线组播和全局广播三种消息推送方式

#### `ConnectionManager.__init__()`

**Returns**: `None`


#### `async ConnectionManager.connect(websocket: WebSocket, session_id: str)`

接受 WebSocket 连接并注册。

**Returns**: `None`


#### `async ConnectionManager.disconnect(session_id: str)`

断开连接并清理所有订阅关系。

**Returns**: `None`


#### `async ConnectionManager.subscribe(session_id: str, route_id: str)`

订阅路线更新。

**Returns**: `None`


#### `async ConnectionManager.unsubscribe(session_id: str, route_id: str)`

取消订阅路线更新。

**Returns**: `None`


#### `async ConnectionManager.send_personal_message(session_id: str, message: dict)`

向单个连接发送 JSON 消息。发送失败时自动断开。

**Returns**: `None`


#### `async ConnectionManager.broadcast_to_route(route_id: str, message: dict)`

向订阅了指定路线的所有连接广播消息。

**Returns**: `None`


#### `async ConnectionManager.broadcast_all(message: dict)`

向所有活跃连接广播消息。

**Returns**: `None`


#### `ConnectionManager.get_connection_count()`

获取当前活跃连接数。

**Returns**: `int`


#### `ConnectionManager.get_subscription_count()`

获取当前订阅的路线数。

**Returns**: `int`


#### `ConnectionManager.get_subscribers(route_id: str)`

获取某条路线的所有订阅者。

**Returns**: `Set[str]`


#### `ConnectionManager.is_connected(session_id: str)`

检查指定 session 是否在线。

**Returns**: `bool`


### `get_websocket_manager()`

获取全局 WebSocket 连接管理器单例。

**Returns**: `ConnectionManager`

---

## backend.tests.test_adaptive_rate_limiter

**文件**: `backend\tests\test_adaptive_rate_limiter.py`

自适应限流器单元测试。

### class `TestSystemMetrics`

#### `TestSystemMetrics.test_load_score_low()`

**Returns**: `None`


#### `TestSystemMetrics.test_load_score_normal()`

**Returns**: `None`


#### `TestSystemMetrics.test_load_score_high()`

**Returns**: `None`


#### `TestSystemMetrics.test_load_score_critical()`

**Returns**: `None`


#### `TestSystemMetrics.test_latency_factor_capped_at_1s()`

**Returns**: `None`


#### `TestSystemMetrics.test_zero_metrics()`

**Returns**: `None`


### class `TestMetricsCollector`

#### `TestMetricsCollector.test_collect_returns_metrics()`

**Returns**: `None`


#### `TestMetricsCollector.test_record_response_tracks_latency()`

**Returns**: `None`


#### `TestMetricsCollector.test_record_response_tracks_errors()`

**Returns**: `None`


#### `TestMetricsCollector.test_reset_clears_state()`

**Returns**: `None`


#### `TestMetricsCollector.test_sliding_window_limit()`

**Returns**: `None`


### class `TestAdaptiveRateLimiter`

#### `TestAdaptiveRateLimiter.test_default_multiplier_is_one()`

**Returns**: `None`


#### `TestAdaptiveRateLimiter.test_manual_multiplier_override()`

**Returns**: `None`


#### `TestAdaptiveRateLimiter.test_force_update_changes_multiplier_for_high_load()`

**Returns**: `None`


#### `TestAdaptiveRateLimiter.test_force_update_increases_multiplier_for_low_load()`

**Returns**: `None`


#### `TestAdaptiveRateLimiter.test_multiplier_clamped_to_range()`

**Returns**: `None`


#### `TestAdaptiveRateLimiter.test_record_response_updates_metrics()`

**Returns**: `None`


#### `TestAdaptiveRateLimiter.test_get_status_returns_dict()`

**Returns**: `None`


#### `TestAdaptiveRateLimiter.test_get_status_manual_mode()`

**Returns**: `None`


#### `async TestAdaptiveRateLimiter.test_start_and_stop_monitoring()`

**Returns**: `None`


#### `async TestAdaptiveRateLimiter.test_start_monitoring_idempotent()`

**Returns**: `None`


#### `TestAdaptiveRateLimiter.test_load_level_property()`

**Returns**: `None`


### class `TestGetAdaptiveLimiter`

#### `TestGetAdaptiveLimiter.test_singleton()`

**Returns**: `None`


## backend.tests.test_alert_notifier

**文件**: `backend\tests\test_alert_notifier.py`

告警通知器单元测试。

### class `TestAlertNotifierHandleAlert`

测试 handle_alert 方法（三参数签名）。

#### `async TestAlertNotifierHandleAlert.test_handle_alert_increments_count()`

**Returns**: `None`


#### `async TestAlertNotifierHandleAlert.test_handle_alert_publishes_event()`

**Returns**: `None`


### class `TestAlertNotifierHandleAlertEvent`

测试 handle_alert_event 方法（AlertEvent 对象签名）。

#### `async TestAlertNotifierHandleAlertEvent.test_handle_alert_event_increments_count()`

**Returns**: `None`


#### `async TestAlertNotifierHandleAlertEvent.test_handle_critical_event_uses_critical_log()`

**Returns**: `None`


### class `TestConvenienceMethods`

测试 send_info / send_warning / send_critical。

#### `async TestConvenienceMethods.test_send_info()`

**Returns**: `None`


#### `async TestConvenienceMethods.test_send_warning()`

**Returns**: `None`


#### `async TestConvenienceMethods.test_send_critical()`

**Returns**: `None`


### class `TestPublishEvent`

测试事件总线发布集成。

#### `async TestPublishEvent.test_publish_event_calls_event_bus()`

**Returns**: `None`


#### `async TestPublishEvent.test_publish_event_exception_does_not_raise()`

事件总线异常不应中断通知器。

**Returns**: `None`


### class `TestGetStatus`

#### `TestGetStatus.test_initial_status()`

**Returns**: `None`


### class `TestAlertNotifierSingleton`

#### `TestAlertNotifierSingleton.test_singleton()`

**Returns**: `None`


#### `TestAlertNotifierSingleton.test_reset_creates_new()`

**Returns**: `None`


## backend.tests.test_audit_logger

**文件**: `backend\tests\test_audit_logger.py`

审计日志服务单元测试。

### class `TestAuditAction`

审计动作枚举测试。

#### `TestAuditAction.test_action_values()`

**Returns**: `None`


#### `TestAuditAction.test_action_is_string_enum()`

**Returns**: `None`


### class `TestAuditLogger`

审计日志记录器测试。

#### `TestAuditLogger.test_init_default_buffer_size()`

**Returns**: `None`


#### `TestAuditLogger.test_init_custom_buffer_size()`

**Returns**: `None`


#### `async TestAuditLogger.test_log_adds_to_buffer()`

**Returns**: `None`


#### `async TestAuditLogger.test_log_with_details()`

**Returns**: `None`


#### `async TestAuditLogger.test_log_with_ip_and_user_agent()`

**Returns**: `None`


#### `async TestAuditLogger.test_log_flushes_when_buffer_full()`

**Returns**: `None`


#### `async TestAuditLogger.test_flush_clears_buffer()`

**Returns**: `None`


#### `async TestAuditLogger.test_flush_noop_when_empty()`

**Returns**: `None`


#### `async TestAuditLogger.test_query_calls_flush_first()`

**Returns**: `None`


#### `async TestAuditLogger.test_export_json_format()`

**Returns**: `None`


#### `async TestAuditLogger.test_export_csv_format()`

**Returns**: `None`


#### `async TestAuditLogger.test_export_csv_empty()`

**Returns**: `None`


#### `TestAuditLogger.test_to_dict()`

**Returns**: `None`


### class `TestGetAuditLogger`

全局单例测试。

#### `TestGetAuditLogger.test_returns_same_instance()`

**Returns**: `None`


#### `TestGetAuditLogger.test_returns_audit_logger_instance()`

**Returns**: `None`


### class `TestAuditLogDecorator`

审计日志装饰器测试。

#### `async TestAuditLogDecorator.test_decorator_records_log()`

**Returns**: `None`


#### `async TestAuditLogDecorator.test_decorator_preserves_function_name()`

**Returns**: `None`


## backend.tests.test_auto_recovery

**文件**: `backend\tests\test_auto_recovery.py`

自动恢复模块单元测试。

### class `TestRecoveryAttempt`

#### `TestRecoveryAttempt.test_to_dict()`

**Returns**: `None`


#### `TestRecoveryAttempt.test_to_dict_with_error()`

**Returns**: `None`


### class `TestRecoveryResult`

#### `TestRecoveryResult.test_all_succeeded_true()`

**Returns**: `None`


#### `TestRecoveryResult.test_all_succeeded_false()`

**Returns**: `None`


#### `TestRecoveryResult.test_empty_is_success()`

**Returns**: `None`


#### `TestRecoveryResult.test_to_dict()`

**Returns**: `None`


### class `TestAutoRecovery`

#### `async TestAutoRecovery.test_no_action_for_unregistered()`

**Returns**: `None`


#### `async TestAutoRecovery.test_success_on_first_try()`

**Returns**: `None`


#### `async TestAutoRecovery.test_failure_increments_retry()`

**Returns**: `None`


#### `async TestAutoRecovery.test_max_retries_skips()`

**Returns**: `None`


#### `async TestAutoRecovery.test_cooldown_skips()`

**Returns**: `None`


#### `async TestAutoRecovery.test_success_resets_retry_count()`

**Returns**: `None`


#### `async TestAutoRecovery.test_attempt_many_parallel()`

**Returns**: `None`


#### `async TestAutoRecovery.test_attempt_many_empty()`

**Returns**: `None`


#### `async TestAutoRecovery.test_attempt_many_partial_failure()`

**Returns**: `None`


#### `async TestAutoRecovery.test_handle_unhealthy()`

**Returns**: `None`


#### `async TestAutoRecovery.test_handle_unhealthy_no_registered()`

**Returns**: `None`


#### `async TestAutoRecovery.test_history_recorded()`

**Returns**: `None`


#### `async TestAutoRecovery.test_get_service_history()`

**Returns**: `None`


#### `TestAutoRecovery.test_reset_retry_count()`

**Returns**: `None`


#### `TestAutoRecovery.test_reset_all()`

**Returns**: `None`


#### `TestAutoRecovery.test_unregister()`

**Returns**: `None`


### class `TestExponentialBackoff`

#### `async TestExponentialBackoff.test_delay_increases()`

验证多次失败时等待时间递增。

**Returns**: `None`


## backend.tests.test_backup

**文件**: `backend\tests\test_backup.py`

备份服务测试。

### `backup_dir(tmp_path: Path)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| tmp_path | Path | - | - |

**Returns**: `Path`

---

### `data_dir(tmp_path: Path)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| tmp_path | Path | - | - |

**Returns**: `Path`

---

### `config_file(tmp_path: Path)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| tmp_path | Path | - | - |

**Returns**: `Path`

---

### `backup(backup_dir: Path, data_dir: Path)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup_dir | Path | - | - |
| data_dir | Path | - | - |

**Returns**: `DataBackup`

---

### `async test_create_backup_default_name(backup: DataBackup)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup | DataBackup | - | - |

**Returns**: `None`

---

### `async test_create_backup_custom_name(backup: DataBackup)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup | DataBackup | - | - |

**Returns**: `None`

---

### `async test_create_backup_creates_files(backup: DataBackup, backup_dir: Path)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup | DataBackup | - | - |
| backup_dir | Path | - | - |

**Returns**: `None`

---

### `async test_create_backup_metadata_content(backup: DataBackup)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup | DataBackup | - | - |

**Returns**: `None`

---

### `async test_create_backup_checksum_is_stable(backup: DataBackup, backup_dir: Path)`

同一数据目录的两次备份应产生相同校验和。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup | DataBackup | - | - |
| backup_dir | Path | - | - |

**Returns**: `None`

---

### `async test_restore_backup(backup: DataBackup, data_dir: Path)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup | DataBackup | - | - |
| data_dir | Path | - | - |

**Returns**: `None`

---

### `async test_restore_nonexistent_backup(backup: DataBackup)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup | DataBackup | - | - |

**Returns**: `None`

---

### `async test_restore_detects_corruption(backup: DataBackup, backup_dir: Path)`

篡改备份数据后恢复应触发完整性校验失败。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup | DataBackup | - | - |
| backup_dir | Path | - | - |

**Returns**: `None`

---

### `async test_list_backups_empty(backup: DataBackup)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup | DataBackup | - | - |

**Returns**: `None`

---

### `async test_list_backups_sorted(backup: DataBackup)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup | DataBackup | - | - |

**Returns**: `None`

---

### `async test_cleanup_old_backups(backup: DataBackup)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup | DataBackup | - | - |

**Returns**: `None`

---

### `async test_cleanup_nothing_to_remove(backup: DataBackup)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup | DataBackup | - | - |

**Returns**: `None`

---

### `async test_delete_backup(backup: DataBackup)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup | DataBackup | - | - |

**Returns**: `None`

---

### `async test_delete_nonexistent(backup: DataBackup)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup | DataBackup | - | - |

**Returns**: `None`

---

### `async test_backup_includes_config(tmp_path: Path, data_dir: Path, config_file: Path)`

如果有 .env 文件存在于工作目录，备份应包含它。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| tmp_path | Path | - | - |
| data_dir | Path | - | - |
| config_file | Path | - | - |

**Returns**: `None`

---

### `test_get_backup_singleton()`

**Returns**: `None`

---

## backend.tests.test_circuit_breaker

**文件**: `backend\tests\test_circuit_breaker.py`

熔断器单元测试。

### class `TestCircuitState`

#### `TestCircuitState.test_initial_state_is_closed()`

**Returns**: `None`


#### `TestCircuitState.test_stays_closed_below_threshold()`

**Returns**: `None`


#### `TestCircuitState.test_opens_at_threshold()`

**Returns**: `None`


#### `TestCircuitState.test_open_to_half_open_after_timeout()`

**Returns**: `None`


#### `TestCircuitState.test_half_open_success_closes()`

**Returns**: `None`


#### `TestCircuitState.test_half_open_failure_reopens()`

**Returns**: `None`


#### `TestCircuitState.test_success_resets_failure_count()`

**Returns**: `None`


### class `TestCircuitBreakerDecorator`

#### `async TestCircuitBreakerDecorator.test_passes_through_when_closed()`

**Returns**: `None`


#### `async TestCircuitBreakerDecorator.test_records_failure_on_exception()`

**Returns**: `None`


#### `async TestCircuitBreakerDecorator.test_rejects_when_open()`

**Returns**: `None`


#### `async TestCircuitBreakerDecorator.test_only_catches_expected_exceptions()`

**Returns**: `None`


#### `TestCircuitBreakerDecorator.test_sync_function_support()`

**Returns**: `None`


### class `TestCircuitBreakerManualControl`

#### `TestCircuitBreakerManualControl.test_reset()`

**Returns**: `None`


#### `TestCircuitBreakerManualControl.test_trip()`

**Returns**: `None`


#### `TestCircuitBreakerManualControl.test_reject_if_open()`

**Returns**: `None`


#### `TestCircuitBreakerManualControl.test_reject_if_open_noop_when_closed()`

**Returns**: `None`


### class `TestCircuitBreakerMetrics`

#### `TestCircuitBreakerMetrics.test_tracks_counts()`

**Returns**: `None`


#### `TestCircuitBreakerMetrics.test_tracks_rejected()`

**Returns**: `None`


## backend.tests.test_code_generator

**文件**: `backend\tests\test_code_generator.py`

CityFlow 代码生成器测试。

### class `TestHelpers`

内部辅助函数测试。

#### `TestHelpers.test_capitalize_snake_case()`

snake_case 转 PascalCase。

**Returns**: `None`


#### `TestHelpers.test_capitalize_kebab_case()`

kebab-case 转 PascalCase。

**Returns**: `None`


#### `TestHelpers.test_capitalize_single_word()`

单个单词。

**Returns**: `None`


#### `TestHelpers.test_resolve_type_known()`

已知类型映射。

**Returns**: `None`


#### `TestHelpers.test_resolve_type_unknown()`

未知类型原样返回。

**Returns**: `None`


### class `TestGenerateApiEndpoint`

API 端点生成测试。

#### `TestGenerateApiEndpoint.generator()`

**Returns**: `CodeGenerator`


#### `TestGenerateApiEndpoint.sample_fields()`

**Returns**: `list[dict]`


#### `TestGenerateApiEndpoint.test_contains_router_definition(generator: CodeGenerator, sample_fields: list[dict])`

生成的代码包含 router 定义。

**Returns**: `None`


#### `TestGenerateApiEndpoint.test_contains_crud_endpoints(generator: CodeGenerator, sample_fields: list[dict])`

生成的代码包含完整 CRUD 端点。

**Returns**: `None`


#### `TestGenerateApiEndpoint.test_contains_request_models(generator: CodeGenerator, sample_fields: list[dict])`

生成的代码包含请求模型。

**Returns**: `None`


#### `TestGenerateApiEndpoint.test_optional_field_handling(generator: CodeGenerator, sample_fields: list[dict])`

可选字段使用 Optional 类型。

**Returns**: `None`


#### `TestGenerateApiEndpoint.test_custom_prefix(generator: CodeGenerator, sample_fields: list[dict])`

支持自定义前缀。

**Returns**: `None`


#### `TestGenerateApiEndpoint.test_custom_tag(generator: CodeGenerator, sample_fields: list[dict])`

支持自定义标签。

**Returns**: `None`


### class `TestGenerateModel`

数据模型生成测试。

#### `TestGenerateModel.generator()`

**Returns**: `CodeGenerator`


#### `TestGenerateModel.sample_fields()`

**Returns**: `list[dict]`


#### `TestGenerateModel.test_contains_model_class(generator: CodeGenerator, sample_fields: list[dict])`

生成的代码包含模型类。

**Returns**: `None`


#### `TestGenerateModel.test_contains_id_field(generator: CodeGenerator, sample_fields: list[dict])`

生成的代码包含 id 字段。

**Returns**: `None`


#### `TestGenerateModel.test_contains_timestamps_by_default(generator: CodeGenerator, sample_fields: list[dict])`

默认包含时间戳字段。

**Returns**: `None`


#### `TestGenerateModel.test_exclude_timestamps(generator: CodeGenerator, sample_fields: list[dict])`

可选排除时间戳字段。

**Returns**: `None`


#### `TestGenerateModel.test_custom_description(generator: CodeGenerator, sample_fields: list[dict])`

支持自定义描述。

**Returns**: `None`


### class `TestGenerateService`

服务类生成测试。

#### `TestGenerateService.generator()`

**Returns**: `CodeGenerator`


#### `TestGenerateService.test_contains_service_class(generator: CodeGenerator)`

生成的代码包含服务类。

**Returns**: `None`


#### `TestGenerateService.test_contains_crud_methods(generator: CodeGenerator)`

生成的代码包含 CRUD 方法。

**Returns**: `None`


#### `TestGenerateService.test_contains_singleton_getter(generator: CodeGenerator)`

生成的代码包含单例获取函数。

**Returns**: `None`


#### `TestGenerateService.test_database_mode(generator: CodeGenerator)`

数据库模式包含 AsyncSession 注入。

**Returns**: `None`


#### `TestGenerateService.test_non_database_mode(generator: CodeGenerator)`

非数据库模式不包含数据库相关导入。

**Returns**: `None`


### class `TestGenerateTest`

测试文件生成测试。

#### `TestGenerateTest.generator()`

**Returns**: `CodeGenerator`


#### `TestGenerateTest.sample_fields()`

**Returns**: `list[dict]`


#### `TestGenerateTest.test_contains_test_class(generator: CodeGenerator, sample_fields: list[dict])`

生成的代码包含测试类。

**Returns**: `None`


#### `TestGenerateTest.test_contains_crud_tests(generator: CodeGenerator, sample_fields: list[dict])`

生成的代码包含 CRUD 测试方法。

**Returns**: `None`


### class `TestSaveFile`

文件保存测试。

#### `TestSaveFile.test_save_creates_file(tmp_path: Path)`

保存文件会创建目标文件。

**Returns**: `None`


#### `TestSaveFile.test_save_creates_parent_dirs(tmp_path: Path)`

保存文件会自动创建父目录。

**Returns**: `None`


#### `TestSaveFile.test_save_returns_absolute_path(tmp_path: Path)`

返回绝对路径。

**Returns**: `None`


### class `TestGenerateFull`

一次性生成全部文件测试。

#### `TestGenerateFull.generator()`

**Returns**: `CodeGenerator`


#### `TestGenerateFull.sample_fields()`

**Returns**: `list[dict]`


#### `TestGenerateFull.test_returns_four_keys(generator: CodeGenerator, sample_fields: list[dict])`

返回四个键。

**Returns**: `None`


#### `TestGenerateFull.test_save_creates_all_files(tmp_path: Path, sample_fields: list[dict])`

save=True 会创建全部文件。

**Returns**: `None`


### class `TestCLI`

CLI 入口测试。

#### `TestCLI.test_main_with_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch)`

CLI --save 模式写入文件。

**Returns**: `None`


## backend.tests.test_errors

**文件**: `backend\tests\test_errors.py`

CityFlow 统一错误处理机制测试。

### class `TestErrorCode`

错误码枚举测试。

#### `TestErrorCode.test_error_code_values_unique()`

错误码值必须唯一。


#### `TestErrorCode.test_error_code_ranges()`

错误码按段分类。


### class `TestCityFlowException`

基础异常测试。

#### `TestCityFlowException.test_basic_creation()`

创建基础异常。


#### `TestCityFlowException.test_with_details()`

带详情的异常。


#### `TestCityFlowException.test_custom_status_code()`

自定义 HTTP 状态码。


#### `TestCityFlowException.test_to_dict_basic()`

转换为基础字典。


#### `TestCityFlowException.test_to_dict_with_details()`

带详情的字典。


#### `TestCityFlowException.test_is_exception()`

CityFlowException 是 Exception 子类。


#### `TestCityFlowException.test_str_representation()`

字符串表示包含消息。


### class `TestExceptionSubclasses`

异常子类默认值测试。

#### `TestExceptionSubclasses.test_intent_parse_error()`


#### `TestExceptionSubclasses.test_no_pois_found_error()`


#### `TestExceptionSubclasses.test_route_solving_error()`


#### `TestExceptionSubclasses.test_narrative_generation_error()`


#### `TestExceptionSubclasses.test_dialogue_error()`


#### `TestExceptionSubclasses.test_llm_service_error()`


#### `TestExceptionSubclasses.test_rate_limit_error()`


#### `TestExceptionSubclasses.test_custom_message()`

子类支持自定义消息。


#### `TestExceptionSubclasses.test_custom_details()`

子类支持自定义详情。


### class `TestGlobalErrorHandlers`

FastAPI 全局异常处理器测试。

#### `TestGlobalErrorHandlers.app()`


#### `TestGlobalErrorHandlers.client(app)`


#### `TestGlobalErrorHandlers.test_cityflow_exception_returns_json(client)`

CityFlowException 返回标准化 JSON。


#### `TestGlobalErrorHandlers.test_intent_parse_error_status(client)`

IntentParseError 返回 400。


#### `TestGlobalErrorHandlers.test_llm_service_error_status(client)`

LLMServiceError 返回 503。


#### `TestGlobalErrorHandlers.test_dialogue_error_status(client)`

DialogueError 返回 500。


#### `TestGlobalErrorHandlers.test_no_pois_error_status(client)`

NoPOIsFoundError 返回 404。


#### `TestGlobalErrorHandlers.test_rate_limit_error_status(client)`

RateLimitError 返回 429。


#### `TestGlobalErrorHandlers.test_generic_error_returns_500(client)`

未预期异常返回 500 且不暴露内部细节。


#### `TestGlobalErrorHandlers.test_error_response_format_consistency(client)`

所有错误响应格式一致：{error: {code, message, [details]}}。


### class `TestHandleErrorsDecorator`

handle_errors 装饰器测试。

#### `async TestHandleErrorsDecorator.test_passes_through_cityflow_exception()`

CityFlowException 原样抛出。


#### `async TestHandleErrorsDecorator.test_wraps_generic_exception()`

其他异常包装为 CityFlowException。


#### `async TestHandleErrorsDecorator.test_success_passes_through()`

正常执行不受影响。


### class `TestHandleLLMErrorsDecorator`

handle_llm_errors 装饰器测试。

#### `async TestHandleLLMErrorsDecorator.test_timeout_error()`

TimeoutError 转换为 LLMServiceError。


#### `async TestHandleLLMErrorsDecorator.test_generic_error()`

其他异常转换为 LLMServiceError。


#### `async TestHandleLLMErrorsDecorator.test_passes_through_cityflow_exception()`

CityFlowException 原样抛出。


#### `async TestHandleLLMErrorsDecorator.test_success_passes_through()`

正常执行不受影响。


## backend.tests.test_fallback

**文件**: `backend\tests\test_fallback.py`

降级策略单元测试。

### class `TestFallbackDecorator`

#### `async TestFallbackDecorator.test_no_fallback_on_success()`

**Returns**: `None`


#### `async TestFallbackDecorator.test_fallback_on_exception()`

**Returns**: `None`


#### `async TestFallbackDecorator.test_only_catches_specified_exceptions()`

**Returns**: `None`


#### `async TestFallbackDecorator.test_fallback_receives_original_args()`

**Returns**: `None`


#### `async TestFallbackDecorator.test_fallback_failure_raises()`

降级函数本身也失败时，应该抛出异常。

**Returns**: `None`


#### `TestFallbackDecorator.test_sync_function_support()`

**Returns**: `None`


### class `TestPredefinedFallbacks`

#### `async TestPredefinedFallbacks.test_fallback_route_planning_shape()`

**Returns**: `None`


#### `async TestPredefinedFallbacks.test_fallback_poi_search_shape()`

**Returns**: `None`


#### `async TestPredefinedFallbacks.test_fallback_narrative_generation_shape()`

**Returns**: `None`


#### `async TestPredefinedFallbacks.test_fallback_llm_chat_returns_string()`

**Returns**: `None`


#### `async TestPredefinedFallbacks.test_fallback_emotion_analysis_shape()`

**Returns**: `None`


## backend.tests.test_health_checker

**文件**: `backend\tests\test_health_checker.py`

健康检查模块单元测试。

### class `TestCheckResult`

#### `TestCheckResult.test_to_dict()`

**Returns**: `None`


#### `TestCheckResult.test_to_dict_with_error()`

**Returns**: `None`


#### `TestCheckResult.test_to_dict_excludes_none_fields()`

**Returns**: `None`


### class `TestHealthReport`

#### `TestHealthReport.test_overall_healthy_when_all_ok()`

**Returns**: `None`


#### `TestHealthReport.test_overall_degraded()`

**Returns**: `None`


#### `TestHealthReport.test_overall_unhealthy_on_error()`

**Returns**: `None`


#### `TestHealthReport.test_overall_unhealthy_on_unhealthy()`

**Returns**: `None`


#### `TestHealthReport.test_overall_healthy_when_empty()`

**Returns**: `None`


#### `TestHealthReport.test_unhealthy_names()`

**Returns**: `None`


#### `TestHealthReport.test_to_dict()`

**Returns**: `None`


### class `TestHealthChecker`

#### `async TestHealthChecker.test_run_all_empty()`

**Returns**: `None`


#### `async TestHealthChecker.test_run_check_registered()`

**Returns**: `None`


#### `async TestHealthChecker.test_run_check_unregistered()`

**Returns**: `None`


#### `async TestHealthChecker.test_run_check_returns_false()`

**Returns**: `None`


#### `async TestHealthChecker.test_run_check_exception()`

**Returns**: `None`


#### `async TestHealthChecker.test_run_check_returns_check_result()`

**Returns**: `None`


#### `async TestHealthChecker.test_run_all_aggregates()`

**Returns**: `None`


#### `async TestHealthChecker.test_history_recorded()`

**Returns**: `None`


#### `async TestHealthChecker.test_history_size_limit()`

**Returns**: `None`


#### `async TestHealthChecker.test_unregister()`

**Returns**: `None`


#### `async TestHealthChecker.test_on_unhealthy_callback()`

**Returns**: `None`


#### `async TestHealthChecker.test_on_unhealthy_not_called_when_healthy()`

**Returns**: `None`


#### `async TestHealthChecker.test_start_stop()`

**Returns**: `None`


#### `async TestHealthChecker.test_start_idempotent()`

**Returns**: `None`


## backend.tests.test_i18n

**文件**: `backend\tests\test_i18n.py`

i18n 模块测试。

### class `TestTranslate`

翻译功能测试。

#### `TestTranslate.test_simple_key(i18n: I18n)`

**Returns**: `None`


#### `TestTranslate.test_nested_key(i18n: I18n)`

**Returns**: `None`


#### `TestTranslate.test_missing_key_returns_key(i18n: I18n)`

**Returns**: `None`


#### `TestTranslate.test_intermediate_key_returns_key(i18n: I18n)`

中间节点不是字符串时应返回 key。

**Returns**: `None`


#### `TestTranslate.test_format_params(i18n: I18n)`

**Returns**: `None`


#### `TestTranslate.test_format_missing_param_returns_template(i18n: I18n)`

缺少参数时应返回原始模板。

**Returns**: `None`


### class `TestLocaleSwitching`

语言切换测试。

#### `TestLocaleSwitching.test_default_locale(i18n: I18n)`

**Returns**: `None`


#### `TestLocaleSwitching.test_switch_to_en(i18n: I18n)`

**Returns**: `None`


#### `TestLocaleSwitching.test_switch_back(i18n: I18n)`

**Returns**: `None`


#### `TestLocaleSwitching.test_invalid_locale_raises(i18n: I18n)`

**Returns**: `None`


#### `TestLocaleSwitching.test_get_available_locales(i18n: I18n)`

**Returns**: `None`


### class `TestEdgeCases`

边界情况测试。

#### `TestEdgeCases.test_empty_locale_dir(tmp_path: Path)`

**Returns**: `None`


#### `TestEdgeCases.test_nonexistent_locale_dir(tmp_path: Path)`

**Returns**: `None`


#### `TestEdgeCases.test_malformed_json_skipped(tmp_path: Path)`

**Returns**: `None`


### class `TestGlobalShortcut`

全局 t() 快捷函数测试。

#### `TestGlobalShortcut.test_t_function(locale_dir: Path, monkeypatch: pytest.MonkeyPatch)`

重置全局单例后测试 t()。

**Returns**: `None`


### `locale_dir(tmp_path: Path)`

创建临时翻译目录。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| tmp_path | Path | - | - |

**Returns**: `Path`

---

### `i18n(locale_dir: Path)`

创建 I18n 实例。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| locale_dir | Path | - | - |

**Returns**: `I18n`

---

## backend.tests.test_ip_rate_limiter

**文件**: `backend\tests\test_ip_rate_limiter.py`

IP 限流器单元测试。

### class `TestIPRateLimitResult`

#### `TestIPRateLimitResult.test_to_headers_basic()`

**Returns**: `None`


#### `TestIPRateLimitResult.test_to_headers_with_ban()`

**Returns**: `None`


### class `TestLocalIPRateLimiter`

#### `async TestLocalIPRateLimiter.test_allows_first_request()`

**Returns**: `None`


#### `async TestLocalIPRateLimiter.test_blocks_after_limit()`

**Returns**: `None`


#### `async TestLocalIPRateLimiter.test_ban_and_unban()`

**Returns**: `None`


#### `async TestLocalIPRateLimiter.test_ban_expires()`

**Returns**: `None`


#### `async TestLocalIPRateLimiter.test_track_endpoint_detects_suspicious()`

**Returns**: `None`


#### `async TestLocalIPRateLimiter.test_different_keys_independent()`

**Returns**: `None`


### class `TestIPRateLimiterLocal`

本地模式集成测试。

#### `async TestIPRateLimiterLocal.test_backend_type_is_local()`

**Returns**: `None`


#### `async TestIPRateLimiterLocal.test_check_allows_within_limit()`

**Returns**: `None`


#### `async TestIPRateLimiterLocal.test_check_blocks_after_endpoint_limit()`

**Returns**: `None`


#### `async TestIPRateLimiterLocal.test_check_blocks_after_global_limit()`

**Returns**: `None`


#### `async TestIPRateLimiterLocal.test_manual_ban_blocks_requests()`

**Returns**: `None`


#### `async TestIPRateLimiterLocal.test_manual_unban_restores_access()`

**Returns**: `None`


#### `async TestIPRateLimiterLocal.test_is_banned()`

**Returns**: `None`


#### `async TestIPRateLimiterLocal.test_custom_limit_override()`

**Returns**: `None`


#### `async TestIPRateLimiterLocal.test_suspicious_flag_on_result()`

**Returns**: `None`


#### `async TestIPRateLimiterLocal.test_result_fields()`

**Returns**: `None`


### class `TestIPRateLimitExceededError`

#### `TestIPRateLimitExceededError.test_default_message()`

**Returns**: `None`


#### `TestIPRateLimitExceededError.test_custom_details()`

**Returns**: `None`


## backend.tests.test_locale_middleware

**文件**: `backend\tests\test_locale_middleware.py`

CityFlow 本地化中间件测试。

### class `TestParseLocale`

Accept-Language 解析测试。

#### `TestParseLocale.test_empty_string()`

**Returns**: `None`


#### `TestParseLocale.test_simple_en()`

**Returns**: `None`


#### `TestParseLocale.test_simple_zh()`

**Returns**: `None`


#### `TestParseLocale.test_en_us_full()`

**Returns**: `None`


#### `TestParseLocale.test_zh_cn_full()`

**Returns**: `None`


#### `TestParseLocale.test_en_gb()`

**Returns**: `None`


#### `TestParseLocale.test_zh_tw()`

**Returns**: `None`


#### `TestParseLocale.test_zh_hk()`

**Returns**: `None`


#### `TestParseLocale.test_quality_values()`

q 值高的语言优先。

**Returns**: `None`


#### `TestParseLocale.test_quality_values_en_first()`

**Returns**: `None`


#### `TestParseLocale.test_multiple_with_defaults()`

未指定 q 值时默认 1.0。

**Returns**: `None`


#### `TestParseLocale.test_unknown_locale_fallback()`

**Returns**: `None`


#### `TestParseLocale.test_prefix_matching()`

语言前缀应匹配。

**Returns**: `None`


### class `TestLocaleMiddlewareIntegration`

中间件集成测试。

#### `TestLocaleMiddlewareIntegration.test_default_locale_is_zh_cn(client: TestClient)`

无 Accept-Language 时默认 zh_CN。

**Returns**: `None`


#### `TestLocaleMiddlewareIntegration.test_accept_language_en(client: TestClient)`

**Returns**: `None`


#### `TestLocaleMiddlewareIntegration.test_accept_language_zh(client: TestClient)`

**Returns**: `None`


#### `TestLocaleMiddlewareIntegration.test_content_language_header_present(client: TestClient)`

每个响应都应包含 Content-Language 头。

**Returns**: `None`


### `app()`

创建测试用 FastAPI 应用。

**Returns**: `FastAPI`

---

### `client(app: FastAPI)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| app | FastAPI | - | - |

**Returns**: `TestClient`

---

## backend.tests.test_localized_response

**文件**: `backend\tests\test_localized_response.py`

CityFlow 本地化响应测试。

### class `TestSuccess`

#### `TestSuccess.test_default_message()`

**Returns**: `None`


#### `TestSuccess.test_custom_key()`

**Returns**: `None`


#### `TestSuccess.test_en_locale()`

**Returns**: `None`


### class `TestError`

#### `TestError.test_default_message()`

**Returns**: `None`


#### `TestError.test_custom_key()`

**Returns**: `None`


#### `TestError.test_en_locale()`

**Returns**: `None`


### class `TestData`

#### `TestData.test_basic_data()`

**Returns**: `None`


#### `TestData.test_list_data()`

**Returns**: `None`


#### `TestData.test_none_data()`

**Returns**: `None`


#### `TestData.test_en_locale()`

**Returns**: `None`


### class `TestPaginated`

#### `TestPaginated.test_basic_paginated()`

**Returns**: `None`


#### `TestPaginated.test_exact_page_count()`

**Returns**: `None`


#### `TestPaginated.test_single_page()`

**Returns**: `None`


#### `TestPaginated.test_zero_total()`

**Returns**: `None`


#### `TestPaginated.test_en_locale()`

**Returns**: `None`


## backend.tests.test_pool

**文件**: `backend\tests\test_pool.py`

连接池管理单元测试。

覆盖：
- DatabasePool 生命周期与统计
- HTTPPool 生命周期与统计
- PoolMonitor 健康检查与报告

### class `TestPoolStats`

#### `TestPoolStats.test_utilization_normal()`

**Returns**: `None`


#### `TestPoolStats.test_utilization_zero_pool()`

**Returns**: `None`


#### `TestPoolStats.test_utilization_full()`

**Returns**: `None`


#### `TestPoolStats.test_utilization_with_overflow()`

**Returns**: `None`


### class `TestDatabasePool`

#### `TestDatabasePool.pool()`

**Returns**: `DatabasePool`


#### `TestDatabasePool.test_initial_state(pool: DatabasePool)`

**Returns**: `None`


#### `async TestDatabasePool.test_start_idempotent(pool: DatabasePool)`

**Returns**: `None`


#### `async TestDatabasePool.test_close_without_start(pool: DatabasePool)`

**Returns**: `None`


#### `async TestDatabasePool.test_close_disposes_engine(pool: DatabasePool)`

**Returns**: `None`


#### `async TestDatabasePool.test_get_session_yields_session(pool: DatabasePool)`

**Returns**: `None`


#### `async TestDatabasePool.test_get_session_rollback_on_error(pool: DatabasePool)`

**Returns**: `None`


#### `async TestDatabasePool.test_ping_success(pool: DatabasePool)`

**Returns**: `None`


#### `async TestDatabasePool.test_ping_failure(pool: DatabasePool)`

**Returns**: `None`


#### `async TestDatabasePool.test_ping_before_start(pool: DatabasePool)`

**Returns**: `None`


#### `TestDatabasePool.test_get_stats(pool: DatabasePool)`

**Returns**: `None`


#### `TestDatabasePool.test_get_stats_dict(pool: DatabasePool)`

**Returns**: `None`


### class `TestHTTPPoolStats`

#### `TestHTTPPoolStats.test_create()`

**Returns**: `None`


### class `TestHTTPPool`

#### `TestHTTPPool.pool()`

**Returns**: `HTTPPool`


#### `TestHTTPPool.test_initial_state(pool: HTTPPool)`

**Returns**: `None`


#### `async TestHTTPPool.test_start_creates_client(pool: HTTPPool)`

**Returns**: `None`


#### `async TestHTTPPool.test_start_idempotent(pool: HTTPPool)`

**Returns**: `None`


#### `async TestHTTPPool.test_close(pool: HTTPPool)`

**Returns**: `None`


#### `async TestHTTPPool.test_close_without_start(pool: HTTPPool)`

**Returns**: `None`


#### `async TestHTTPPool.test_get_stats(pool: HTTPPool)`

**Returns**: `None`


#### `async TestHTTPPool.test_get_stats_dict_closed(pool: HTTPPool)`

**Returns**: `None`


#### `async TestHTTPPool.test_get_stats_dict_started(pool: HTTPPool)`

**Returns**: `None`


#### `async TestHTTPPool.test_http_methods_delegate_to_client(pool: HTTPPool)`

各 HTTP 方法应正确委托给底层 client。

**Returns**: `None`


#### `async TestHTTPPool.test_request_delegates(pool: HTTPPool)`

**Returns**: `None`


### class `TestPoolMonitor`

#### `TestPoolMonitor.monitor()`

**Returns**: `PoolMonitor`


#### `async TestPoolMonitor.test_get_stats(monitor: PoolMonitor)`

**Returns**: `None`


#### `async TestPoolMonitor.test_check_health_all_ok(monitor: PoolMonitor)`

**Returns**: `None`


#### `async TestPoolMonitor.test_check_health_db_down(monitor: PoolMonitor)`

**Returns**: `None`


#### `async TestPoolMonitor.test_check_health_high_utilization_warning(monitor: PoolMonitor)`

**Returns**: `None`


#### `TestPoolMonitor.test_report_no_warnings(monitor: PoolMonitor)`

**Returns**: `None`


#### `TestPoolMonitor.test_report_with_warning(monitor: PoolMonitor)`

**Returns**: `None`


## backend.tests.test_quota

**文件**: `backend\tests\test_quota.py`

配额管理器单元测试。

### class `TestQuotaPeriod`

#### `TestQuotaPeriod.test_hourly_value()`

**Returns**: `None`


#### `TestQuotaPeriod.test_daily_value()`

**Returns**: `None`


### class `TestQuotaInfo`

#### `TestQuotaInfo.test_within_quota_when_remaining_positive()`

**Returns**: `None`


#### `TestQuotaInfo.test_not_within_quota_when_remaining_zero()`

**Returns**: `None`


### class `TestQuotaCheckResult`

#### `TestQuotaCheckResult.test_within_quota_all_periods_ok()`

**Returns**: `None`


#### `TestQuotaCheckResult.test_not_within_quota_when_one_period_exceeded()`

**Returns**: `None`


#### `TestQuotaCheckResult.test_to_dict()`

**Returns**: `None`


### class `TestQuotaManagerWithoutRedis`

测试无 Redis 时的配额管理器（默认放行）。

#### `async TestQuotaManagerWithoutRedis.test_get_usage_returns_zero_when_no_redis()`

**Returns**: `None`


#### `async TestQuotaManagerWithoutRedis.test_check_and_consume_always_passes_without_redis()`

**Returns**: `None`


#### `async TestQuotaManagerWithoutRedis.test_reset_noop_without_redis()`

**Returns**: `None`


#### `async TestQuotaManagerWithoutRedis.test_unknown_quota_type_returns_empty_periods()`

**Returns**: `None`


### class `TestQuotaExceededError`

#### `TestQuotaExceededError.test_default_message()`

**Returns**: `None`


#### `TestQuotaExceededError.test_custom_details()`

**Returns**: `None`


### class `TestQuotaLimits`

#### `TestQuotaLimits.test_route_planning_limits()`

**Returns**: `None`


#### `TestQuotaLimits.test_poi_search_limits()`

**Returns**: `None`


#### `TestQuotaLimits.test_dialogue_limits()`

**Returns**: `None`


#### `TestQuotaLimits.test_all_types_have_both_periods()`

**Returns**: `None`


## backend.tests.test_rate_limiter

**文件**: `backend\tests\test_rate_limiter.py`

速率限制器单元测试。

### class `TestRateLimitResult`

#### `TestRateLimitResult.test_to_headers()`

**Returns**: `None`


#### `TestRateLimitResult.test_allowed_is_true_when_within_limit()`

**Returns**: `None`


#### `TestRateLimitResult.test_allowed_is_false_when_exceeded()`

**Returns**: `None`


### class `TestLocalRateLimiter`

#### `async TestLocalRateLimiter.test_allows_first_request()`

**Returns**: `None`


#### `async TestLocalRateLimiter.test_blocks_after_limit_reached()`

**Returns**: `None`


#### `async TestLocalRateLimiter.test_different_keys_independent()`

**Returns**: `None`


#### `async TestLocalRateLimiter.test_window_reset()`

**Returns**: `None`


#### `async TestLocalRateLimiter.test_remaining_decrements()`

**Returns**: `None`


#### `async TestLocalRateLimiter.test_cleanup_removes_stale_windows()`

**Returns**: `None`


### class `TestRateLimiterWithoutRedis`

测试无 Redis 时的本地模式。

#### `async TestRateLimiterWithoutRedis.test_uses_local_backend()`

**Returns**: `None`


#### `async TestRateLimiterWithoutRedis.test_is_allowed_delegates_to_local()`

**Returns**: `None`


#### `async TestRateLimiterWithoutRedis.test_cleanup_local_noop_for_redis_mode()`

**Returns**: `None`


### class `TestRateLimitExceededError`

#### `TestRateLimitExceededError.test_default_message()`

**Returns**: `None`


#### `TestRateLimitExceededError.test_custom_details()`

**Returns**: `None`


## backend.tests.test_registry

**文件**: `backend\tests\test_registry.py`

服务注册中心单元测试。

### class `TestServiceInfo`

#### `TestServiceInfo.test_create_with_defaults()`

**Returns**: `None`


#### `TestServiceInfo.test_to_dict()`

**Returns**: `None`


#### `TestServiceInfo.test_port_validation()`

**Returns**: `None`


### class `TestServiceRegistry`

#### `TestServiceRegistry.registry()`

**Returns**: `ServiceRegistry`


#### `async TestServiceRegistry.test_register_and_get(registry: ServiceRegistry)`

**Returns**: `None`


#### `async TestServiceRegistry.test_get_nonexistent_returns_none(registry: ServiceRegistry)`

**Returns**: `None`


#### `async TestServiceRegistry.test_deregister(registry: ServiceRegistry)`

**Returns**: `None`


#### `async TestServiceRegistry.test_deregister_nonexistent(registry: ServiceRegistry)`

**Returns**: `None`


#### `async TestServiceRegistry.test_heartbeat(registry: ServiceRegistry)`

**Returns**: `None`


#### `async TestServiceRegistry.test_heartbeat_nonexistent(registry: ServiceRegistry)`

**Returns**: `None`


#### `async TestServiceRegistry.test_get_all_services(registry: ServiceRegistry)`

**Returns**: `None`


#### `async TestServiceRegistry.test_unhealthy_service_not_returned(registry: ServiceRegistry)`

**Returns**: `None`


#### `async TestServiceRegistry.test_health_check_marks_unhealthy(registry: ServiceRegistry)`

**Returns**: `None`


#### `async TestServiceRegistry.test_remove_unhealthy(registry: ServiceRegistry)`

**Returns**: `None`


#### `async TestServiceRegistry.test_service_count_properties(registry: ServiceRegistry)`

**Returns**: `None`


#### `async TestServiceRegistry.test_start_stop(registry: ServiceRegistry)`

**Returns**: `None`


#### `async TestServiceRegistry.test_start_idempotent(registry: ServiceRegistry)`

**Returns**: `None`


### class `TestServiceDiscovery`

#### `TestServiceDiscovery.registry()`

**Returns**: `ServiceRegistry`


#### `async TestServiceDiscovery.test_discover_local(registry: ServiceRegistry)`

**Returns**: `None`


#### `async TestServiceDiscovery.test_discover_not_found(registry: ServiceRegistry)`

**Returns**: `None`


#### `async TestServiceDiscovery.test_get_service_url_raises(registry: ServiceRegistry)`

**Returns**: `None`


#### `async TestServiceDiscovery.test_get_service_url_success(registry: ServiceRegistry)`

**Returns**: `None`


## backend.tests.test_resource_monitor

**文件**: `backend\tests\test_resource_monitor.py`

资源监控器单元测试。

### class `TestResourceMetrics`

#### `TestResourceMetrics.test_to_dict_rounds_values()`

**Returns**: `None`


#### `TestResourceMetrics.test_to_dict_has_timestamp()`

**Returns**: `None`


### class `TestAlertEvent`

#### `TestAlertEvent.test_to_dict()`

**Returns**: `None`


### class `TestComparisonOperator`

#### `TestComparisonOperator.test_comparison_operators(op: str, a: float, b: float, expected: bool)`

**Returns**: `None`


### class `TestCollectMetrics`

#### `TestCollectMetrics.test_collect_returns_resource_metrics(mock_psutil: object)`

**Returns**: `None`


### class `TestResourceMonitor`

#### `TestResourceMonitor.setup_method()`

**Returns**: `None`


#### `TestResourceMonitor.test_add_rule()`

**Returns**: `None`


#### `TestResourceMonitor.test_add_rule_overwrites_same_name()`

**Returns**: `None`


#### `TestResourceMonitor.test_remove_rule()`

**Returns**: `None`


#### `TestResourceMonitor.test_remove_nonexistent_rule()`

**Returns**: `None`


#### `TestResourceMonitor.test_add_callback()`

**Returns**: `None`


#### `TestResourceMonitor.test_initial_state()`

**Returns**: `None`


#### `TestResourceMonitor.test_get_status()`

**Returns**: `None`


### class `TestResourceMonitorEvaluateRules`

测试告警规则评估逻辑。

#### `TestResourceMonitorEvaluateRules.setup_method()`

**Returns**: `None`


#### `async TestResourceMonitorEvaluateRules.test_rule_triggers_when_threshold_exceeded()`

**Returns**: `None`


#### `async TestResourceMonitorEvaluateRules.test_rule_does_not_trigger_below_threshold()`

**Returns**: `None`


#### `async TestResourceMonitorEvaluateRules.test_cooldown_prevents_duplicate_alerts()`

**Returns**: `None`


#### `async TestResourceMonitorEvaluateRules.test_callback_exception_does_not_block_others()`

单个回调异常不应阻止其他回调执行。

**Returns**: `None`


#### `async TestResourceMonitorEvaluateRules.test_multiple_rules_evaluate_independently()`

**Returns**: `None`


### class `TestResourceMonitorStartStop`

测试启动和停止监控循环。

#### `async TestResourceMonitorStartStop.test_start_and_stop()`

**Returns**: `None`


#### `async TestResourceMonitorStartStop.test_double_start_is_idempotent()`

**Returns**: `None`


### class `TestDefaultRules`

#### `TestDefaultRules.test_default_rules_loaded()`

**Returns**: `None`


#### `TestDefaultRules.test_singleton_returns_same_instance()`

**Returns**: `None`


#### `TestDefaultRules.test_reset_creates_new_instance()`

**Returns**: `None`


## backend.tests.test_retry

**文件**: `backend\tests\test_retry.py`

重试机制单元测试。

### class `TestRetryDecorator`

#### `async TestRetryDecorator.test_no_retry_on_success()`

**Returns**: `None`


#### `async TestRetryDecorator.test_retries_on_failure()`

**Returns**: `None`


#### `async TestRetryDecorator.test_raises_after_exhaustion()`

**Returns**: `None`


#### `async TestRetryDecorator.test_only_retries_specified_exceptions()`

**Returns**: `None`


#### `async TestRetryDecorator.test_on_retry_callback()`

**Returns**: `None`


#### `async TestRetryDecorator.test_max_delay_respected()`

验证延迟不会超过 max_delay。

**Returns**: `None`


#### `TestRetryDecorator.test_sync_function_support()`

**Returns**: `None`


#### `async TestRetryDecorator.test_zero_retries()`

max_retries=0 时不重试，直接抛出。

**Returns**: `None`


## backend.tests.test_scheduled_backup

**文件**: `backend\tests\test_scheduled_backup.py`

定时备份调度器测试。

### `backup_instance(tmp_path: Path)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| tmp_path | Path | - | - |

**Returns**: `DataBackup`

---

### `async test_start_and_stop(backup_instance: DataBackup)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup_instance | DataBackup | - | - |

**Returns**: `None`

---

### `async test_double_start(backup_instance: DataBackup)`

重复启动不应创建多个任务。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup_instance | DataBackup | - | - |

**Returns**: `None`

---

### `async test_stop_when_not_running()`

未启动时调用 stop 不应报错。

**Returns**: `None`

---

### `async test_run_now(backup_instance: DataBackup, tmp_path: Path)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup_instance | DataBackup | - | - |
| tmp_path | Path | - | - |

**Returns**: `None`

---

### `async test_run_now_failure_returns_none(monkeypatch: pytest.MonkeyPatch)`

备份创建失败时 run_now 应返回 None，不抛异常。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| monkeypatch | pytest.MonkeyPatch | - | - |

**Returns**: `None`

---

### `async test_loop_runs_backup(backup_instance: DataBackup)`

调度器启动后应自动执行一次备份。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| backup_instance | DataBackup | - | - |

**Returns**: `None`

---

### `test_get_scheduled_backup_singleton()`

**Returns**: `None`

---

## backend.tests.test_user_rate_limiter

**文件**: `backend\tests\test_user_rate_limiter.py`

用户限流器单元测试。

### class `TestEndpointTier`

#### `TestEndpointTier.test_resolve_plan_route()`

**Returns**: `None`


#### `TestEndpointTier.test_resolve_search_poi()`

**Returns**: `None`


#### `TestEndpointTier.test_resolve_dialogue()`

**Returns**: `None`


#### `TestEndpointTier.test_resolve_default_for_unknown()`

**Returns**: `None`


### class `TestUserRateLimitResult`

#### `TestUserRateLimitResult.test_to_headers()`

**Returns**: `None`


### class `TestLocalUserRateLimiter`

#### `async TestLocalUserRateLimiter.test_allows_first_request()`

**Returns**: `None`


#### `async TestLocalUserRateLimiter.test_blocks_after_limit()`

**Returns**: `None`


#### `async TestLocalUserRateLimiter.test_window_reset()`

**Returns**: `None`


#### `async TestLocalUserRateLimiter.test_different_keys_independent()`

**Returns**: `None`


### class `TestUserRateLimiterLocal`

本地模式集成测试。

#### `async TestUserRateLimiterLocal.test_backend_type_is_local()`

**Returns**: `None`


#### `async TestUserRateLimiterLocal.test_check_respects_endpoint_tier()`

**Returns**: `None`


#### `async TestUserRateLimiterLocal.test_different_endpoints_independent()`

**Returns**: `None`


#### `async TestUserRateLimiterLocal.test_multiplier_reduces_limit()`

**Returns**: `None`


#### `async TestUserRateLimiterLocal.test_multiplier_increases_limit()`

**Returns**: `None`


#### `async TestUserRateLimiterLocal.test_whitelist_user_always_allowed()`

**Returns**: `None`


#### `async TestUserRateLimiterLocal.test_check_with_tier()`

**Returns**: `None`


#### `async TestUserRateLimiterLocal.test_result_contains_correct_fields()`

**Returns**: `None`


### class `TestUserRateLimitExceededError`

#### `TestUserRateLimitExceededError.test_default_message()`

**Returns**: `None`


#### `TestUserRateLimitExceededError.test_custom_details()`

**Returns**: `None`


## backend.tools.changelog_generator

**文件**: `backend\tools\changelog_generator.py`

CityFlow 变更日志生成器。

支持两种模式：
1. 手动添加版本及变更条目
2. 从 Git 提交历史自动生成

### class `ChangelogGenerator`

变更日志生成器。

读写 CHANGELOG.md，支持手动追加版本或从 Git 日志生成。

Parameters
----------
changelog_file : str
    变更日志文件路径，默认为当前目录下的 CHANGELOG.md。

#### `ChangelogGenerator.__init__(changelog_file: str = 'CHANGELOG.md')`

**Returns**: `None`


#### `ChangelogGenerator.add_version(version: str, changes: list[dict[str, str]], date: str | None = None)`

向变更日志追加一个新版本。

Parameters
----------
version : str
    语义化版本号，如 "1.2.0"。
changes : list[dict[str, str]]
    变更列表，每项需包含 "type" 和 "description"。
    type 取值：added / fixed / changed / removed。
date : str | None
    日期字符串，默认使用当天。

**Returns**: `None`


#### `ChangelogGenerator.generate_from_git(last_tag: str | None = None)`

从 Git 提交历史提取变更条目。

解析 conventional commits 格式（type: description），
将 commit type 映射为变更类型。

Parameters
----------
last_tag : str | None
    起始 tag，为空则读取全部历史。

Returns
-------
list[dict[str, str]]
    变更列表，每项含 "type" 和 "description"。

**Returns**: `list[dict[str, str]]`


#### `ChangelogGenerator.generate_from_commits(commits: list[str])`

从 commit 列表提取变更条目（便于测试）。

**Returns**: `list[dict[str, str]]`


## backend.tools.changelog_parser

**文件**: `backend\tools\changelog_parser.py`

CityFlow 变更日志解析器。

解析符合 Keep a Changelog 格式的 CHANGELOG.md 文件，
提取版本号、日期和变更内容。

文件格式要求：
    ## [x.y.z] - YYYY-MM-DD
    ### 新增
    - 描述内容
    ### 修复
    - 描述内容

### class `VersionEntry`

单个版本的变更记录。

### class `ChangelogParser`

变更日志解析器。

读取 CHANGELOG.md 文件并解析为结构化的版本列表。

Parameters
----------
changelog_file : str
    变更日志文件路径，默认为当前目录下的 CHANGELOG.md。

#### `ChangelogParser.__init__(changelog_file: str = 'CHANGELOG.md')`

**Returns**: `None`


#### `ChangelogParser.parse()`

解析变更日志，返回版本列表（按时间倒序）。

**Returns**: `list[VersionEntry]`


#### `ChangelogParser.get_latest_version()`

获取最新版本条目，无版本时返回 None。

**Returns**: `VersionEntry | None`


#### `ChangelogParser.get_version(version: str)`

按版本号查找，未找到返回 None。

**Returns**: `VersionEntry | None`


#### `ChangelogParser.get_changes_by_type(version: str)`

提取指定版本的按类型分组变更列表。

Returns
-------
dict[str, list[str]]
    键为变更类型英文名 (added/fixed/changed/removed)，
    值为该类型下的描述列表。

**Returns**: `dict[str, list[str]]`


## backend.tools.code_generator

**文件**: `backend\tools\code_generator.py`

CityFlow 代码生成工具。

根据字段定义自动生成符合项目规范的 API 端点、数据模型和服务类代码。
生成的代码遵循 CityFlow 项目的编码风格：
- 使用 `from __future__ import annotations`
- Pydantic v2 BaseModel + Field
- 统一的注释分隔线风格
- 类型注解完整

### class `CodeGenerator`

代码生成器。

根据字段定义生成 FastAPI 端点、Pydantic 模型、异步服务类的代码，
并可选择直接写入文件。

Parameters
----------
output_dir : str
    输出根目录，默认 ``"backend"``。

#### `CodeGenerator.__init__(output_dir: str = 'backend')`

**Returns**: `None`


#### `CodeGenerator.generate_api_endpoint(name: str, fields: list[dict[str, Any]])`

生成 CRUD API 端点代码。

Parameters
----------
name : str
    资源名称（英文小写，如 ``"order"``）。
fields : list[dict]
    字段列表，每项包含 ``name``、``type``、``optional`` 键。
tag : str | None
    OpenAPI 标签，默认使用资源名称。
prefix : str | None
    路由前缀，默认 ``/api/{name}``。

Returns
-------
str
    完整的端点模块代码。

**Returns**: `str`


#### `CodeGenerator.generate_model(name: str, fields: list[dict[str, Any]])`

生成 Pydantic 数据模型代码。

Parameters
----------
name : str
    模型名称（英文小写，如 ``"order"``）。
fields : list[dict]
    字段列表，每项包含 ``name``、``type``、``optional``、``description`` 键。
description : str | None
    模型描述，默认自动生成。
include_timestamps : bool
    是否包含 ``created_at`` 和 ``updated_at`` 字段，默认 ``True``。

Returns
-------
str
    完整的模型模块代码。

**Returns**: `str`


#### `CodeGenerator.generate_service(name: str)`

生成异步服务类代码。

Parameters
----------
name : str
    服务名称（英文小写，如 ``"order"``）。
description : str | None
    服务描述，默认自动生成。
use_database : bool
    是否包含数据库会话注入，默认 ``False``。

Returns
-------
str
    完整的服务模块代码。

**Returns**: `str`


#### `CodeGenerator.generate_test(name: str, fields: list[dict[str, Any]])`

生成测试文件代码。

Parameters
----------
name : str
    资源名称（英文小写）。
fields : list[dict]
    字段列表。

Returns
-------
str
    完整的测试模块代码。

**Returns**: `str`


#### `CodeGenerator.save_file(filename: str, content: str)`

将生成的代码保存到文件。

Parameters
----------
filename : str
    相对于输出目录的文件路径，如 ``"routers/order.py"``。
content : str
    文件内容。

Returns
-------
Path
    保存后的绝对路径。

**Returns**: `Path`


#### `CodeGenerator.generate_full(name: str, fields: list[dict[str, Any]])`

一次性生成端点、模型、服务、测试四个文件的代码。

Parameters
----------
name : str
    资源名称（英文小写）。
fields : list[dict]
    字段列表。
save : bool
    是否同时写入文件，默认 ``False``。

Returns
-------
dict[str, str]
    键为 ``router``/``model``/``service``/``test``，值为生成的代码。

**Returns**: `dict[str, str]`


### `main()`

命令行入口，用于快速生成代码。

用法::

    python -m backend.tools.code_generator order             --fields '[{"name": "title", "type": "str"}, {"name": "price", "type": "float"}]'             --save

**Returns**: `None`

---

## backend.tools.doc_generator

**文件**: `backend\tools\doc_generator.py`

CityFlow 文档自动生成工具。

从 Python 源码中提取 API 文档、SDK 文档和使用指南。
支持解析 FastAPI 路由、Pydantic 模型、服务类等模块，
自动生成结构化的 Markdown 文档。

Features:
    - 基于 AST 解析，无需运行代码即可提取文档
    - 支持函数、类、方法的 docstring 提取
    - 自动生成参数表格和返回值说明
    - 支持 FastAPI 路由端点的 HTTP 方法和路径识别

### class `DocType`

**继承**: `Enum`

文档类型枚举。

### class `ParamInfo`

函数参数信息。

### class `ReturnInfo`

函数返回值信息。

### class `FunctionDoc`

函数/方法文档信息。

### class `ClassDoc`

类文档信息。

### class `ModuleDoc`

模块文档信息。

### class `RouteInfo`

FastAPI 路由信息。

### class `_AstParser`

AST 解析辅助类，从 Python 源码中提取文档信息。

#### `_AstParser.parse_annotation(node: ast.expr | None)`

将 AST 类型注解节点转换为可读字符串。

Parameters
----------
node : ast.expr | None
    AST 类型注解节点。

Returns
-------
str
    可读的类型注解字符串。

**Returns**: `str`


#### `_AstParser.parse_default(node: ast.expr | None)`

将 AST 默认值节点转换为可读字符串。

Parameters
----------
node : ast.expr | None
    AST 默认值节点。

Returns
-------
str
    可读的默认值字符串。

**Returns**: `str`


#### `_AstParser.extract_params(func_node: ast.FunctionDef | ast.AsyncFunctionDef)`

从函数定义中提取参数信息。

Parameters
----------
func_node : ast.FunctionDef | ast.AsyncFunctionDef
    函数定义节点。

Returns
-------
list[ParamInfo]
    参数信息列表。

**Returns**: `list[ParamInfo]`


#### `_AstParser.extract_return(func_node: ast.FunctionDef | ast.AsyncFunctionDef)`

从函数定义中提取返回值信息。

Parameters
----------
func_node : ast.FunctionDef | ast.AsyncFunctionDef
    函数定义节点。

Returns
-------
ReturnInfo
    返回值信息。

**Returns**: `ReturnInfo`


#### `_AstParser.extract_decorators(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)`

提取装饰器名称列表。

Parameters
----------
node : ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
    AST 节点。

Returns
-------
list[str]
    装饰器名称列表。

**Returns**: `list[str]`


#### `_AstParser.extract_route_info(decorators: list[str])`

从装饰器中提取 FastAPI 路由信息。

Parameters
----------
decorators : list[str]
    装饰器名称列表。

Returns
-------
tuple[str, str] | None
    (HTTP方法, 路径) 元组，未找到返回 None。

**Returns**: `tuple[str, str] | None`


### class `DocGenerator`

文档生成器。

从 Python 源码目录中提取文档信息，生成 API 文档、SDK 文档和使用指南。

Parameters
----------
source_dir : str
    源码目录路径，默认 ``"backend"``。
project_name : str
    项目名称，默认 ``"CityFlow"``。

#### `DocGenerator.__init__(source_dir: str = 'backend', project_name: str = 'CityFlow')`

**Returns**: `None`


#### `DocGenerator.parse()`

解析源码目录，提取所有文档信息。

遍历源码目录中的所有 Python 文件，提取模块、类、函数的文档信息，
以及 FastAPI 路由端点信息。

**Returns**: `None`


#### `DocGenerator.generate_api_docs()`

生成 API 文档数据结构。

Returns
-------
dict[str, Any]
    包含模块、路由、统计信息的文档数据。

**Returns**: `dict[str, Any]`


#### `DocGenerator.generate_api_docs_markdown()`

生成 API 文档的 Markdown 格式。

Returns
-------
str
    API 文档 Markdown 内容。

**Returns**: `str`


#### `DocGenerator.generate_sdk_docs()`

生成 SDK 文档的 Markdown 格式。

SDK 文档面向开发者使用 CityFlow 的服务类和工具，
侧重于类和方法的使用说明。

Returns
-------
str
    SDK 文档 Markdown 内容。

**Returns**: `str`


#### `DocGenerator.generate_usage_guide()`

生成使用指南的 Markdown 格式。

使用指南面向最终用户和新开发者，包含快速开始、
常见用例和最佳实践。

Returns
-------
str
    使用指南 Markdown 内容。

**Returns**: `str`


#### `DocGenerator.save_docs(output_dir: str = 'docs')`

生成并保存所有文档文件。

Parameters
----------
output_dir : str
    输出目录，默认 ``"docs"``。

Returns
-------
dict[str, Path]
    键为文档类型，值为保存路径。

**Returns**: `dict[str, Path]`


### `main()`

命令行入口，用于生成文档。

用法::

    python -m backend.tools.doc_generator --source backend --output docs

**Returns**: `None`

---

## backend.tools.markdown_generator

**文件**: `backend\tools\markdown_generator.py`

CityFlow Markdown 文档生成工具。

提供 Markdown 内容的构建块，包括表格、代码块、目录、
列表等常用结构的生成方法。

设计为无状态工具类，所有方法均为纯函数，便于组合使用。

### class `MarkdownGenerator`

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

#### `MarkdownGenerator.generate_table(headers: list[str], rows: list[list[str]])`

生成 Markdown 表格。

Parameters
----------
headers : list[str]
    表头列表。
rows : list[list[str]]
    数据行列表，每行长度应与 headers 一致。
align : str
    列对齐方式，可选 ``"left"``/``"center"``/``"right"``，默认 ``"left"``。

Returns
-------
str
    Markdown 表格字符串。

Examples
--------
>>> md = MarkdownGenerator()
>>> print(md.generate_table(["Name", "Age"], [["Alice", "30"]]))
| Name | Age |
| --- | --- |
| Alice | 30 |

**Returns**: `str`


#### `MarkdownGenerator.generate_code_block(code: str, language: str = 'python')`

生成带语法高亮标记的代码块。

Parameters
----------
code : str
    代码内容。
language : str
    编程语言标识，默认 ``"python"``。

Returns
-------
str
    Markdown 代码块字符串。

Examples
--------
>>> md = MarkdownGenerator()
>>> print(md.generate_code_block("print('hi')", "python"))
```python
print('hi')
```

**Returns**: `str`


#### `MarkdownGenerator.generate_inline_code(text: str)`

生成行内代码标记。

Parameters
----------
text : str
    代码文本。

Returns
-------
str
    带反引号的行内代码。

**Returns**: `str`


#### `MarkdownGenerator.generate_toc(headings: list[dict[str, Any]])`

生成 Markdown 目录。

Parameters
----------
headings : list[dict[str, Any]]
    标题列表，每项包含 ``level``（标题级别）和 ``title``（标题文本）。
max_depth : int
    最大目录深度，默认 ``3``。

Returns
-------
str
    Markdown 目录字符串。

Examples
--------
>>> md = MarkdownGenerator()
>>> toc = md.generate_toc([
...     {"level": 1, "title": "Introduction"},
...     {"level": 2, "title": "Getting Started"},
... ])
>>> print(toc)
- [Introduction](#introduction)
  - [Getting Started](#getting-started)

**Returns**: `str`


#### `MarkdownGenerator.generate_unordered_list(items: list[str])`

生成无序列表。

Parameters
----------
items : list[str]
    列表项内容。
marker : str
    列表标记符，默认 ``"-"``。

Returns
-------
str
    Markdown 无序列表字符串。

**Returns**: `str`


#### `MarkdownGenerator.generate_ordered_list(items: list[str])`

生成有序列表。

Parameters
----------
items : list[str]
    列表项内容。

Returns
-------
str
    Markdown 有序列表字符串。

**Returns**: `str`


#### `MarkdownGenerator.generate_heading(text: str, level: int = 1)`

生成标题。

Parameters
----------
text : str
    标题文本。
level : int
    标题级别（1-6），默认 ``1``。

Returns
-------
str
    Markdown 标题字符串。

**Returns**: `str`


#### `MarkdownGenerator.generate_horizontal_rule()`

生成水平分隔线。

Returns
-------
str
    水平分隔线 ``---``。

**Returns**: `str`


#### `MarkdownGenerator.generate_link(text: str, url: str)`

生成超链接。

Parameters
----------
text : str
    链接文本。
url : str
    链接地址。

Returns
-------
str
    Markdown 链接。

**Returns**: `str`


#### `MarkdownGenerator.generate_image(alt: str, url: str)`

生成图片。

Parameters
----------
alt : str
    替代文本。
url : str
    图片地址。

Returns
-------
str
    Markdown 图片。

**Returns**: `str`


#### `MarkdownGenerator.generate_blockquote(text: str)`

生成引用块。

Parameters
----------
text : str
    引用文本，支持多行。

Returns
-------
str
    Markdown 引用块。

**Returns**: `str`


#### `MarkdownGenerator.generate_key_value_pairs(data: dict[str, str])`

生成键值对列表。

Parameters
----------
data : dict[str, str]
    键值对数据。
separator : str
    键值分隔符，默认 ``":"``。

Returns
-------
str
    格式化后的键值对文本。

**Returns**: `str`


#### `MarkdownGenerator.generate_details_block(summary: str, content: str)`

生成可折叠的详情块（HTML <details> 标签）。

Parameters
----------
summary : str
    摘要标题。
content : str
    展开后的内容。

Returns
-------
str
    HTML details 块。

**Returns**: `str`


## backend.utils.cpu_profiler

**文件**: `backend\utils\cpu_profiler.py`

CityFlow CPU 分析器。

基于 cProfile 提供 CPU 级别的函数调用分析，
支持按累计耗时 / 自身耗时 / 调用次数排序。

### class `FunctionStat`

单个函数的 CPU 统计。

#### `FunctionStat.to_dict()`

**Returns**: `dict[str, Any]`


### class `CPUProfileResult`

一次 CPU 分析的结果。

#### `CPUProfileResult.to_dict()`

**Returns**: `dict[str, Any]`


### class `CPUProfiler`

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

#### `CPUProfiler.__init__()`

**Returns**: `None`


#### `CPUProfiler.enabled()`

**Returns**: `bool`


#### `CPUProfiler.start()`

开始 CPU 分析。

**Returns**: `None`


#### `CPUProfiler.stop(label: str = 'default')`

停止分析并生成结果。

Args:
    label: 本次分析的标签。

Returns:
    分析结果。

**Returns**: `CPUProfileResult`


#### `CPUProfiler.run(label: str = 'default')`

返回上下文管理器，在退出时自动分析。

用法::

    with cpu_profiler.run("my_block"):
        do_work()

**Returns**: `_CPURunContext`


#### `CPUProfiler.profile(name: str | None = None)`

装饰器，对单个函数进行 CPU 分析。

用法::

    @cpu_profiler.profile("heavy_func")
    def heavy_func():
        ...

**Returns**: `Any`


#### `CPUProfiler.get_top_functions(limit: int = 20, label: str | None = None, sort_by: str = 'cumtime')`

获取 CPU 耗时 Top N 函数。

Args:
    limit: 返回条数。
    label: 指定分析结果标签，为 None 时取最新的。
    sort_by: 排序字段，可选 "cumtime"（累计）、"tottime"（自身）、"ncalls"（调用次数）。

Returns:
    排序后的函数统计列表。

**Returns**: `list[dict[str, Any]]`


#### `CPUProfiler.get_pstats_text(label: str | None = None, sort_by: str = 'cumulative')`

获取 pstats 原始文本输出（便于调试）。

Args:
    label: 指定分析结果标签。
    sort_by: pstats 排序键，如 "cumulative", "tottime", "calls"。

Returns:
    格式化的文本报告。

**Returns**: `str`


#### `CPUProfiler.get_all_labels()`

返回所有分析结果的标签。

**Returns**: `list[str]`


#### `CPUProfiler.remove_result(label: str)`

删除指定分析结果。

**Returns**: `bool`


#### `CPUProfiler.reset()`

清空所有结果并重置 profiler。

**Returns**: `None`


### class `_CPURunContext`

CPUProfiler.run() 返回的上下文管理器。

#### `_CPURunContext.__init__(profiler: CPUProfiler, label: str)`

**Returns**: `None`


## backend.utils.encryption

**文件**: `backend\utils\encryption.py`

CityFlow 数据加密工具。

基于 Fernet 对称加密，使用 PBKDF2 派生密钥。
用于加密数据库中的敏感字段（如用户手机号、API Key 等）。

### class `EncryptionError`

**继承**: `Exception`

加密/解密操作失败。

### class `DataEncryptor`

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

#### `DataEncryptor.__init__(key: str | None = None, salt: bytes = _DEFAULT_SALT, iterations: int = _PBKDF2_ITERATIONS)`

**Returns**: `None`


#### `DataEncryptor.encrypt(data: str)`

加密字符串，返回 base64 编码的密文。

**Returns**: `str`


#### `DataEncryptor.decrypt(encrypted_data: str)`

解密 base64 编码的密文，返回明文。

**Returns**: `str`


#### `DataEncryptor.encrypt_dict(data: dict[str, Any])`

将字典序列化为 JSON 后加密。

**Returns**: `str`


#### `DataEncryptor.decrypt_dict(encrypted_data: str)`

解密后反序列化为字典。

**Returns**: `dict[str, Any]`


### `get_encryptor()`

获取全局加密器实例（懒加载单例）。

**Returns**: `DataEncryptor`

---

### `reset_encryptor()`

重置全局加密器（测试用）。

**Returns**: `None`

---

### `encrypt_sensitive_data(data: str)`

快捷函数：加密敏感数据。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| data | str | - | - |

**Returns**: `str`

---

### `decrypt_sensitive_data(encrypted_data: str)`

快捷函数：解密敏感数据。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| encrypted_data | str | - | - |

**Returns**: `str`

---

## backend.utils.error_handler

**文件**: `backend\utils\error_handler.py`

CityFlow 错误处理装饰器。

为 service 层函数提供统一的异常包装，把底层异常
转换为 CityFlowException 子类，避免在每个函数里重复 try/except。

### `handle_errors(default_message: str = '操作失败')`

通用错误处理装饰器。

- CityFlowException 原样抛出（不做二次包装）。
- 其他异常包装为 CityFlowException(INTERNAL_ERROR)。

用法::

    @handle_errors("意图解析失败")
    async def parse_intent(...):
        ...

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| default_message | str | '操作失败' | - |

**Returns**: `Callable`

---

### `handle_llm_errors(func: Callable)`

LLM 调用专用错误处理装饰器。

- TimeoutError -> LLM_SERVICE_ERROR (超时)
- 其他异常 -> LLM_SERVICE_ERROR (通用)

用法::

    @handle_llm_errors
    async def call_llm(prompt: str) -> str:
        ...

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| func | Callable | - | - |

**Returns**: `Callable`

---

## backend.utils.field_encryption

**文件**: `backend\utils\field_encryption.py`

CityFlow 字段加密装饰器。

为 service 层函数提供透明的字段加解密，
支持对返回字典中的指定字段自动加密/解密。

### `encrypt_field(field_name: str)`

加密返回字典中的指定字段。

用法::

    @encrypt_field("phone")
    async def create_user(data: dict) -> dict:
        return {"id": 1, "phone": "13800138000"}
        # 实际返回: {"id": 1, "phone": "<encrypted>"}

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| field_name | str | - | - |

**Returns**: `Callable`

---

### `decrypt_field(field_name: str)`

解密返回字典中的指定字段。

用法::

    @decrypt_field("phone")
    async def get_user(user_id: int) -> dict:
        return {"id": 1, "phone": "<encrypted>"}
        # 实际返回: {"id": 1, "phone": "13800138000"}

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| field_name | str | - | - |

**Returns**: `Callable`

---

### `encrypt_fields()`

批量加密返回字典中的多个字段。

用法::

    @encrypt_fields("phone", "id_card")
    async def create_user(data: dict) -> dict:
        ...

**Returns**: `Callable`

---

### `decrypt_fields()`

批量解密返回字典中的多个字段。

用法::

    @decrypt_fields("phone", "id_card")
    async def get_user(user_id: int) -> dict:
        ...

**Returns**: `Callable`

---

### `encrypt_value(value: str)`

直接加密单个值（不通过装饰器）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| value | str | - | - |

**Returns**: `str`

---

### `decrypt_value(value: str)`

直接解密单个值（不通过装饰器）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| value | str | - | - |

**Returns**: `str`

---

## backend.utils.localized_response

**文件**: `backend\utils\localized_response.py`

CityFlow 本地化响应工具。

提供统一的 API 响应格式，所有消息通过 i18n 翻译后返回。

### class `LocalizedResponse`

本地化 API 响应构建器。

所有方法返回字典，可直接由 FastAPI 序列化为 JSON。
消息键默认使用 "common.*" 下的翻译。

#### `LocalizedResponse.success(message_key: str = 'common.success')`

构造成功响应。

Args:
    message_key: 翻译键。
    **kwargs: 翻译插值参数。

Returns:
    {"success": True, "message": "..."}

**Returns**: `dict[str, Any]`


#### `LocalizedResponse.error(message_key: str = 'common.error')`

构造错误响应。

Args:
    message_key: 翻译键。
    **kwargs: 翻译插值参数。

Returns:
    {"success": False, "message": "..."}

**Returns**: `dict[str, Any]`


#### `LocalizedResponse.data(data: Any, message_key: str = 'common.success')`

构造带数据的成功响应。

Args:
    data: 要返回的数据。
    message_key: 翻译键。
    **kwargs: 翻译插值参数。

Returns:
    {"success": True, "message": "...", "data": ...}

**Returns**: `dict[str, Any]`


#### `LocalizedResponse.paginated(data: list[Any], total: int, page: int = 1, page_size: int = 20, message_key: str = 'common.success')`

构造分页响应。

Args:
    data: 当前页数据列表。
    total: 总记录数。
    page: 当前页码（从 1 开始）。
    page_size: 每页条数。
    message_key: 翻译键。
    **kwargs: 翻译插值参数。

Returns:
    包含分页信息的响应字典。

**Returns**: `dict[str, Any]`


## backend.utils.memory_profiler

**文件**: `backend\utils\memory_profiler.py`

CityFlow 内存分析器。

基于 tracemalloc 提供内存分配追踪能力，
支持快照对比、Top N 排查、增量分析。

### class `AllocationInfo`

单条内存分配记录。

#### `AllocationInfo.to_dict()`

**Returns**: `dict[str, Any]`


### class `SnapshotInfo`

快照摘要。

#### `SnapshotInfo.to_dict()`

**Returns**: `dict[str, Any]`


### class `MemoryProfiler`

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

#### `MemoryProfiler.__init__(nframes: int = 1)`

**Returns**: `None`


#### `MemoryProfiler.enabled()`

**Returns**: `bool`


#### `MemoryProfiler.start(nframes: int | None = None)`

启动内存追踪。

Args:
    nframes: 每个分配记录保存的栈帧层数，默认 1。
             层数越大越精确，但开销也越大。

**Returns**: `None`


#### `MemoryProfiler.stop()`

停止内存追踪并清空快照。

**Returns**: `None`


#### `MemoryProfiler.take_snapshot(label: str = 'default')`

拍摄内存快照。

Args:
    label: 快照标签，用于后续对比。

Returns:
    快照摘要，未启用时返回 None。

**Returns**: `SnapshotInfo | None`


#### `MemoryProfiler.get_top_allocations(limit: int = 10, label: str = 'default')`

获取内存分配 Top N。

Args:
    limit: 返回条数。
    label: 使用哪个快照。

Returns:
    按内存大小降序排列的分配列表。

**Returns**: `list[dict[str, Any]]`


#### `MemoryProfiler.compare_snapshots(label_before: str, label_after: str, limit: int = 10)`

对比两个快照，返回内存增量 Top N。

Args:
    label_before: 基准快照标签。
    label_after: 后续快照标签。
    limit: 返回条数。

Returns:
    按增量降序排列的对比结果。

**Returns**: `list[dict[str, Any]]`


#### `MemoryProfiler.get_snapshot_labels()`

返回所有已保存的快照标签。

**Returns**: `list[str]`


#### `MemoryProfiler.remove_snapshot(label: str)`

删除指定快照。

**Returns**: `bool`


## backend.utils.profiler

**文件**: `backend\utils\profiler.py`

CityFlow 性能分析器。

提供函数耗时统计功能，包括装饰器和手动记录两种方式。
支持全局统计与慢函数告警。

### class `ProfilerStats`

单个函数的统计数据。

#### `ProfilerStats.__init__()`

**Returns**: `None`


#### `ProfilerStats.record(duration: float)`

**Returns**: `None`


#### `ProfilerStats.avg()`

**Returns**: `float`


#### `ProfilerStats.to_dict()`

**Returns**: `dict[str, Any]`


### class `Profiler`

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

#### `Profiler.__init__(slow_threshold: float = 1.0)`

**Returns**: `None`


#### `Profiler.enabled()`

**Returns**: `bool`


#### `Profiler.enable()`

**Returns**: `None`


#### `Profiler.disable()`

**Returns**: `None`


#### `Profiler.set_slow_threshold(seconds: float)`

设置慢函数告警阈值（秒）。

**Returns**: `None`


#### `Profiler.record(name: str, duration: float)`

记录一次函数耗时。

**Returns**: `None`


#### `Profiler.get_stats()`

获取所有函数的统计数据。

**Returns**: `dict[str, dict[str, Any]]`


#### `Profiler.get_slow_functions()`

获取超过慢阈值的函数列表。

**Returns**: `list[dict[str, Any]]`


#### `Profiler.reset()`

重置所有统计数据。

**Returns**: `None`


#### `Profiler.log_summary()`

以日志形式输出统计摘要。

**Returns**: `None`


### `get_profiler()`

获取全局性能分析器实例。

**Returns**: `Profiler`

---

### `profile(name: str | None = None)`

性能分析装饰器（异步函数）。

用法::

    @profile()
    async def my_func():
        ...

    @profile("custom_name")
    async def my_func():
        ...

Args:
    name: 自定义统计名称，默认使用函数名。
    slow_threshold: 覆盖全局慢函数阈值（秒），仅对本次调用生效。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| name | str | None | None | - |

**Returns**: `Callable`

---

## backend.utils.serialization

**文件**: `backend\utils\serialization.py`

CityFlow 高效 JSON 序列化工具。

使用 orjson 实现高性能序列化，可选 gzip 压缩。

### class `FastJSONSerializer`

基于 orjson 的高性能 JSON 序列化器。

orjson 比标准库 json 快 5-10 倍，
且原生支持 numpy 类型和非字符串 key。

#### `FastJSONSerializer.dumps(obj: Any, compress: bool = False)`

序列化为 bytes，可选 gzip 压缩。

Args:
    obj: 任意可序列化对象。
    compress: 是否启用 gzip 压缩。

Returns:
    序列化后的 bytes 数据。

**Returns**: `bytes`


#### `FastJSONSerializer.loads(data: bytes, compressed: bool = False)`

从 bytes 反序列化，可选 gzip 解压。

Args:
    data: 序列化的 bytes 数据。
    compressed: 是否需要 gzip 解压。

Returns:
    反序列化后的 Python 对象。

**Returns**: `Any`


#### `FastJSONSerializer.dumps_str(obj: Any)`

序列化为 UTF-8 字符串。

**Returns**: `str`


#### `FastJSONSerializer.loads_str(data: str)`

从 UTF-8 字符串反序列化。

**Returns**: `Any`


### class `CompressedJSONSerializer`

基于标准库 json + gzip 的压缩序列化器。

用于不依赖 orjson 的场景（如脚本、迁移工具）。

#### `CompressedJSONSerializer.dumps(obj: Any)`

序列化并压缩。

**Returns**: `bytes`


#### `CompressedJSONSerializer.loads(data: bytes)`

解压并反序列化。

**Returns**: `Any`


### `serialize_response(data: Any, compress: bool = False)`

序列化 API 响应数据。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| data | Any | - | - |
| compress | bool | False | - |

**Returns**: `bytes`

---

### `deserialize_request(data: bytes, compressed: bool = False)`

反序列化 API 请求数据。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| data | bytes | - | - |
| compressed | bool | False | - |

**Returns**: `Any`

---

## backend.utils.serializers

**文件**: `backend\utils\serializers.py`

CityFlow 序列化装饰器。

为函数/路由提供自动序列化/反序列化能力。

### `serialize_output(compress: bool = False)`

将函数返回值自动序列化为 bytes。

适用于需要直接返回序列化数据的场景（如缓存、消息队列）。

Args:
    compress: 是否启用 gzip 压缩。

Example::

    @serialize_output(compress=True)
    async def get_large_data() -> dict:
        return {"items": list(range(10000))}

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| compress | bool | False | - |

**Returns**: `Callable[List(elts=[Name(id='F', ctx=Load())], ctx=Load()), F]`

---

### `deserialize_input(compressed: bool = False)`

将函数的 bytes 类型参数自动反序列化。

仅处理位置参数中 `bytes` 类型的值，其他参数原样传递。

Args:
    compressed: 输入数据是否经过 gzip 压缩。

Example::

    @deserialize_input(compressed=True)
    async def process_data(payload: dict) -> dict:
        return {"processed": True, **payload}

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| compressed | bool | False | - |

**Returns**: `Callable[List(elts=[Name(id='F', ctx=Load())], ctx=Load()), F]`

---

## backend.utils.version_compat

**文件**: `backend\utils\version_compat.py`

API 版本兼容性处理工具。

### `convert_v1_to_v2_request(v1_request: dict[str, Any])`

将 V1 请求转换为 V2 格式。

V1 请求格式:
    {"user_input": "..."}

V2 请求格式:
    {"user_input": "...", "preferences": null, "constraints": [], "pace": "平衡型"}

Args:
    v1_request: V1 格式的请求数据

Returns:
    V2 格式的请求数据

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| v1_request | dict[str, Any] | - | - |

**Returns**: `dict[str, Any]`

---

### `convert_v2_to_v1_response(v2_response: dict[str, Any])`

将 V2 响应转换为 V1 格式。

V2 响应包含 emotion_curve 和 metadata，V1 不需要这些字段。

Args:
    v2_response: V2 格式的响应数据

Returns:
    V1 格式的响应数据（移除了 emotion_curve 和 metadata）

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| v2_response | dict[str, Any] | - | - |

**Returns**: `dict[str, Any]`

---

### `convert_v2_to_v1_poi(poi: dict[str, Any])`

将 V2 POI 数据转换为 V1 格式。

V2 POI 包含完整的 constraints 和 emotion_tags，V1 只返回基本字段。

Args:
    poi: V2 格式的 POI 数据

Returns:
    V1 格式的 POI 数据

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi | dict[str, Any] | - | - |

**Returns**: `dict[str, Any]`

---

### `get_version_from_request(request: Any)`

从请求中获取 API 版本。

优先级：请求状态 > URL路径 > 请求头 > 默认版本

Args:
    request: FastAPI Request 对象

Returns:
    版本号（如 "v1"）

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| request | Any | - | - |

**Returns**: `str`

---

### `is_v1_request(request: Any)`

判断是否为 V1 请求。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| request | Any | - | - |

**Returns**: `bool`

---

### `is_v2_request(request: Any)`

判断是否为 V2 请求。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| request | Any | - | - |

**Returns**: `bool`

---

## backend.validators.base

**文件**: `backend\validators\base.py`

CityFlow 数据校验框架。

提供请求/响应数据的校验基类和业务校验器。
基于 Pydantic v2，与项目已有的错误体系 (CityFlowException) 对接。

### class `BaseValidator`

**继承**: `BaseModel`

基础校验器 — 所有业务校验器的基类。

### class `RequestValidator`

**继承**: `BaseValidator`

请求校验基类 — 自动清理所有字符串字段。

#### `RequestValidator.sanitize_all_strings(data: Any)`

在字段校验之前，清理所有字符串值。

**Returns**: `Any`


### class `EmotionTagsValidator`

**继承**: `BaseValidator`

POI 情绪标签校验（6 维，取值 0~1）。

### class `ConstraintsValidator`

**继承**: `BaseValidator`

POI 约束条件校验。

### class `POIValidator`

**继承**: `RequestValidator`

POI 数据校验器 — 匹配 city_poi_db.json 的实际字段。

#### `POIValidator.validate_id(v: str)`

**Returns**: `str`


#### `POIValidator.validate_business_hours(v: str)`

**Returns**: `str`


### class `POISearchValidator`

**继承**: `RequestValidator`

POI 搜索请求校验器 — 匹配 SearchRequest 模型。

### class `RouteStepValidator`

**继承**: `BaseValidator`

路线步骤校验器。

#### `RouteStepValidator.validate_time_format(v: str | None)`

**Returns**: `str | None`


### class `RouteValidator`

**继承**: `RequestValidator`

路线校验器 — 用于校验完整的路线数据。

#### `RouteValidator.validate_route_not_empty(v: list[dict])`

**Returns**: `list[dict]`


### class `PlanRequestValidator`

**继承**: `RequestValidator`

V1 路线规划请求校验器 — 匹配 PlanRequestV1。

#### `PlanRequestValidator.validate_user_input(v: str)`

**Returns**: `str`


### class `DialogueRequestValidator`

**继承**: `RequestValidator`

对话调整请求校验器 — 匹配 AdjustRequestV1。

#### `DialogueRequestValidator.validate_instruction(v: str)`

**Returns**: `str`


### class `DistanceMatrixValidator`

**继承**: `RequestValidator`

距离矩阵请求校验器 — 匹配 DistanceMatrixRequest。

#### `DistanceMatrixValidator.validate_poi_ids(v: list[str])`

**Returns**: `list[str]`


### class `ChatRequestValidator`

**继承**: `RequestValidator`

LLM 对话请求校验器 — 匹配 ChatRequest。

#### `ChatRequestValidator.validate_message(v: str)`

**Returns**: `str`


### `sanitize_string(value: str)`

清理字符串：去除 HTML 标签、首尾空白。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| value | str | - | - |

**Returns**: `str`

---

### `check_injection(value: str)`

检测 SQL 注入模式，匹配则抛出 CityFlowException。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| value | str | - | - |

**Returns**: `None`

---

## backend.validators.decorators

**文件**: `backend\validators\decorators.py`

校验装饰器。

为 FastAPI 路由函数提供声明式的数据校验能力：
- validate_request: 在函数执行前校验请求参数
- validate_response: 在函数执行后校验返回值

### `validate_request(model: Type[BaseModel])`

请求校验装饰器。

将函数的 kwargs 按 model 进行校验，校验通过后用清理后的值替换原参数。

Usage::

    @validate_request(PlanRequestValidator)
    async def plan_route(user_input: str):
        ...

Args:
    model: Pydantic 模型类，用于校验请求数据。

Returns:
    装饰后的异步函数。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| model | Type[BaseModel] | - | - |

**Returns**: `Any`

---

### `validate_response(model: Type[BaseModel])`

响应校验装饰器。

将函数的返回值按 model 进行校验，确保响应数据结构正确。

Usage::

    @validate_response(SearchResponse)
    async def search_pois(request: SearchRequest):
        return {"pois": [...], "total": 10}

Args:
    model: Pydantic 模型类，用于校验响应数据。

Returns:
    装饰后的异步函数。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| model | Type[BaseModel] | - | - |

**Returns**: `Any`

---

## backend.routers.v1.dialogue

**文件**: `backend\routers\v1\dialogue.py`

V1 对话式路线调整接口。

### class `AdjustRequestV1`

**继承**: `BaseModel`

V1 对话调整请求。

### class `DialogueResultV1`

**继承**: `BaseModel`

V1 对话调整响应。

### `async dialogue_v1(session_id: str, request: AdjustRequestV1)`

V1 版本的对话式路线调整。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| session_id | str | - | - |
| request | AdjustRequestV1 | - | - |

---

### `async get_route_v1(route_id: str)`

V1 版本的路线详情查询。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| route_id | str | - | - |

---

## backend.routers.v1.plan

**文件**: `backend\routers\v1\plan.py`

V1 路线规划接口。

### class `PlanRequestV1`

**继承**: `BaseModel`

V1 路线规划请求。

### class `PlanResponseV1`

**继承**: `BaseModel`

V1 路线规划响应。

### `async plan_route_v1(request: PlanRequestV1)`

V1版本的路线规划（SSE流式响应）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| request | PlanRequestV1 | - | - |

---

## backend.routers.v1.poi

**文件**: `backend\routers\v1\poi.py`

V1 POI 查询接口。

### class `SearchRequestV1`

**继承**: `BaseModel`

V1 POI 搜索请求。

### class `DistanceMatrixRequestV1`

**继承**: `BaseModel`

V1 距离矩阵请求。

### `load_pois()`

**Returns**: `None`

---

### `get_price_range(avg_price: float)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| avg_price | float | - | - |

**Returns**: `str`

---

### `haversine(lat1: float, lon1: float, lat2: float, lon2: float)`

返回两点间的球面直线距离（米）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| lat1 | float | - | - |
| lon1 | float | - | - |
| lat2 | float | - | - |
| lon2 | float | - | - |

**Returns**: `float`

---

### `enrich_poi(poi: dict)`

为 POI 补充 emotion_tags、constraints、price_range 字段。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi | dict | - | - |

**Returns**: `dict`

---

### `async search_pois_v1(request: SearchRequestV1, lat: Optional[float] = Query(...), lng: Optional[float] = Query(...))`

V1 版本的 POI 搜索。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| request | SearchRequestV1 | - | - |
| lat | Optional[float] | Query(...) | - |
| lng | Optional[float] | Query(...) | - |

---

### `async get_poi_detail_v1(poi_id: str)`

V1 版本的 POI 详情。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi_id | str | - | - |

---

### `async get_distance_matrix_v1(request: DistanceMatrixRequestV1)`

V1 版本的距离矩阵计算。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| request | DistanceMatrixRequestV1 | - | - |

---

## backend.routers.v2.plan

**文件**: `backend\routers\v2\plan.py`

V2 路线规划接口（增强版）。

### class `PlanRequestV2`

**继承**: `BaseModel`

V2 路线规划请求（增强版，支持约束和节奏）。

### class `EmotionCurvePoint`

**继承**: `BaseModel`

情绪曲线数据点。

### class `RouteMetadata`

**继承**: `BaseModel`

路线元数据。

### class `PlanResponseV2`

**继承**: `BaseModel`

V2 路线规划响应（增强版，包含情绪曲线和元数据）。

### `async plan_route_v2(request: PlanRequestV2)`

V2版本的路线规划（SSE流式响应，增强版）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| request | PlanRequestV2 | - | - |

---

## backend.routers.v2.poi

**文件**: `backend\routers\v2\poi.py`

V2 POI 查询接口（增强版）。

### class `SearchRequestV2`

**继承**: `BaseModel`

V2 POI 搜索请求（增强版，支持约束过滤）。

### class `DistanceMatrixRequestV2`

**继承**: `BaseModel`

V2 距离矩阵请求。

### `load_pois()`

**Returns**: `None`

---

### `get_price_range(avg_price: float)`

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| avg_price | float | - | - |

**Returns**: `str`

---

### `haversine(lat1: float, lon1: float, lat2: float, lon2: float)`

返回两点间的球面直线距离（米）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| lat1 | float | - | - |
| lon1 | float | - | - |
| lat2 | float | - | - |
| lon2 | float | - | - |

**Returns**: `float`

---

### `enrich_poi(poi: dict)`

为 POI 补充 emotion_tags、constraints、price_range 字段。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi | dict | - | - |

**Returns**: `dict`

---

### `async search_pois_v2(request: SearchRequestV2, lat: Optional[float] = Query(...), lng: Optional[float] = Query(...))`

V2 版本的 POI 搜索（增强版）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| request | SearchRequestV2 | - | - |
| lat | Optional[float] | Query(...) | - |
| lng | Optional[float] | Query(...) | - |

---

### `async get_poi_detail_v2(poi_id: str)`

V2 版本的 POI 详情（增强版）。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| poi_id | str | - | - |

---

### `async get_distance_matrix_v2(request: DistanceMatrixRequestV2)`

V2 版本的距离矩阵计算。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| request | DistanceMatrixRequestV2 | - | - |

---
