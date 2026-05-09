/**
 * app.js — CityFlow 应用主模块
 *
 * 职责：
 * - 初始化 Chart3D（地图）、LLMChat（对话）
 * - 初始化 POIList（POI 列表组件）、Timeline（时间轴组件）
 * - 负责 POI 列表 ↔ 地图的双向同步
 * - 提供 SSE 事件处理回调
 * - 异常告警弹窗管理
 * - 拖拽重排后的时间重算
 */

const API_BASE = 'http://127.0.0.1:8002';

// ================================================================
// 全局状态
// ================================================================

const appState = {
  chart: null,      // Chart3D 实例（地图）
  chat: null,       // LLMChat 实例
  poiList: null,    // POIList 实例
  timeline: null,   // Timeline 实例

  route: null,        // 完整路线对象
  routeId: null,      // 当前路线 ID
  steps: [],          // 步骤数组

  narrative: null,
  selectedIndex: -1,
  isPlaying: false,
  playTimer: null,
  playProgress: 0,
};

// ================================================================
// 工具函数
// ================================================================

/** "09:30" -> 分钟数 570 */
function parseTimeToMinutes(timeStr) {
  if (!timeStr || typeof timeStr !== 'string') return 0;
  const parts = timeStr.split(':');
  if (parts.length < 2) return 0;
  return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
}

/** 570 -> "09:30" */
function minutesToTimeStr(minutes) {
  const h = Math.floor(minutes / 60) % 24;
  const m = Math.floor(minutes % 60);
  return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0');
}

/**
 * 根据步骤数组重算到达/离开时间（前端预估）
 * @param {Array} steps
 * @returns {Array}
 */
function recalculateTimestamps(steps) {
  if (!steps || !steps.length) return steps;

  let currentMin = parseTimeToMinutes(steps[0].arrival_time);
  if (currentMin <= 0) currentMin = 9 * 60; // 默认 09:00

  return steps.map((step, i) => {
    step.index = i + 1;
    step.arrival_time = minutesToTimeStr(currentMin);
    const duration = step.duration_minutes || (step.poi && step.poi.avg_stay_min) || 45;
    step.departure_time = minutesToTimeStr(currentMin + duration);
    currentMin += duration + 15; // 15 分钟路程
    return step;
  });
}

// ================================================================
// 异常告警系统
// ================================================================

/** 异常类型对应的图标和颜色 */
const ANOMALY_CONFIG = {
  weather: { icon: '\u26C5', color: '#3498db' },   // 🌥
  fatigue: { icon: '\uD83D\uDE30', color: '#e67e22' }, // 😰
  emotion: { icon: '\uD83D\uDE15', color: '#9b59b6' }, // 😕
  time:    { icon: '\u23F0', color: '#e74c3c' },       // ⏰
};

/**
 * 显示异常告警弹窗
 * @param {string} message - 告警消息
 * @param {string} type - 类型: weather/fatigue/emotion/time
 * @param {string} severity - 严重程度: high/yellow/info
 */
function showAnomalyAlert(message, type, severity) {
  const container = document.getElementById('anomaly-container');
  if (!container) return;

  const cfg = ANOMALY_CONFIG[type] || { icon: '\u26A0', color: '#f39c12' };
  const severityColors = {
    high: '#e74c3c',
    yellow: '#f39c12',
    info: '#3498db',
  };
  const borderColor = severityColors[severity] || severityColors.info;

  const alert = document.createElement('div');
  alert.className = 'anomaly-alert';
  alert.style.borderLeftColor = borderColor;
  alert.innerHTML =
    '<span class="anomaly-icon">' + cfg.icon + '</span>' +
    '<span class="anomaly-text">' + message + '</span>' +
    '<button class="anomaly-close" aria-label="关闭">&times;</button>';

  // 点击关闭
  alert.querySelector('.anomaly-close').addEventListener('click', function() {
    dismissAnomalyAlert(alert);
  });

  // 点击整个 alert 也可关闭
  alert.addEventListener('click', function() {
    dismissAnomalyAlert(alert);
  });

  container.appendChild(alert);

  // 8 秒后自动关闭
  alert._dismissTimer = setTimeout(function() {
    dismissAnomalyAlert(alert);
  }, 8000);
}

/**
 * 关闭单个异常告警
 * @param {HTMLElement} alert
 */
function dismissAnomalyAlert(alert) {
  if (alert._dismissTimer) {
    clearTimeout(alert._dismissTimer);
    alert._dismissTimer = null;
  }
  alert.classList.add('anomaly-dismissing');
  setTimeout(function() {
    if (alert.parentNode) alert.parentNode.removeChild(alert);
  }, 300);
}

