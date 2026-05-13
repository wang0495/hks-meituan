# C版本架构诊断图（2026-05-13 第二轮）

> 测试数据: 30场景 5.5/10 | 通过率 5/28(18%) | 及格线 6.5
> 上一轮: 5.3/10 | 通过率 4/29(14%)

---

## 架构全图（问题已标注）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  用户输入                                                                    │
│  例: "上午想安静画画，下午突然想蹦迪"                                         │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ① rule_guard (入口)                                                        │
│                                                                             │
│  parse_intent(user_input)                                                   │
│    → user_intent: {city, budget, group, pace, scene_requirements, ...}     │
│                                                                             │
│  get_data() → 加载全量POI (4734个)                                          │
│  filter_candidates() → 预筛 (~120个候选)                                     │
│  _ensure_key_pois() → 保证核心景点在池中                                      │
│                                                                             │
│  输出: user_intent, candidates(~120个)                                       │
│        "scene_requirements": ["安静画画", "蹦迪"]                            │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │    7个Agent并行（fan-out）     │
                └──────────────┬──────────────┘
                               │
     ┌──────────┬──────────┬───┴───────┬──────────┬──────────┬──────────┐
     ▼          ▼          ▼           ▼          ▼          ▼          ▼
┌─────────┐┌─────────┐┌─────────┐┌─────────┐┌─────────┐┌─────────┐┌─────────┐
│② POI    ││③ Food   ││④ Hotel  ││⑤Traffic ││⑥ Weather││⑦ Expert ││⑧Insure │
│  Agent  ││  Agent  ││  Agent  ││  Agent  ││  Agent  ││  Agent  ││  Agent │
│         ││         ││         ││         ││         ││         ││        │
│DeepSeek ││DeepSeek ││DeepSeek ││DeepSeek ││DeepSeek ││DeepSeek ││DeepSeek│
│选景点   ││选餐厅   ││选酒店   ││排顺序   ││评天气   ││推隐藏景 ││评风险  │
│         ││         ││         ││         ││         ││         ││        │
│🟢 场景  ││         ││         ││╔═══════╗││         ││         ││        │
│分化prompt││         ││         ││║🟡问题A║││         ││         ││        │
│(亲子/情 ││         ││         ││║看不到 ║││         ││         ││        │
│侣/特种兵││         ││         ││║POI结果║││         ││         ││        │
│等)      ││         ││         │║╚═══════╝││         ││         ││        │
│         ││         ││         ││         ││         ││         ││        │
│🟢 地理  ││         ││         ││         ││         ││         ││        │
│聚类后处 ││         ││         ││         ││         ││         ││        │
│理       ││         ││         ││         ││         ││         ││        │
│         ││         ││         ││         ││         ││         ││        │
│输出:    ││输出:    ││输出:    ││输出:    ││输出:    ││输出:    ││输出:   │
│proposals││proposals││proposals││proposals││proposals││proposals││proposals│
│(5-8景点)││(1-3餐厅)││(0-2酒店)││(排序建议)││(天气建议)││(隐藏景点)││(风险)  │
└────┬────┘└────┬────┘└────┬────┘└────┬────┘└────┬────┘└────┬────┘└────┬───┘
     │          │          │            │          │          │          │
     └──────────┴─────┬────┴────────────┴──────────┴──────────┴──────────┘
                       │ proposals 合并 (Annotated[list, operator.add])
                       │ → 12~18个提案拼在一起
                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ⑨ group_debate (Phase 2: 结构化约束反驳)                                   │
