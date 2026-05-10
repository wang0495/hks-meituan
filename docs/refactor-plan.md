# CityFlow V2 柔性人机协作改造计划

> 版本: 2.2 | 上下文感知偏好学习 + 可学习权重映射模型

---

## 零、核心概念

### 问题（现状）

当前求解器用固定权重 `_ALPHA=1.0, _BETA=0.5, _GAMMA=0.2, _DELTA=0.8`，这些值在不同画像和情境下差异很大。让 LLM 直接输出权重数值 → 容易幻觉，和写死规则没区别。

### 方案：三层分离

```
LLM (语义层)     →  可学习映射模型 (数值层)     →  求解器 (执行层)
只提取方向         把方向转成权重调整量             用最终权重算路线
不出数值           支持在线学习                    不关心权重来源
                   每人每模型                      只接受权重
```

### 反馈闭环

```
用户意图 → LLM解析 → 需求向量 → 映射模型 → 权重 → 求解器 → 路线
                           ↑                                  │
                           └───── 用户反馈(采纳/修改/跳过) ────┘
                                      │
                                      ▼
                              调整映射模型参数
                              (下一轮更准)
```

---

## 一、需求向量（LLM 的输出接口）

### 定义

LLM 只输出语义方向，不输出具体数值：

```python
# LLM 从用户话语中提取
DEMAND_VECTOR = {
    "efficiency_seeking": 0.0 ~ 1.0,   # 是否赶时间/追求效率
    "excitement_seeking": 0.0 ~ 1.0,   # 是否想要兴奋刺激
    "tranquility_seeking": 0.0 ~ 1.0,  # 是否想要宁静放松
    "budget_sensitivity": 0.0 ~ 1.0,   # 预算敏感度
    "novelty_seeking": 0.0 ~ 1.0,      # 是否想尝新
    "social_desire": 0.0 ~ 1.0,        # 社交需求强度
    "physical_energy": 0.0 ~ 1.0,      # 体力意愿
}
```

### 提取方式

```python
# preference_dialogue.py
async def extract_demand_vector(
    user_input: str,
    dialogue_history: list[dict],
    llm_client
) -> dict:
    """
    LLM 从对话中提取需求向量。
    
    输入: "周末想出去走走，不想太累，安静点"
    输出: {
        "efficiency_seeking": 0.2,    # 不赶时间
        "excitement_seeking": 0.1,    # 不要兴奋
        "tranquility_seeking": 0.9,   # 要安静
        "budget_sensitivity": 0.5,    # 中性
        "novelty_seeking": 0.3,       # 不需要新鲜感
        "social_desire": 0.1,         # 不社交
        "physical_energy": 0.2,       # 低体力
        "_confidence": {              # 每个维度的置信度
            "tranquility_seeking": 0.95,
            "budget_sensitivity": 0.3  # 低置信度 → 追问
        }
    }

    原则：
    - 只提取方向和置信度
    - 低置信度的维度 → 追问轮询问
    - 不输出任何数值权重
    """
```

---

## 二、可学习映射模型（核心新增）

### services/weight_mapper.py

