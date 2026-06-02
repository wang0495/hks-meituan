/**
 * architecture-viz.js — CityFlow MoE 架构可视化组件
 *
 * 在 Canvas 上绘制多专家混合架构（Mixture of Experts）的动态流程图，
 * 展示 rule_guard → expert_router → Wave1/Wave2 → review → synthesizer 的完整流程。
 */

class ArchitectureViz {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    if (!this.container) return;

    this.canvas = document.createElement('canvas');
    this.canvas.style.width = '100%';
    this.canvas.style.height = '100%';
    this.container.appendChild(this.canvas);
    this.ctx = this.canvas.getContext('2d');

    this.dpr = window.devicePixelRatio || 1;
    this.time = 0;
    this.activeNode = null;
    this.nodeStates = {};
    this.particles = [];

    // MoE 架构节点定义
    this.nodes = [
      // Entry
      { id: 'input', x: 0.5, y: 0.04, label: '用户输入', icon: '💬', color: '#e8886a', group: 'entry' },
      { id: 'rule_guard', x: 0.5, y: 0.14, label: '规则守卫', icon: '🛡️', color: '#e8c86a', group: 'guard' },
      { id: 'expert_router', x: 0.5, y: 0.24, label: '专家路由', icon: '🧭', color: '#6a9ec8', group: 'router' },

      // Wave 1
      { id: 'poi', x: 0.12, y: 0.38, label: 'POI 专家', icon: '📍', color: '#e8886a', group: 'wave1' },
      { id: 'food', x: 0.37, y: 0.38, label: '美食专家', icon: '🍜', color: '#e8c86a', group: 'wave1' },
      { id: 'weather', x: 0.62, y: 0.38, label: '天气专家', icon: '🌤️', color: '#6a9ec8', group: 'wave1' },
      { id: 'destination', x: 0.87, y: 0.38, label: '目的地专家', icon: '🎯', color: '#9b59b6', group: 'wave1' },

      // Wave 2
      { id: 'traffic', x: 0.12, y: 0.54, label: '交通专家', icon: '🚗', color: '#e74c3c', group: 'wave2' },
      { id: 'hotel', x: 0.37, y: 0.54, label: '住宿专家', icon: '🏨', color: '#3498db', group: 'wave2' },
      { id: 'local', x: 0.62, y: 0.54, label: '本地达人', icon: '🗺️', color: '#2ecc71', group: 'wave2' },
      { id: 'budget', x: 0.87, y: 0.54, label: '省钱黑客', icon: '💰', color: '#f39c12', group: 'wave2' },

      // Synthesis
      { id: 'review', x: 0.5, y: 0.66, label: '质量评审', icon: '🔍', color: '#e74c3c', group: 'review' },
      { id: 'emergence', x: 0.5, y: 0.76, label: '涌现校验', icon: '✨', color: '#9b59b6', group: 'emergence' },
      { id: 'synthesizer', x: 0.5, y: 0.86, label: '路线合成', icon: '🗺️', color: '#2ecc71', group: 'synth' },
      { id: 'output', x: 0.5, y: 0.96, label: '个性化路线', icon: '🎯', color: '#e8886a', group: 'output' },
    ];

    // 连线定义
    this.edges = [
      { from: 'input', to: 'rule_guard' },
      { from: 'rule_guard', to: 'expert_router' },
      // Wave 1 fan-out
      { from: 'expert_router', to: 'poi', group: 'wave1' },
      { from: 'expert_router', to: 'food', group: 'wave1' },
      { from: 'expert_router', to: 'weather', group: 'wave1' },
      { from: 'expert_router', to: 'destination', group: 'wave1' },
      // Wave 1 → Wave 2
      { from: 'poi', to: 'traffic', group: 'wave12' },
      { from: 'poi', to: 'hotel', group: 'wave12' },
      { from: 'food', to: 'local', group: 'wave12' },
      { from: 'weather', to: 'budget', group: 'wave12' },
      // Wave 2 → Review
      { from: 'traffic', to: 'review', group: 'wave2' },
      { from: 'hotel', to: 'review', group: 'wave2' },
      { from: 'local', to: 'review', group: 'wave2' },
      { from: 'budget', to: 'review', group: 'wave2' },
      // Flow
      { from: 'review', to: 'emergence' },
      { from: 'emergence', to: 'synthesizer' },
      { from: 'synthesizer', to: 'output' },
    ];

