# CityFlow API文档

## 基础信息

- Base URL: `http://localhost:8000`
- Content-Type: `application/json`
- 认证: 无（开发环境）

## 错误响应

所有错误响应格式：
```json
{
  "error": "错误信息",
  "code": 400
}
```

## API端点

### 1. 健康检查

**GET /api/health**

检查服务状态

**响应：**
```json
{
  "status": "ok"
}
```

### 2. 规划路线

**POST /api/plan**

流式规划路线（SSE）

**请求：**
```json
{
  "user_input": "周末想一个人安静走走"
}
```

**SSE事件：**

| 事件 | 数据 | 说明 |
|------|------|------|
| phase | {"phase": "parsing", "message": "..."} | 阶段状态 |
| step | {"index": 1, "poi": {...}, "narrative": "..."} | 路线步骤 |
| done | {"route_id": "xxx", "full_route": {...}} | 完成 |
| error | {"error": "错误信息"} | 错误 |

**示例：**
```bash
curl -X POST http://localhost:8000/api/plan \
  -H "Content-Type: application/json" \
  -d '{"user_input": "周末想一个人安静走走"}'
```

### 3. 搜索POI

**POST /api/poi/search**

搜索兴趣点

**请求：**
```json
{
  "region": "珠海",
  "categories": ["文化", "美食"],
  "tags": ["免费"],
  "exclude_ids": ["poi_00001"]
}
```

**响应：**
```json
{
  "pois": [
    {
      "id": "poi_00002",
      "name": "珠海渔女",
      "category": "文化",
      "rating": 4.5,
      "avg_price": 0,
      "lat": 22.27,
      "lng": 113.58,
      "emotion_tags": {
        "excitement": 0.3,
        "tranquility": 0.8,
        "sociability": 0.4,
        "culture_depth": 0.9,
        "surprise": 0.6,
        "physical_demand": 0.2
      },
      "constraints": {
        "time_window": {"start": "09:00", "end": "17:00"},
        "budget": "free",
        "accessibility": true
      }
    }
  ]
}
```

### 4. 获取POI详情

**GET /api/poi/detail/{poi_id}**

获取单个POI详情

**响应：**
```json
{
  "id": "poi_00001",
  "name": "珠海渔女",
  "category": "文化",
  "rating": 4.5,
  "avg_price": 0,
  "lat": 22.27,
  "lng": 113.58,
  "business_hours": "09:00-17:00",
  "tags": ["免费", "拍照"],
  "emotion_tags": {
    "excitement": 0.3,
    "tranquility": 0.8,
    "sociability": 0.4,
    "culture_depth": 0.9,
    "surprise": 0.6,
    "physical_demand": 0.2
  },
  "constraints": {
    "time_window": {"start": "09:00", "end": "17:00"},
    "budget": "free",
    "accessibility": true
  },
  "ugc_comments": [
    {"user": "user1", "comment": "风景很美", "rating": 5}
  ]
}
```

### 5. 计算距离矩阵

**POST /api/poi/distance-matrix**

计算多个POI之间的距离

**请求：**
```json
{
  "poi_ids": ["poi_00001", "poi_00002", "poi_00003"]
}
```

**响应：**
```json
{
  "matrix": [
    [{"distance_m": 0, "time_min": 0}, {"distance_m": 1500, "time_min": 20}, {"distance_m": 3000, "time_min": 40}],
    [{"distance_m": 1500, "time_min": 20}, {"distance_m": 0, "time_min": 0}, {"distance_m": 2000, "time_min": 30}],
    [{"distance_m": 3000, "time_min": 40}, {"distance_m": 2000, "time_min": 30}, {"distance_m": 0, "time_min": 0}]
  ]
}
```

### 6. 获取路线详情

**GET /api/route/{route_id}**

获取已规划路线的完整信息

**响应：**
```json
{
  "route_id": "route_abc123",
  "route": [
    {
      "index": 1,
      "poi": {
        "id": "poi_00001",
        "name": "珠海渔女",
        "lat": 22.27,
        "lng": 113.58
      },
      "arrival_time": "10:00",
      "duration_min": 60,
      "narrative": "清晨的珠海渔女，海风轻拂，是开始旅程的完美起点。"
    }
  ],
  "narrative": {
    "title": "珠海文艺一日游",
    "summary": "从珠海渔女出发，沿着情侣路漫步，感受这座城市的浪漫与文艺。",
    "total_duration": "6小时",
    "total_distance": "12公里"
  },
  "user_intent": {
    "emotion": "tranquility",
    "group_size": 1,
    "budget": "medium",
    "pace": "relaxed"
  }
}
```

### 7. 对话调整

**POST /api/dialogue/{session_id}**

通过对话调整路线

**请求：**
```json
{
  "instruction": "太赶了，想轻松点"
}
```

**响应：**
```json
{
  "reply": "好的，我帮你调整为轻松型行程，减少了景点数量，增加了休息时间。",
  "route": {
    "route_id": "route_abc123_v2",
    "route": [...],
    "narrative": {...}
  },
  "changes_made": [
    {
      "type": "pace",
      "old_pace": "紧凑型",
      "new_pace": "闲逛型"
    },
    {
      "type": "remove",
      "poi_id": "poi_00003",
      "reason": "时间冲突"
    }
  ]
}
```

## 支持的对话指令

| 类型 | 示例 | 说明 |
|------|------|------|
| 替换 | "换掉第二个景点" | 替换指定POI |
| 节奏 | "太赶了"、"想轻松点" | 调整行程节奏 |
| 预算 | "太贵了"、"便宜一点" | 调整预算 |
| 时间 | "早一点"、"5点前结束" | 调整时间 |
| 重试 | "重新来"、"再想一个" | 重新规划 |

## SDK示例

### Python

```python
import httpx
import json

# 规划路线
response = httpx.post(
    "http://localhost:8000/api/plan",
    json={"user_input": "周末想出去走走"},
    timeout=30
)

# 解析SSE事件
for line in response.text.split("\n"):
    if line.startswith("data: "):
        data = json.loads(line[6:])
        print(data)
```

### JavaScript

```javascript
// 规划路线
const response = await fetch('/api/plan', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({user_input: '周末想出去走走'})
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const {done, value} = await reader.read();
  if (done) break;

  const text = decoder.decode(value);
  console.log(text);
}
```

### cURL

```bash
# 规划路线
curl -X POST http://localhost:8000/api/plan \
  -H "Content-Type: application/json" \
  -d '{"user_input": "周末想一个人安静走走"}'

# 搜索POI
curl -X POST http://localhost:8000/api/poi/search \
  -H "Content-Type: application/json" \
  -d '{"region": "珠海", "categories": ["文化"]}'

# 获取POI详情
curl http://localhost:8000/api/poi/detail/poi_00001

# 对话调整
curl -X POST http://localhost:8000/api/dialogue/session_123 \
  -H "Content-Type: application/json" \
  -d '{"instruction": "太赶了，想轻松点"}'
```

## 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

## 限流

- 开发环境：无限制
- 生产环境：100请求/分钟/IP

## 版本控制

当前API版本：v1

未来版本将通过URL前缀区分：`/api/v2/plan`