```python
"""
权重映射模型：将语义"需求向量"转化为求解器"权重调整量"。

设计原则：
- 每个用户持有自己的模型参数（独立个性化）
- 新用户使用全局默认参数（基于画像模板初始化）
- 每次用户反馈后微调参数（在线学习）
- 不使用外部 ML 框架，纯 Python 数值更新
"""

# ---------------------------------------------------------------------------
# 全局基线的权重调整映射表
# 每条: [需求向量维度 → 对某个权重的贡献系数]
# 正的系数表示：该需求越强，对应权重越大
# ---------------------------------------------------------------------------

_BASE_MAPPING: dict[str, dict[str, float]] = {
    # 位移成本权重 alpha (default=1.0)
    # 节约时间的需求越强 → alpha 越大
    "alpha": {
        "efficiency_seeking": 0.6,      # 效率越高 → 越在意时间成本
        "excitement_seeking": -0.1,      # 追求兴奋 → 愿意路上花时间
        "tranquility_seeking": 0.0,
        "budget_sensitivity": 0.0,
        "novelty_seeking": 0.1,
        "social_desire": -0.1,
        "physical_energy": 0.0,
        "_bias": 1.0,                    # 基础值
    },
    # 情绪收益权重 beta (default=0.5)
    "beta": {
        "efficiency_seeking": -0.3,      # 效率越高 → 越不在意情绪体验
        "excitement_seeking": 0.5,       # 追求兴奋 → 情绪收益权重高
        "tranquility_seeking": 0.4,      # 追求宁静 → 同样需要情绪匹配
        "budget_sensitivity": 0.0,
        "novelty_seeking": 0.3,
        "social_desire": 0.2,
        "physical_energy": 0.1,
        "_bias": 0.5,
    },
    # 疲劳惩罚权重 gamma (default=0.2)
    "gamma": {
        "efficiency_seeking": -0.1,
        "excitement_seeking": 0.0,
        "tranquility_seeking": 0.3,      # 想放松 → 疲劳惩罚高
        "budget_sensitivity": 0.0,
        "novelty_seeking": 0.0,
        "social_desire": 0.0,
        "physical_energy": -0.3,         # 体力好 → 不介意累
        "_bias": 0.2,
    },
    # 同类惩罚权重 delta (default=0.8)
    "delta": {
        "efficiency_seeking": 0.2,
        "excitement_seeking": 0.1,
        "tranquility_seeking": 0.3,      # 想放松 → 多样性不重要
        "budget_sensitivity": 0.0,
        "novelty_seeking": 0.4,          # 想尝新 → 多样性重要
        "social_desire": 0.1,
        "physical_energy": 0.0,
        "_bias": 0.8,
    },
    # 预算约束严格度 budget_strictness (default=1.0)
    "budget_strictness": {
        "efficiency_seeking": 0.0,
        "excitement_seeking": 0.0,
        "tranquility_seeking": 0.0,
        "budget_sensitivity": 0.6,       # 预算敏感 → 严格
        "novelty_seeking": -0.1,
        "social_desire": 0.0,
        "physical_energy": 0.0,
        "_bias": 0.5,
    },
}


class WeightMapper:
    """
    需求向量 → 权重调整量的映射器。
    
    每个用户持有一个独立的偏移量矩阵（_user_deltas），
    从全局基线开始，随用户反馈渐进调整。
    """
    
    def __init__(self, user_id: str, base_mapping: dict | None = None):
        self.user_id = user_id
        self._base = base_mapping or _BASE_MAPPING
        # 用户个人偏移量（与 _BASE_MAPPING 同结构，初始全0）
        self._deltas: dict[str, dict[str, float]] = {}
        self._init_deltas()
    
    def _init_deltas(self) -> None:
        """初始化用户偏移量（全0）。"""
        for weight_name, dims in self._base.items():
            self._deltas[weight_name] = {
                k: 0.0 for k in dims if k != "_bias"
            }
    
    def compute_weights(self, demand_vector: dict) -> dict[str, float]:
        """
        将需求向量映射为求解器权重。
        
        公式: weight = bias + Σ(dim_value × (base_coef + user_delta))
        
        输入 demand_vector:
            {"efficiency_seeking": 0.8, "excitement_seeking": 0.2, ...}
        
        输出:
            {
                "alpha": 1.32,
                "beta": 0.42,
                "gamma": 0.18,
                "delta": 1.04,
                "budget_strictness": 0.56,
            }
        """
        result = {}
        for weight_name, dim_map in self._base.items():
            bias = dim_map.get("_bias", 0.0)
            total = bias
            for dim, value in demand_vector.items():
                if dim.startswith("_"):
                    continue
                if dim in dim_map:
                    base_coef = dim_map[dim]
                    user_delta = self._deltas.get(weight_name, {}).get(dim, 0.0)
                    total += value * (base_coef + user_delta)
            # 确保权重在合理范围
            result[weight_name] = max(0.01, min(3.0, total))
        return result
    
    def update_from_feedback(
        self,
        demand_vector: dict,
        applied_weights: dict,
        feedback: str,  # "accepted" / "modified" / "rejected"
        modification_hint: str | None = None,
    ) -> dict[str, float]:
        """
        根据用户反馈更新映射参数（在线学习）。
        
        更新规则：
        - accepted: 正强化（小幅增大已使用维度的系数）
        - rejected: 负强化（减小高贡献维度的系数）
        - modified: 分析修改方向，调整相关维度的系数
        
        返回: 更新后的权重
        """
        updates: dict[str, dict[str, float]] = {}
        
        if feedback == "accepted":
            # 正强化：所有非零需求维度的系数 +0.02
            for weight_name in self._base:
                for dim, value in demand_vector.items():
                    if dim.startswith("_") or dim not in self._deltas.get(weight_name, {}):
                        continue
                    if value > 0.3:
                        self._deltas[weight_name][dim] += 0.02
        
        elif feedback == "rejected":
            # 负强化：降低贡献最大的维度的系数
            # 找出对当前权重贡献最大的需求维度
            for weight_name in self._base:
                contributions = []
                for dim, value in demand_vector.items():
                    if dim.startswith("_") or dim not in self._deltas.get(weight_name, {}):
                        continue
                    base_coef = self._base[weight_name].get(dim, 0)
                    delta = self._deltas[weight_name].get(dim, 0)
                    contrib = value * (base_coef + delta)
                    contributions.append((dim, contrib))
                
                # 降幅最大的维度的系数
                if contributions:
                    contributions.sort(key=lambda x: -abs(x[1]))
                    top_dim = contributions[0][0]
                    self._deltas[weight_name][top_dim] -= 0.05
        
        elif feedback == "modified" and modification_hint:
            # 分析修改意图，调整对应维度
            # "太累了" → physical_energy 系数调整
            # "太贵了" → budget_sensitivity 系数调整
            adjustments = self._parse_modification_hint(modification_hint)
            for weight_name, dim_adjustments in adjustments.items():
                for dim, delta in dim_adjustments.items():
                    if dim in self._deltas.get(weight_name, {}):
                        self._deltas[weight_name][dim] += delta
        
        # 重新计算并返回权重
        return self.compute_weights(demand_vector)
    
    def _parse_modification_hint(self, hint: str) -> dict:
        """解析修改提示，返回权重调整建议。"""
        mapping = {
            "赶": {"alpha": {"efficiency_seeking": 0.1}},
            "累": {"gamma": {"physical_energy": 0.1}},
            "贵": {"budget_strictness": {"budget_sensitivity": 0.1}},
            "无聊": {"delta": {"novelty_seeking": 0.1}},
            "兴奋": {"beta": {"excitement_seeking": 0.1}},
            "安静": {"beta": {"tranquility_seeking": 0.1}},
        }
        result: dict = {}
        for kw, adj in mapping.items():
            if kw in hint:
                for w, d in adj.items():
                    result.setdefault(w, {}).update(d)
        return result
    
    def to_dict(self) -> dict:
        """序列化（用于 LTM 存储）。"""
        return {
            "user_id": self.user_id,
            "deltas": self._deltas,
        }
    
    @classmethod
    def from_dict(cls, user_id: str, data: dict) -> "WeightMapper":
        """从 LTM 恢复。"""
        mapper = cls(user_id)
        if data and "deltas" in data:
            for w in mapper._deltas:
                if w in data["deltas"]:
                    for d in mapper._deltas[w]:
                        if d in data["deltas"][w]:
                            mapper._deltas[w][d] = data["deltas"][w][d]
        return mapper
```

