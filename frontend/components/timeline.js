/**
 * Timeline - CityFlow 时间轴组件
 *
 * 功能：
 * - 播放/暂停 + 变速控制（0.5x / 1x / 2x / 4x）
 * - POI 时间标记
 * - requestAnimationFrame 平滑动画
 * - 键盘快捷键（空格播放/暂停，左右键微调）
 * - 进度分段（按 POI 到达时间分段高亮）
 * - ARIA 无障碍
 */
class Timeline {
  /**
   * @param {HTMLElement|string} container - 时间轴容器或其 ID
   */
  constructor(container) {
    this.container = typeof container === 'string'
      ? document.getElementById(container)
      : container;

    /** @type {number} 当前进度 0-1000 */
    this.position = 0;

    /** @type {boolean} */
    this.isPlaying = false;

    /** @type {number|null} rAF ID */
    this._rafId = null;

    /** @type {number} 上一帧时间戳 */
    this._lastTimestamp = 0;

    /** @type {number} 播放速度倍率 */
    this.speed = 1;

    /** @type {boolean} 是否循环播放 */
    this.loop = true;

    /** @type {{start:number, end:number}} 时间范围（分钟） */
    this.timeRange = { start: 0, end: 0 };

    /** @type {Array} POI 步骤（用于渲染时间标记） */
    this.steps = [];

    /** @type {boolean} */
    this._enabled = false;

    this._render();
    this._bindEvents();
  }

  // ================================================================
  //  渲染
  // ================================================================

  _render() {
    this.container.innerHTML = `
      <div class="timeline-controls">
        <button class="play-btn" id="playBtn" disabled
                aria-label="播放" title="播放/暂停 (空格键)">&#9654;</button>
        <button class="speed-btn" id="speedBtn" disabled
                aria-label="播放速度" title="切换速度">1x</button>
        <input type="range" class="timeline-slider" id="timelineSlider"
               min="0" max="1000" value="0" disabled
               aria-label="时间轴进度" aria-valuemin="0" aria-valuemax="1000" aria-valuenow="0">
        <div class="time-display" id="timeDisplay">--:-- - --:--</div>
      </div>
      <div class="timeline-progress-bar" id="progressBar">
        <div class="timeline-progress-fill" id="progressFill"></div>
      </div>
      <div class="timeline-poi-markers" id="timelinePoiMarkers"></div>
    `;
  }

  _bindEvents() {
    const playBtn = this.container.querySelector('#playBtn');
    const speedBtn = this.container.querySelector('#speedBtn');
    const slider = this.container.querySelector('#timelineSlider');

    playBtn.addEventListener('click', () => this.togglePlay());
    speedBtn.addEventListener('click', () => this.cycleSpeed());

    slider.addEventListener('input', (e) => {
      this.position = parseInt(e.target.value, 10);
      this._updateDisplay();
      this._emitUpdate();
    });

    // 键盘快捷键
    document.addEventListener('keydown', (e) => {
      if (!this._enabled) return;
      // 如果焦点在输入框内，不拦截
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      if (e.key === ' ' || e.code === 'Space') {
        e.preventDefault();
        this.togglePlay();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        this.position = Math.min(1000, this.position + 10);
        this._syncSlider();
        this._updateDisplay();
        this._emitUpdate();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        this.position = Math.max(0, this.position - 10);
        this._syncSlider();
        this._updateDisplay();
        this._emitUpdate();
      }
    });
  }

  // ================================================================
  //  公共 API
  // ================================================================

  /**
   * 设置时间轴范围和步骤数据
   * @param {number} startMinutes - 开始时间（分钟）
   * @param {number} endMinutes - 结束时间（分钟）
   * @param {Array} [steps] - POI 步骤数组
   */
  setTimeRange(startMinutes, endMinutes, steps) {
    this.timeRange = { start: startMinutes, end: endMinutes };
    this.steps = steps || [];

    this.position = 0;
    this._syncSlider();
    this._updateDisplay();
    this._renderMarkers();
  }

