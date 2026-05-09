# Tasks: F005-perception

## Task Rules

- **Status**: `[TODO]` → `[DOING]` → `[DONE]`
- **Task communication / confirmation**:
  - `[TODO] → [DOING]`: share the task title first, then update the task state in `tasks.md`
  - `[DOING] → [DONE]`: share the result and verification first, then update `Acceptance` and `Checklist` in the same edit
  - Ask for approval before changing task state only when the task crosses a documented review checkpoint or before remote/destructive actions.
  - Do not invent a standalone `OK` approval step when the workflow does not require one.
  - Do not mark `[DONE]` while any item in that task's `Checklist` remains unchecked.
- **PRD mapping (recommended)**: add an existing PRD requirement ID tag like `[PRD-FR-001]` or `[PRD-SCOPE-V1-DESKTOP-EDITOR` to each task line, or tag non-PRD tasks as `[NON-PRD]`.
  - Do not invent PRD IDs in `tasks.md`. Only reference IDs that already exist in `docs/prd` or the upstream requirements doc.
  - If this is a legacy feature without PRD IDs yet, backfill IDs in the source requirements doc first, then align `spec.md` `PRD Refs` and task tags together.
  - `[NON-PRD]` is for internal implementation work only. If the task changes user-facing behavior, acceptance criteria, or scope, backfill PRD first and tag it as `[PRD-...]`.

---
## Local Tracking
- **Doc Status**: Draft
- **Repo**: hks-meituan
- **Branch**: `feat/F005-perception`
- **Pending Change Request**: -
- **PR Review**: -
- **PR Review Evidence**: -

---
## Task List

---

### [DONE][NON-PRD] T-F005-01 感知数据类定义

- Date: 2026-05-09
- Acceptance: `PerceptionContext`、`Anomaly`、`AdjustmentResult` 三个数据类定义完整 ✅
- Checklist:
  - [x] `PerceptionContext`: dataclass 含 weather/temperature/hour_of_day/season/step_count/fatigue_level/avg_stay_duration/photo_frequency
  - [x] `AnomalyType`: Enum + `Anomaly` 数据类含 type/severity/message/timestamp + to_dict()
  - [x] `AdjustmentAction`: Enum + `AdjustmentResult` 数据类含 action_type/target_poi_ids/reasoning

---

### [DONE][NON-PRD] T-F005-02 Mock 数据生成 + 场景预设

- Date: 2026-05-09
- Acceptance: 4 种演示场景（晴天悠闲/雨天室内/体力预警/时间压力）可复现 ✅
- Checklist:
  - [x] `ScenePresets` 类: 4 个预设场景的 PerceptionContext 常量
  - [x] `PerceptionService.get_context(scene=None)`: 默认随机生成，scene 参数切换预设
  - [x] 随机模式: weather 按概率分布（sunny 55%, rainy 10%）
  - [x] 步数模拟: random.randint(0, 8000) 随机

---

### [DONE][NON-PRD] T-F005-03 异常检测逻辑

- Date: 2026-05-09
- Acceptance: 4 种异常类型（天气突变/体力预警/情绪低谷/时间压力）均可检测 ✅
- Checklist:
  - [x] `detect_anomaly()`: 天气突变（sunny→rainy 触发）
  - [x] `detect_anomaly()`: 体力预警（>15000 sev=0.7, >10000 sev=0.4）
  - [x] `detect_anomaly()`: 情绪低谷（连续 3 站 emotion_intensity < 0.4）
  - [x] `detect_anomaly()`: 时间压力（hour_of_day >= 16）
  - [x] 返回 `list[Anomaly]`：空列表表示无异常

---

### [DONE][NON-PRD] T-F005-04 动态调整策略

- Date: 2026-05-09
- Acceptance: 4 种异常对应 4 种调整策略，返回 `AdjustmentResult` ✅
- Checklist:
  - [x] 天气突变 → `INDOOR_REPLACEMENT`: 替换室外 POI
  - [x] 体力预警 → `REST_INSERTION`: 中间插入休息节点
  - [x] 情绪低谷 → `STYLE_SWITCH`: 切换高情绪 POI
  - [x] 时间压力 → `SKIP_LOW_VALUE`: 跳过 avg_stay>45 且 rating<4.0 的 POI

---

### [DONE][NON-PRD] T-F005-05 与 solver 集成

- Date: 2026-05-09
- Acceptance: `solve_route` 可接收感知上下文，异常检测结果影响路线评分 ✅
- Checklist:
  - [x] `solve_route(candidates, user_intent, start_time, perception_ctx=None)` 新增参数
  - [x] 体力预警 → `_gamma_multiplier` 动态调整（fatigue>0.7→3x, >0.5→2x）
  - [x] SSE 路由在调用 `solve_route` 前获取感知上下文，检测异常后推 anomaly 事件

---

### [DONE][NON-PRD] T-F005-06 单元测试 + 场景验证

- Date: 2026-05-09
- Acceptance: `pytest tests/test_perception.py -v` 全部通过 ✅
- Checklist:
  - [x] 测试 4 种预设场景可复现
  - [x] 测试 4 种异常检测逻辑正确
  - [x] 测试 4 种调整策略返回正确 action_type
  - [x] 测试 solver 集成后路线评分变化

---

## Completion Criteria

- [x] All tasks are `[DONE]`, and each task's `Acceptance` is verified and `Checklist` is checked
- [x] Tests executed and passing (record command/result below)
- [x] Final outcome shared and any required user confirmation recorded at the documented workflow checkpoint

### Test Run Log (Latest by Command)

| Command | Last Run (Local, YYYY-MM-DD) | Result |
| --- | --- | --- |
| `pytest tests/test_perception.py -v` | `2026-05-09` | `24 passed` |