---

## 三、完整架构图

```
┌───────────────────────────────────────────────┐
│              用户交互层 (TUI)                   │
│  输入/选择/快捷按钮/确认/修改/拒绝              │
└──────────┬────────────────────────────────────┘
           │ 自然语言
           ▼
┌───────────────────────────────────────────────┐
│         LLM 意图与偏好解析层                    │
│  • parse_intent() → 结构化意图                 │
│  • extract_demand_vector() → 需求向量(语义)    │
│  • detect_emotion_need() → 情感需求             │
│  输出: {需求向量, 结构化意图, 情感需求}          │
│  原则: 不出数值权重，只出语义方向                │
└──────────┬────────────────────────────────────┘
           │ 需求向量 (0~1 语义值)
           ▼
┌───────────────────────────────────────────────┐
│         可学习映射模型 (WeightMapper)           │
│  输入: 需求向量 + 画像特征 + 上下文             │
│  输出: solver 权重 {α, β, γ, δ, strictness}   │
│  存储: 每人一份 delta 参数在 LTM 中             │
│  更新: 用户反馈 → 在线微调 delta 参数          │
│  冷启动: 全局基线映射表初始化                    │
└──────────┬────────────────────────────────────┘
           │ 权重 (具体数值)
           ▼
┌───────────────────────────────────────────────┐
│          TSPTW 多约束求解器 (solver.py)         │
│  接收: candidates + intent + weights           │
│  执行: 5阶段混合算法                            │
│  输出: 路线 + 情绪曲线 + 预算                   │
└──────────┬────────────────────────────────────┘
           │ 路线方案
           ▼
┌───────────────────────────────────────────────┐
│           用户反馈收集                          │
│  采纳 ✅ → 正强化系数                           │
│  修改 🔧 → 分析修改方向调整                     │
│  拒绝 ❌ → 负强化系数                           │
│  所有反馈 → WeightMapper.update_from_feedback() │
│  更新后参数 → LTM 持久化                       │
└───────────────────────────────────────────────┘
```

---

## 四、数据流全景（完整闭环）

