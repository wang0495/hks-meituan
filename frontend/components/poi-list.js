/**
 * POIList - CityFlow POI 列表组件
 *
 * 功能：
 * - 情绪标签驱动的卡片样式（兴奋/宁静/文化/自然）
 * - 拖拽排序 + 自动重算时间
 * - SSE 流式逐步追加
 * - 3D 联动（hover 高亮、click 飞入）
 * - XSS 防护
 * - 键盘可访问
 */
class POIList {
  /**
   * @param {HTMLElement|string} container - 列表容器或其 ID
   */
  constructor(container) {
    this.container = typeof container === 'string'
      ? document.getElementById(container)
      : container;

    /** @type {Array} 当前 POI 步骤列表 */
    this.steps = [];

    /** @type {string|null} 当前选中的 POI ID */
    this.selectedPoiId = null;

    /** @type {Object|null} 当前拖拽中的元素 */
    this._dragState = null;

    this._init();
  }

  // ================================================================
  //  初始化
  // ================================================================

  _init() {
    this.container.setAttribute('role', 'list');
    this.container.setAttribute('aria-label', '路线 POI 列表');
    this._showPlaceholder('输入出行需求，开始规划路线');
    this._bindDragAndDrop();
    this._bindKeyboardNav();
  }

  // ================================================================
  //  渲染入口
  // ================================================================

  /**
   * 完整渲染一组步骤（规划完成后调用）
   * @param {Array} steps - 含 poi, arrival_time, departure_time, index 等字段
   */
  render(steps) {
    this.steps = steps || [];
    this.container.innerHTML = '';

    if (!this.steps.length) {
      this._showPlaceholder('未找到匹配的 POI');
      return;
    }

    const fragment = document.createDocumentFragment();
    this.steps.forEach((step, i) => {
      step.index = step.index || i + 1;
      fragment.appendChild(this._createCard(step));
    });
    this.container.appendChild(fragment);
  }

  /**
   * 流式追加单个步骤（SSE step 事件）
   * @param {Object} step
   */
  addStep(step) {
    // 移除占位卡片
    const placeholder = this.container.querySelector('.placeholder-card');
    if (placeholder) placeholder.remove();

    step.index = this.steps.length + 1;
    this.steps.push(step);
    const card = this._createCard(step);
    // 追加动画
    card.style.opacity = '0';
    card.style.transform = 'translateY(10px)';
    this.container.appendChild(card);
    requestAnimationFrame(() => {
      card.style.transition = 'opacity 0.3s, transform 0.3s';
      card.style.opacity = '1';
      card.style.transform = 'translateY(0)';
    });
    // 自动滚动到最新
    this.container.scrollTop = this.container.scrollHeight;
  }

  /**
   * 清空列表并显示占位信息
   * @param {string} text
   */
  clear(text) {
    this.steps = [];
    this.selectedPoiId = null;
    this._showPlaceholder(text || '输入出行需求，开始规划路线');
  }

  // ================================================================
  //  卡片创建
  // ================================================================

  /**
   * @param {Object} step
   * @returns {HTMLElement}
   */
  _createCard(step) {
    const poi = step.poi;
    const card = document.createElement('div');
    const mood = POIList.getMoodClass(poi.emotion_tags);

    card.className = 'poi-card ' + mood;
    card.dataset.id = poi.id;
    card.draggable = true;
    card.setAttribute('role', 'listitem');
    card.setAttribute('aria-label', `第${step.index}站：${poi.name}`);
    card.setAttribute('tabindex', '0');

    const emotionTags = POIList.getEmotionTagList(poi.emotion_tags);
    const price = poi.avg_price != null ? poi.avg_price : '--';
    const rating = poi.rating != null ? poi.rating : '--';
    const hours = poi.business_hours || '';

    card.innerHTML =
      '<div class="drag-handle" aria-hidden="true">' +
        '<span></span><span></span><span></span>' +
      '</div>' +
      '<div class="poi-card-index" aria-hidden="true">' + step.index + '</div>' +
      '<div class="poi-card-body">' +
        '<div class="poi-header">' +
          '<span class="poi-name">' + POIList.escapeHtml(poi.name) + '</span>' +
          '<span class="poi-time">' + POIList.escapeHtml(step.arrival_time || '') + '</span>' +
        '</div>' +
        '<div class="poi-subheader">' +
          '<span class="poi-rating">\u2605 ' + rating + '</span>' +
          (hours ? '<span class="poi-hours">' + POIList.escapeHtml(hours) + '</span>' : '') +
        '</div>' +
        '<div class="poi-meta">' +
          '<div class="poi-tags">' +
            '<span class="tag">' + POIList.escapeHtml(poi.category || '') + '</span>' +
            emotionTags.map(t =>
              '<span class="tag ' + t.cls + '">' + t.text + '</span>'
            ).join('') +
          '</div>' +
          '<span class="poi-price">\u00A5' + price + '</span>' +
        '</div>' +
      '</div>';

    // 点击事件
    card.addEventListener('click', () => {
      if (card.classList.contains('dragging')) return;
      this.selectPoi(poi.id);
      this._emit('poi-click', { poiId: poi.id, poi, step });
    });

    // hover 事件
    card.addEventListener('mouseenter', () => {
      this._emit('poi-hover', { poiId: poi.id, hovered: true });
    });
    card.addEventListener('mouseleave', () => {
      this._emit('poi-hover', { poiId: poi.id, hovered: false });
    });

    return card;
  }

