# Feature Spec: F005-perception

---
## Overview

- **Feature ID**: F005
- **Feature Name**: F005-perception
- **Target Repo**: hks-meituan
- **Created**: 2026-05-09
- **Status**: Draft

---
## Purpose

构建感知系统 Mock 层 + 动态调整策略。实时采集天气/时间/体力/用户行为等感知信号，检测异常后触发路线调整。对应架构文档 D2（产品设计 §5）。

> 比赛环境说明：所有外部数据使用 Mock 模拟，无需真实 API。

---
## User Stories

### US-1: 天气突变时推荐室内替代

**As a** 用户
**I want** 行程中突然下雨时系统主动提示室内替代方案
**So that** 不被天气打乱体验

**Acceptance Criteria:**
- [ ] 天气从晴天变为雨天时，系统触发室内 POI 替代
- [ ] SSE 推送 `anomaly` 事件，告知用户天气变化和调整建议

### US-2: 体力预警时插入休息点

**As a** 用户
**I want** 走了很久后系统提醒休息或打车
**So that** 不会太累影响后续体验

**Acceptance Criteria:**
- [ ] 步数超过 15000 时触发体力预警
- [ ] 系统推荐附近休息点或打车选项

### US-3: 情绪低谷时切换推荐风格

**As a** 用户
**I want** 连续多个景点体验平淡时系统调整推荐风格
**So that** 保持旅程新鲜感

**Acceptance Criteria:**
- [ ] 连续 3 站情绪强度 < 0.4 时触发风格切换
- [ ] 切换到高刺激/惊喜类型 POI

### US-4: 时间压力时跳过低价值景点

**As a** 用户
**I want** 快到结束时系统帮我跳过耗时长价值低的景点
**So that** 按时回家不赶路

**Acceptance Criteria:**
- [ ] 剩余时间 < 1 小时时，系统建议跳过耗时 > 45min 的低评分 POI

---
## Functional Requirements

### FR-1: 感知数据采集（Mock）[NON-PRD]

`PerceptionService` 聚合 5 类感知信号，全部 Mock 生成：
- `weather`: 随机场景（sunny/rainy/cloudy/hot/cold）
- `hour_of_day`: `datetime.now().hour`
- `step_count`: 基于 POI 停留时间模拟
- `avg_stay_duration`: 模拟停留时长
- `photo_frequency`: 模拟拍照频率

### FR-2: 异常检测 [NON-PRD]

`detect_anomaly(ctx)` 返回 `list[Anomaly]`，覆盖 4 种场景：
- 天气突变（5% 概率）
- 体力预警（step_count > 15000）
- 情绪低谷（连续 3 站 < 0.4）
- 时间压力（剩余时间 < 1h）

### FR-3: 动态调整 [NON-PRD]

`adjust_suggestions(ctx, plan)` 返回调整建议：
- 天气突变 → 替换为室内 POI
- 体力预警 → 插入休息节点
- 情绪低谷 → 切换高刺激 POI
- 时间压力 → 跳过低价值 POI

### FR-4: 演示场景预设 [NON-PRD]

4 种预设场景用于演示：
- 场景A（晴天悠闲）: `weather=sunny, temp=25°C, fatigue=0.2`
- 场景B（雨天室内）: `weather=rainy, temp=18°C, fatigue=0.5`
- 场景C（体力预警）: `weather=sunny, temp=30°C, fatigue=0.8` → 触发休息建议
- 场景D（时间压力）: `weather=cloudy, hour=16:00` → 跳过耗时景点

---
## Non-Functional Requirements

- **Performance**: 感知数据采集 < 5ms（纯内存计算）
- **Determinism**: 同一场景参数产生一致的感知数据（Mock 种子可控）

---
## Related Documents

- PRD: `../../prd/hks-meituan-prd.md`
- PRD Refs: - (D2 来自产品设计文档)
- Architecture: `../../architecture-and-optimization.md` §感知系统 D2