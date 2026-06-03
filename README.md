# CityFlow - 智能城市出行规划系统

> 基于情绪感知的个性化城市路线规划，让每次出行都成为独特体验。

## ✨ 特性

- 🎯 **情绪感知** - 理解用户情绪需求，匹配最适合的出行体验
- 🗺️ **智能规划** - TSPTW算法优化路线，兼顾时间窗、疲劳度、情绪曲线
- 💬 **多轮对话** - 支持实时调整路线，"太赶了"、"换一个"都能理解
- 🎨 **个性文案** - 自动生成路线描述，每段行程都有温度
- 🏙️ **珠海本地** - 覆盖珠海2000+ POI，本地化体验

## 🚀 快速开始

### 环境要求

- Python >= 3.12
- LLM API Key（可选，有规则降级）

### 安装运行

```bash
# 克隆项目
git clone https://github.com/yourusername/cityflow.git
cd cityflow

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 LLM_API_KEY

# 一键启动
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000 打开Web界面

### Docker部署

```bash
docker-compose up -d
```

## 📁 项目结构

```
cityflow/
├── backend/
│   ├── main.py                 # FastAPI入口
│   ├── routers/               # API路由
│   │   ├── data.py           # 数据接口
│   │   ├── llm.py            # LLM接口
│   │   └── poi.py            # POI接口
│   ├── services/              # 业务逻辑
│   │   ├── intent_parser.py  # 意图解析
│   │   ├── filters.py        # 约束过滤
│   │   ├── solver.py         # 路线求解
│   │   ├── narrator.py       # 文案生成
│   │   ├── dialogue.py       # 对话引擎
│   │   └── user_profiles.py  # 用户画像
│   └── data/                  # 数据文件
│       └── city_poi_db.json  # POI数据库
├── frontend/
│   └── index.html             # Web界面
├── tests/                     # 测试用例
├── scripts/                   # 工具脚本
├── docs/                      # 项目文档
├── ops/                       # 运维配置
├── docker-compose.yml         # Docker配置
└── README.md
```

## 🎯 核心概念

### 情绪标签

每个POI都有6维情绪标签：

| 维度 | 说明 | 示例 |
|------|------|------|
| excitement | 兴奋度 | 过山车: 0.95 |
| tranquility | 宁静度 | 图书馆: 0.95 |
| sociability | 社交性 | 夜市: 0.8 |
| culture_depth | 文化深度 | 博物馆: 0.95 |
| surprise | 惊喜度 | 隐藏景点: 0.8 |
| physical_demand | 体力消耗 | 登山: 0.9 |

### 用户画像

20组预设画像，覆盖主流用户类型：

- P1: 社恐独居 - 低社交、高宁静
- P2: 浪漫情侣 - 氛围感、可拍照
- P3: 活力亲子 - 儿童友好、有教育意义
- P4: 朋友聚会 - 高社交、热闹
- P5: 退休休闲 - 无障碍、慢节奏
- ...

### 路线求解

5阶段混合求解算法：

1. **初始化** - 贪心选择，考虑时间窗、情绪、疲劳
2. **局部改进** - 2-opt交换，优化总评分
3. **呼吸空间** - 自动插入休息节点
4. **高潮收尾** - 确保结尾有情绪高潮
5. **输出组装** - 生成完整路线数据

## 📚 API文档

启动服务后访问：http://localhost:8000/docs

详细API文档请查看：[docs/API.md](docs/API.md)

## 🧪 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_intent.py

# 查看覆盖率
pytest --cov=backend --cov-report=html
```

## 🛠️ 技术栈

- **后端**: FastAPI + Pydantic
- **算法**: TSPTW + 情绪兼容性评分
- **LLM**: OpenAI API（可选降级规则）
- **前端**: 原生JS + CSS Flex布局
- **数据**: 珠海2000+ POI
- **部署**: Docker + Nginx

## 📖 开发指南

详细开发文档请查看：[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)

## 🎯 TODO

- [ ] 3D沙盘可视化
- [ ] 路线分享功能
- [ ] 历史路线记录
- [ ] 多城市支持
- [ ] 实时交通数据
- [ ] 移动端适配

## 🤝 贡献

欢迎提 Issue 和 PR。

---

**CityFlow** - 让城市出行更有温度 🌟
