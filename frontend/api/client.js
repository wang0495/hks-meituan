/**
 * CityFlow API Client
 *
 * 封装所有后端 API 调用，包含：
 * - SSE 流式解析（正确处理 event:/data: 格式）
 * - 统一错误处理（对齐后端 ErrorCode 体系）
 * - 请求超时与 AbortController 支持
 * - 自动重试（可配置）
 */

// ---------------------------------------------------------------------------
//  错误码定义（对齐后端 backend/errors.py）
// ---------------------------------------------------------------------------

const ErrorCode = {
  // 通用 (1xxx)
  UNKNOWN_ERROR: 1000,
  INVALID_REQUEST: 1001,
  NOT_FOUND: 1002,
  INTERNAL_ERROR: 1003,
  TIMEOUT: 1004,
  RATE_LIMITED: 1005,
  // 认证 (2xxx)
  UNAUTHORIZED: 2001,
  FORBIDDEN: 2002,
  TOKEN_EXPIRED: 2003,
  // 业务 (3xxx)
  INTENT_PARSE_FAILED: 3001,
  NO_POIS_FOUND: 3002,
  ROUTE_SOLVING_FAILED: 3003,
  NARRATIVE_GENERATION_FAILED: 3004,
  DIALOGUE_FAILED: 3005,
  // 数据 (4xxx)
  INVALID_POI_DATA: 4001,
  INVALID_USER_INPUT: 4002,
  INVALID_ROUTE_DATA: 4003,
  // 外部服务 (5xxx)
  LLM_SERVICE_ERROR: 5001,
  EXTERNAL_API_ERROR: 5002,
};

/** 错误码 -> 用户友好提示映射 */
const ERROR_MESSAGES = {
  [ErrorCode.UNKNOWN_ERROR]: '发生未知错误',
  [ErrorCode.INVALID_REQUEST]: '请求参数无效',
  [ErrorCode.NOT_FOUND]: '资源不存在',
  [ErrorCode.INTERNAL_ERROR]: '服务器内部错误',
  [ErrorCode.TIMEOUT]: '请求超时，请重试',
  [ErrorCode.RATE_LIMITED]: '请求过于频繁，请稍后再试',
  [ErrorCode.UNAUTHORIZED]: '未授权，请重新登录',
  [ErrorCode.FORBIDDEN]: '无权访问',
  [ErrorCode.TOKEN_EXPIRED]: '登录已过期',
  [ErrorCode.INTENT_PARSE_FAILED]: '无法理解你的需求，请换个说法试试',
  [ErrorCode.NO_POIS_FOUND]: '没有找到符合条件的地点，请放宽条件',
  [ErrorCode.ROUTE_SOLVING_FAILED]: '路线规划失败，请重试',
  [ErrorCode.NARRATIVE_GENERATION_FAILED]: '行程说明生成失败',
  [ErrorCode.DIALOGUE_FAILED]: '对话处理失败',
  [ErrorCode.INVALID_POI_DATA]: 'POI 数据异常',
  [ErrorCode.INVALID_USER_INPUT]: '输入内容不合法',
  [ErrorCode.INVALID_ROUTE_DATA]: '路线数据异常',
  [ErrorCode.LLM_SERVICE_ERROR]: 'AI 服务暂时不可用',
  [ErrorCode.EXTERNAL_API_ERROR]: '外部服务异常',
};

// ---------------------------------------------------------------------------
//  自定义错误类
// ---------------------------------------------------------------------------

class APIError extends Error {
  /**
   * @param {number}  code      - 后端 ErrorCode 数值
   * @param {string}  message   - 错误消息
   * @param {object}  [details] - 附加详情
   * @param {number}  [status]  - HTTP 状态码
   */
  constructor(code, message, details, status) {
    super(message || ERROR_MESSAGES[code] || '请求失败');
    this.name = 'APIError';
    this.code = code;
    this.details = details || {};
    this.status = status || 0;
  }

  /** 是否可重试的瞬时错误 */
  get retryable() {
    return [ErrorCode.TIMEOUT, ErrorCode.RATE_LIMITED, ErrorCode.LLM_SERVICE_ERROR, ErrorCode.EXTERNAL_API_ERROR].includes(this.code);
  }
}

// ---------------------------------------------------------------------------
//  API Client
// ---------------------------------------------------------------------------

