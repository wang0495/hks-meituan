/**
 * CityFlow 状态管理
 *
 * 发布-订阅模式的响应式状态管理，包含：
 * - 路线数据管理
 * - POI 选择状态
 * - 时间轴播放状态
 * - 加载与错误状态
 * - 事件监听与批量更新
 */

// ---------------------------------------------------------------------------
//  Event Emitter 基类
// ---------------------------------------------------------------------------

class EventEmitter {
  constructor() {
    this._listeners = {};
    this._onceListeners = {};
  }

  /**
   * 注册事件监听。
   * @param {string}  event
   * @param {function} callback
   * @returns {function} 取消监听的函数
   */
  on(event, callback) {
    if (!this._listeners[event]) {
      this._listeners[event] = [];
    }
    this._listeners[event].push(callback);

    var self = this;
    return function off() {
      self.off(event, callback);
    };
  }

  /**
   * 注册一次性事件监听。
   * @param {string}  event
   * @param {function} callback
   */
  once(event, callback) {
    if (!this._onceListeners[event]) {
      this._onceListeners[event] = [];
    }
    this._onceListeners[event].push(callback);
  }

  /**
   * 移除事件监听。
   * @param {string}  event
   * @param {function} callback
   */
  off(event, callback) {
    if (this._listeners[event]) {
      this._listeners[event] = this._listeners[event].filter(function (cb) {
        return cb !== callback;
      });
    }
    if (this._onceListeners[event]) {
      this._onceListeners[event] = this._onceListeners[event].filter(function (cb) {
        return cb !== callback;
      });
    }
  }

  /**
   * 触发事件。
   * @param {string}  event
   * @param {*}       data
   */
  emit(event, data) {
    var i;

    if (this._listeners[event]) {
      var callbacks = this._listeners[event].slice();
      for (i = 0; i < callbacks.length; i++) {
        try {
          callbacks[i](data);
        } catch (err) {
          console.error('[EventEmitter] listener error on "' + event + '":', err);
        }
      }
    }

    if (this._onceListeners[event]) {
      var onceCallbacks = this._onceListeners[event].slice();
      this._onceListeners[event] = [];
      for (i = 0; i < onceCallbacks.length; i++) {
        try {
          onceCallbacks[i](data);
        } catch (err) {
          console.error('[EventEmitter] once-listener error on "' + event + '":', err);
        }
      }
    }
  }

  /** 移除所有监听 */
  removeAllListeners(event) {
    if (event) {
      delete this._listeners[event];
      delete this._onceListeners[event];
    } else {
      this._listeners = {};
      this._onceListeners = {};
    }
  }
}

// ---------------------------------------------------------------------------
//  时间工具
// ---------------------------------------------------------------------------

function parseTimeToMinutes(timeStr) {
  if (!timeStr || typeof timeStr !== 'string') return 0;
  var parts = timeStr.split(':');
  if (parts.length < 2) return 0;
  return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
}

function minutesToTimeStr(minutes) {
  var h = Math.floor(minutes / 60) % 24;
  var m = Math.floor(minutes % 60);
  return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0');
}

// ---------------------------------------------------------------------------
//  应用状态
// ---------------------------------------------------------------------------

class AppState extends EventEmitter {
  constructor() {
    super();

    // --- 路线 ---
    /** @type {object|null} 完整路线数据，结构 { route: [...], narrative: {...} } */
    this.route = null;
    /** @type {string|null} 当前路线的 session ID */
    this.routeId = null;

    // --- POI ---
    /** @type {string|null} 当前选中的 POI ID */
    this.selectedPoi = null;
    /** @type {string|null} 当前 hover 的 POI ID */
    this.hoveredPoi = null;

    // --- 时间轴 ---
    /** @type {number} 滑块位置 0-1000 */
    this.timelinePosition = 0;
    /** @type {boolean} 是否正在播放 */
    this.isPlaying = false;
    /** @type {object} 时间范围 { start: 分钟数, end: 分钟数 } */
    this.timeRange = { start: 0, end: 0 };
    /** @type {number|null} 播放定时器 ID */
    this._playInterval = null;

    // --- UI ---
    /** @type {boolean} 是否加载中 */
    this.loading = false;
    /** @type {string|null} 加载阶段描述 */
    this.loadingMessage = '';
    /** @type {object|null} 当前错误 { code, message, details } */
    this.error = null;

    // --- 撤销 ---
    /** @type {object[]} 历史快照栈 */
    this._history = [];
    /** @type {number} 最大历史深度 */
    this._maxHistory = 20;
  }

