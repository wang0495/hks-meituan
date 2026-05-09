# CityFlow 开发者指南

## 开发环境搭建

### 前置要求

- Python 3.10+
- Git
- OpenAI API Key（可选）

### 环境配置

```bash
# 克隆仓库
git clone https://github.com/yourusername/cityflow.git
cd cityflow

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入配置
```

### 环境变量说明

| 变量名 | 说明 | 必填 | 默认值 |
|--------|------|------|--------|
| OPENAI_API_KEY | OpenAI API密钥 | 否 | - |
| OPENAI_BASE_URL | OpenAI API地址 | 否 | https://api.openai.com/v1 |
| OPENAI_MODEL | 使用的模型 | 否 | gpt-4 |
| HOST | 服务监听地址 | 否 | 0.0.0.0 |
| PORT | 服务端口 | 否 | 8000 |
| LOG_LEVEL | 日志级别 | 否 | INFO |
| DATA_PATH | POI数据路径 | 否 | backend/data/city_poi_db.json |
| SECURITY_ENCRYPTION_KEY | 数据加密密钥 | 是 | - |
| SENTRY_DSN | Sentry错误追踪 | 否 | - |
| APP_VERSION | 应用版本 | 否 | 1.0.0 |

## 项目架构

### 目录结构

```
cityflow/
├── backend/
│   ├── main.py              # FastAPI应用入口
│   ├── routers/             # 路由层
│   │   ├── data.py         # 数据接口
│   │   ├── llm.py          # LLM调用接口
│   │   ├── poi.py          # POI相关接口
│   │   ├── health.py       # 健康检查
│   │   ├── metrics.py      # 监控指标
│   │   └── session.py      # 会话管理
│   ├── services/            # 业务逻辑层
│   │   ├── intent_parser.py # 意图解析服务
│   │   ├── filters.py      # 约束过滤服务
│   │   ├── solver.py       # 路线求解器
│   │   ├── narrator.py     # 文案生成器
│   │   ├── dialogue.py     # 对话引擎
│   │   └── user_profiles.py # 用户画像管理
│   └── data/               # 数据文件
│       └── city_poi_db.json # POI数据库
├── frontend/               # 前端资源
│   └── index.html          # 单页应用
├── tests/                  # 测试用例
│   ├── test_intent.py     # 意图解析测试
│   ├── test_filters.py    # 过滤器测试
│   ├── test_solver.py     # 求解器测试
│   └── conftest.py        # 测试配置
├── docs/                   # 项目文档
├── scripts/                # 工具脚本
├── monitoring/             # 监控配置
├── nginx/                  # Nginx配置
├── alembic/                # 数据库迁移
├── .github/                # GitHub配置
│   └── workflows/         # CI/CD流水线
├── requirements.txt        # Python依赖
├── Dockerfile             # Docker镜像
├── docker-compose.yml     # Docker编排
└── pytest.ini             # 测试配置
```

### 核心模块

#### 1. 意图解析器 (intent_parser.py)

解析用户自然语言输入，提取关键信息：

```python
class IntentParser:
    async def parse(self, user_input: str) -> UserIntent:
        """
        解析用户输入，返回结构化意图

        Args:
            user_input: 用户原始输入

        Returns:
            UserIntent: 包含情绪、人数、时间等信息
        """
        pass
```

#### 2. 约束过滤器 (filters.py)

根据用户约束筛选POI：

```python
class POIFilter:
    def filter(self, pois: List[POI], constraints: Constraints) -> List[POI]:
        """
        根据约束条件过滤POI列表

        Args:
            pois: 候选POI列表
            constraints: 约束条件（时间、预算、体力等）

        Returns:
            List[POI]: 过滤后的POI列表
        """
        pass
```

#### 3. 路线求解器 (solver.py)

TSPTW算法实现：

```python
class RouteSolver:
    def solve(self, pois: List[POI], constraints: Constraints) -> Route:
        """
        求解最优路线

        实现5阶段混合求解：
        1. 贪心初始化
        2. 2-opt局部优化
        3. 呼吸空间插入
        4. 高潮收尾调整
        5. 输出组装

        Args:
            pois: 候选POI列表
            constraints: 约束条件

        Returns:
            Route: 优化后的路线
        """
        pass
```

#### 4. 文案生成器 (narrator.py)

生成路线描述文案：

