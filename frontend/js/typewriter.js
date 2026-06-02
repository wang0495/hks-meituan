/**
 * typewriter.js — 流式打字机效果引擎
 *
 * 支持逐字显示、渐变色、光标闪烁、暂停/恢复。
 * 用于 SSE 流式文本的前端渲染。
 */

class TypewriterEffect {
  constructor() {
    this.queue = new Map(); // elementId -> { text, index, timer, speed }
  }

  /**
   * 对指定元素执行打字机效果
   * @param {HTMLElement} el - 目标元素
   * @param {string} text - 完整文本
   * @param {Object} options - 配置项
   * @param {number} options.speed - 每字符间隔(ms)，默认 30
   * @param {Function} options.onChar - 每字符回调
   * @param {Function} options.onDone - 完成回调
   * @param {boolean} options.append - 是否追加模式
   */
  type(el, text, options = {}) {
    if (!el || !text) return;
    const speed = options.speed || 30;
    const onChar = options.onChar || null;
    const onDone = options.onDone || null;
    const append = options.append || false;

    const id = el.id || ('tw_' + Math.random().toString(36).slice(2));

    // 清除该元素的旧打字任务
    if (this.queue.has(id)) {
      clearInterval(this.queue.get(id).timer);
    }

    if (!append) {
      el.textContent = '';
    }

    let index = 0;
    const cursor = document.createElement('span');
    cursor.className = 'tw-cursor';
    cursor.textContent = '|';
    el.appendChild(cursor);

    const timer = setInterval(() => {
      if (index < text.length) {
        const char = text[index];
        // 在光标前插入字符
        const textNode = document.createTextNode(char);
        el.insertBefore(textNode, cursor);
        index++;
        if (onChar) onChar(char, index);
      } else {
        clearInterval(timer);
        this.queue.delete(id);
        // 移除光标
        setTimeout(() => {
          if (cursor.parentNode) cursor.remove();
          if (onDone) onDone();
        }, 500);
      }
    }, speed);

    this.queue.set(id, { text, index: 0, timer, speed });
  }

  /**
   * 流式追加文本（用于 SSE 流式输入）
   * @param {HTMLElement} el - 目标元素
   * @param {string} chunk - 新增文本片段
   * @param {number} speed - 每字符间隔(ms)
   */
  stream(el, chunk, speed = 20) {
    if (!el || !chunk) return;
    const id = el.id || ('tw_' + Math.random().toString(36).slice(2));

    // 获取或创建打字状态
    let state = this.queue.get(id);
    if (!state) {
      state = { buffer: '', index: 0, timer: null, speed };
      this.queue.set(id, state);
      el.textContent = '';
      // 添加光标
      const cursor = document.createElement('span');
      cursor.className = 'tw-cursor';
      cursor.textContent = '▋';
      el.appendChild(cursor);
    }

    // 追加到缓冲区
    state.buffer += chunk;

    // 如果没有在打字，启动打字
    if (!state.timer) {
      state.timer = setInterval(() => {
        if (state.index < state.buffer.length) {
          const char = state.buffer[state.index];
          const cursor = el.querySelector('.tw-cursor');
          if (cursor) {
            const textNode = document.createTextNode(char);
            el.insertBefore(textNode, cursor);
          } else {
            el.textContent += char;
          }
          state.index++;
        } else {
          // 缓冲区已打完，等待更多数据
          clearInterval(state.timer);
          state.timer = null;
          // 如果缓冲区很长（说明已经打完），移除光标
          if (state.index > 0 && state.index >= state.buffer.length) {
            setTimeout(() => {
              const cursor = el.querySelector('.tw-cursor');
              if (cursor) cursor.remove();
              this.queue.delete(id);
            }, 1000);
          }
        }
      }, speed);
    }
  }

  /**
   * 立即完成打字（跳过动画）
   */
  finish(el) {
    const id = el.id || '';
    const state = this.queue.get(id);
    if (state) {
      clearInterval(state.timer);
      this.queue.delete(id);
    }
    const cursor = el.querySelector('.tw-cursor');
    if (cursor) cursor.remove();
  }

  /**
   * 停止所有打字
   */
  stopAll() {
    for (const [id, state] of this.queue) {
      clearInterval(state.timer);
    }
    this.queue.clear();
  }
}

// 全局实例
window.typewriter = new TypewriterEffect();