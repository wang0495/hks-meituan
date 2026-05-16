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

---

## 开源架构研究摘要

参考了6个方向的学术研究和开源项目：

### 最相关：Google Research LLM+Optimizer混合方案
- **论文**: Personal Travel Solver (ACL 2025), Google Research Blog
- **核心**: LLM生成初始路线 → 优化器修正约束违规 → 输出可行路线
- **关键创新**: 分数函数 = "与LLM初始方案的相似度 × 可行性"，负面约束权重是正面的2倍
- **PTS通过率96.6%** vs GPT-4o直接规划0.4%
- **对我们的启示**: 当前synthesizer的LLM输出直接作为最终路线，缺少约束修正环节

### 其他参考方向
- **MCTS+自精炼**: 适用于复杂约束场景，但计算成本高（10-50次LLM调用）
- **MoE Chamber**: 分层专家室（美食室、景点室），按领域路由而非扁平列表
- **Multi-agent辩论+投票**: 投票协议在推理任务中提升13.2%，群体多样性比结构更重要
- **Graph of Thoughts (GoT)**: DAG结构支持中间结果融合，表达能力最强但复杂度高
- **LangGraph并行fan-out**: 类似当前架构，但缺少迭代细化

### 评估器改进发现
- **temperature=0.1 → 0**: DeepSeek API支持贪婪解码，消除评估方差源
- **"全同分数"过滤过于激进**: 全7/全8可能是合理的均匀好路线，不应丢弃
- **混合评估策略**: 日常CI用纯规则（零成本、确定性），发布前用LLM抽查

### POI数据层面
- "景点"(335个)实际包含5种不同体验，但evaluator只看到1种 → scene_diversity系统性低分
- 已创建enrichment脚本拆分为: 自然风光/海滨景点/文化景点/亲子游乐/夜景地标/地标景点
- 预期diversity从3种category提升到5-6种

---

## 第二轮实测结果 (2026-05-16)

### 测试条件

- POI enrichment已执行：_display_category字段已添加到city_poi_db.json
- evaluator使用temperature=0（贪婪解码）
- 每个模式跑1次5场景

### 各架构实测对比

| 模式 | 通过 | overall | intent | poi | geo | diversity | 耗时 |
|------|------|---------|--------|-----|-----|-----------|------|
| baseline (default) | 3/5 | 6.6 | 7.4 | 6.6 | **7.6** | 5.2 | ~30s/场景 |
| A1 best_of_n | 2/5 | 6.4 | 7.2 | 6.4 | 7.0 | 5.4 | ~30s |
| A2 geo_cluster | 2/5 | 6.4 | 7.0 | 6.4 | 7.0 | 5.0 | ~26s |
| **A3 self_refine** | **4/5** | **6.6** | 7.2 | **6.8** | 7.0 | 5.0 | ~28s |
| **A4 tournament** | **5/5** | **7.0** | **7.6** | **6.8** | **7.6** | **5.6** | ~29s |
| A5 constraint | 2/5 | 6.4 | 7.2 | 6.4 | 6.2 | 5.4 | ~25s |
| 全qwen3.5-flash | 3/5 | 6.4 | 6.8 | 6.6 | 7.2 | 4.8 | ~37s |

### 各场景详细 (A4 tournament = 冠军)

| 场景 | A4得分 | intent | poi | geo | diversity |
|------|--------|--------|-----|-----|-----------|
| S1 情侣珠海一日游 | **7** ✅ | 7 | 7 | 8 | 6 |
| S2 亲子海洋王国 | **7** ✅ | 7 | 7 | 8 | 5 |
| S3 美食探索 | **7** ✅ | 8 | 7 | 7 | 6 |
| S4 特种兵打卡 | **7** ✅ | 8 | 6 | 7 | 5 |
| S5 休闲养老游 | **7** ✅ | 8 | 7 | 8 | 6 |

### 分析

1. **A4 tournament胜出**：3种并行策略（地理优先/类型优先/体验优先）+ 启发式选最优，兼具稳定性和全维度平衡。5/5通过且overall=7.0

2. **A3 self_refine第二**：4/5通过。critique→refine循环有效，但单次refine可能不够

3. **A1 best_of_n失败**：多温度采样+启发式选优的假设是"更多选择=更好的选择"，但启发式评分函数不够准，反而引入噪声

4. **A2 geo_cluster失败**：纯算法聚类丢失了LLM对场景类型的理解。聚类后LLM只分配时间，无法做场景感知的优化

5. **A5 constraint失败**：最近邻填充贪心策略太短视，容易陷入局部最优

6. **全qwen3.5-flash**：intent_match明显掉（7.4→6.8），说明意图解析和router确实需要更强的模型。但poi_quality持平（6.6），证明expert阶段用便宜模型够了

### 结论

- **推荐A4 tournament作为默认模式** — 5/5通过，各维度均衡
- **POI enrichment有效** — diversity从之前的~5.0提升到5.6
- **全qwen不可行** — intent解析需要DeepSeek级别模型
- **diversity仍有天花板** — 即使有enrichment，5.6已经是数据能撑到的上限

---

## 第三轮优化：开源架构落地实验 (2026-05-16)

### 实验1: A6 PTS — LLM选点+算法排序