  // ================================================================
  //  选中
  // ================================================================

  /**
   * @param {string} poiId
   */
  selectPoi(poiId) {
    this.selectedPoiId = poiId;
    this.container.querySelectorAll('.poi-card').forEach(card => {
      const match = card.dataset.id === poiId;
      card.classList.toggle('active', match);
      if (match) {
        card.setAttribute('aria-selected', 'true');
        // 确保可见
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } else {
        card.removeAttribute('aria-selected');
      }
    });
  }

  /**
   * 取消所有选中
   */
  deselectAll() {
    this.selectedPoiId = null;
    this.container.querySelectorAll('.poi-card').forEach(card => {
      card.classList.remove('active');
      card.removeAttribute('aria-selected');
    });
  }

  // ================================================================
  //  拖拽排序
  // ================================================================

  _bindDragAndDrop() {
    const list = this.container;

    // --- HTML5 Drag and Drop ---
    list.addEventListener('dragstart', (e) => {
      const card = e.target.closest('.poi-card');
      if (!card || card.classList.contains('placeholder-card')) {
        e.preventDefault();
        return;
      }
      card.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', card.dataset.id || '');
      this._dragState = { cardId: card.dataset.id, source: 'html5' };
    });

    list.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';

      const dragging = list.querySelector('.poi-card.dragging');
      if (!dragging) return;

      // Remove previous drop indicators
      list.querySelectorAll('.drop-indicator').forEach(el => el.remove());

      const afterEl = this._getDragAfterElement(e.clientY);
      if (afterEl == null) {
        list.appendChild(dragging);
        // Add indicator at end
        const indicator = document.createElement('div');
        indicator.className = 'drop-indicator';
        list.appendChild(indicator);
      } else {
        list.insertBefore(dragging, afterEl);
        // Add indicator before afterEl
        const indicator = document.createElement('div');
        indicator.className = 'drop-indicator';
        list.insertBefore(indicator, afterEl);
      }
    });

    list.addEventListener('dragend', () => {
      this._clearDropIndicators();
      const dragging = list.querySelector('.poi-card.dragging');
      if (dragging) {
        dragging.classList.remove('dragging');
        dragging.style.opacity = '';
        this._reorderByDOM();
      }
      this._dragState = null;
    });

    list.addEventListener('dragleave', (e) => {
      // Only clear if leaving the list entirely
      if (!list.contains(e.relatedTarget)) {
        this._clearDropIndicators();
      }
    });

    // --- Touch support for mobile ---
    let touchDragEl = null;
    let touchStartY = 0;
    let touchCurrentY = 0;
    let touchGhost = null;
    let touchOriginalIndex = -1;

    list.addEventListener('touchstart', (e) => {
      const card = e.target.closest('.poi-card');
      if (!card || card.classList.contains('placeholder-card')) return;
      // Only start drag from the drag-handle area
      const handle = e.target.closest('.drag-handle');
      if (!handle) return;

      touchDragEl = card;
      touchStartY = e.touches[0].clientY;
      touchOriginalIndex = Array.from(list.querySelectorAll('.poi-card:not(.placeholder-card)')).indexOf(card);

      // Store initial position
      card.dataset.touchStartY = touchStartY;
      card.classList.add('touch-dragging');

      // Prevent page scroll while dragging
      e.preventDefault();
    }, { passive: false });

    list.addEventListener('touchmove', (e) => {
      if (!touchDragEl) return;
      e.preventDefault();

      touchCurrentY = e.touches[0].clientY;
      this._clearDropIndicators();

      // Determine drop position
      const afterEl = this._getDragAfterElement(touchCurrentY);
      if (afterEl == null) {
        list.appendChild(touchDragEl);
        const indicator = document.createElement('div');
        indicator.className = 'drop-indicator';
        list.appendChild(indicator);
      } else {
        list.insertBefore(touchDragEl, afterEl);
        const indicator = document.createElement('div');
        indicator.className = 'drop-indicator';
        list.insertBefore(indicator, afterEl);
      }
    }, { passive: false });

    list.addEventListener('touchend', (e) => {
      if (!touchDragEl) return;
      dragEnd();
    });

    list.addEventListener('touchcancel', () => {
      if (!touchDragEl) return;
      dragEnd();
    });

    const dragEnd = () => {
      this._clearDropIndicators();
      if (touchDragEl) {
        touchDragEl.classList.remove('touch-dragging');
      }
      const originalCards = Array.from(list.querySelectorAll('.poi-card:not(.placeholder-card)'));
      const newIndex = originalCards.indexOf(touchDragEl);
      if (newIndex !== touchOriginalIndex && touchDragEl) {
        // Order actually changed
        this._reorderByDOM();
      }
      touchDragEl = null;
      touchStartY = 0;
      touchCurrentY = 0;
      touchGhost = null;
      touchOriginalIndex = -1;
    };
  }

  _clearDropIndicators() {
    this.container.querySelectorAll('.drop-indicator').forEach(el => el.remove());
  }

  /**
   * @param {number} y - 鼠标/触摸 Y 坐标
   * @returns {HTMLElement|null}
   */
  _getDragAfterElement(y) {
    const elements = Array.from(
      this.container.querySelectorAll('.poi-card:not(.dragging):not(.touch-dragging):not(.placeholder-card)')
    );

    return elements.reduce((closest, child) => {
      const box = child.getBoundingClientRect();
      const offset = y - box.top - box.height / 2;
      if (offset < 0 && offset > closest.offset) {
        return { offset, element: child };
      }
      return closest;
    }, { offset: Number.NEGATIVE_INFINITY }).element || null;
  }

  /**
   * 根据 DOM 顺序重排 steps 并重新计算时间
   */
  _reorderByDOM() {
    const cards = this.container.querySelectorAll('.poi-card:not(.placeholder-card)');
    const newOrder = Array.from(cards).map(c => c.dataset.id);

    const reordered = newOrder
      .map(id => this.steps.find(s => s.poi.id === id))
      .filter(Boolean);

    this.steps = reordered;
    this._recalculateTimes();
    this.render(this.steps);
    this._emit('route-reordered', { steps: this.steps });
    this._emit('poi-reorder', { steps: this.steps });
  }

  /**
   * 拖拽排序后重算到达/离开时间
   */
  _recalculateTimes() {
    if (!this.steps.length) return;

    let currentMin = POIList.parseTimeToMinutes(this.steps[0].arrival_time);
    if (currentMin <= 0) currentMin = 9 * 60; // 默认 09:00

    this.steps.forEach((step, i) => {
      step.index = i + 1;
      step.arrival_time = POIList.minutesToTimeStr(currentMin);
      const duration = step.duration_minutes || 45;
      step.departure_time = POIList.minutesToTimeStr(currentMin + duration);
      currentMin += duration + 15; // 15 分钟路程
    });
  }

  // ================================================================
  //  SSE 流式追加 / 更新
  // ================================================================

  /**
   * 流式追加单个步骤（SSE step 事件的别名，返回该卡片）
   * @param {Object} step
   * @returns {HTMLElement} 刚创建的卡片
   */
  appendCard(step) {
    this.addStep(step);
    return this.container.querySelector('.poi-card:last-child');
  }

  /**
   * 更新指定索引卡片的叙述文案（SSE step_update 事件）
   * @param {number} index - 0-based 索引
   * @param {string} description - 新的叙述文案
   */
  updateCardNarrative(index, description) {
    const cards = this.container.querySelectorAll('.poi-card:not(.placeholder-card)');
    if (index < 0 || index >= cards.length) return;
    const card = cards[index];
    let narrativeEl = card.querySelector('.poi-narrative');
    if (!narrativeEl) {
      narrativeEl = document.createElement('div');
      narrativeEl.className = 'poi-narrative';
      card.querySelector('.poi-card-body').appendChild(narrativeEl);
    }
    // 打字机效果：逐字追加
    narrativeEl.textContent = description;
    // 更新 steps 数据
    if (this.steps[index]) {
      this.steps[index].narrative = description;
    }
  }

  // ================================================================
  //  高亮 & 滚动（用于地图联动）
  // ================================================================

  /**
   * 高亮指定 POI 卡片
   * @param {string} poiId
   */
  highlightCard(poiId) {
    this.selectPoi(poiId);
  }

  /**
   * 滚动到指定 POI 卡片
   * @param {string} poiId
   */
  scrollToCard(poiId) {
    const card = this.container.querySelector(`.poi-card[data-id="${poiId}"]`);
    if (card) {
      card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  // ================================================================
  //  键盘导航
  // ================================================================

  _bindKeyboardNav() {
    this.container.addEventListener('keydown', (e) => {
      const card = e.target.closest('.poi-card');
      if (!card) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        const next = card.nextElementSibling;
        if (next && next.classList.contains('poi-card')) next.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prev = card.previousElementSibling;
        if (prev && prev.classList.contains('poi-card')) prev.focus();
      } else if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        card.click();
      }
    });
  }

  // ================================================================
  //  占位卡片
  // ================================================================

  _showPlaceholder(text) {
    this.container.innerHTML = '';
    const card = document.createElement('div');
    card.className = 'poi-card placeholder-card';
    card.setAttribute('role', 'listitem');
    card.textContent = text;
    this.container.appendChild(card);
  }

  // ================================================================
  //  事件发射
  // ================================================================

  _emit(eventName, detail) {
    this.container.dispatchEvent(new CustomEvent(eventName, {
      detail,
      bubbles: true,
    }));
  }

  // ================================================================
  //  静态工具方法
  // ================================================================

  /** XSS 防护 */
  static escapeHtml(text) {
    const el = document.createElement('span');
    el.textContent = text || '';
    return el.innerHTML;
  }

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

  /**
   * 情绪 -> 卡片 mood 类名
   * @param {Object} emotionTags
   * @returns {string}
   */
  static getMoodClass(emotionTags) {
    if (!emotionTags) return 'mood-default';

    const excitement = emotionTags.excitement || 0;
    const tranquility = emotionTags.tranquility || 0;
    const cultureDepth = emotionTags.culture_depth || 0;

    if (excitement >= 0.7) return 'mood-exciting';
    if (cultureDepth >= 0.7) return 'mood-cultural';
    if (tranquility >= 0.7) return 'mood-calm';
    if (tranquility >= 0.4) return 'mood-nature';

    return 'mood-default';
  }

  /**
   * 情绪 -> 显示标签数组
   * @param {Object} emotionTags
   * @returns {Array<{text:string, cls:string}>}
   */
  static getEmotionTagList(emotionTags) {
    if (!emotionTags) return [];
    const tags = [];
    if ((emotionTags.excitement || 0) > 0.7)
      tags.push({ text: '兴奋', cls: 'exciting' });
    if ((emotionTags.tranquility || 0) > 0.7)
      tags.push({ text: '宁静', cls: 'calm' });
    if ((emotionTags.culture_depth || 0) > 0.7)
      tags.push({ text: '文化', cls: 'cultural' });
    if ((emotionTags.nature || 0) > 0.7)
      tags.push({ text: '自然', cls: 'nature' });
    return tags;
  }

  /**
   * 情绪标签 -> 背景色（用于图表等场景）
   * @param {Object} emotionTags
   * @returns {string} CSS 颜色值
   */
  static getEmotionColor(emotionTags) {
    if (!emotionTags) return '#666';
    const { excitement, tranquility, culture_depth } = emotionTags;
    if (excitement > 0.7) return '#e94560';
    if (tranquility > 0.7) return '#3498db';
    if (culture_depth > 0.7) return '#9b59b6';
    return '#666';
  }

  /**
   * 获取当前步骤列表（供外部读取）
   * @returns {Array}
   */
  getSteps() {
    return [...this.steps];
  }

  /**
   * 根据 POI ID 查找步骤
   * @param {string} poiId
   * @returns {Object|null}
   */
  findStep(poiId) {
    return this.steps.find(s => s.poi.id === poiId) || null;
  }
}