// ================================================================
// SSE 事件处理
// ================================================================

/**
 * 处理 SSE 事件（由 submitIntent 中的读取循环调用）
 * @param {string} type - 事件类型
 * @param {Object} data - 事件数据
 */
function handleSSEEvent(type, data) {
  const loadingText = document.getElementById('loadingText');
  const phaseIcon = document.getElementById('phaseIndicator');

  switch (type) {
    case 'phase':
      // 阶段更新：显示加载指示器
      loadingText.textContent = data.message || '处理中...';
      if (phaseIcon) {
        phaseIcon.className = 'phase-indicator phase-' + (data.phase || 'unknown');
      }
      break;

    case 'step':
      // 逐步追加 POI 卡片
      appState.steps.push(data);
      if (appState.poiList) {
        appState.poiList.addStep(data);
      } else {
        renderPOIListFallback();
      }
      // 更新地图路线标记
      if (appState.chart && typeof appState.chart.addRouteMarker === 'function') {
        appState.chart.addRouteMarker(data);
      }
      break;

    case 'step_update':
      // 更新特定步骤的叙述文案
      if (data.index != null && data.description && appState.poiList) {
        appState.poiList.updateCardNarrative(data.index, data.description);
      }
      break;

    case 'budget':
      renderBudget(data);
      break;

    case 'anomaly':
      // 异常告警
      showAnomalyAlert(
        data.message || '检测到异常',
        data.type || 'info',
        data.severity || 'info'
      );
      break;

    case 'done':
      appState.routeId = data.route_id;
      if (data.full_route) {
        appState.route = data.full_route;
        appState.narrative = data.full_route.narrative;
        renderNarrative();
        renderEmotionCurve(data.full_route.emotion_curve || []);
        renderTimelineInfo();
        // 更新地图路线标记（完整路线）
        if (appState.chart && typeof appState.chart.updateMarkers === 'function') {
          appState.chart.updateMarkers(appState.steps);
        }
        if (appState.poiList) {
          // 确保列表显示所有步骤
          appState.poiList.render(appState.steps);
        }
      }
      document.getElementById('dialogueBar').classList.add('active');
      // 隐藏 loading
      document.getElementById('loadingOverlay').classList.remove('active');
      document.getElementById('submitBtn').disabled = false;
      break;

    case 'error':
      showAnomalyAlert(data.error || '规划失败', 'time', 'high');
      document.getElementById('loadingOverlay').classList.remove('active');
      document.getElementById('submitBtn').disabled = false;
      break;
  }
}

/**
 * 回退：无 POIList 实例时的简单渲染
 */
function renderPOIListFallback() {
  const list = document.getElementById('poiList');
  if (!list) return;
  if (appState.steps.length === 0) {
    list.innerHTML = '<div class="empty-state">正在规划路线...</div>';
    return;
  }
  // 简易渲染（仅用于 fallback）
  list.innerHTML = appState.steps.map(function(step, i) {
    var poi = step.poi;
    var mood = getMoodClass(poi);
    return '<div class="poi-card ' + mood + '">' +
      '<div class="poi-index">' + (i + 1) + '</div>' +
      '<div class="poi-body">' +
        '<div class="poi-top"><span class="poi-name">' + escapeHtml(poi.name) + '</span>' +
        '<span class="poi-time">' + (step.arrival_time || '') + '</span></div>' +
      '</div></div>';
  }).join('');
}

// ================================================================
// 注入 Chart3D 路线标记方法
// ================================================================

/**
 * 在 Chart3D 实例上添加路线标记支持
 * 这样 app.js 无需修改 Chart3D 类即可实现 chart.highlightMarker / flyTo / updateMarkers
 * @param {Chart3D} chartInstance
 */
