/**
 * particles.js — Canvas 粒子效果系统
 *
 * 在地图 Canvas 上叠加粒子效果，用于：
 * - 路线规划中的数据流动画
 * - Agent 活跃时的能量粒子
 * - 完成时的庆祝效果
 */

class ParticleSystem {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.particles = [];
    this.emitters = [];
    this.active = false;
  }

  /**
   * 添加沿路线的流动粒子
   * @param {Array} points - [{x, y}] 路线点
   * @param {Object} options - { color, count, speed }
   */
  addRouteFlow(points, options = {}) {
    if (!points || points.length < 2) return;
    const color = options.color || '232, 136, 106';
    const count = options.count || 20;
    const speed = options.speed || 0.002;

    for (let i = 0; i < count; i++) {
      this.particles.push({
        type: 'route',
        points: points,
        progress: Math.random(),
        speed: speed + Math.random() * speed,
        size: 2 + Math.random() * 3,
        color: color,
        alpha: 0.3 + Math.random() * 0.5,
      });
    }
    this.active = true;
  }

  /**
   * 添加能量爆发粒子（Agent 完成时）
   * @param {number} x - 爆发中心 X
   * @param {number} y - 爆发中心 Y
   * @param {string} color - RGB 颜色
   */
  addBurst(x, y, color = '106, 158, 200') {
    for (let i = 0; i < 30; i++) {
      const angle = (Math.PI * 2 / 30) * i + Math.random() * 0.5;
      const speed = 1 + Math.random() * 3;
      this.particles.push({
        type: 'burst',
        x: x, y: y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        size: 2 + Math.random() * 4,
        color: color,
        alpha: 0.8,
        life: 1.0,
        decay: 0.01 + Math.random() * 0.02,
      });
    }
    this.active = true;
  }

  /**
   * 添加环境粒子（持续的微光效果）
   * @param {number} count - 粒子数量
   */
  addAmbient(count = 30) {
    const w = this.canvas.width;
    const h = this.canvas.height;
    for (let i = 0; i < count; i++) {
      this.particles.push({
        type: 'ambient',
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.3,
        vy: -0.1 - Math.random() * 0.3,
        size: 1 + Math.random() * 2,
        color: '232, 200, 106',
        alpha: 0.1 + Math.random() * 0.2,
        life: 1.0,
        decay: 0.001 + Math.random() * 0.003,
      });
    }
    this.active = true;
  }

  /**
   * 清除所有粒子
   */
  clear() {
    this.particles = [];
    this.emitters = [];
    this.active = false;
  }

  /**
   * 更新和绘制粒子（每帧调用）
   */
  update() {
    if (!this.active || this.particles.length === 0) return;

    const ctx = this.ctx;
    const toRemove = [];

    for (let i = 0; i < this.particles.length; i++) {
      const p = this.particles[i];

      if (p.type === 'route') {
        // 沿路线流动
        p.progress += p.speed;
        if (p.progress >= 1) p.progress = 0;

        // 计算位置（线性插值）
        const totalLen = p.points.length - 1;
        const segIdx = Math.floor(p.progress * totalLen);
        const segProgress = (p.progress * totalLen) - segIdx;
        const p1 = p.points[Math.min(segIdx, totalLen)];
        const p2 = p.points[Math.min(segIdx + 1, totalLen)];
        const x = p1.x + (p2.x - p1.x) * segProgress;
        const y = p1.y + (p2.y - p1.y) * segProgress;

        ctx.beginPath();
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${p.color}, ${p.alpha})`;
        ctx.fill();
      }

      if (p.type === 'burst') {
        p.x += p.vx;
        p.y += p.vy;
        p.vy += 0.02; // gravity
        p.life -= p.decay;
        p.alpha = p.life * 0.8;

        if (p.life <= 0) {
          toRemove.push(i);
          continue;
        }

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size * p.life, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${p.color}, ${p.alpha})`;
        ctx.fill();
      }

      if (p.type === 'ambient') {
        p.x += p.vx;
        p.y += p.vy;
        p.life -= p.decay;
        p.alpha = p.life * 0.2;

        if (p.life <= 0 || p.y < -10) {
          toRemove.push(i);
          continue;
        }

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${p.color}, ${p.alpha})`;
        ctx.fill();
      }
    }

    // 移除死亡粒子
    for (let i = toRemove.length - 1; i >= 0; i--) {
      this.particles.splice(toRemove[i], 1);
    }

    if (this.particles.length === 0) {
      this.active = false;
    }
  }
}