class APIClient {
  /**
   * @param {string}  [baseURL]              - API 基地址，默认同源
   * @param {object}  [options]
   * @param {number}  [options.timeout=30000] - 默认请求超时（毫秒）
   * @param {number}  [options.retries=0]    - 默认重试次数
   * @param {number}  [options.retryDelay=1000] - 重试间隔（毫秒）
   */
  constructor(baseURL, options) {
    if (baseURL === undefined) {
      this.baseURL = window.location.origin;
    } else {
      this.baseURL = baseURL;
    }
    this.timeout = (options && options.timeout) || 30000;
    this.retries = (options && options.retries) || 0;
    this.retryDelay = (options && options.retryDelay) || 1000;
  }

  // -------------------------------------------------------------------------
  //  核心请求方法
  // -------------------------------------------------------------------------

  /**
   * 发起普通 JSON 请求（POST/GET）。
   *
   * @param {string}  path    - 接口路径，如 /api/poi/search
   * @param {object}  [options]
   * @param {string}  [options.method='GET']
   * @param {object}  [options.body]        - POST body（自动 JSON 序列化）
   * @param {number}  [options.timeout]     - 覆盖默认超时
   * @param {AbortSignal} [options.signal]  - 外部 AbortSignal
   * @returns {Promise<object>}
   */
  async request(path, options) {
    const method = (options && options.method) || 'GET';
    const timeout = (options && options.timeout) || this.timeout;
    const externalSignal = options && options.signal;

    const controller = new AbortController();
    const combinedSignal = externalSignal
      ? this._combineSignals(externalSignal, controller.signal)
      : controller.signal;

    const timer = setTimeout(function () { controller.abort(); }, timeout);

    const fetchOptions = {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      signal: combinedSignal,
    };

    if (options && options.body !== undefined) {
      fetchOptions.body = JSON.stringify(options.body);
    }

    try {
      const response = await fetch(this.baseURL + path, fetchOptions);
      return await this._handleResponse(response);
    } catch (err) {
      if (err.name === 'AbortError') {
        throw new APIError(ErrorCode.TIMEOUT, '请求超时', {}, 0);
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  /**
   * 带自动重试的请求。
   *
   * @param {string}  path
   * @param {object}  [options]   - 同 request()
   * @param {number}  [retries]   - 覆盖默认重试次数
   * @returns {Promise<object>}
   */
  async requestWithRetry(path, options, retries) {
    const maxRetries = retries !== undefined ? retries : this.retries;
    let lastError = null;

    for (var attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await this.request(path, options);
      } catch (err) {
        lastError = err;
        if (attempt < maxRetries && err instanceof APIError && err.retryable) {
          await this._sleep(this.retryDelay * Math.pow(2, attempt));
          continue;
        }
        throw err;
      }
    }

    throw lastError;
  }

  // -------------------------------------------------------------------------
  //  SSE 流式请求
  // -------------------------------------------------------------------------

  /**
   * 发起 SSE 请求，逐条解析 event/data 消息。
   *
   * 后端格式：
   *   event: phase
   *   data: {"phase":"parsing","message":"正在理解..."}
   *
   * @param {string}  path
   * @param {object}  [options]
   * @param {object}  [options.body]        - POST body
   * @param {number}  [options.timeout]     - SSE 总超时
   * @param {AbortSignal} [options.signal]
   * @param {function} [options.onEvent]    - 每条事件的回调 (eventType, data) => void
   * @param {function} [options.onPhase]    - phase 事件回调
   * @param {function} [options.onStep]     - step 事件回调
   * @param {function} [options.onDone]     - done 事件回调
   * @param {function} [options.onError]    - error 事件回调
   * @returns {Promise<object[]>} 所有事件的数组
   */
  async requestSSE(path, options) {
    var self = this;
    var timeout = (options && options.timeout) || 120000; // SSE 默认 2 分钟
    var externalSignal = options && options.signal;

    var controller = new AbortController();
    var combinedSignal = externalSignal
      ? this._combineSignals(externalSignal, controller.signal)
      : controller.signal;

    var timer = setTimeout(function () { controller.abort(); }, timeout);

    var fetchOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: combinedSignal,
    };

    if (options && options.body !== undefined) {
      fetchOptions.body = JSON.stringify(options.body);
    }

    var events = [];

    try {
      var response = await fetch(self.baseURL + path, fetchOptions);

      if (!response.ok) {
        throw await self._parseError(response);
      }

      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';

      while (true) {
        var result = await reader.read();
        if (result.done) break;

        buffer += decoder.decode(result.value, { stream: true });

        // 按双换行分割 SSE 消息
        var messages = buffer.split('\n\n');
        buffer = messages.pop(); // 保留未完成的片段

        for (var i = 0; i < messages.length; i++) {
          var msg = messages[i];
          if (!msg.trim()) continue;

          var parsed = self._parseSSEMessage(msg);
          if (!parsed) continue;

          events.push(parsed);

          // 分发回调
          if (options && options.onEvent) {
            options.onEvent(parsed.event, parsed.data);
          }

          if (parsed.event === 'phase' && options && options.onPhase) {
            options.onPhase(parsed.data);
          } else if (parsed.event === 'step' && options && options.onStep) {
            options.onStep(parsed.data);
          } else if (parsed.event === 'done' && options && options.onDone) {
            options.onDone(parsed.data);
          } else if (parsed.event === 'error') {
            if (options && options.onError) {
              options.onError(parsed.data);
            }
            throw new APIError(
              ErrorCode.UNKNOWN_ERROR,
              (parsed.data && parsed.data.error) || '规划失败',
              parsed.data,
              0
            );
          }
        }
      }

      // 处理 buffer 残留
      if (buffer.trim()) {
        var parsed = self._parseSSEMessage(buffer);
        if (parsed) {
          events.push(parsed);
          if (options && options.onEvent) {
            options.onEvent(parsed.event, parsed.data);
          }
          if (parsed.event === 'done' && options && options.onDone) {
            options.onDone(parsed.data);
          }
        }
      }

      return events;
    } catch (err) {
      if (err.name === 'AbortError' && !(err instanceof APIError)) {
        throw new APIError(ErrorCode.TIMEOUT, '请求超时', {}, 0);
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  // -------------------------------------------------------------------------
  //  业务 API 方法
  // -------------------------------------------------------------------------

  /**
   * 路线规划（SSE 流式）。
   *
   * @param {string}  userInput - 用户出行需求
   * @param {object}  [options]
   * @param {function} [options.onPhase]
   * @param {function} [options.onStep]
   * @param {function} [options.onDone]
   * @param {AbortSignal} [options.signal]
   * @returns {Promise<object[]>}
   */
  async planRoute(userInput, options) {
    var opts = options || {};
    return this.requestSSE('/api/plan', {
      body: { user_input: userInput },
      onPhase: opts.onPhase,
      onStep: opts.onStep,
      onDone: opts.onDone,
      signal: opts.signal,
      timeout: opts.timeout,
    });
  }

  /**
   * 搜索 POI。
   *
   * @param {object}  params
   * @param {string}  [params.region]
   * @param {string[]} [params.categories]
   * @param {string[]} [params.tags]
   * @param {string}  [params.keyword]
   * @param {number}  [params.min_rating]
   * @param {number}  [params.max_price]
   * @param {number}  [params.lat]
   * @param {number}  [params.lng]
   * @returns {Promise<{pois: object[], total: number}>}
   */
  async searchPOIs(params) {
    var queryParts = [];
    if (params.lat !== undefined) queryParts.push('lat=' + params.lat);
    if (params.lng !== undefined) queryParts.push('lng=' + params.lng);
    var query = queryParts.length > 0 ? '?' + queryParts.join('&') : '';

    var body = {};
    if (params.region) body.region = params.region;
    if (params.categories) body.categories = params.categories;
    if (params.tags) body.tags = params.tags;
    if (params.keyword) body.keyword = params.keyword;
    if (params.min_rating !== undefined) body.min_rating = params.min_rating;
    if (params.max_price !== undefined) body.max_price = params.max_price;

    return this.requestWithRetry('/api/poi/search' + query, {
      method: 'POST',
      body: body,
    });
  }

  /**
   * 获取 POI 详情。
   *
   * @param {string}  poiId
   * @returns {Promise<object>}
   */
  async getPOIDetail(poiId) {
    return this.requestWithRetry('/api/poi/detail/' + encodeURIComponent(poiId));
  }

  /**
   * 计算距离矩阵。
   *
   * @param {string[]} poiIds - 2~50 个 POI ID
   * @returns {Promise<{matrix: object[][], poi_ids: string[]}>}
   */
  async getDistanceMatrix(poiIds) {
    return this.requestWithRetry('/api/poi/distance-matrix', {
      method: 'POST',
      body: { poi_ids: poiIds },
    });
  }

  /**
   * 对话式路线调整。
   *
   * @param {string}  routeId     - 路线 ID
   * @param {string}  instruction - 用户调整指令
   * @returns {Promise<{reply: string, route: object, changes_made: object[]}>}
   */
  async adjustRoute(routeId, instruction) {
    return this.requestWithRetry('/api/dialogue/' + encodeURIComponent(routeId), {
      method: 'POST',
      body: { instruction: instruction },
    });
  }

  /**
   * 获取路线详情。
   *
   * @param {string}  routeId
   * @returns {Promise<object>}
   */
  async getRoute(routeId) {
    return this.requestWithRetry('/api/route/' + encodeURIComponent(routeId));
  }

  /**
   * LLM 聊天。
   *
   * @param {string}  message
   * @returns {Promise<{response: string}>}
   */
  async chat(message) {
    return this.requestWithRetry('/api/llm/chat', {
      method: 'POST',
      body: { message: message },
    });
  }

  // -------------------------------------------------------------------------
  //  内部工具方法
  // -------------------------------------------------------------------------

  /** 解析 HTTP 错误响应为 APIError */
  async _handleResponse(response) {
    if (!response.ok) {
      throw await this._parseError(response);
    }
    return response.json();
  }

  /** 从 HTTP 响应构造 APIError */
  async _parseError(response) {
    var body = null;
    try {
      body = await response.json();
    } catch (_e) {
      // 响应不是 JSON
    }

    // 后端错误格式: { "error": { "code": 3001, "message": "...", "details": {...} } }
    if (body && body.error) {
      var errObj = body.error;
      return new APIError(
        errObj.code || ErrorCode.UNKNOWN_ERROR,
        errObj.message || '请求失败',
        errObj.details || {},
        response.status
      );
    }

    // FastAPI HTTPException 格式: { "detail": "..." }
    if (body && body.detail) {
      var detail = body.detail;
      if (typeof detail === 'object' && detail.error) {
        return new APIError(detail.code || ErrorCode.UNKNOWN_ERROR, detail.error, {}, response.status);
      }
      return new APIError(ErrorCode.UNKNOWN_ERROR, String(detail), {}, response.status);
    }

    return new APIError(ErrorCode.UNKNOWN_ERROR, 'HTTP ' + response.status, {}, response.status);
  }

  /** 解析单条 SSE 消息文本 */
  _parseSSEMessage(text) {
    var eventType = 'message';
    var dataStr = '';

    var lines = text.split('\n');
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith('data: ')) {
        dataStr += line.slice(6);
      } else if (line.startsWith('data:')) {
        // 无空格的 data: 行
        dataStr += line.slice(5);
      }
    }

    if (!dataStr) return null;

    try {
      return { event: eventType, data: JSON.parse(dataStr) };
    } catch (e) {
      console.warn('[APIClient] SSE JSON parse error:', dataStr);
      return null;
    }
  }

  /** 合并两个 AbortSignal（任一 abort 即触发） */
  _combineSignals(external, internal) {
    if (typeof AbortSignal.any === 'function') {
      return AbortSignal.any([external, internal]);
    }
    // 降级：手动合并
    var controller = new AbortController();
    function onAbort() { controller.abort(); }
    external.addEventListener('abort', onAbort, { once: true });
    internal.addEventListener('abort', onAbort, { once: true });
    return controller.signal;
  }

  /** Promise 版 sleep */
  _sleep(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }
}

// ---------------------------------------------------------------------------
//  导出
// ---------------------------------------------------------------------------

// 支持 ES Module 和全局变量两种使用方式
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { APIClient, APIError, ErrorCode, ERROR_MESSAGES };
} else {
  window.APIClient = APIClient;
  window.APIError = APIError;
  window.ErrorCode = ErrorCode;
  window.ERROR_MESSAGES = ERROR_MESSAGES;
}
