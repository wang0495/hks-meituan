# MoE Pipeline 优化日志

> 基线: commit `477531a` — qwen3.5-flash(experts) + DeepSeek(intent/router/review), 4/5通过, overall=6.8

## 优化尝试总览

| # | 方向 | 改动 | 结果 | 结论 |
|---|------|------|------|------|
| 1 | LLM统一 | 4处独立client→base.py prefix参数化 | 4/5, 6.8 持平 | 纯重构，不影响质量 |
| 2 | crash fix | _extract_json类型校验+过滤非dict列表项 | 修复Scene4间歇性崩溃 | 真实bug，必须保留 |
| 3 | expert规则化 | hotel/traffic/weather/destination/budget_hacker去掉LLM | 3/5, 6.4 退步 | **失败** — baseline用qwen不是DeepSeek |
| 4 | narrator模板化 | 关闭LLM文案生成 | 不确定 | 不推荐，文案质量下降 |
| 5 | intent短prompt | 从2971→842字符 | A/B测试质量退化 | **失败** — 短prompt丢信息 |
| 6 | rule_guard正则化 | 用规则替代LLM补核心景点 | 不确定 | **失败** — LLM判断更准 |
| 7 | diversity后处理 | 按category去重/替换同质POI | 4/5→3/5 | **失败** — 破坏地理顺序 |
| 8 | 连锁黑名单 | 肯德基/麦当劳等排除 | 边际 | **无效** — 黑名单里的店本来就不会被选 |
| 9 | 美食型2家上限 | 修复第7条(最多4家)与第8条(不超过2家)矛盾 | 美食diversity+1 | **有效** — 修复逻辑矛盾 |
| 10 | food_list补字段 | 加category/rating/tags让LLM判断类型 | 配合#9有效 | **有效** — 给LLM更多信息 |
| 11 | cap/ensure重排序 | _cap_route_stops移到_ensure_*之前 | **5/5, 7.0** | **有效** — 修复追加站点被截断bug |
| 12 | diversity prompt | 观光/特种兵/休闲加"至少N种类型" | 某场景+1但另一场景-2 | **失败** — LLM方差吃掉改进 |
| 13 | narrator并行化 | asyncio.gather + synthesizer禁用LLM润色 | 提速，质量持平 | **有效** — 12次LLM→6次 |
| 14 | cap内餐饮保留 | 截断时优先保留lunch/dinner站点 | 0/5, 6.0 暴跌 | **失败** — 破坏地理顺序 |

## 详细分析

### 为什么"expert规则化"失败 (attempt #3)

**错误的假设**: 认为baseline用DeepSeek做expert，用规则替代可以省成本。

**实际**: commit `477531a` 和 `012f853` 的A/B测试明确记录：
- baseline已经用qwen3.5-flash做experts（通过EXPERT_LLM_*环境变量）
- qwen3.5-flash的输入成本仅¥0.2/M token（DeepSeek是¥1/M）
- 规则化不是"省一个贵的LLM调用"，而是"用固定规则替代一个便宜的智能决策"

**教训**: 优化前必须确认baseline的模型配置，不要凭代码默认值推断运行时配置。

### 为什么"diversity后处理"和"prompt微调"失败 (attempt #7, #12)

**根因**: diversity瓶颈不在pipeline，在**数据**。

POI数据库（2005个POI）的大类分布：
- 景点/自然: 335 (30%) — 充足
- 文化: 231 (21%) — 充足
- 运动: 148 (13%) — 充足
- **娱乐: 39 (3.5%)** — 多为夜店/KTV/密室逃脱，日间旅游用不了
- **自然风光: 1 (0.05%)** — 几乎为零
- 科技: 11 — 忽略不计

evaluator期望路线包含4种以上大类（景点+餐饮+文化+自然+娱乐），
但数据中娱乐和自然风光几乎不存在，路线永远只能在景点+文化+运动+餐饮里打转。

**结论**: 要提升diversity必须**补数据**（加日间娱乐POI、自然风光POI），
而不是改pipeline代码。pipeline已经做到了数据允许的上限。

### 为什么"cap/ensure重排序"有效 (attempt #11)

**原始bug**: 执行顺序是 ensure_food → ensure_poi → cap_route_stops
- LLM排了6个景点（观光型上限6）
- ensure_food追加1个餐厅到第7位
- cap截掉第7位 → 路线无餐饮 → diversity扣分

**修复**: 调换为 cap → ensure_food → ensure_poi
- LLM排了6个景点，cap截到6个
- ensure追加餐厅到第7位（在cap之后，不受截断）
- 路线有6个景点+1个餐饮 → diversity+1

**为什么简单有效**: 不是加新功能，只是修复执行顺序的bug。

### LLM方差问题

同一份代码、同一个prompt跑多次，同一场景的评分波动：
- 场景3（美食型）: overall 6 或 7（随机）
- 场景4（特种兵）: overall 6 或 7（随机）
- 场景5（休闲型）: overall 6 或 7（随机）

这意味着：
- 4/5通过和5/5通过之间只差LLM的一次随机选择
- 任何prompt微调的效果都会被这个方差吃掉
- 无法通过A/B测试验证小改动（需要20+次run才有统计意义）

