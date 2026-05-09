# Implementation Plan: F005-perception

---
## Overview

- **Feature ID**: F005
- **Target Repo**: hks-meituan
- **Created**: 2026-05-09
- **Status**: Draft

---
## Tech Stack

| Category | Choice | Reason |
|----------|--------|--------|
| 数据类 | dataclass | 感知上下文结构清晰 |
| 随机 | random + datetime | 纯 Python，无外部依赖 |
| 异常 | Enum | 异常类型枚举 |

---
## Architecture

```
感知系统（PerceptionService）
┌─────────────────────────────────────────┐
│  get_context(user_id) → PerceptionContext │
│  ├─ weather: Mock 随机/预设场景            │
│  ├─ hour_of_day: datetime.now()           │
│  ├─ step_count: 基于 POI 停留模拟          │
│  ├─ fatigue_level: 步数映射               │
│  └─ avg_stay_duration: 停留时长模拟       │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  detect_anomaly(ctx) → list[Anomaly]     │
│  ├─ 天气突变 / 体力预警 / 情绪低谷 / 时间压力 │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  adjust_suggestions(ctx, plan) → AdjResult │
│  ├─ 室内替代 / 休息节点 / 风格切换 / 跳过   │
└─────────────────────────────────────────┘
```

**与现有系统集成**:
- `solver.py` → 添加 `perception_ctx` 参数，影响路线评分中的 `fatigue_penalty` 和情绪匹配权重
- `emotion.py` → 情绪低谷检测依赖 `emotion.get_dominant_emotion()` 的输出
- `sse.py` → 推送 `anomaly` 事件到前端（注意: 与 F003 冲突风险，需约定 sse.py 修改顺序）

**情绪低谷检测的数据流**:
```
PerceptionContext → solver.solve_route → route["emotion_curve"]
  → perception.detect_anomaly → 检查最近 3 站 emotion < 0.4
  → 触发 style_switch → 修改 user_intent 偏好转高情绪 POI
  → 触发重新求解或调整

---
## File Structure

```
backend/services/
├── perception.py           # 新增: 感知服务主模块
│   ├── PerceptionContext   # 数据类: 聚合所有感知信号
│   ├── Anomaly             # 数据类: 异常事件
│   ├── AdjustmentResult    # 数据类: 调整建议
│   ├── ScenePresets        # 演示场景预设
│   └── PerceptionService  # 主类: 采集+检测+调整
tests/
├── test_perception.py      # 新增: 感知系统测试
```

---
## Test Strategy

- **Unit Tests**: `test_perception.py` — Mock 数据生成、异常检测逻辑、场景预设验证
- **Integration**: 与 `solver.py` 集成后，验证动态调整能改变路线评分
- **Manual**: 4 种预设场景逐一验证

---
## Mock 数据规格

```python
@dataclass
class PerceptionContext:
    weather: str           # sunny/rainy/cloudy/hot/cold
    temperature: float      # 15.0 ~ 35.0
    hour_of_day: int       # 6 ~ 22
    day_of_week: int       # 0=周一
    season: str            # spring/summer/autumn/winter
    step_count: int        # 0 ~ 30000
    fatigue_level: float   # 0.0 ~ 1.0
    avg_stay_duration: int # 30 ~ 180 (min)
    photo_frequency: float # 0 ~ 5 (次/小时)
```

---
## Related Documents

- Spec: [spec.md](./spec.md)
- Decisions: [decisions.md](./decisions.md)