    this._resize();
    window.addEventListener('resize', () => this._resize());
    this._animate();
  }

  _resize() {
    if (!this.container) return;
    const rect = this.container.getBoundingClientRect();
    this.w = rect.width;
    this.h = rect.height;
    this.canvas.width = this.w * this.dpr;
    this.canvas.height = this.h * this.dpr;
    this.canvas.style.width = this.w + 'px';
    this.canvas.style.height = this.h + 'px';
    this.ctx.scale(this.dpr, this.dpr);
  }

  _getNodePos(node) {
    return {
      x: node.x * this.w,
      y: node.y * this.h,
    };
  }

  _getNodeById(id) {
    return this.nodes.find(n => n.id === id);
  }

  /**
   * 设置节点状态：'idle' | 'active' | 'done'
   */
  setNodeState(nodeId, state) {
    this.nodeStates[nodeId] = state;
  }

  /**
   * 设置当前活跃节点（带动画脉冲）
   */
  setActiveNode(nodeId) {
    this.activeNode = nodeId;
  }

  /**
   * 批量设置节点状态（从 SSE 事件）
   */
  updateFromAgentEvent(event) {
    const agentMap = {
      'rule_guard': 'rule_guard',
      'expert_router': 'expert_router',
      'poi': 'poi', 'food': 'food', 'weather': 'weather', 'destination': 'destination',
      'traffic': 'traffic', 'hotel': 'hotel', 'local_expert': 'local', 'budget_hacker': 'budget',
      'review': 'review', 'emergence_check': 'emergence',
      'synthesizer': 'synthesizer', 'live_itinerary': 'output',
    };
    const nodeId = agentMap[event.agent] || event.agent;
    if (event.status === 'active') {
      this.setActiveNode(nodeId);
      this.setNodeState(nodeId, 'active');
    } else if (event.status === 'done') {
      this.setNodeState(nodeId, 'done');
    }
  }

  _drawEdge(from, to, progress = 0, isActive = false) {
    const ctx = this.ctx;
    const f = this._getNodePos(from);
    const t = this._getNodePos(to);

    ctx.beginPath();
    ctx.moveTo(f.x, f.y);
    ctx.lineTo(t.x, t.y);

    if (isActive) {
      ctx.strokeStyle = 'rgba(106, 158, 200, 0.6)';
      ctx.lineWidth = 2;
      ctx.setLineDash([]);
    } else {
      ctx.strokeStyle = 'rgba(160, 152, 136, 0.15)';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // Flow particles on active edges
    if (isActive && progress > 0) {
      const px = f.x + (t.x - f.x) * progress;
      const py = f.y + (t.y - f.y) * progress;
      ctx.beginPath();
      ctx.arc(px, py, 3, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(106, 158, 200, 0.8)';
      ctx.fill();
    }
  }

  _drawNode(node) {
    const ctx = this.ctx;
    const pos = this._getNodePos(node);
    const state = this.nodeStates[node.id] || 'idle';
    const isActive = this.activeNode === node.id;
    const nodeR = Math.min(this.w * 0.028, 18);

    // Glow for active node
    if (isActive) {
      const glowR = nodeR + 8 + Math.sin(this.time * 3) * 4;
      const gradient = ctx.createRadialGradient(pos.x, pos.y, nodeR, pos.x, pos.y, glowR);
      gradient.addColorStop(0, node.color + '40');
      gradient.addColorStop(1, node.color + '00');
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, glowR, 0, Math.PI * 2);
      ctx.fillStyle = gradient;
      ctx.fill();
    }

    // Node circle
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, nodeR, 0, Math.PI * 2);

    if (state === 'done') {
      ctx.fillStyle = '#6aaa6a';
      ctx.strokeStyle = '#5a9a5a';
    } else if (state === 'active') {
      ctx.fillStyle = node.color;
      ctx.strokeStyle = node.color;
    } else {
      ctx.fillStyle = '#faf7f2';
      ctx.strokeStyle = 'rgba(0,0,0,0.1)';
    }
    ctx.lineWidth = 2;
    ctx.fill();
    ctx.stroke();

    // Icon
    const fontSize = Math.max(10, nodeR * 0.8);
    ctx.font = `${fontSize}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = state === 'idle' ? '#a09888' : '#fff';
    ctx.fillText(node.icon, pos.x, pos.y);

    // Label
    ctx.font = `600 ${Math.max(8, this.w * 0.012)}px -apple-system, "PingFang SC", sans-serif`;
    ctx.fillStyle = state === 'idle' ? '#a09888' : '#3a3530';
    ctx.textAlign = 'center';
    ctx.fillText(node.label, pos.x, pos.y + nodeR + 14);

    // Status indicator
    if (state === 'active') {
      ctx.beginPath();
      ctx.arc(pos.x + nodeR - 2, pos.y - nodeR + 2, 4, 0, Math.PI * 2);
      ctx.fillStyle = '#6a9ec8';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    } else if (state === 'done') {
      ctx.beginPath();
      ctx.arc(pos.x + nodeR - 2, pos.y - nodeR + 2, 4, 0, Math.PI * 2);
      ctx.fillStyle = '#6aaa6a';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  }

  _animate() {
    this.time += 0.016;
    this._draw();
    requestAnimationFrame(() => this._animate());
  }

  _draw() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.w, this.h);

    // Draw edges
    const flowProgress = (this.time * 0.5) % 1;
    for (const edge of this.edges) {
      const fromNode = this._getNodeById(edge.from);
      const toNode = this._getNodeById(edge.to);
      if (!fromNode || !toNode) continue;

      const fromState = this.nodeStates[edge.from] || 'idle';
      const toState = this.nodeStates[edge.to] || 'idle';
      const isActive = fromState === 'active' || toState === 'active' ||
                       (fromState === 'done' && toState !== 'idle');
      this._drawEdge(fromNode, toNode, isActive ? flowProgress : 0, isActive);
    }

    // Draw nodes
    for (const node of this.nodes) {
      this._drawNode(node);
    }

    // Title
    ctx.font = '600 11px -apple-system, "PingFang SC", sans-serif';
    ctx.fillStyle = '#a09888';
    ctx.textAlign = 'left';
    ctx.fillText('MoE 多专家混合架构', 8, 14);
  }

  /**
   * 重置所有节点状态
   */
  reset() {
    this.nodeStates = {};
    this.activeNode = null;
    this.particles = [];
  }
}