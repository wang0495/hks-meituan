class LLMChat {
  constructor(messagesEl, inputEl, sendBtn) {
    this.messagesEl = messagesEl;
    this.inputEl = inputEl;
    this.sendBtn = sendBtn;
    this._bindEvents();
  }

  _bindEvents() {
    this.sendBtn.addEventListener("click", () => this._send());
    this.inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") this._send();
    });
  }

  async _send() {
    const msg = this.inputEl.value.trim();
    if (!msg) return;
    this.inputEl.value = "";
    this._append("user", msg);

    const loadingEl = this._append("assistant loading", "思考中...");

    try {
      const resp = await fetch(`${API_BASE}/api/llm/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg }),
      });
      const json = await resp.json();
      loadingEl.textContent = json.response;
      loadingEl.className = "msg assistant";
    } catch (err) {
      loadingEl.textContent = `请求失败: ${err.message}`;
      loadingEl.className = "msg assistant";
    }
  }

  _append(cls, text) {
    const el = document.createElement("div");
    el.className = `msg ${cls}`;
    el.textContent = text;
    this.messagesEl.appendChild(el);
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    return el;
  }
}
