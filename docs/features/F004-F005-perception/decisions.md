# Decisions Log

## D001: F005-perception design decision (2026-05-09)

- **Context**: 感知系统需要采集天气/步数/时间/行为数据，但比赛环境无真实外部 API
- **Constraints**: Mock 数据需可复现；感知结果需能影响 solver 路线评分
- **Options**:
  1. 全部随机生成，每次调用生成不同数据
  2. 场景预设 + 随机混合：默认随机，关键演示用预设
  3. 完全预设：所有数据硬编码，不可变
- **Decision**: 选项 2 — 场景预设 + 随机混合
- **Rationale**:
  - 用户演示需要确定性场景（场景A晴天悠闲 → 场景B突然下雨 → 触发室内替代）
  - 随机模式保证日常使用的真实性
  - 预设场景可 seed 化，便于测试复现
  - 感知数据作为 solver 的辅助输入，不应阻断核心流程
- **Trace**:
  - **At DOING start**: 比赛环境说明数据全部 Mock，架构文档 D2 已明确
  - **Before DONE**: 确认场景预设 + 随机混合方案
  - **Post-merge check**: -
- **Evidence**:
  - **Commit**: -
  - **PR**: -
  - **Test/Log**: -