function injectRouteMarkers(chartInstance) {
  if (!chartInstance) return;

  /** @type {Array} 路线标记的 mesh 对象 */
  chartInstance._routeMeshes = [];
  /** @type {Object|null} 当前高亮的路线 POI */
  chartInstance._highlightedRoutePoi = null;

  /**
   * 高亮路线上的某个 POI 标记
   * @param {string} poiId
   */
  chartInstance.highlightMarker = function(poiId) {
    if (!this._routeMeshes || !this._routeMeshes.length) return;
    this._routeMeshes.forEach(function(mesh) {
      var isMatch = mesh.userData.poiId === poiId;
      if (isMatch) {
        mesh.material.emissive.setHex(0xe94560);
        mesh.material.emissiveIntensity = 0.6;
        mesh.scale.set(1.5, 1.5, 1.5);
      } else {
        mesh.material.emissive.setHex(0x000000);
        mesh.material.emissiveIntensity = 0;
        mesh.scale.set(1, 1, 1);
      }
    });
    this._highlightedRoutePoi = poiId;
  };

  /**
   * 飞行到指定 POI
   * @param {string} poiId
   */
  chartInstance.flyTo = function(poiId) {
    if (!this.map || !this.data) return;
    // 在 POI 数据中查找
    var target = null;
    if (this._routePoData) {
      target = this._routePoData.find(function(p) { return p.id === poiId; });
    }
    if (!target) {
      target = this.data.find(function(p) { return p.id === poiId; });
    }
    if (target && target.lng && target.lat) {
      this.map.setZoomAndCenter(15, [target.lng, target.lat]);
      // 弹出 InfoWindow
      if (typeof showPOIDetail === 'function') {
        showPOIDetail(target);
      }
    }
  };

  /**
   * 添加单个路线标记
   * @param {Object} step
   */
  chartInstance.addRouteMarker = function(step) {
    if (!this.scene || !this.glReady || !this.customCoords) return;
    var poi = step.poi;
    if (!poi || !poi.lng || !poi.lat) return;

    if (!this._routePoData) this._routePoData = [];
    this._routePoData.push(poi);

    var coords = this.customCoords.lngLatsToCoords([[poi.lng, poi.lat]]);
    if (!coords || !coords[0]) return;

    var index = this._routePoData.length;
    var geometry = new THREE.SphereGeometry(80, 16, 16);
    var material = new THREE.MeshPhongMaterial({
      color: 0xe94560,
      emissive: 0xe94560,
      emissiveIntensity: 0.3,
      transparent: true,
      opacity: 0.95,
    });
    var mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(coords[0][0], coords[0][1], 40);
    mesh.userData = { poiId: poi.id, poi: poi, index: index };
    this.scene.add(mesh);
    this._routeMeshes.push(mesh);

    // 添加序号标签（Sprite）
    var canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 64;
    var ctx = canvas.getContext('2d');
    ctx.fillStyle = '#e94560';
    ctx.beginPath();
    ctx.arc(32, 32, 28, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 28px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(String(index), 32, 32);

    var texture = new THREE.CanvasTexture(canvas);
    var spriteMat = new THREE.SpriteMaterial({ map: texture, depthTest: false });
    var sprite = new THREE.Sprite(spriteMat);
    sprite.position.set(coords[0][0], coords[0][1], 120);
    sprite.scale.set(200, 200, 1);
    this.scene.add(sprite);
    this._routeLabelSprites = this._routeLabelSprites || [];
    this._routeLabelSprites.push(sprite);

    this.map.render();
  };

  /**
   * 根据步骤数组更新所有路线标记
   * @param {Array} steps
   */
  chartInstance.updateMarkers = function(steps) {
    // 清除旧路线标记
    this.clearRouteMarkers();
    // 逐个添加
    var self = this;
    steps.forEach(function(step) {
      self.addRouteMarker(step);
    });
  };

  /**
   * 清除路线标记
   */
  chartInstance.clearRouteMarkers = function() {
    if (this._routeMeshes) {
      this._routeMeshes.forEach(function(mesh) {
        if (mesh.parent) mesh.parent.remove(mesh);
        mesh.geometry.dispose();
        mesh.material.dispose();
      });
      this._routeMeshes = [];
    }
    if (this._routeLabelSprites) {
      this._routeLabelSprites.forEach(function(sprite) {
        if (sprite.parent) sprite.parent.remove(sprite);
        sprite.material.map.dispose();
        sprite.material.dispose();
      });
      this._routeLabelSprites = [];
    }
    this._routePoData = null;
    if (this.map) this.map.render();
  };

  // 拦截 Chart3D 的 click 事件，增加 marker-click 发射
  var origClickListener = chartInstance._initInteraction;
  chartInstance._initInteraction = function() {
    if (origClickListener) origClickListener.call(chartInstance);

    // 在原有 click 基础上增加路线标记射线检测
    var container = chartInstance.container;
    container.addEventListener('click', function(e) {
      if (!chartInstance.glReady || !chartInstance._routeMeshes || !chartInstance._routeMeshes.length) return;
      var rect = container.getBoundingClientRect();
      var mouse = new THREE.Vector2();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      var raycaster = new THREE.Raycaster();
      raycaster.setFromCamera(mouse, chartInstance.camera);
      var intersects = raycaster.intersectObjects(chartInstance._routeMeshes);
      if (intersects.length > 0) {
        var poi = intersects[0].object.userData.poi;
        if (poi && poi.id) {
          container.dispatchEvent(new CustomEvent('marker-click', {
            detail: { poiId: poi.id, poi: poi },
            bubbles: true,
          }));
        }
      }
    });
  };
}

// ================================================================
// UI 渲染函数（用于没有 POIList/Timeline 实例时的回退）
// ================================================================

function escapeHtml(text) {
  var el = document.createElement('span');
  el.textContent = text || '';
  return el.innerHTML;
}

function getMoodClass(poi) {
  var et = poi.emotion_tags || {};
  if (et.excitement > 0.6) return 'mood-exciting';
  if (et.tranquility > 0.6) return 'mood-calm';
  if (et.culture_depth > 0.6) return 'mood-cultural';
  if (et.physical_demand > 0.6) return 'mood-nature';
  return '';
}

function renderNarrative() {
  if (!appState.narrative) return;
  document.getElementById('narrativeOpening').textContent = appState.narrative.opening || '';
  document.getElementById('narrativeClosing').textContent = appState.narrative.closing || '';
}

function renderEmotionCurve(curve) {
  if (!curve || curve.length === 0) return;
  document.getElementById('curveContainer').style.display = 'block';
  var canvas = document.getElementById('emotionCurve');
  var ctx = canvas.getContext('2d');
  var dpr = window.devicePixelRatio || 1;
  canvas.width = canvas.offsetWidth * dpr;
  canvas.height = canvas.offsetHeight * dpr;
  ctx.scale(dpr, dpr);
  var w = canvas.offsetWidth, h = canvas.offsetHeight;
  var pad = { top: 10, right: 10, bottom: 20, left: 30 };
  var plotW = w - pad.left - pad.right, plotH = h - pad.top - pad.bottom;
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = '#2a2a4a'; ctx.lineWidth = 0.5;
  for (var i = 0; i <= 4; i++) {
    var y = pad.top + (plotH / 4) * i;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(w - pad.right, y); ctx.stroke();
  }
  var emotions = [
    { key: 'excitement', color: '#e94560', label: '\u5174\u594B' },
    { key: 'tranquility', color: '#3498db', label: '\u5B81\u9759' },
    { key: 'culture_depth', color: '#9b59b6', label: '\u6587\u5316' },
  ];
  emotions.forEach(function(emotion) {
    ctx.strokeStyle = emotion.color; ctx.lineWidth = 2; ctx.beginPath();
    var started = false;
    curve.forEach(function(point, i) {
      var x = pad.left + (i / (curve.length - 1)) * plotW;
      var val = point[emotion.key] || 0;
      var y = pad.top + plotH * (1 - val);
      if (!started) { ctx.moveTo(x, y); started = true; } else { ctx.lineTo(x, y); }
    });
    ctx.stroke();
  });
  var legendY = h - 8; var legendX = pad.left;
  emotions.forEach(function(emotion) {
    ctx.fillStyle = emotion.color; ctx.fillRect(legendX, legendY - 6, 12, 3);
    ctx.fillStyle = '#888'; ctx.font = '10px sans-serif';
    ctx.fillText(emotion.label, legendX + 16, legendY);
    legendX += 60;
  });
}

function renderBudget(budget) {
  if (!budget) return;
  document.getElementById('budgetBar').style.display = 'flex';
  document.getElementById('budgetCost').textContent = '\u00A5' + (budget.total || 0);
  document.getElementById('budgetLeverage').textContent = (budget.leverage_summary && budget.leverage_summary['\u9AD8']) || 0 + '个';
  if (budget.total_hours) document.getElementById('budgetTime').textContent = budget.total_hours + 'h';
  if (budget.total_steps) document.getElementById('budgetSteps').textContent = budget.total_steps + '步';
}

function renderTimelineInfo() {
  if (appState.steps.length === 0) return;
  document.getElementById('timelineContainer').style.display = 'block';
  document.getElementById('timelineCurrentTime').textContent = appState.steps[0].arrival_time;
  document.getElementById('timelineEndTime').textContent = appState.steps[appState.steps.length - 1].departure_time;
  document.getElementById('timelineSteps').innerHTML = appState.steps.map(function(_, i) {
    return '<div class="timeline-step-dot ' + (i === 0 ? 'active' : '') + '"></div>';
  }).join('');
}

// ================================================================
// 初始化
// ================================================================

function initApp() {
  console.log('[app.js] initApp...');

  // 确保 DOM 元素就绪
  var chartContainer = document.getElementById('chart-container');
  if (chartContainer) {
    appState.chart = new Chart3D('chart-container', showTooltip, showPOIDetail);
    // 注入路线标记方法
    injectRouteMarkers(appState.chart);
  }

  // 初始化 POIList（如果存在）
  var poiListEl = document.getElementById('poiList');
  if (poiListEl && typeof POIList !== 'undefined') {
    try {
      appState.poiList = new POIList(poiListEl);
    } catch (e) {
      console.warn('[app.js] POIList init failed:', e);
    }
  }

  // 初始化 Timeline（如果存在）
  var timelineEl = document.getElementById('timelineContainer');
  if (timelineEl && typeof Timeline !== 'undefined') {
    try {
      appState.timeline = new Timeline(timelineEl);
    } catch (e) {
      console.warn('[app.js] Timeline init failed:', e);
    }
  }

  // 设置 POI 列表 ↔ 地图双向同步
  _setupDualViewSync();

  console.log('[app.js] initialized. chart:', !!appState.chart, 'poiList:', !!appState.poiList, 'timeline:', !!appState.timeline);
}

function _setupDualViewSync() {
  // POI 列表 → 地图
  if (appState.poiList && appState.chart) {
    appState.poiList.container.addEventListener('poi-click', function(e) {
      var detail = e.detail || {};
      if (detail.poiId && appState.chart.highlightMarker) {
        appState.chart.highlightMarker(detail.poiId);
      }
      if (detail.poiId && appState.chart.flyTo) {
        appState.chart.flyTo(detail.poiId);
      }
    });

    appState.poiList.container.addEventListener('poi-hover', function(e) {
      var detail = e.detail || {};
      if (detail.poiId && detail.hovered && appState.chart.highlightMarker) {
        appState.chart.highlightMarker(detail.poiId);
      } else if (!detail.hovered && appState.chart.highlightMarker) {
        appState.chart.highlightMarker(null);
      }
    });

    appState.poiList.container.addEventListener('poi-reorder', function(e) {
      var detail = e.detail || {};
      var newSteps = detail.steps || appState.poiList.getSteps();
      // 重算时间戳
      var recalculated = recalculateTimestamps(newSteps);
      appState.poiList.render(recalculated);
      // 更新地图标记
      if (appState.chart && appState.chart.updateMarkers) {
        appState.chart.updateMarkers(recalculated);
      }
      // 更新时间轴
      renderTimelineInfo();
      if (appState.timeline) {
        var startMin = parseTimeToMinutes(recalculated[0].arrival_time);
        var endMin = parseTimeToMinutes(recalculated[recalculated.length - 1].departure_time);
        appState.timeline.setTimeRange(startMin, endMin, recalculated);
      }
    });
  }

  // 地图 → POI 列表
  if (appState.chart) {
    var container = appState.chart.container;
    container.addEventListener('marker-click', function(e) {
      var detail = e.detail || {};
      if (detail.poiId && appState.poiList) {
        appState.poiList.highlightCard(detail.poiId);
        appState.poiList.scrollToCard(detail.poiId);
      }
    });
  }
}

// ================================================================
// LLMChat 初始化
// ================================================================

function initChat() {
  var chatMessages = document.getElementById('chat-messages');
  var chatInput = document.getElementById('chat-input');
  var chatSend = document.getElementById('chat-send');
  if (chatMessages && chatInput && chatSend && typeof LLMChat !== 'undefined') {
    try {
      appState.chat = new LLMChat(chatMessages, chatInput, chatSend);
    } catch (e) {
      console.warn('[app.js] LLMChat init failed:', e);
    }
  }
}

// ================================================================
// 在 DOM 就绪后初始化
// ================================================================

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function() {
    initApp();
    initChat();
    // 等地图加载完再加载 POI 数据
    setTimeout(async function() {
      if (appState.chart) {
        await appState.chart.loadData('珠海', '');
        await appState.chart.loadOrder('珠海', 1, null);
      }
    }, 2000);
  });
} else {
  initApp();
  initChat();
  setTimeout(async function() {
    if (appState.chart) {
      await appState.chart.loadData('珠海', '');
      await appState.chart.loadOrder('珠海', 1, null);
    }
  }, 2000);
}
