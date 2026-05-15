# Intent Parser Prompt优化: 长→短

## 背景

intent_parser的system prompt约2000 tokens，包含大量示例和解释。测试发现短prompt不影响质量，还能加速。

## 长prompt (~2000 tokens)

```
你是 CityFlow 城市出行路线规划系统的意图解析器。
用户会用自然语言描述出行需求，你需要解析为严格的 JSON 格式。

输出格式（只输出 JSON，不要任何其他文字）：
{
  "city": "珠海/广州/湛江",
  "time": {"period": "上午/下午/全天", "start": "HH:MM", "end": "HH:MM"},
  "budget": {"per_person": 金额整数, "type": "硬约束/弹性"},
  "group": {"size": 人数整数, "type": "独居/情侣/亲子/朋友/退休"},
  "preferences": {"culture": 0到1的小数, "food": 0到1的小数, "nature": 0到1的小数, "social": 0到1的小数},
  "pace": "特种兵型/平衡型/闲逛型",
  "hard_constraints": ["约束1", "约束2"],
  "scene_requirements": ["场景元素1", "场景元素2"],
  "preferred_categories": ["类别1", "类别2", "类别3"],
  "demand_vector": { ... 7个维度 },
  "location": "用户在哪个区域/地标附近"
}

规则：
- city: 根据用户提到的城市判断，无明确城市则默认"珠海"
- budget: 无明确预算则 per_person=500, type="弹性"
- group.type: 根据同行人判断，默认"独居"
- time: ...各种时间推断规则...
- preferences: ...4个维度的关键词映射...
- pace: ...3种节奏的判断标准...
- hard_constraints: ...8种约束类型及映射规则...
- scene_requirements: 【必须填写】...10个完整示例...
- preferred_categories: ...15个可选类别 + 8个示例...
- demand_vector: ...7个维度的含义解释...
```

**问题：**
- 10个scene_requirements示例 → 模型已经能推断
- 8个preferred_categories示例 → 冗余
- 每个字段的详细解释 → 模型看JSON schema就懂
- hard_constraints的映射规则 → 可以直接列出可选值

## 短prompt (~300 tokens)

```
你是CityFlow意图解析器。输出JSON:
{"city":"珠海","time":{"period":"上午/下午/全天","start":"HH:MM","end":"HH:MM"},
"budget":{"per_person":金额,"type":"硬约束/弹性"},
"group":{"size":人数,"type":"独居/情侣/亲子/朋友/退休"},
"preferences":{"culture":0~1,"food":0~1,"nature":0~1,"social":0~1},
"pace":"特种兵型/平衡型/闲逛型","hard_constraints":[],
"scene_requirements":["关键词1","关键词2"],
"preferred_categories":["类别1","类别2","类别3"],
"demand_vector":{"efficiency_seeking":0~1,"excitement_seeking":0~1,
"tranquility_seeking":0~1,"budget_sensitivity":0~1,
"novelty_seeking":0~1,"social_desire":0~1,"physical_energy":0~1},
"location":"区域或null"}

规则：
- scene_requirements: 必须提取所有关键词，至少3个
- preferred_categories: 3-6个，从[餐饮,景点,购物,文化,运动,娱乐,
  温泉SPA,海景咖啡馆,夜市,夜市小吃,书店,咖啡馆,自然风光,文艺,休闲]选
- hard_constraints: queue_intolerant/accessible/pet_friendly/indoor_only/
  outdoor_preferred/late_night/needs_entertainment
- 只输出JSON。
```

**优化手段：**
1. **示例全删** — 10个scene_requirements示例 + 8个categories示例全部删除
2. **解释压缩** — "根据用户提到的城市判断，无明确城市则默认珠海" → 删掉，模型从schema推断
3. **格式一行化** — JSON schema从多行格式化为紧凑一行，省token
4. **枚举内联** — preferred_categories和hard_constraints的可选值直接列在规则里

## 对比测试结果

| 配置 | qwen-turbo | deepseek |
|------|-----------|----------|
| 长prompt | 2.6s, 5/5 | 2.1s, 5/5 |
| 短prompt | **1.7s**, 5/5 | 2.2s, 5/5 |

- 质量完全一样：5/5满分，所有required字段齐全
- qwen-turbo短prompt加速35%（2.6s→1.7s），甚至比DeepSeek还快
- scene_requirements提取更丰富（qwen-turbo短prompt提取6-8个关键词 vs 长prompt的3-5个）

## 为什么短prompt不影响质量

1. **JSON schema本身就是最好的指令** — 现代LLM看到schema就能推断字段含义
2. **示例是"训练数据"不是"规则"** — 模型已经见过大量类似任务，不需要few-shot
3. **规则越少模型越自由** — 长prompt里的硬性规则反而限制了模型的提取能力
4. **token越少prefill越快** — 2000tok→300tok，推理时间直接降
