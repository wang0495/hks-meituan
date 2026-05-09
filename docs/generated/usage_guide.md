# CityFlow 使用指南

## 快速开始

### 环境要求

- Python 3.12+
- 依赖包见 `requirements.txt`

### 安装

```bash
# 克隆项目
git clone <repo-url>
cd cityflow

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
```

### 启动服务

```bash
# 开发模式
python -m backend.main

# 或使用 uvicorn
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## API 概览

项目包含 **68** 个 API 端点，
分布在 **166** 个模块中。

### 主要接口

| 方法 | 路径 | 说明 |
| :--- | :--- | :--- |
| POST | /api/plan | 流式规划路线 |
| GET | /api/route/{route_id} | 获取路线详情 |
| GET | /api/route/{route_id}/adjust | 通过指令调整路线（快捷方式） |
| POST | /api/dialogue/{session_id} | 对话式路线调整 |
| GET | /api/health | 健康检查 |
| GET | /api/cache/stats | 缓存统计 |
| GET | /docs |  |
| GET | /redoc |  |
| GET | /health | 网关健康检查 |
| GET | /logs | 查询审计日志 |
| GET | /export | 导出审计日志 |
| GET | /stats | 审计日志统计 |
| GET | /data/ | 查询数据集 |
| GET | /poi/ | 查询城市POI数据 |
| GET | /datasets | 列出所有数据集 |
| GET | /order/ | 查询POI交通流量 |
| GET | /road-traffic/ | 查询道路拥堵指数 |
| GET | /health | 基础健康检查 |
| GET | /health/detailed | 详细健康状态 |
| POST | /chat | LLM对话 |
| POST | /chat/stream | LLM流式对话 |
| GET | /metrics | Prometheus 指标 |
| POST | /publish/{queue} | 发布单条消息 |
| POST | /publish/{queue}/batch | 批量发布消息 |
| POST | /consume/{queue} | 启动消费者 |
| GET | /status/{queue} | 查询队列状态 |
| DELETE | /{queue} | 清空队列 |
| GET | /handlers | 列出已注册处理器 |
| POST | /search | 搜索POI |
| GET | /detail/{poi_id} | 获取POI详情 |
| POST | /distance-matrix | 计算距离矩阵 |
| POST | /register | 注册服务 |
| POST | /deregister/{service_id} | 注销服务 |
| POST | /heartbeat/{service_id} | 服务心跳 |
| GET | /services | 获取服务列表 |
| GET | /services/{service_name} | 发现服务 |
| GET | /stats | 注册中心统计 |
| POST | /cleanup | 清理不健康实例 |
| POST | / | 创建会话 |
| GET | /stats | 会话统计 |
| GET | /{session_id} | 获取会话 |
| PUT | /{session_id} | 更新会话 |
| DELETE | /{session_id} | 删除会话 |
| POST | /{session_id}/refresh | 刷新会话 |
| GET | /user/{user_id}/list | 获取用户会话列表 |
| POST | /{func_name} | 提交后台任务 |
| GET | /{task_id} | 查询任务状态 |
| DELETE | /{task_id} | 取消任务 |
| GET | / | 列出所有任务 |
| GET | /cityflow-error |  |
| GET | /intent-error |  |
| GET | /llm-error |  |
| GET | /dialogue-error |  |
| GET | /no-pois-error |  |
| GET | /rate-limit-error |  |
| GET | /generic-error |  |
| GET | /test |  |
| PATCH |  |  |
| POST | /dialogue/{session_id} | [V1] 对话式路线调整 |
| GET | /route/{route_id} | [V1] 获取路线详情 |
| POST | /plan | [V1] 流式规划路线 |
| POST | /poi/search | [V1] 搜索POI |
| GET | /poi/detail/{poi_id} | [V1] 获取POI详情 |
| POST | /poi/distance-matrix | [V1] 计算距离矩阵 |
| POST | /plan | [V2] 流式规划路线（增强版） |
| POST | /poi/search | [V2] 搜索POI（增强版） |
| GET | /poi/detail/{poi_id} | [V2] 获取POI详情（增强版） |
| POST | /poi/distance-matrix | [V2] 计算距离矩阵 |

## 使用示例

### 路线规划

使用 `plan_route` 接口进行路线规划：

```python
import httpx

async def plan_route():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/plan",
            json={
                "user_input": "周末想一个人安静走走"
            },
        )
        result = response.json()
        print(result)
```

### POI 查询

使用 `get_poi` 接口查询兴趣点：

```python
import httpx

async def search_pois():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/poi/search",
            params={
                "region": "珠海",
                "categories": ["文化", "美食"],
            },
        )
        pois = response.json()
        for poi in pois:
            print(f"{poi['name']} - {poi['category']}")
```

## 项目结构

```python
backend/
├── main.py          # 应用入口
├── config.py        # 配置管理
├── errors.py        # 异常体系
├── docs.py          # OpenAPI 文档
├── routers/         # API 路由
│   ├── v1/          # API v1
│   └── v2/          # API v2
├── services/        # 业务服务
├── models/          # 数据模型
├── middleware/      # 中间件
├── database/        # 数据库
├── tools/           # 开发工具
└── utils/           # 工具函数
```

## 最佳实践

1. **错误处理**: 使用 `CityFlowException` 及其子类，统一错误码体系
2. **类型注解**: 所有函数必须有完整的类型注解
3. **异步优先**: I/O 操作使用 `async/await`
4. **日志记录**: 使用 `logging` 模块，关键操作记录日志
5. **配置管理**: 敏感信息通过环境变量配置，不硬编码

## 故障排查

| 问题 | 可能原因 | 解决方案 |
| :--- | :--- | :--- |
| 服务启动失败 | 端口被占用 | 修改 .env 中的 PORT 配置 |
| 数据库连接失败 | 数据库未启动 | 检查数据库服务状态 |
| API 返回 500 | 内部服务异常 | 查看日志文件定位错误 |
| API 返回 429 | 请求频率超限 | 降低请求频率或联系管理员 |