  /**
   * 启用/禁用时间轴控件
   * @param {boolean} enabled
   */
  setEnabled(enabled) {
    this._enabled = enabled;
    const playBtn = this.container.querySelector('#playBtn');
    const speedBtn = this.container.querySelector('#speedBtn');
    const slider = this.container.querySelector('#timelineSlider');

    playBtn.disabled = !enabled;
    speedBtn.disabled = !enabled;
    slider.disabled = !enabled;

    if (!enabled && this.isPlaying) {
      this.stop();
    }
  }

  /**
   * 开始播放
   */
  play() {
    if (!this._enabled || this.isPlaying) return;
    this.isPlaying = true;
    this._lastTimestamp = performance.now();

    const playBtn = this.container.querySelector('#playBtn');
    playBtn.innerHTML = '&#9646;&#9646;';
    playBtn.setAttribute('aria-label', '暂停');

    this._rafId = requestAnimationFrame(this._animate.bind(this));
  }

  /**
   * 暂停播放
   */
  stop() {
    this.isPlaying = false;
    if (this._rafId) {
      cancelAnimationFrame(this._rafId);
      this._rafId = null;
    }

    const playBtn = this.container.querySelector('#playBtn');
    playBtn.innerHTML = '&#9654;';
    playBtn.setAttribute('aria-label', '播放');
  }

  /**
   * 切换播放/暂停
   */
  togglePlay() {
    if (this.isPlaying) {
      this.stop();
    } else {
      this.play();
    }
  }

  /**
   * 循环切换播放速度：0.5x -> 1x -> 2x -> 4x -> 0.5x
   */
  cycleSpeed() {
    const speeds = [0.5, 1, 2, 4];
    const idx = speeds.indexOf(this.speed);
    this.speed = speeds[(idx + 1) % speeds.length];

    const speedBtn = this.container.querySelector('#speedBtn');
    speedBtn.textContent = this.speed + 'x';
  }

  /**
   * 设置进度（外部调用）
   * @param {number} value - 0-1000
   */
  setPosition(value) {
    this.position = Math.max(0, Math.min(1000, Math.round(value)));
    this._syncSlider();
    this._updateDisplay();
    this._updateProgressBar();
  }

  /**
   * 重置到起点
   */
  reset() {
    this.stop();
    this.position = 0;
    this._syncSlider();
    this._updateDisplay();
    this._updateProgressBar();
    this._updateActiveMarker(-1);
  }

  /**
   * 获取当前对应的时间（分钟）
   * @returns {number}
   */
  getCurrentMinutes() {
    const range = this.timeRange.end - this.timeRange.start || 1;
    return this.timeRange.start + (this.position / 1000) * range;
  }

  /**
   * 获取当前对应的格式化时间字符串
   * @returns {string} 如 "10:30"
   */
  getCurrentTimeStr() {
    return Timeline.minutesToTimeStr(Math.round(this.getCurrentMinutes()));
  }

  // ================================================================
  //  动画（requestAnimationFrame）
  // ================================================================

  _animate(timestamp) {
    if (!this.isPlaying) return;

    const delta = timestamp - this._lastTimestamp;
    this._lastTimestamp = timestamp;

    // 每帧推进量：基准 2/帧 @60fps，乘以速度倍率
    // 实际按时间增量计算，保证不同帧率下速度一致
    const increment = (delta / 16.67) * 2 * this.speed;

    this.position += increment;

    if (this.position >= 1000) {
      if (this.loop) {
        this.position = this.position % 1000;
      } else {
        this.position = 1000;
        this.stop();
      }
    }

    this._syncSlider();
    this._updateDisplay();
    this._updateProgressBar();
    this._updateActiveMarkerByPosition();
    this._emitUpdate();

    if (this.isPlaying) {
      this._rafId = requestAnimationFrame(this._animate.bind(this));
    }
  }

  // ================================================================
  //  内部更新
  // ================================================================