│                                                                             │
│  Step 1: 规则冲突检测 (纯规则, 不调LLM)                                      │
│    ├─ 主题矛盾: 亲子+夜生活 → remove                                         │
│    ├─ 预算超支: 总价>1.5x预算 → suggest_cheaper                              │
│    └─ 地理冲突: 餐厅距景点簇>10km → remove_food                              │
│                                                                             │
│  Step 2: 执行规则决议                                                        │
│    remove → 加入黑名单                                                       │
│    suggest_cheaper → 降低confidence到0.3                                      │
│                                                                             │
│  Step 3: LLM结构化反驳 (1轮)                                                 │
│    检查: geo_far / type_repeat / time_conflict / scene_mismatch              │
│    决议: remove / swap(confidence=0.2) / keep                                │
│                                                                             │
│  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓                              │
│  ┃ ⚠️ 问题B: group_debate不改proposals        ┃                              │
│  ┃                                            ┃                              │
│  ┃ 只返回 conflicts 列表                      ┃                              │
│  ┃ proposals字段不变(Annotated不能替换)        ┃                              │
│  ┃ coordinator读的是原始proposals             ┃                              │
│  ┃ → 只能靠name匹配来remove，容易漏           ┃                              │
│  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛                              │
│                                                                             │
│  输出: negotiation_msgs, conflicts                                           │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ⑩ coordinator (Phase 3: 路线组装)          ← 🔴🔴 最关键瓶颈 🔴🔴         │
│                                                                             │
│  Step 0: 读conflicts → 移除被标记remove的proposal                           │
│  Step 1: 收集poi/food/hotel proposals (跳过confidence<0.3)                  │
│  Step 2: 构建solver候选池                                                   │
│  Step 3: 调用 solver.solve_route()                                          │
│  Step 4: 生成文案                                                           │
│                                                                             │
│  ╔═══════════════════════════════════════════════════════════════════╗      │
│  ║ 🔴🔴🔴 核心问题: Agent选的好POI被solver丢弃                        ║      │
│  ║                                                                     ║      │
│  ║  当前数据流:                                                        ║      │
│  ║                                                                     ║      │
│  ║  Agent精选 (poi_quality=6.6)                                       ║      │
│  ║    ↓                                                                ║      │
│  ║    ↓  ← 这条线被忽略了！coordinator传全量candidates给solver          ║      │
│  ║    ↓                                                                ║      │
│  ║  solver.solve_route(candidates_pool, intent)                        ║      │
│  ║    ↓                                                                ║      │
│  ║  solver Phase 0: _select_diverse_candidates()                      ║      │
│  ║    ├─ tourist_relevance过滤 (只保留>=0.4的)                         ║      │
│  ║    ├─ 🔴🔴 scene_requirements过滤 (ANY-match, 最致命!)              ║      │
│  ║    │   例: "安静画画" → 只匹配到1个POI → 其他全丢                    ║      │
│  ║    │   例: "蹦迪" → 匹配到2个 → 只剩这2个                           ║      │
│  ║    │   结果: 30个候选 → 只剩2-3个 → 路线只有3-4站                    ║      │
│  ║    ├─ 预算过滤 (budget=0 → 所有POI被丢掉!)                          ║      │
│  ║    └─ 类别多样性选择 (每类最多N个, 总共最多30)                        ║      │
│  ║                                                                     ║      │
│  ║  solver Phase 1: 贪心选点                                            ║      │
│  ║    scene_matched POI: -8.0分奖励(最强信号)                           ║      │
│  ║    → 如果Phase 0已经把候选筛到2-3个                                   ║      │
│  ║    → Phase 1只能从2-3个里选 → 路线太短                                ║      │
│  ║                                                                     ║      │
│  ║  🔴 结果: Agent的LLM精选(12-18个提案) 全部浪费                       ║      │
│  ║  solver自己从头选 → poi质量不如Agent → geo也没提升                    ║      │
│  ║                                                                     ║      │
│  ║  数据佐证:                                                           ║      │
│  ║    Agent选POI: poi_quality = 6.6 (最强项)                            ║      │
│  ║    Solver选POI: poi_quality = 6.6 (持平, 但多样性下降)               ║      │
│  ║    Agent排路线: geo_continuity = 5.0                                 ║      │
│  ║    Solver排路线: geo_continuity = 5.1 (几乎没提升!)                  ║      │
│  ║                                                                     ║      │
│  ║  结论: solver的Phase 0选点能力不如Agent的LLM                          ║      │
│  ║        solver的路线排序也没有显著优于最近邻+2-opt                      ║      │
│  ╚═════════════════════════════════════════════════════════════════════╝      │
│                                                                             │
│  输出: route, narrative, errors                                              │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ⑪ live_itinerary (热力图 + 决策溯源)                                       │
│  读取proposals + conflicts → 构建heatmap和decision_trace                    │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
                          SSE 输出