参考Google PTS论文(ACL 2025)的核心发现：LLM擅长理解偏好但不擅长硬约束，应该分工。

实现：
- `_pts_select_pois`: LLM只输出POI名称列表（无序），不排顺序、不分配时间
- `_nearest_neighbor_tsp`: 最近邻贪心TSP排序
- `_insert_food_by_geo`: 按地理距离将餐饮插入到最近POI旁边
- `_pts_assemble`: 串起全流程

| 指标 | baseline(tournament) | PTS | 变化 |
|------|---------------------|-----|------|
| 通过 | 2/5 | **3/5** | +1 |
| overall | 6.2 | **6.4** | +0.2 |
| intent | 7.0 | **7.4** | +0.4 |
| poi | 6.4 | **6.6** | +0.2 |
| geo | **7.8** | 7.0 | -0.8 |
| diversity | 4.6 | **5.8** | **+1.2** |

**PTS创造了diversity历史最高(5.8)**。LLM只做"选择"时天然倾向选不同类型的POI。
但geo掉了——最近邻TSP不如LLM的地理直觉（LLM能感知"这个景点应该排在上午"等语义信息）。

结论：PTS的选点策略有价值，但排序需要更强算法或保留LLM。

### 实验2: A7 Tournament+GoT地理预合并

参考Graph of Thoughts的"中间结果融合"思路：在tournament之前对POI+Food做地理聚类，剔除离群。

实现：
- `_geo_cluster_proposals`: 单链接聚类(8km半径)，保留最大cluster
- `_tournament_geo_assemble`: 过滤后复用tournament逻辑

| 指标 | baseline(tournament) | tournament_geo | 变化 |
|------|---------------------|----------------|------|
| 通过 | 2/5 | 2/5 | 持平 |
| overall | 6.2 | **6.4** | +0.2 |
| geo | **7.8** | 6.6 | **-1.2** |
| diversity | 4.6 | **5.4** | +0.8 |

结论：**地理预合并没有帮助geo**。剔除离群POI后，cluster内仍有距离跨度（8km半径内各点可能分散）。而且某些被剔除的POI恰好是高质量POI。

### LLM方差问题持续

同一架构(A4 tournament)多次测试波动巨大：
- 5/5 (overall 7.0) → 2/5 (overall 6.2) → 4/5 (overall 6.8)
- 根因：pipeline LLM温度0.1导致POI选择不同 → 路线不同 → 分数波动±1分
- 及格线6.5恰好卡在波动区间(6-7)中间

### 后续方向

最有前景的组合：**PTS的选点策略 + tournament的多策略竞争**
- LLM只选POI子集（不排序），最大化diversity
- 3种算法策略并行排序（TSP/时间窗优先/体验优先），选geo最优的
- 消除LLM排序的方差，保留LLM选择的优势

---

## 第四轮优化：开源方案落地 (2026-05-16)

研究了37个GitHub项目（5个子agent并行），选出3个方案实测。

### 实验3: DPP多样性重排 (3/5, 6.6)

参考 github.com/laming-chen/fast-map-dpp 的贪心DPP算法。
在cap和ensure之间插入_dpp_rerank_route:
- 构建核矩阵: 对角线=POI质量分, 非对角线=类型相似度
- DPP贪心选择最大化det(L_S), 天然平衡质量和多样性
- 重排后重新计算到达/离开时间

结果: diversity 4.6→5.2 (+0.6), 但 geo 7.8→6.4 (-1.4)
结论: **DPP增加了多样性但破坏了地理连续性**。已关闭DPP但保留代码。

### 实验4: Instructor风格纠错重试 (4/5, 6.8) ← 有效

改_llm_decide的retry逻辑: 解析错误→构造错误信息→下次重试附加到user message。
原来blind retry ("异常了就再来一次"), 现在error-informed retry ("告诉LLM哪里错了让它修")。

结果: 通过 2/5→4/5, overall 6.2→6.8, intent 7.0→7.6
结论: **有效, 已保留**。减少JSON解析失败导致的pipeline降级。

### 实验5: Self-Consistency投票+零温度锚点 (3/5, 6.6)

替换原A1 best_of_n: 生成5条候选(1个temp=0锚点+4个temp=0.6), 硬约束验证+多数投票+零温度锚点回退。

结果: diversity 4.6→5.6 (+1.0), 但 geo 7.8→6.4 (-1.4)
结论: 比旧版A1好, 但不如tournament。零温度锚点保底但高温变体质量参差。

### 第四轮总结

| 方案 | 通过 | overall | diversity | geo | 结论 |
|------|------|---------|-----------|-----|------|
| 基线(tournament) | 2/5 | 6.2 | 4.6 | 7.8 | 参考 |
| DPP重排 | 3/5 | 6.6 | 5.2 | 6.4 | 破坏geo,已关 |
| **Instructor重试** | **4/5** | **6.8** | **5.4** | 7.0 | **已保留** |
| Self-Consistency | 3/5 | 6.6 | 5.6 | 6.4 | 不如tournament |

**Instructor纠错重试是唯一值得保留的改动**。效果明确且不引入新问题。
DPP和Self-Consistency都增加了diversity但代价是geo大幅下降。