  _syncSlider() {
    const slider = this.container.querySelector('#timelineSlider');
    if (slider) slider.value = Math.round(this.position);
  }

  _updateDisplay() {
    const display = this.container.querySelector('#timeDisplay');
    if (!display) return;

    const start = this.timeRange.start;
    const end = this.timeRange.end;
    const range = end - start || 1;
    const currentMin = start + (this.position / 1000) * range;

    display.textContent =
      Timeline.minutesToTimeStr(start) + ' - ' +
      Timeline.minutesToTimeStr(Math.round(currentMin));
  }

  _updateProgressBar() {
    const fill = this.container.querySelector('#progressFill');
    if (!fill) return;
    fill.style.width = (this.position / 10) + '%';
  }

  /**
   * 根据当前位置高亮对应的 POI 标记
   */
  _updateActiveMarkerByPosition() {
    if (!this.steps.length) return;

    const range = this.timeRange.end - this.timeRange.start || 1;
    const currentMin = this.timeRange.start + (this.position / 1000) * range;

    // 找到当前时间对应的最近 POI
    let activeIdx = -1;
    for (let i = this.steps.length - 1; i >= 0; i--) {
      const stepMin = Timeline.parseTimeToMinutes(this.steps[i].arrival_time);
      if (currentMin >= stepMin) {
        activeIdx = i;
        break;
      }
    }
    this._updateActiveMarker(activeIdx);
  }

  /**
   * @param {number} activeIdx - 当前激活的 POI 索引，-1 表示无
   */
  _updateActiveMarker(activeIdx) {
    const markers = this.container.querySelectorAll('.timeline-poi-marker');
    markers.forEach((m, i) => {
      m.classList.toggle('active', i === activeIdx);
    });
  }

  // ================================================================
  //  时间标记
  // ================================================================

  _renderMarkers() {
    const container = this.container.querySelector('#timelinePoiMarkers');
    if (!container) return;
    container.innerHTML = '';

    const start = this.timeRange.start;
    const end = this.timeRange.end;
    const range = end - start || 1;

    this.steps.forEach((step, i) => {
      const marker = document.createElement('span');
      marker.className = 'timeline-poi-marker';
      const stepMin = Timeline.parseTimeToMinutes(step.arrival_time);
      const pct = ((stepMin - start) / range) * 100;
      marker.style.left = pct + '%';
      marker.textContent = step.poi.name;
      marker.title = step.poi.name + ' ' + (step.arrival_time || '');
      marker.dataset.index = i;

      // 点击标记跳转到该时间点
      marker.style.cursor = 'pointer';
      marker.style.pointerEvents = 'auto';
      marker.addEventListener('click', () => {
        this.position = (pct / 100) * 1000;
        this._syncSlider();
        this._updateDisplay();
        this._updateProgressBar();
        this._updateActiveMarker(i);
        this._emitUpdate();
      });

      container.appendChild(marker);
    });
  }

  // ================================================================
  //  事件发射
  // ================================================================

  _emitUpdate() {
    this.container.dispatchEvent(new CustomEvent('timeline-update', {
      detail: {
        position: this.position,
        progress: this.position / 1000,
        currentMinutes: this.getCurrentMinutes(),
        currentTime: this.getCurrentTimeStr(),
      },
      bubbles: true,
    }));
  }

  // ================================================================
  //  静态工具方法
  // ================================================================

  /** "09:30" -> 分钟数 570 */
  static parseTimeToMinutes(timeStr) {
    if (!timeStr || typeof timeStr !== 'string') return 0;
    const parts = timeStr.split(':');
    if (parts.length < 2) return 0;
    return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
  }

  /** 570 -> "09:30" */
  static minutesToTimeStr(minutes) {
    const h = Math.floor(minutes / 60) % 24;
    const m = Math.floor(minutes % 60);
    return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0');
  }

  // ================================================================
  //  清理
  // ================================================================

  destroy() {
    this.stop();
    this.container.innerHTML = '';
  }
}
