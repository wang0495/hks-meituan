(function () {
  class CityFlowAPI {
    constructor(baseURL) {
      this.baseURL = this.normalizeBase(baseURL || "http://127.0.0.1:8000");
    }

    normalizeBase(baseURL) {
      return String(baseURL || "").replace(/\/+$/, "");
    }

    setBaseURL(baseURL) {
      this.baseURL = this.normalizeBase(baseURL);
    }

    url(path) {
      return this.baseURL + path;
    }

    async health() {
      const paths = ["/api/health", "/health"];
      let lastError = null;
      for (const path of paths) {
        try {
          const response = await fetch(this.url(path), {
            method: "GET",
            headers: { Accept: "application/json" },
            signal: AbortSignal.timeout ? AbortSignal.timeout(3500) : undefined,
          });
          if (response.ok) {
            return await response.json().catch(() => ({ status: "ok" }));
          }
        } catch (error) {
          lastError = error;
        }
      }
      throw lastError || new Error("后端连接失败");
    }

    async plan(payload, handlers) {
      const opts = handlers || {};
      try {
        return await this.requestSSE("/api/v2/plan", payload.v2, opts);
      } catch (error) {
        if (!this.isMissingEndpointError(error)) {
          throw error;
        }
        return this.requestSSE("/api/plan", payload.v1, opts);
      }
    }

    async adjust(routeId, instruction) {
      const body = { instruction };
      const encoded = encodeURIComponent(routeId);
      try {
        return await this.requestJSON("/api/v2/dialogue/" + encoded, {
          method: "POST",
          body,
        });
      } catch (error) {
        if (!this.isMissingEndpointError(error)) {
          throw error;
        }
        return this.requestJSON("/api/dialogue/" + encoded, {
          method: "POST",
          body,
        });
      }
    }

    async getPOIDetail(poiId) {
      const encoded = encodeURIComponent(poiId);
      try {
        return await this.requestJSON("/api/v2/poi/detail/" + encoded);
      } catch (error) {
        if (!this.isMissingEndpointError(error)) {
          throw error;
        }
        return this.requestJSON("/api/poi/detail/" + encoded);
      }
    }

    async requestJSON(path, options) {
      const opts = options || {};
      const response = await fetch(this.url(path), {
        method: opts.method || "GET",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: opts.body ? JSON.stringify(opts.body) : undefined,
        signal: opts.signal,
      });
      if (!response.ok) {
        throw await this.makeHTTPError(response);
      }
      return response.json();
    }

    async requestSSE(path, body, handlers) {
      const response = await fetch(this.url(path), {
        method: "POST",
        headers: {
          Accept: "text/event-stream",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body || {}),
        signal: handlers.signal,
      });

      if (!response.ok) {
        throw await this.makeHTTPError(response);
      }
      if (!response.body) {
        throw new Error("当前浏览器不支持流式读取");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      const events = [];

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split(/\n\n|\r\n\r\n/);
        buffer = chunks.pop() || "";

        for (const chunk of chunks) {
          const event = this.parseSSE(chunk);
          if (!event) continue;
          events.push(event);
          this.dispatchEvent(event, handlers);
          if (event.type === "error") {
            const message = event.data && (event.data.error || event.data.message);
            throw new Error(message || "路线生成失败");
          }
        }
      }

      if (buffer.trim()) {
        const event = this.parseSSE(buffer);
        if (event) {
          events.push(event);
          this.dispatchEvent(event, handlers);
        }
      }

      return events;
    }

    parseSSE(text) {
      let type = "message";
      let dataText = "";
      const lines = String(text || "").split(/\r?\n/);

      for (const line of lines) {
        if (line.startsWith("event:")) {
          type = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataText += line.slice(5).trim();
        }
      }

      if (!dataText) return null;
      let data = dataText;
      try {
        data = JSON.parse(dataText);
      } catch (_error) {
        data = { value: dataText };
      }
      return { type, data };
    }

    dispatchEvent(event, handlers) {
      const data = event.data || {};
      if (event.type === "phase" && handlers.onPhase) handlers.onPhase(data);
      if (event.type === "step" && handlers.onStep) handlers.onStep(data);
      if (event.type === "done" && handlers.onDone) handlers.onDone(data);
      if (event.type === "error" && handlers.onError) handlers.onError(data);
      if (event.type === "agent_start" && handlers.onAgent) handlers.onAgent("start", data);
      if (event.type === "agent_thinking" && handlers.onAgent) handlers.onAgent("thinking", data);
      if (event.type === "agent_done" && handlers.onAgent) handlers.onAgent("done", data);
      if (handlers.onAny) handlers.onAny(event);
    }

    async makeHTTPError(response) {
      let detail = "";
      try {
        const body = await response.json();
        detail = body.detail || body.error || body.message || "";
        if (typeof detail === "object") {
          detail = detail.error || detail.message || JSON.stringify(detail);
        }
      } catch (_error) {
        detail = await response.text().catch(() => "");
      }
      const error = new Error(detail || "HTTP " + response.status);
      error.status = response.status;
      return error;
    }

    isMissingEndpointError(error) {
      return error && (error.status === 404 || error.status === 405);
    }
  }

  window.CityFlowAPI = CityFlowAPI;
})();