```python
class RouteNarrator:
    async def generate(self, route: Route, user_profile: UserProfile) -> Narrative:
        """
        生成路线文案

        Args:
            route: 路线数据
            user_profile: 用户画像

        Returns:
            Narrative: 包含标题、步骤描述、总结
        """
        pass
```

#### 5. 对话引擎 (dialogue.py)

处理多轮对话调整：

```python
class DialogueEngine:
    async def process(self, session_id: str, instruction: str) -> DialogueResponse:
        """
        处理对话指令

        支持的指令类型：
        - 替换：换掉指定景点
        - 节奏：调整行程快慢
        - 预算：调整消费水平
        - 时间：调整时间安排

        Args:
            session_id: 会话ID
            instruction: 用户指令

        Returns:
            DialogueResponse: 包含回复和调整后的路线
        """
        pass
```

## 开发流程

### 1. 分支管理

```
main          # 生产分支
├── develop   # 开发分支
│   ├── feature/xxx  # 功能分支
│   └── fix/xxx      # 修复分支
```

### 2. 代码规范

```bash
# 格式化
black backend/ tests/

# 检查
ruff check backend/ tests/

# 类型检查
mypy backend/

# 运行测试
pytest tests/ -v
```

### 3. 提交规范

```
feat: 新功能
fix: 修复bug
docs: 文档更新
style: 代码格式
refactor: 重构
test: 测试相关
chore: 构建/工具
```

示例：
```bash
git commit -m "feat: 添加疲劳度权重计算"
git commit -m "fix: 修复时间窗溢出问题"
```

## 测试

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_solver.py

# 运行特定测试用例
pytest tests/test_solver.py::test_2opt_optimization

# 查看覆盖率
pytest --cov=backend --cov-report=html

# 并行测试
pytest -n auto
```

### 编写测试

```python
import pytest
from backend.services.solver import RouteSolver

class TestRouteSolver:
    @pytest.fixture
    def solver(self):
        return RouteSolver()

    @pytest.fixture
    def sample_pois(self):
        return [
            POI(id="1", name="景点A", lat=22.27, lng=113.58),
            POI(id="2", name="景点B", lat=22.28, lng=113.59),
        ]

    def test_greedy_initialization(self, solver, sample_pois):
        """测试贪心初始化"""
        route = solver._greedy_init(sample_pois)
        assert len(route.stops) == 2

    def test_2opt_improvement(self, solver, sample_pois):
        """测试2-opt优化"""
        route = solver._2opt(sample_pois)
        assert route.score > 0
```

## 调试

### 日志配置

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
```

### 调试模式

```bash
# 启用调试模式
export DEBUG=1
uvicorn backend.main:app --reload --log-level debug
```

### API文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 部署

### Docker部署

```bash
# 构建镜像
docker build -t cityflow .

# 运行容器
docker run -p 8000:8000 cityflow

# 使用docker-compose
docker-compose up -d
```

### 生产环境

```bash
# 使用gunicorn
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker

# 配置nginx
server {
    listen 80;
    server_name cityflow.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

## 监控

### Prometheus指标

访问 http://localhost:8000/metrics 获取Prometheus指标

### Grafana仪表盘

导入 `grafana_dashboard.json` 获取预配置的监控仪表盘

### 健康检查

```bash
curl http://localhost:8000/api/health
```

## 常见问题

### Q: 没有OpenAI API Key怎么办？

A: 系统支持规则降级，会使用预设模板生成文案，核心功能不受影响。

### Q: 如何添加新的POI数据？

A: 编辑 `backend/data/city_poi_db.json`，按照现有格式添加POI条目。

### Q: 如何自定义用户画像？

A: 修改 `backend/services/user_profiles.py` 中的画像配置。

### Q: 算法性能如何优化？

A: 可以调整 `solver.py` 中的参数：
- `max_iterations`: 最大迭代次数
- `improvement_threshold`: 改进阈值
- `time_limit`: 求解时间限制

### Q: 如何扩展到其他城市？

A: 1. 准备新城市的POI数据
   2. 更新 `user_profiles.py` 中的画像
   3. 调整 `solver.py` 中的距离计算逻辑

## 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/xxx`)
3. 提交更改 (`git commit -m 'feat: 添加xxx'`)
4. 推送到分支 (`git push origin feature/xxx`)
5. 创建 Pull Request

## 联系方式

- Issues: https://github.com/yourusername/cityflow/issues
- Email: your@email.com