```

---

## 问题根因分析（按影响排序）

```
🔴🔴🔴 P0 ── coordinator: Agent精选被solver丢弃
│
│  表现: geo=5.1, 路线只有3-5站, 24%场景intent≤3
│
│  数据流断裂:
│
│   Agent LLM精选 ─────┐
│   poi_quality=6.6    │  ← 这条线被浪费了
│   12-18个提案        │
│                      │
│   candidates_pool ───┼──→ solver.solve_route()
│   (~120个原始POI)    │         │
│                      │         ├─ Phase 0: scene_requirements过滤
│                      │         │   "安静画画" → 只匹配1个POI
│                      │         │   "蹦迪" → 只匹配2个POI
│                      │         │   budget=0 → 所有POI被丢
│                      │         │
│                      │         ├─ Phase 1: 从2-3个候选里贪心选
│                      │         │   → 路线只有3-4站
│                      │         │
│                      │         └─ Phase 2-5: 在3-4个POI上优化
│                      │             → 再怎么优化也只有3-4站
│                      │
│                      └─ Agent的精选提案完全没用上
│
│  根因: coordinator传candidates_pool给solver，不是Agent精选的proposals
│  修复: 把Agent精选的POI直接送给solver，跳过Phase 0的选点
│        或者: 只用solver做排序(Phase 2-5)，不用solver选点(Phase 0-1)

🔴🔴 P1 ── intent_match: 5.5 (24%场景≤3分)
│
│  表现:
│    "摄影夜景" intent=2 → 选了白天景点
│    "矛盾需求" intent=2 → 只会选一类
│    "亲子"    intent=2 → 选了剧本杀
│    "雨夜漫步" intent=3 → 选了攀岩
│
│  根因: solver的scene_requirements过滤太死板
│        用户说"安静画画" → solver只找含这4字的POI → 找不到 → 随便选
│        但Agent的LLM其实能理解"安静画画"="美术馆/画室/安静的咖啡馆"
│
│  修复: 让Agent的proposals成为solver的输入，不传candidates_pool
│        Agent LLM已经理解了语义，solver不需要再从原始数据里找

🟡 P2 ── group_debate不能修改proposals
│
│  表现: Annotated[list, operator.add]只允许追加，不能替换
│        group_debate标记的conflicts靠name匹配删除，容易漏
│
│  修复: 方案A: 把conflicts传给coordinator时带index，精准删除
│        方案B: 用新state字段"cleaned_proposals"绕过Annotated限制

🟡 P3 ── 路线太短 (3-5站)
│
│  表现: 一天行程应该5-8个POI，实际只有3-4个
│  根因: solver的Phase 0把候选筛到只剩几个 → Phase 1没得选
│  修复: 随P0一起解决 — Agent选好POI后，solver只做排序
```

---

## 修复方案：让solver只排序，不选点

```
修复后的数据流:

用户输入
    │
    ▼
rule_guard
    │ 输出: user_intent, candidates(~120个)
    │
    ▼
[7个Agent并行]
    │ 每个Agent调DeepSeek LLM精选
    │
    │ POI Agent → 选出5-8个景点 (poi_quality=6.6)
    │ Food Agent → 选出1-3个餐厅
    │ Hotel Agent → 选出0-2个酒店
    │
    ▼ proposals合并(~15个提案)
group_debate
    │ 移除冲突提案
    │ 输出: conflicts
    │
    ▼
coordinator
    │
    │ 🔧 修复: 不再传candidates_pool给solver
    │
    │  改前: solve_route(candidates_pool, intent)
    │        → solver Phase 0 从120个原始POI重新选 → Agent精选被浪费
    │
    │  改后: 从Agent精选的proposals中提取POI
    │        → 按地点/类别补充少量candidates给solver做呼吸空间/高潮
    │        → solve_route(agent_selected_pois + 少量补充, intent)
    │        → solver Phase 0 的候选池已经很小且高质量
    │        → solver Phase 1-5 在这些精选POI上做路线优化
    │
    │  预期:
    │    poi_quality 保持 6.6 (Agent精选不被丢)
    │    geo_continuity 提升 (solver的2-opt+情绪编排仍然有效)
    │    路线长度提升 (5-8站而非3-4站)
    │    intent_match 提升 (Agent理解了用户语义)
    │
    ▼
  输出
```

---

## 评分对比

| 版本 | 平均 | 通过率 | intent | poi_quality | geo | diversity |
|------|------|--------|--------|-------------|-----|-----------|
| 修复前(无solver) | 5.3 | 14% | 5.4 | 6.6 | 5.0 | 5.7 |
| 当前(全量给solver) | 5.5 | 18% | 5.5 | 6.6 | 5.1 | 6.1 |
| **预期(精选给solver)** | **6.0+** | **30%+** | **6.0+** | **6.6** | **6.5+** | **6.0+** |

---

*诊断生成时间: 2026-05-13*
*测试数据: test_abc_30_results.json (30场景LLM评分)*