  // =========================================================================
  //  路线
  // =========================================================================

  /**
   * 设置完整路线数据。
   * @param {object}  routeData - { route: [...], narrative: {...} }
   * @param {string}  [routeId]
   */
  setRoute(routeData, routeId) {
    this._pushHistory();
    this.route = routeData;
    this.routeId = routeId || this.routeId;
    this.error = null;
    this.emit('route-updated', this.route);
    this._recalculateTimeRange();
  }

  /**
   * 获取路线步骤列表。
   * @returns {object[]}
   */
  getSteps() {
    return (this.route && this.route.route) || [];
  }

  /**
   * 获取路线步骤数。
   * @returns {number}
   */
  getStepCount() {
    return this.getSteps().length;
  }

  /**
   * 根据 POI ID 获取步骤。
   * @param {string}  poiId
   * @returns {object|null}
   */
  getStepByPoiId(poiId) {
    var steps = this.getSteps();
    for (var i = 0; i < steps.length; i++) {
      if (steps[i].poi && steps[i].poi.id === poiId) {
        return steps[i];
      }
    }
    return null;
  }

  /**
   * 重排路线步骤（拖拽后调用）。
   * @param {string[]} poiIds - 新顺序的 POI ID 列表
   */
  reorderSteps(poiIds) {
    this._pushHistory();
    var oldSteps = this.getSteps();
    var reordered = [];
    for (var i = 0; i < poiIds.length; i++) {
      for (var j = 0; j < oldSteps.length; j++) {
        if (oldSteps[j].poi && oldSteps[j].poi.id === poiIds[i]) {
          reordered.push(oldSteps[j]);
          break;
        }
      }
    }

    // 重新计算时间
    this._recalculateTimes(reordered);

    if (this.route) {
      this.route.route = reordered;
    }

    this.emit('route-reordered', reordered);
    this.emit('route-updated', this.route);
    this._recalculateTimeRange();
  }

  /**
   * 清除路线。
   */
  clearRoute() {
    this.route = null;
    this.routeId = null;
    this.selectedPoi = null;
    this.hoveredPoi = null;
    this.timelinePosition = 0;
    this.stopPlayback();
    this._history = [];
    this.emit('route-cleared');
    this.emit('route-updated', null);
  }

  // =========================================================================
  //  POI 选择
  // =========================================================================

  /**
   * 选中一个 POI。
   * @param {string|null} poiId
   */
  selectPoi(poiId) {
    var prev = this.selectedPoi;
    this.selectedPoi = poiId;
    if (prev !== poiId) {
      this.emit('poi-selected', poiId);
    }
  }

  /**
   * hover 一个 POI。
   * @param {string|null} poiId
   */
  hoverPoi(poiId) {
    var prev = this.hoveredPoi;
    this.hoveredPoi = poiId;
    if (prev !== poiId) {
      this.emit('poi-hovered', poiId);
    }
  }

  // =========================================================================
  //  时间轴
  // =========================================================================

  /**
   * 设置时间轴位置。
   * @param {number} position - 0 ~ 1000
   */
  setTimelinePosition(position) {
    this.timelinePosition = Math.max(0, Math.min(1000, position));
    this.emit('timeline-changed', this.timelinePosition);
  }

  /**
   * 获取当前时间轴对应的分钟数。
   * @returns {number}
   */
  getCurrentMinutes() {
    var range = this.timeRange.end - this.timeRange.start || 1;
    return this.timeRange.start + (this.timelinePosition / 1000) * range;
  }

  /**
   * 获取当前时间轴对应的时间字符串。
   * @returns {string}
   */
  getCurrentTimeStr() {
    return minutesToTimeStr(Math.round(this.getCurrentMinutes()));
  }

  /**
   * 开始播放。
   */
  startPlayback() {
    if (this.isPlaying) return;
    this.isPlaying = true;
    this.emit('playback-started');

    var self = this;
    this._playInterval = setInterval(function () {
      var next = self.timelinePosition + 2;
      if (next > 1000) {
        next = 0;
      }
      self.setTimelinePosition(next);
    }, 100);
  }

  /**
   * 停止播放。
   */
  stopPlayback() {
    if (!this.isPlaying) return;
    this.isPlaying = false;
    if (this._playInterval !== null) {
      clearInterval(this._playInterval);
      this._playInterval = null;
    }
    this.emit('playback-stopped');
  }

  /**
   * 切换播放/暂停。
   */
  togglePlayback() {
    if (this.isPlaying) {
      this.stopPlayback();
    } else {
      this.startPlayback();
    }
  }

  // =========================================================================
  //  加载与错误
  // =========================================================================

