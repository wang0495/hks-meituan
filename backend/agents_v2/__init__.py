"""CityFlow A版本 - 3层联邦架构实现。

架构：
1. 意图探测与矛盾调解网络 (Layer 1)
2. 竞标市场 (Market Layer)
3. 对抗性校验市场 (Layer 2)
4. 微协商总线 (Layer 3)
"""

from backend.agents_v2.graph import build_graph_a, get_graph_a
from backend.agents_v2.state import FederatedState

__all__ = ["build_graph_a", "get_graph_a", "FederatedState"]
