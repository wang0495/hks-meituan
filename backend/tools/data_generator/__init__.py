"""
CityFlow 数据生成工具

为 CityFlow 系统生成 4 类模拟数据：
  1. POI highlights（内部体验数据）
  2. POI constraints（约束数据）
  3. nonstandard_experiences 扩充
  4. POI 类别平衡补充（文化/运动）

使用方法：
  python -m backend.tools.data_generator.main --task all

设计原则：
  - 所有 LLM 调用通过 LLMProvider 接口抽象，用户自行实现适配器
  - 数据模型使用 Pydantic v2 做格式校验
  - 生成管线（filter → prompt → parse → validate → save）可独立运行
"""

__version__ = "0.1.0"