  /**
   * 设置加载状态。
   * @param {boolean}       loading
   * @param {string}        [message]
   */
  setLoading(loading, message) {
    this.loading = loading;
    this.loadingMessage = message || '';
    this.emit('loading-changed', { loading: loading, message: this.loadingMessage });
  }

  /**
   * 设置错误。
   * @param {object|null}   error - { code, message, details } 或 null 清除
   */
  setError(error) {
    this.error = error;
    this.emit('error', error);
  }

  /**
   * 清除错误。
   */
  clearError() {
    this.error = null;
    this.emit('error', null);
  }

  /**
   * 从 APIError 设置错误。
   * @param {APIError}  err
   */
  setAPIError(err) {
    this.setError({
      code: err.code || 1000,
      message: err.message || '请求失败',
      details: err.details || {},
    });
  }

  // =========================================================================
  //  撤销
  // =========================================================================

  /**
   * 撤销到上一个路线状态。
   * @returns {boolean} 是否成功撤销
   */
  undo() {
    if (this._history.length === 0) return false;
    var snapshot = this._history.pop();
    this.route = snapshot.route;
    this.routeId = snapshot.routeId;
    this.emit('route-updated', this.route);
    this._recalculateTimeRange();
    return true;
  }

  /**
   * 是否可以撤销。
   * @returns {boolean}
   */
  get canUndo() {
    return this._history.length > 0;
  }

  // =========================================================================
  //  SSE 集成辅助
  // =========================================================================

  /**
   * 为 SSE 规划请求生成回调选项，可直接传给 APIClient.planRoute()。
   *
   * @returns {object} { onPhase, onStep, onDone }
   */
  createPlanCallbacks() {
    var self = this;
    return {
      onPhase: function (data) {
        self.setLoading(true, data.message || '处理中...');
        self.emit('plan-phase', data);
      },
      onStep: function (data) {
        self.emit('plan-step', data);
      },
      onDone: function (data) {
        self.setRoute(data.full_route, data.route_id);
        self.setLoading(false);
        self.emit('plan-done', data);
      },
    };
  }

  // =========================================================================
  //  快照（调试用）
  // =========================================================================

  /**
   * 导出当前状态快照。
   * @returns {object}
   */
  snapshot() {
    return {
      route: this.route,
      routeId: this.routeId,
      selectedPoi: this.selectedPoi,
      timelinePosition: this.timelinePosition,
      isPlaying: this.isPlaying,
      loading: this.loading,
      loadingMessage: this.loadingMessage,
      error: this.error,
    };
  }

  // =========================================================================
  //  内部方法
  // =========================================================================

  /** 保存路线快照到历史栈 */
  _pushHistory() {
    if (!this.route) return;
    this._history.push({
      route: JSON.parse(JSON.stringify(this.route)),
      routeId: this.routeId,
    });
    if (this._history.length > this._maxHistory) {
      this._history.shift();
    }
  }

  /** 从路线数据重新计算时间范围 */
  _recalculateTimeRange() {
    var steps = this.getSteps();
    if (steps.length === 0) {
      this.timeRange = { start: 0, end: 0 };
      return;
    }

    var firstTime = parseTimeToMinutes(steps[0].arrival_time);
    var lastStep = steps[steps.length - 1];
    var lastTime = parseTimeToMinutes(lastStep.departure_time || lastStep.arrival_time);

    if (lastTime <= firstTime) {
      lastTime = firstTime + steps.length * 60;
    }

    this.timeRange = { start: firstTime, end: lastTime };
    this.emit('time-range-updated', this.timeRange);
  }

  /** 拖拽重排后重新计算时间 */
  _recalculateTimes(steps) {
    if (steps.length === 0) return;

    var currentMin = parseTimeToMinutes(steps[0].arrival_time);
    if (currentMin <= 0) currentMin = 9 * 60; // 默认 09:00

    for (var i = 0; i < steps.length; i++) {
      steps[i].index = i + 1;
      steps[i].arrival_time = minutesToTimeStr(currentMin);
      var duration = steps[i].duration_minutes || 45;
      steps[i].departure_time = minutesToTimeStr(currentMin + duration);
      currentMin += duration + 15; // 15 分钟路程
    }
  }
}

// ---------------------------------------------------------------------------
//  全局单例 + 导出
// ---------------------------------------------------------------------------

/** 全局应用状态单例 */
var appState = new AppState();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { AppState, appState, EventEmitter };
} else {
  window.AppState = AppState;
  window.appState = appState;
  window.EventEmitter = EventEmitter;
}
