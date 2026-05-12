"""CityFlow A版本 - 3层联邦架构完整实现。

架构：
1. Layer 1: 意图探测与矛盾调解网络
   - 8种矛盾模式检测
   - LLM深度理解
   - 灵活子需求分解

2. 竞标市场
   - 5个Agent并行竞标（POI/Food/Activity/Transport/Insurance）
   - 动态定价
   - 市场出清
   - 组合投标

3. Layer 2: 对抗性校验市场
   - 6个Validator并行校验
   - 复用B版本validator
   - CriticAgent对抗挑刺
   - RealtimeValidator实时数据

4. Layer 3: 微协商总线
   - 双向协商协议
   - 时间契约形成
   - TSPTW优化
   - 运行时监控
"""

from backend.agents_v2.graph import build_graph_a, get_graph_a
from backend.agents_v2.state import FederatedState

__all__ = ["build_graph_a", "get_graph_a", "FederatedState"]