```
┌─────────────────────────────────────────────────────────────────────┐
│                     单次交互完整数据流                                │
│                                                                     │
│  用户: "周末想出去走走，不要太累"                                    │
│     │                                                                │
│     ▼                                                               │
│  ┌────────────────────┐                                             │
│  │ LLM 提取需求向量    │                                             │
│  │ → efficiency: 0.3   │  ← 不赶时间                               │
│  │ → tranquility: 0.8  │  ← 想要宁静                               │
│  │ → physical: 0.2     │  ← 低体力                                 │
│  │ → novelty: 0.4      │                                             │
│  └─────────┬──────────┘                                             │
│            │ 需求向量                                               │
│            ▼                                                       │
│  ┌────────────────────┐                                             │
│  │ WeightMapper       │  ╔══════════════════╗                      │
│  │ → alpha = 0.95     │  ║ LTM 存储个人     ║                      │
│  │ → beta  = 0.62     │  ║ delta 参数        ║                      │
│  │ → gamma = 0.35     │  ║ + trip_history    ║                      │
│  │ → delta = 0.86     │  ╚══════════════════╝                      │
│  └─────────┬──────────┘                                             │
│            │ 权重                                                   │
│            ▼                                                       │
│  ┌────────────────────┐                                             │
│  │ Solver → 路线      │                                             │
│  └─────────┬──────────┘                                             │
│            │ 路线                                                   │
│            ▼                                                       │
│  ┌────────────────────┐                                             │
│  │ 用户: "还行" ✅    │                                             │
│  │ → 正强化所有系数   │                                             │
│  │ → LTM: record_trip │                                             │
│  └─────────┬──────────┘                                             │
│            │                                                       │
│            ▼                                                       │
│  下次: delta 参数已更新 → 同样需求向量 → 不同权重 → 更好匹配      │
└─────────────────────────────────────────────────────────────────────┘
```

### 多轮演进

```
第1次: 用户说"安静点"
  → LLM: tranquility=0.8, physical=0.2
  → Mapper(默认): gamma=0.35, beta=0.62
  → 路线: 还行 ✅ → gamma 系数 +0.02

第3次: 又说"安静点"
  → LLM: 同方向
  → Mapper(已调3次): gamma=0.41, beta=0.68
  → 路线: 更匹配

第10次: "安静点"
  → Mapper(充分学习): gamma=0.53, beta=0.74
  → 路线: 精准匹配该用户的"安静"定义
```

---

## 五、完整的文件改造清单

| # | 文件 | 改动量 | 说明 |
|---|------|--------|------|
| 1 | `services/holiday_utils.py` | 新~80行 | 中国节假日检测 |
| 2 | `services/memory/long_term.py` | ~200行改造 | trip_history + record_trip + contextual_patterns + predict |
| 3 | **`services/weight_mapper.py`** | **新~250行** | **可学习映射模型（核心）** |
| 4 | `services/preference_manager.py` | 新~300行 | 整合层：身份+LTM+Mapper+推荐 |
| 5 | `services/preference_dialogue.py` | 新~150行 | LLM追问 + 需求向量提取 |
| 6 | `services/intent_parser.py` | ~80行改造 | 情感识别 + 偏好合并 |
| 7 | `services/solver.py` | ~80行改造 | dynamic_weights + progress_callback |
| 8 | `services/dialogue.py` | ~120行改造 | 新指令 + 增量替换 + 反馈收集 |
| 9 | `backend/main.py` | ~120行改造 | 集成全套 + 上下文传递 |
| 10 | `tui/preference_chat.py` | 新~400行 | TUI对话组件 |
| 11 | `tui_app.py` | ~250行改造 | 集成全套TUI |

---

## 六、冷启动策略

| 场景 | 做法 | 映射模型状态 |
|------|------|-------------|
| 新用户第1次 | 使用全局基线映射表 | delta = 全0 |
| 新用户选快捷按钮 | 使用对应画像的初始化参数 | 用画像模板初始化delta |
| 老用户 >5次 | 正常使用学习后的参数 | delta 已收敛 |
| 用户反馈 rejection | 负强化，调低相关维度的系数 | delta 反向调整 |

---

## 七、向后兼容

- `solver.py` 中原有的 `_ALPHA/_BETA/_GAMMA/_DELTA` 常量保留作为默认值
- `dynamic_weights=None` 时行为与 V1 完全一致
- `WeightMapper.compute_weights()` 初始输出接近 V1 默认值
- `LongTermMemory.get_profile()` 返回字段不变
- 现有 20 组画像 P1-P20 保留作为冷启动种子

---

## 八、与"覆盖不覆盖"问题的统一

之前讨论过"不覆盖历史记录"：

```
trip_history: 只 append，不覆盖 → 保留所有选择轨迹
     ↓
contextual_patterns: 查询时实时统计 → 反映真实趋势
     ↓
WeightMapper.delta: 渐进微调（每步±0.02~0.05）→ 不突变
```

三者统一成一个原则：**记录保留原始数据，学习通过渐进微调实现。**