## 当前版本 (commit bf140ee)

### 各节点LLM配置

| 节点 | 模型 | prefix | 说明 |
|------|------|--------|------|
| intent_parser | DeepSeek | LLM_* | 意图解析，质量要求高 |
| expert_router | DeepSeek | LLM_* | 场景分类+权重分配 |
| poi_expert | qwen3.5-flash | EXPERT_LLM_* | 景点选择 |
| food_expert | qwen3.5-flash | EXPERT_LLM_* | 餐饮选择 |
| hotel_expert | 规则 | — | 过夜检测+评分排序 |
| traffic_expert | 规则 | — | 地理分布分析 |
| weather_expert | 规则 | — | 天气查询（无LLM） |
| destination_expert | 规则 | — | 大景区匹配 |
| budget_hacker | 规则 | — | 免费景点占比优化 |
| local_expert | qwen3.5-flash | EXPERT_LLM_* | 小众秘境推荐 |
| rule_guard._ensure_key_pois | DeepSeek | LLM_* | 补核心景点 |
| review | DeepSeek | LLM_* | 审查提案质量 |
| rework (poi+food) | DeepSeek | LLM_* | 按反馈重选 |
| synthesizer | qwen3.5-flash | EXPERT_LLM_* | 路线编排 |
| narrator | DeepSeek | LLM_* | 文案润色（SSE路径） |

### LLM调用次数（单次请求）

| 阶段 | 调用次数 | 模型 |
|------|---------|------|
| intent_parser | 1 | DeepSeek |
| expert_router | 1 | DeepSeek |
| rule_guard | 1 | DeepSeek |
| experts (活跃4-6个) | 2-4 (qwen) + 0 (规则) | qwen3.5-flash |
| review | 1 | DeepSeek |
| rework (如触发) | 0-2 | DeepSeek |
| synthesizer | 1 | qwen3.5-flash |
| **总计** | **7-12次** | |

### 天花板分析

| 维度 | 当前 | 天花板 | 瓶颈 |
|------|------|--------|------|
| intent_match | 7.6-7.8 | ~8.5 | LLM解析能力上限 |
| poi_quality | 6.8-7.0 | ~7.5 | 数据质量+LLM选择 |
| geo_continuity | 7.0-7.2 | ~8.0 | 已接近上限 |
| scene_diversity | 5.6-5.8 | ~6.0 | **数据不支持** |
| overall | 6.8-7.0 | ~7.2 | diversity拖后腿 |

## 后续优化方向（如有需要）

1. **补数据**: 加日间娱乐POI（海洋馆、动物园、科技馆）和自然风光POI → 唯一能根本提升diversity的方案
2. **多次run取最优**: 跑2-3次pipeline取overall最高的 → 从4/5稳定到5/5
3. **evaluator稳定性**: 用多次eval取平均，减少单次评分的随机性

---

## 第二轮优化：架构探索 (2026-05-16)

### 评估系统诊断

对评估系统进行了深度分析，发现：

1. **评分不算苛刻**：有5条"防苛政"规则，如"不可能需求给5-6分"、"合理路线geo至少给5分"
2. **scene_diversity是结构性不公平**：娱乐类POI只有39个(3.5%多为夜店)，自然风光仅1个(0.05%)。路线永远只能在景点+文化+运动+餐饮里打转，但evaluator期望4种以上大类
3. **LLM方差是主要问题**：同一代码、同一prompt，overall波动6-8分。4/5和5/5之间只差一次LLM随机选择
4. **美食型是短板**：geo_continuity=5（折返），poi_quality=6（非本地特色）
5. **"全相同分数"过滤**（test_c_version.py line 140）：如果LLM给所有维度打相同分数，结果被丢弃——偏向"差异化"评分

### 5个新架构方案

所有架构通过 `SYNTHESIZER_MODE` 环境变量切换，不影响default模式。

| 架构 | 模式名 | 核心思路 | 目标维度 |
|------|--------|---------|---------|
| A1: Best-of-N | `best_of_n` | 并行跑3次LLM组装，启发式评分选最优 | 减少方差 |
| A2: Geo-Cluster | `geo_cluster` | 先按坐标聚类，选最优簇，TSP排序，LLM只分配时间 | geo_continuity |
| A3: Self-Refine | `self_refine` | 先组装→规则critique→带反馈重新组装 | 针对性改进 |
| A4: Tournament | `tournament` | 并行3种策略(地理/类型/体验优先)，选最优 | 全维度平衡 |
| A5: Constraint | `constraint` | 从锚点开始，最近邻填充，自动约束满足 | 可预测性 |

测试方法：
```bash
# 基线对照
SYNTHESIZER_MODE=default python tests/test_c_version.py

# 测试各架构
SYNTHESIZER_MODE=best_of_n python tests/test_c_version.py
SYNTHESIZER_MODE=geo_cluster python tests/test_c_version.py
SYNTHESIZER_MODE=self_refine python tests/test_c_version.py
SYNTHESIZER_MODE=tournament python tests/test_c_version.py
SYNTHESIZER_MODE=constraint python tests/test_c_version.py
```
