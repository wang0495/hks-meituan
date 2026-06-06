(function () {
  const $ = (selector) => document.querySelector(selector);

  const els = {
    apiBaseInput: $("#apiBaseInput"),
    apiStatus: $("#apiStatus"),
    sourcePill: $("#sourcePill"),
    checkApiBtn: $("#checkApiBtn"),
    clearBtn: $("#clearBtn"),
    intentInput: $("#intentInput"),
    sceneGrid: $("#sceneGrid"),
    startLocationInput: $("#startLocationInput"),
    startTimeInput: $("#startTimeInput"),
    durationSelect: $("#durationSelect"),
    budgetSelect: $("#budgetSelect"),
    paceControl: $("#paceControl"),
    constraintGrid: $("#constraintGrid"),
    phaseList: $("#phaseList"),
    planBtn: $("#planBtn"),
    routeTitle: $("#routeTitle"),
    metricStops: $("#metricStops"),
    metricTime: $("#metricTime"),
    metricCost: $("#metricCost"),
    metricDistance: $("#metricDistance"),
    amapContainer: $("#amapContainer"),
    mapConfig: $("#mapConfig"),
    amapKeyInput: $("#amapKeyInput"),
    amapSecurityInput: $("#amapSecurityInput"),
    loadAmapBtn: $("#loadAmapBtn"),
    mapHint: $("#mapHint"),
    routeReason: $("#routeReason"),
    emotionBars: $("#emotionBars"),
    timelineBand: $("#timelineBand"),
    routeList: $("#routeList"),
    quickAdjust: $("#quickAdjust"),
    adjustForm: $("#adjustForm"),
    adjustInput: $("#adjustInput"),
    chatLog: $("#chatLog"),
    exportBtn: $("#exportBtn"),
    poiDialog: $("#poiDialog"),
    poiDialogBody: $("#poiDialogBody"),
    dialogCloseBtn: $("#dialogCloseBtn"),
    toast: $("#toast"),
  };

  const api = new window.CityFlowAPI(
    localStorage.getItem("cityflow-api-base") || els.apiBaseInput.value
  );

  const scenes = [
    {
      id: "quiet",
      label: "安静独处",
      icon: "moon",
      prompt: "周末想一个人安静走走，不想去人多的地方，最好有海边和文化感",
      tags: ["安静", "文化历史", "休闲放松", "海滨"],
      categories: ["文化", "景点", "餐饮", "景点"],
      preferences: { culture: 0.82, food: 0.25, nature: 0.72, social: 0.12 },
    },
    {
      id: "couple",
      label: "情侣约会",
      icon: "heart",
      prompt: "想带女朋友在珠海海边走走，吃点好吃的，傍晚拍拍照，节奏不要太赶",
      tags: ["拍照出片", "海滨", "夜景", "品质体验"],
      categories: ["景点", "餐饮", "文化", "景点"],
      preferences: { culture: 0.45, food: 0.7, nature: 0.78, social: 0.42 },
    },
    {
      id: "family",
      label: "亲子出游",
      icon: "baby",
      prompt: "周末一家人带孩子出去玩，希望儿童友好、有休息区，不要太累",
      tags: ["亲子", "儿童", "休闲放松", "互动"],
      categories: ["景点", "文化", "餐饮", "景点"],
      preferences: { culture: 0.55, food: 0.45, nature: 0.58, social: 0.5 },
    },
    {
      id: "friends",
      label: "朋友聚会",
      icon: "users",
      prompt: "想和朋友找便宜好玩的地方，能吃能逛，晚上有点热闹",
      tags: ["朋友聚会", "经济实惠", "夜生活", "互动"],
      categories: ["餐饮", "娱乐", "购物", "景点"],
      preferences: { culture: 0.2, food: 0.8, nature: 0.32, social: 0.82 },
    },
    {
      id: "food",
      label: "美食探索",
      icon: "utensils",
      prompt: "想在珠海吃本地特色和海鲜，顺路安排几个轻松散步点",
      tags: ["美食", "海鲜", "本地特色", "经济实惠"],
      categories: ["餐饮", "餐饮", "景点", "餐饮"],
      preferences: { culture: 0.24, food: 0.95, nature: 0.38, social: 0.5 },
    },
    {
      id: "coast",
      label: "海边漫步",
      icon: "waves",
      prompt: "想看海、吹风、拍照，路线轻松一点，最好有傍晚景色",
      tags: ["海滨", "自然风光", "拍照出片", "夜景"],
      categories: ["景点", "景点", "餐饮", "景点"],
      preferences: { culture: 0.28, food: 0.42, nature: 0.92, social: 0.28 },
    },
  ];

  const paces = [
    { id: "闲逛型", label: "闲逛型" },
    { id: "平衡型", label: "平衡型" },
    { id: "特种兵型", label: "特种兵型" },
  ];

  const constraints = [
    { id: "easy", label: "低体力", value: "低体力消耗", checked: true },
    { id: "queue", label: "低排队", value: "不想排队", checked: true },
    { id: "family", label: "亲子友好", value: "亲子友好", checked: false },
    { id: "accessible", label: "无障碍", value: "accessible", checked: false },
    { id: "pet", label: "宠物友好", value: "pet_friendly", checked: false },
    { id: "indoor", label: "室内优先", value: "indoor_only", checked: false },
  ];

  const phases = [
    { id: "parsing", label: "理解需求" },
    { id: "searching", label: "寻找地点" },
    { id: "solving", label: "编排路线" },
    { id: "narrating", label: "生成说明" },
  ];

  const quickAdjusts = ["太赶了", "便宜一点", "换第二站", "更多海边", "少走路"];

  const knownLocations = {
    香洲: { name: "香洲", lat: 22.271, lng: 113.576 },
    拱北: { name: "拱北", lat: 22.218, lng: 113.552 },
    吉大: { name: "吉大", lat: 22.252, lng: 113.581 },
    唐家湾: { name: "唐家湾", lat: 22.368, lng: 113.595 },
    横琴: { name: "横琴", lat: 22.116, lng: 113.548 },
  };

  const fallbackPois = [
    makePoi("fallback_1", "珠海博物馆", "文化", 4.7, 0, 22.276, 113.576, ["文化历史", "室内"], {
      culture_depth: 0.92,
      tranquility: 0.76,
      surprise: 0.45,
      excitement: 0.3,
      sociability: 0.25,
      physical_demand: 0.18,
    }),
    makePoi("fallback_2", "情侣路海滨", "景点", 4.8, 0, 22.263, 113.588, ["海滨", "自然风光"], {
      culture_depth: 0.35,
      tranquility: 0.82,
      surprise: 0.48,
      excitement: 0.52,
      sociability: 0.35,
      physical_demand: 0.24,
    }),
    makePoi("fallback_3", "珠海渔女", "文化", 4.6, 0, 22.265, 113.583, ["拍照出片", "海滨"], {
      culture_depth: 0.9,
      tranquility: 0.6,
      surprise: 0.5,
      excitement: 0.4,
      sociability: 0.3,
      physical_demand: 0.2,
    }),
    makePoi("fallback_4", "湾仔海鲜街", "餐饮", 4.4, 90, 22.193, 113.535, ["美食", "海鲜"], {
      culture_depth: 0.28,
      tranquility: 0.18,
      surprise: 0.54,
      excitement: 0.72,
      sociability: 0.75,
      physical_demand: 0.18,
    }),
    makePoi("fallback_5", "日月贝海岸", "景点", 4.7, 0, 22.269, 113.602, ["夜景", "拍照出片"], {
      culture_depth: 0.58,
      tranquility: 0.64,
      surprise: 0.66,
      excitement: 0.62,
      sociability: 0.42,
      physical_demand: 0.2,
    }),
  ];

  const state = {
    pois: [],
    steps: [],
    routeId: "",
    fullRoute: null,
    metadata: {},
    emotionCurve: [],
    selectedScene: "quiet",
    selectedPace: "平衡型",
    selectedIndex: 0,
    source: "local",
    planning: false,
    abortController: null,
    amap: null,
    amapMap: null,
    amapReady: false,
    amapLoading: false,
    amapOverlays: [],
    amapInfoWindow: null,
    amapLoaderPromise: null,
    lastPresetText: scenes[0].prompt,
  };

  function makePoi(id, name, category, rating, avgPrice, lat, lng, tags, emotion) {
    return {
      id,
      name,
      city: "珠海",
      category,
      rating,
      avg_price: avgPrice,
      lat,
      lng,
      business_hours: "09:00-18:00",
      tags,
      _scene_tags: tags,
      avg_stay_min: category === "餐饮" ? 80 : 60,
      emotion_tags: emotion,
      constraints: {
        accessible: true,
        pet_friendly: category === "景点",
        queue_time_min: 8,
        opening_hours: "09:00-18:00",
      },
      _suitability: {
        情侣友好: true,
        亲子友好: category !== "餐饮",
        独自友好: true,
        朋友友好: true,
      },
      ugc_comments: [],
    };
  }

  function init() {
    els.apiBaseInput.value = api.baseURL;
    renderScenes();
    renderPaces();
    renderConstraints();
    renderPhases();
    renderQuickAdjusts();
    bindEvents();
    initAmapControls();
    loadLocalPois().then(() => {
      setRoute(buildFallbackRoute(), "local");
    });
    checkAPI(false);
    refreshIcons();
  }

  function refreshIcons() {
    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  function bindEvents() {
    els.apiBaseInput.addEventListener("change", () => {
      api.setBaseURL(els.apiBaseInput.value);
      localStorage.setItem("cityflow-api-base", api.baseURL);
      checkAPI(true);
    });
    els.checkApiBtn.addEventListener("click", () => checkAPI(true));
    els.clearBtn.addEventListener("click", () => {
      els.intentInput.value = "";
      els.intentInput.focus();
    });
    els.planBtn.addEventListener("click", planRoute);
    els.adjustForm.addEventListener("submit", handleAdjust);
    els.exportBtn.addEventListener("click", copyRouteSummary);
    els.dialogCloseBtn.addEventListener("click", () => els.poiDialog.close());
    els.loadAmapBtn.addEventListener("click", () => loadAmapMap(true));
    window.addEventListener("resize", drawMap);

    document.querySelectorAll(".mobile-tab").forEach((button) => {
      button.addEventListener("click", () => {
        const view = button.dataset.view;
        document.body.dataset.mobileView = view;
        document.querySelectorAll(".mobile-tab").forEach((tab) => {
          tab.classList.toggle("active", tab === button);
        });
        setTimeout(drawMap, 80);
      });
    });
  }

  function initAmapControls() {
    const savedKey = localStorage.getItem("cityflow-amap-key") || "";
    const savedSecurity = localStorage.getItem("cityflow-amap-security") || "";
    els.amapKeyInput.value = savedKey;
    els.amapSecurityInput.value = savedSecurity;
    if (savedKey) {
      loadAmapMap(false);
    } else {
      setMapStatus("填写高德 JS API Key 后加载真实地图");
    }
  }

  async function loadAmapMap(showResult) {
    if (state.amapLoading) return;
    const key = els.amapKeyInput.value.trim();
    const securityJsCode = els.amapSecurityInput.value.trim();
    if (!key) {
      setMapStatus("需要填写高德 JS API Key 才能加载真实地图");
      if (showResult) showToast("请先填写高德 JS API Key");
      return;
    }

    localStorage.setItem("cityflow-amap-key", key);
    localStorage.setItem("cityflow-amap-security", securityJsCode);
    if (securityJsCode) {
      window._AMapSecurityConfig = { securityJsCode };
    } else {
      delete window._AMapSecurityConfig;
    }

    state.amapLoading = true;
    els.loadAmapBtn.disabled = true;
    els.loadAmapBtn.querySelector("span").textContent = "加载中";
    setMapStatus("正在连接高德地图");

    try {
      await ensureAmapLoader();
      const AMap = await window.AMapLoader.load({
        key,
        version: "2.0",
        plugins: ["AMap.Scale", "AMap.ToolBar"],
      });
      state.amap = AMap;
      if (state.amapMap && typeof state.amapMap.destroy === "function") {
        state.amapMap.destroy();
      }
      state.amapMap = new AMap.Map(els.amapContainer, {
        center: [113.576, 22.271],
        zoom: 12,
        viewMode: "3D",
        pitch: 0,
        resizeEnable: true,
        mapStyle: "amap://styles/normal",
      });
      state.amapMap.addControl(new AMap.Scale());
      state.amapMap.addControl(new AMap.ToolBar({ position: "RB" }));
      state.amapReady = true;
      els.amapContainer.closest(".map-stage").classList.add("map-ready");
      setMapStatus(state.steps.length ? "已接入高德地图，点击路线点查看详情" : "已接入高德地图");
      renderAmapRoute();
      if (showResult) showToast("高德地图已加载");
    } catch (error) {
      state.amapReady = false;
      els.amapContainer.closest(".map-stage").classList.remove("map-ready");
      setMapStatus("高德地图加载失败，请检查 Key、安全码和网络");
      if (showResult) showToast("高德地图加载失败，请检查配置");
      console.warn("AMap load failed", error);
    } finally {
      state.amapLoading = false;
      els.loadAmapBtn.disabled = false;
      els.loadAmapBtn.querySelector("span").textContent = "加载地图";
      refreshIcons();
    }
  }

  function ensureAmapLoader() {
    if (window.AMapLoader) return Promise.resolve();
    if (state.amapLoaderPromise) return state.amapLoaderPromise;
    state.amapLoaderPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://webapi.amap.com/loader.js";
      script.async = true;
      script.onload = resolve;
      script.onerror = () => reject(new Error("高德地图 Loader 加载失败"));
      document.head.appendChild(script);
    });
    return state.amapLoaderPromise;
  }

  function setMapStatus(text) {
    els.mapHint.textContent = text;
  }

  async function loadLocalPois() {
    try {
      const response = await fetch("./assets/data/city_poi_db.json");
      if (!response.ok) throw new Error("本地数据读取失败");
      const data = await response.json();
      state.pois = Array.isArray(data) ? data : fallbackPois;
    } catch (_error) {
      state.pois = fallbackPois;
    }
  }

  async function checkAPI(showResult) {
    api.setBaseURL(els.apiBaseInput.value);
    localStorage.setItem("cityflow-api-base", api.baseURL);
    setAPIStatus("checking", "检查中");
    try {
      await api.health();
      setAPIStatus("online", "后端在线");
      if (showResult) showToast("后端连接正常");
    } catch (_error) {
      setAPIStatus("offline", "本地预览");
      if (showResult) showToast("后端暂未连接，当前使用本地预览");
    }
  }

  function setAPIStatus(status, text) {
    els.apiStatus.classList.remove("online", "offline");
    if (status === "online") els.apiStatus.classList.add("online");
    if (status === "offline") els.apiStatus.classList.add("offline");
    els.apiStatus.lastChild.textContent = text;
  }

  function setSource(source) {
    state.source = source;
    els.sourcePill.classList.toggle("online", source === "backend");
    els.sourcePill.classList.toggle("local", source !== "backend");
    els.sourcePill.textContent = source === "backend" ? "真实后端" : "本地预览";
  }

  function renderScenes() {
    els.sceneGrid.innerHTML = scenes
      .map((scene) => `
        <button class="scene-button ${scene.id === state.selectedScene ? "active" : ""}" type="button" data-scene="${scene.id}">
          <i data-lucide="${scene.icon}"></i>
          <span>${scene.label}</span>
        </button>
      `)
      .join("");

    els.sceneGrid.querySelectorAll("[data-scene]").forEach((button) => {
      button.addEventListener("click", () => {
        const scene = scenes.find((item) => item.id === button.dataset.scene);
        state.selectedScene = scene.id;
        if (!els.intentInput.value.trim() || els.intentInput.value === state.lastPresetText) {
          els.intentInput.value = scene.prompt;
          state.lastPresetText = scene.prompt;
        }
        renderScenes();
        refreshIcons();
      });
    });
  }

  function renderPaces() {
    els.paceControl.innerHTML = paces
      .map((pace) => `
        <button class="segment-button ${pace.id === state.selectedPace ? "active" : ""}" type="button" data-pace="${pace.id}">
          ${pace.label}
        </button>
      `)
      .join("");

    els.paceControl.querySelectorAll("[data-pace]").forEach((button) => {
      button.addEventListener("click", () => {
        state.selectedPace = button.dataset.pace;
        renderPaces();
      });
    });
  }

  function renderConstraints() {
    els.constraintGrid.innerHTML = constraints
      .map((item) => `
        <label class="toggle-chip">
          <span>${item.label}</span>
          <input type="checkbox" data-constraint="${item.id}" ${item.checked ? "checked" : ""}>
        </label>
      `)
      .join("");
  }

  function renderPhases(activeId, errorMessage) {
    els.phaseList.innerHTML = phases
      .map((phase) => {
        const index = phases.findIndex((item) => item.id === phase.id);
        const activeIndex = activeId ? phases.findIndex((item) => item.id === activeId) : -1;
        const status = errorMessage ? "error" : activeIndex > index ? "done" : activeIndex === index ? "running" : "";
        const message = status === "running" ? "进行中" : status === "done" ? "完成" : status === "error" ? "异常" : "等待";
        return `
          <div class="phase-row ${status}" data-phase="${phase.id}">
            <span class="phase-dot"></span>
            <span class="phase-name">${phase.label}</span>
            <span class="phase-message">${message}</span>
          </div>
        `;
      })
      .join("");

    if (errorMessage) {
      const first = els.phaseList.querySelector(".phase-row");
      if (first) first.querySelector(".phase-message").textContent = errorMessage;
    }
  }

  function renderQuickAdjusts() {
    els.quickAdjust.innerHTML = quickAdjusts
      .map((text) => `<button class="quick-button" type="button" data-adjust="${text}">${text}</button>`)
      .join("");
    els.quickAdjust.querySelectorAll("[data-adjust]").forEach((button) => {
      button.addEventListener("click", () => {
        els.adjustInput.value = button.dataset.adjust;
        els.adjustForm.requestSubmit();
      });
    });
  }

  function buildPayload() {
    const scene = getScene();
    const checked = Array.from(els.constraintGrid.querySelectorAll("input:checked"))
      .map((input) => constraints.find((item) => item.id === input.dataset.constraint))
      .filter(Boolean);
    const startLocation = els.startLocationInput.value.trim() || "香洲";
    const startPoint = knownLocations[startLocation] || knownLocations.香洲;
    const budget = Number(els.budgetSelect.value || 300);
    const text = [
      els.intentInput.value.trim(),
      `出发地${startLocation}`,
      `出发时间${els.startTimeInput.value}`,
      `游玩时长${els.durationSelect.value}`,
      `预算${budget}元以内`,
      `节奏${state.selectedPace}`,
      checked.length ? `约束${checked.map((item) => item.label).join("、")}` : "",
    ]
      .filter(Boolean)
      .join("；");

    const constraintsList = checked.map((item) => item.value);
    return {
      v2: {
        user_input: text,
        city: "珠海",
        pace: state.selectedPace,
        preferences: scene.preferences,
        constraints: constraintsList,
        start_point: startPoint,
      },
      v1: {
        user_input: text,
        start_location: startLocation,
        agent: true,
        version: "b",
      },
    };
  }

  async function planRoute() {
    if (state.planning) return;
    state.planning = true;
    state.abortController = new AbortController();
    els.planBtn.disabled = true;
    els.planBtn.querySelector("span").textContent = "生成中";
    setSource("local");
    state.steps = [];
    state.routeId = "";
    state.fullRoute = null;
    renderPhases("parsing");
    setRoute({ steps: [], metadata: {}, title: "正在生成路线" }, "local", { keepPhases: true });
    document.body.dataset.mobileView = "map";
    syncMobileTabs();

    try {
      const payload = buildPayload();
      await api.plan(payload, {
        signal: state.abortController.signal,
        onPhase: (data) => {
          const phase = data.phase || "parsing";
          renderPhases(phase);
          els.mapHint.textContent = data.message || "正在生成路线";
        },
        onStep: (step) => {
          const normalized = normalizeStep(step, state.steps.length);
          if (normalized && normalized.poi) {
            state.steps.push(normalized);
            setRoute({ steps: state.steps, metadata: computeMetadata(state.steps) }, "backend", { keepPhases: true });
          }
        },
        onDone: (data) => {
          const route = normalizeDone(data);
          setRoute(route, "backend");
          markAllPhasesDone();
          showToast("路线已由后端生成");
        },
        onError: (data) => {
          throw new Error(data.error || "路线生成失败");
        },
      });
    } catch (error) {
      if (error.name !== "AbortError") {
        renderPhases("parsing", "已切换预览");
        setRoute(buildFallbackRoute(), "local");
        showToast("后端暂不可用，已用本地数据生成预览路线");
      }
    } finally {
      state.planning = false;
      els.planBtn.disabled = false;
      els.planBtn.querySelector("span").textContent = "生成路线";
      refreshIcons();
    }
  }

  function markAllPhasesDone() {
    els.phaseList.querySelectorAll(".phase-row").forEach((row) => {
      row.classList.remove("running", "error");
      row.classList.add("done");
      row.querySelector(".phase-message").textContent = "完成";
    });
  }

  function normalizeDone(data) {
    const fullRoute = data.full_route || data.route || {};
    const rawSteps = fullRoute.route || data.route || state.steps || [];
    const steps = rawSteps
      .map((step, index) => normalizeStep(step, index, fullRoute.narrative))
      .filter((step) => step && step.poi && !step.poi._is_point);
    return {
      steps,
      routeId: data.route_id || state.routeId,
      fullRoute,
      metadata: data.metadata || fullRoute.metadata || computeMetadata(steps),
      emotionCurve: data.emotion_curve || fullRoute.emotion_curve || buildEmotionCurve(steps),
      narrative: fullRoute.narrative || {},
      title: makeRouteTitle(),
    };
  }

  function normalizeStep(step, index, narrative) {
    if (!step) return null;
    const poi = step.poi || step;
    const narrativeSteps = narrative && Array.isArray(narrative.steps) ? narrative.steps : [];
    return {
      index: step.index || index + 1,
      poi,
      arrival_time: step.arrival_time || addMinutes(els.startTimeInput.value || "09:30", index * 82),
      departure_time: step.departure_time || addMinutes(els.startTimeInput.value || "09:30", index * 82 + (poi.avg_stay_min || 60)),
      travel_from_prev: step.travel_from_prev || null,
      narrative: narrativeToText(step.narrative || narrativeSteps[index]) || makeReason(poi),
    };
  }

  function setRoute(route, source, options) {
    const opts = options || {};
    if (!opts.keepPhases) {
      renderPhases();
    }
    setSource(source);
    state.steps = route.steps || [];
    state.routeId = route.routeId || state.routeId || "";
    state.fullRoute = route.fullRoute || state.fullRoute || null;
    state.metadata = route.metadata || computeMetadata(state.steps);
    state.emotionCurve = route.emotionCurve || buildEmotionCurve(state.steps);
    state.selectedIndex = Math.min(state.selectedIndex, Math.max(state.steps.length - 1, 0));

    els.routeTitle.textContent = route.title || makeRouteTitle();
    els.mapHint.textContent = state.steps.length ? "点击地图点或右侧站点可查看详情" : "路线点位会随生成过程逐步出现";
    els.routeReason.textContent = getRouteReason(route);
    renderMetrics();
    renderRouteList();
    renderTimeline();
    renderEmotionBars();
    drawMap();
    refreshIcons();
  }

  function buildFallbackRoute() {
    const scene = getScene();
    const paceCount = state.selectedPace === "特种兵型" ? 6 : state.selectedPace === "闲逛型" ? 4 : 5;
    const selected = pickLocalPois(scene, paceCount);
    const start = els.startTimeInput.value || "09:30";
    const steps = selected.map((poi, index) => {
      const arrival = addMinutes(start, index * 90);
      const stay = poi.avg_stay_min || (poi.category === "餐饮" ? 80 : 60);
      return {
        index: index + 1,
        poi,
        arrival_time: arrival,
        departure_time: addMinutes(arrival, stay),
        travel_from_prev: index === 0 ? null : estimateTravel(selected[index - 1], poi),
        narrative: makeReason(poi),
      };
    });
    return {
      steps,
      metadata: computeMetadata(steps),
      emotionCurve: buildEmotionCurve(steps),
      title: makeRouteTitle(),
      narrative: {
        opening: getScene().prompt,
      },
    };
  }

  function pickLocalPois(scene, count) {
    const pool = (state.pois && state.pois.length ? state.pois : fallbackPois)
      .filter((poi) => poi.city === "珠海" && poi.lat && poi.lng)
      .filter((poi) => !isLikelyBadPoi(poi));
    const used = new Set();
    const picks = [];

    for (const category of scene.categories) {
      const candidate = pool
        .filter((poi) => !used.has(poi.id))
        .filter((poi) => !category || normalizeCategory(poi.category) === normalizeCategory(category))
        .sort((a, b) => scorePoi(b, scene) - scorePoi(a, scene))[0];
      if (candidate) {
        used.add(candidate.id);
        picks.push(candidate);
      }
      if (picks.length >= count) break;
    }

    if (picks.length < count) {
      pool
        .filter((poi) => !used.has(poi.id))
        .sort((a, b) => scorePoi(b, scene) - scorePoi(a, scene))
        .slice(0, count - picks.length)
        .forEach((poi) => {
          used.add(poi.id);
          picks.push(poi);
        });
    }

    const route = picks.length ? picks : fallbackPois.slice(0, count);
    return orderGeographically(route);
  }

  function scorePoi(poi, scene) {
    const text = [
      poi.name,
      poi.category,
      ...cleanTags(poi.tags || [], poi._scene_tags || []),
    ].join(" ");
    let score = Number(poi.rating || 0) * 1.2;
    const start = knownLocations[els.startLocationInput.value.trim()] || knownLocations.香洲;
    const distanceFromStart = poi.lat && poi.lng ? haversine(start.lat, start.lng, poi.lat, poi.lng) : 20;
    score -= Math.min(distanceFromStart, 35) * 0.35;
    if (distanceFromStart <= 12) score += 1.5;
    for (const tag of scene.tags) {
      if (text.includes(tag)) score += 4;
    }
    if (poi._llm_quality && poi._llm_quality.is_tourist) score += 1.2;
    if (poi.avg_price <= Number(els.budgetSelect.value || 300)) score += 1;
    if (isConstraintChecked("easy") && (poi.emotion_tags || {}).physical_demand <= 0.45) score += 1.4;
    if (isConstraintChecked("queue") && (poi.constraints || {}).queue_time_min <= 12) score += 1.2;
    if (isConstraintChecked("family") && (poi._suitability || {}).亲子友好) score += 1.4;
    if (isConstraintChecked("accessible") && (poi.constraints || {}).accessible) score += 1.4;
    if (isConstraintChecked("pet") && (poi.constraints || {}).pet_friendly) score += 1.4;
    if (isConstraintChecked("indoor") && ((poi.constraints || {}).is_indoor || text.includes("室内"))) score += 1.4;
    return score;
  }

  function orderGeographically(pois) {
    if (!pois.length) return pois;
    const start = knownLocations[els.startLocationInput.value.trim()] || knownLocations.香洲;
    const remaining = [...pois];
    const ordered = [];
    let cursor = start;

    while (remaining.length) {
      remaining.sort((a, b) => haversine(cursor.lat, cursor.lng, a.lat, a.lng) - haversine(cursor.lat, cursor.lng, b.lat, b.lng));
      const next = remaining.shift();
      ordered.push(next);
      cursor = next;
    }

    return ordered;
  }

  function isLikelyBadPoi(poi) {
    const name = poi.name || "";
    return /Macau|Museu|Casa|Lisboa|Venetian|Parisian|Wynn/i.test(name);
  }

  function normalizeCategory(category) {
    if (!category) return "";
    if (["餐饮", "美食", "夜市小吃", "海景咖啡馆"].includes(category)) return "餐饮";
    if (["文化景点", "文化"].includes(category)) return "文化";
    if (["自然风光", "观景地标"].includes(category)) return "景点";
    return category;
  }

  function isConstraintChecked(id) {
    const input = els.constraintGrid.querySelector(`[data-constraint="${id}"]`);
    return Boolean(input && input.checked);
  }

  function renderMetrics() {
    const metadata = state.metadata || {};
    const totalTime = metadata.total_time_min || metadata.time_min || computeMetadata(state.steps).total_time_min;
    const budget = metadata.estimated_budget || metadata.budget_used || computeMetadata(state.steps).estimated_budget;
    const distance = metadata.total_distance_m || computeMetadata(state.steps).total_distance_m;
    els.metricStops.textContent = String(state.steps.length);
    els.metricTime.textContent = formatHours(totalTime);
    els.metricCost.textContent = Math.round(budget || 0) + "元";
    els.metricDistance.textContent = formatDistance(distance || 0);
  }

  function renderRouteList() {
    if (!state.steps.length) {
      els.routeList.innerHTML = `<div class="empty-state">路线生成后，会在这里显示每一站的时间、地点和推荐原因。</div>`;
      return;
    }

    els.routeList.innerHTML = state.steps
      .map((step, index) => {
        const poi = step.poi;
        const tags = cleanTags([poi.category], poi._scene_tags || poi.tags || []).slice(0, 3);
        return `
          <article class="route-card ${index === state.selectedIndex ? "active" : ""}" data-index="${index}">
            <div class="route-index">${index + 1}</div>
            <div class="route-main">
              <div class="route-top">
                <span class="route-name">${escapeHTML(poi.name)}</span>
                <span class="route-time">${escapeHTML(step.arrival_time || "")}</span>
              </div>
              <div class="route-meta">${escapeHTML(poi.category || "地点")} · ${formatPrice(poi.avg_price)} · ${formatRating(poi.rating)} · 停留 ${poi.avg_stay_min || 60} 分钟</div>
              <div class="tag-row">
                ${tags.map((tag, tagIndex) => `<span class="tag ${tagIndex === 1 ? "amber" : ""}">${escapeHTML(tag)}</span>`).join("")}
              </div>
              <div class="route-note">${escapeHTML(getStepNarrative(step))}</div>
              <div class="route-actions">
                <button class="mini-action" type="button" data-action="detail" data-index="${index}"><i data-lucide="info"></i>详情</button>
                <button class="mini-action" type="button" data-action="replace" data-index="${index}"><i data-lucide="shuffle"></i>替换</button>
                <button class="mini-action" type="button" data-action="remove" data-index="${index}"><i data-lucide="trash-2"></i>删除</button>
              </div>
            </div>
          </article>
        `;
      })
      .join("");

    els.routeList.querySelectorAll(".route-card").forEach((card) => {
      card.addEventListener("click", (event) => {
        if (event.target.closest("button")) return;
        selectStep(Number(card.dataset.index));
      });
    });

    els.routeList.querySelectorAll("[data-action]").forEach((button) => {
      button.addEventListener("click", () => {
        const index = Number(button.dataset.index);
        if (button.dataset.action === "detail") openPOIDialog(state.steps[index]);
        if (button.dataset.action === "replace") replaceStep(index);
        if (button.dataset.action === "remove") removeStep(index);
      });
    });
  }

  function renderTimeline() {
    if (!state.steps.length) {
      els.timelineBand.innerHTML = "";
      return;
    }

    els.timelineBand.innerHTML = state.steps
      .map((step, index) => `
        <button class="timeline-item ${index === state.selectedIndex ? "active" : ""}" type="button" data-index="${index}">
          <span class="timeline-time">${escapeHTML(step.arrival_time || "")}</span>
          <span class="timeline-name">${escapeHTML(step.poi.name)}</span>
          <span class="timeline-meta">${escapeHTML(step.poi.category || "地点")} · ${formatPrice(step.poi.avg_price)}</span>
        </button>
      `)
      .join("");

    els.timelineBand.querySelectorAll(".timeline-item").forEach((item) => {
      item.addEventListener("click", () => selectStep(Number(item.dataset.index)));
    });
  }

  function renderEmotionBars() {
    const averages = averageEmotions(state.steps);
    const labels = [
      ["tranquility", "宁静"],
      ["culture_depth", "文化"],
      ["excitement", "兴奋"],
      ["surprise", "惊喜"],
      ["sociability", "社交"],
    ];
    els.emotionBars.innerHTML = labels
      .map(([key, label]) => {
        const value = Math.max(0, Math.min(1, averages[key] || 0));
        return `
          <div class="emotion-bar">
            <span>${label}</span>
            <span class="emotion-track"><span class="emotion-fill" style="width:${Math.round(value * 100)}%"></span></span>
            <span>${Math.round(value * 100)}</span>
          </div>
        `;
      })
      .join("");
  }

  function selectStep(index) {
    state.selectedIndex = Math.max(0, Math.min(index, state.steps.length - 1));
    renderRouteList();
    renderTimeline();
    drawMap();
    refreshIcons();
  }

  function openPOIDialog(step) {
    if (!step || !step.poi) return;
    const poi = step.poi;
    const emotion = poi.emotion_tags || {};
    const constraints = poi.constraints || {};
    const suitability = poi._suitability || {};
    const tags = cleanTags(poi._scene_tags || [], poi.tags || []).slice(0, 6);

    els.poiDialogBody.innerHTML = `
      <h3>${escapeHTML(poi.name)}</h3>
      <p>${escapeHTML(getStepNarrative(step))}</p>
      <div class="dialog-stats">
        <div class="dialog-stat"><span>评分</span><strong>${formatRating(poi.rating)}</strong></div>
        <div class="dialog-stat"><span>价格</span><strong>${formatPrice(poi.avg_price)}</strong></div>
        <div class="dialog-stat"><span>营业时间</span><strong>${escapeHTML(poi.business_hours || constraints.opening_hours || "待确认")}</strong></div>
        <div class="dialog-stat"><span>建议停留</span><strong>${poi.avg_stay_min || 60} 分钟</strong></div>
        <div class="dialog-stat"><span>排队</span><strong>${constraints.queue_time_min != null ? constraints.queue_time_min + " 分钟" : "较低"}</strong></div>
        <div class="dialog-stat"><span>无障碍</span><strong>${constraints.accessible === false ? "未确认" : "支持"}</strong></div>
      </div>
      <div class="tag-row">${tags.map((tag) => `<span class="tag">${escapeHTML(tag)}</span>`).join("")}</div>
      <p>适合：${Object.keys(suitability).filter((key) => suitability[key]).slice(0, 4).join("、") || "多数出行场景"}</p>
      <p>情绪标签：宁静 ${toPct(emotion.tranquility)}，文化 ${toPct(emotion.culture_depth)}，兴奋 ${toPct(emotion.excitement)}，惊喜 ${toPct(emotion.surprise)}</p>
    `;
    if (typeof els.poiDialog.showModal === "function") {
      els.poiDialog.showModal();
    } else {
      showToast(poi.name);
    }
  }

  function replaceStep(index) {
    const current = state.steps[index];
    if (!current) return;
    const scene = getScene();
    const used = new Set(state.steps.map((step) => step.poi.id));
    const alternative = (state.pois.length ? state.pois : fallbackPois)
      .filter((poi) => poi.lat && poi.lng && !used.has(poi.id))
      .filter((poi) => normalizeCategory(poi.category) === normalizeCategory(current.poi.category))
      .sort((a, b) => scorePoi(b, scene) - scorePoi(a, scene))[0];

    if (!alternative) {
      showToast("暂时没有找到更合适的同类地点");
      return;
    }
    state.steps[index].poi = alternative;
    state.steps[index].narrative = makeReason(alternative);
    recalcLocalRoute("已替换 " + current.poi.name);
  }

  function removeStep(index) {
    if (state.steps.length <= 2) {
      showToast("路线至少保留两个站点");
      return;
    }
    const removed = state.steps.splice(index, 1)[0];
    recalcLocalRoute("已删除 " + removed.poi.name);
  }

  function recalcLocalRoute(message) {
    const start = els.startTimeInput.value || "09:30";
    state.steps = state.steps.map((step, index) => ({
      ...step,
      index: index + 1,
      arrival_time: addMinutes(start, index * 90),
      departure_time: addMinutes(start, index * 90 + (step.poi.avg_stay_min || 60)),
      travel_from_prev: index === 0 ? null : estimateTravel(state.steps[index - 1].poi, step.poi),
    }));
    setRoute({
      steps: state.steps,
      metadata: computeMetadata(state.steps),
      emotionCurve: buildEmotionCurve(state.steps),
      title: makeRouteTitle(),
    }, state.source);
    showToast(message);
  }

  async function handleAdjust(event) {
    event.preventDefault();
    const instruction = els.adjustInput.value.trim();
    if (!instruction) return;
    addMessage(instruction, "user");
    els.adjustInput.value = "";

    if (state.routeId && state.source === "backend") {
      try {
        const result = await api.adjust(state.routeId, instruction);
        addMessage(result.reply || "已根据你的想法调整路线", "system");
        if (result.route) {
          const route = {
            steps: (result.route.route || []).map((step, index) => normalizeStep(step, index, result.route.narrative)),
            metadata: computeMetadata(result.route.route || []),
            fullRoute: result.route,
            routeId: state.routeId,
            title: makeRouteTitle(),
          };
          setRoute(route, "backend");
        }
        return;
      } catch (_error) {
        addMessage("后端调整暂不可用，已在本地做轻量调整。", "system");
      }
    } else {
      addMessage("已在本地预览里调整，接通后端后会使用真实对话接口。", "system");
    }

    applyLocalInstruction(instruction);
  }

  function applyLocalInstruction(instruction) {
    if (instruction.includes("便宜")) {
      const sorted = [...state.steps].sort((a, b) => (a.poi.avg_price || 0) - (b.poi.avg_price || 0));
      state.steps = sorted.slice(0, state.steps.length);
      recalcLocalRoute("已优先保留低消费地点");
    } else if (instruction.includes("海边") || instruction.includes("看海")) {
      state.selectedScene = "coast";
      renderScenes();
      setRoute(buildFallbackRoute(), "local");
    } else if (instruction.includes("换")) {
      replaceStep(Math.min(1, state.steps.length - 1));
    } else if (instruction.includes("少走") || instruction.includes("太赶") || instruction.includes("轻松")) {
      state.selectedPace = "闲逛型";
      renderPaces();
      state.steps = state.steps.slice(0, Math.max(3, Math.min(4, state.steps.length)));
      recalcLocalRoute("已改为更轻松的节奏");
    } else {
      setRoute(buildFallbackRoute(), "local");
    }
  }

  function addMessage(text, type) {
    const div = document.createElement("div");
    div.className = "message " + (type === "user" ? "user" : "system");
    div.textContent = text;
    els.chatLog.appendChild(div);
    els.chatLog.scrollTop = els.chatLog.scrollHeight;
  }

  function drawMap() {
    renderAmapRoute();
  }

  function renderAmapRoute() {
    if (!state.amapReady || !state.amapMap || !state.amap) {
      setMapStatus(els.amapKeyInput.value.trim() ? "点击加载地图，接入高德真实底图" : "填写高德 JS API Key 后加载真实地图");
      return;
    }

    const AMap = state.amap;
    const map = state.amapMap;
    clearAmapOverlays();
    if (typeof map.resize === "function") map.resize();

    const steps = getMapSteps();
    if (!steps.length) {
      map.setCenter([113.576, 22.271]);
      map.setZoom(12);
      setMapStatus("已接入高德地图，路线点位会随生成过程逐步出现");
      return;
    }

    const path = steps.map((step) => [Number(step.poi.lng), Number(step.poi.lat)]);
    const polyline = new AMap.Polyline({
      path,
      strokeColor: "#117c76",
      strokeWeight: 6,
      strokeOpacity: 0.86,
      lineJoin: "round",
      lineCap: "round",
      showDir: true,
    });
    map.add(polyline);
    state.amapOverlays.push(polyline);

    steps.forEach((step, index) => {
      const marker = new AMap.Marker({
        position: path[index],
        anchor: "center",
        content: `<div class="amap-route-marker ${index === state.selectedIndex ? "active" : ""}">${index + 1}</div>`,
        zIndex: index === state.selectedIndex ? 120 : 90,
      });
      marker.on("click", () => {
        selectStep(index);
        openPOIDialog(step);
      });
      map.add(marker);
      state.amapOverlays.push(marker);
    });

    const activeStep = steps[state.selectedIndex] || steps[0];
    if (activeStep && activeStep.poi) {
      state.amapInfoWindow = new AMap.InfoWindow({
        isCustom: false,
        offset: new AMap.Pixel(0, -28),
        content: `
          <div class="amap-info-window">
            <strong>${escapeHTML(activeStep.poi.name)}</strong>
            <span>${escapeHTML(activeStep.poi.category || "地点")} · ${formatPrice(activeStep.poi.avg_price)} · ${formatRating(activeStep.poi.rating)}</span>
          </div>
        `,
      });
      state.amapInfoWindow.open(map, [Number(activeStep.poi.lng), Number(activeStep.poi.lat)]);
    }

    if (path.length === 1) {
      map.setCenter(path[0]);
      map.setZoom(15);
    } else {
      map.setFitView(state.amapOverlays, false, [56, 42, 56, 42], 16);
    }
    setMapStatus("已接入高德地图，点击地图点或右侧站点可查看详情");
  }

  function getMapSteps() {
    return state.steps.filter((step) => {
      const poi = step && step.poi;
      const lat = poi && Number(poi.lat);
      const lng = poi && Number(poi.lng);
      return Number.isFinite(lat) && Number.isFinite(lng);
    });
  }

  function clearAmapOverlays() {
    if (!state.amapMap) return;
    if (state.amapInfoWindow && typeof state.amapInfoWindow.close === "function") {
      state.amapInfoWindow.close();
    }
    if (state.amapOverlays.length) {
      state.amapMap.remove(state.amapOverlays);
    }
    state.amapOverlays = [];
    state.amapInfoWindow = null;
  }

  function drawMapBase(ctx, w, h) {
    ctx.fillStyle = "#cfe7e3";
    ctx.fillRect(0, 0, w, h);

    ctx.fillStyle = "#f6fbf8";
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(w * 0.42, 0);
    ctx.bezierCurveTo(w * 0.38, h * 0.16, w * 0.22, h * 0.22, w * 0.18, h * 0.38);
    ctx.bezierCurveTo(w * 0.15, h * 0.5, w * 0.05, h * 0.58, 0, h * 0.72);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = "rgba(17, 124, 118, 0.18)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(w * 0.08, h * 0.72);
    ctx.bezierCurveTo(w * 0.24, h * 0.64, w * 0.46, h * 0.7, w * 0.66, h * 0.6);
    ctx.stroke();

    ctx.strokeStyle = "rgba(255,255,255,0.52)";
    ctx.lineWidth = 1;
    for (let i = 0; i < 4; i += 1) {
      const y = h * (0.22 + i * 0.16);
      ctx.beginPath();
      ctx.moveTo(w * 0.42, y);
      ctx.bezierCurveTo(w * 0.56, y - 18, w * 0.72, y + 18, w * 0.92, y - 8);
      ctx.stroke();
    }

    ctx.fillStyle = "rgba(17, 124, 118, 0.18)";
    ctx.font = "700 12px " + getComputedStyle(document.body).fontFamily;
    ctx.fillText("Zhuhai Coast", 18, h - 22);
  }

  function drawEmptyRoute(ctx, w, h) {
    ctx.strokeStyle = "rgba(17, 124, 118, 0.52)";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(w * 0.22, h * 0.32);
    ctx.bezierCurveTo(w * 0.38, h * 0.2, w * 0.55, h * 0.42, w * 0.72, h * 0.34);
    ctx.bezierCurveTo(w * 0.78, h * 0.3, w * 0.82, h * 0.48, w * 0.66, h * 0.58);
    ctx.stroke();
    [0.22, 0.42, 0.6, 0.72].forEach((x, index) => {
      const y = [0.32, 0.27, 0.48, 0.34][index];
      drawNumberedDot(ctx, x * w, y * h, index + 1, index === 0);
    });
  }

  function drawNearbyDots(ctx, w, h, bounds) {
    if (!state.pois.length) return;
    ctx.fillStyle = "rgba(17, 124, 118, 0.34)";
    const sample = state.pois.filter((poi) => poi.lat && poi.lng).slice(0, 160);
    sample.forEach((poi) => {
      const p = projectPoint(poi, w, h, bounds);
      if (!p) return;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 2, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  function drawRouteLine(ctx, points) {
    if (points.items.length < 2) return;
    ctx.save();
    ctx.lineWidth = 4;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    const gradient = ctx.createLinearGradient(
      points.items[0].x,
      points.items[0].y,
      points.items[points.items.length - 1].x,
      points.items[points.items.length - 1].y
    );
    gradient.addColorStop(0, "#117c76");
    gradient.addColorStop(1, "#c98719");
    ctx.strokeStyle = gradient;
    ctx.beginPath();
    points.items.forEach((point, index) => {
      if (index === 0) ctx.moveTo(point.x, point.y);
      else ctx.lineTo(point.x, point.y);
    });
    ctx.stroke();
    ctx.restore();
  }

  function drawRouteStops(ctx, points) {
    points.items.forEach((point, index) => {
      const active = index === state.selectedIndex;
      if (active) {
        ctx.fillStyle = "rgba(200,95,73,0.16)";
        ctx.beginPath();
        ctx.arc(point.x, point.y, 24, 0, Math.PI * 2);
        ctx.fill();
      }
      drawNumberedDot(ctx, point.x, point.y, index + 1, active);

      if (active) {
        const label = point.step.poi.name;
        ctx.font = "800 13px " + getComputedStyle(document.body).fontFamily;
        const width = Math.min(ctx.measureText(label).width + 24, 220);
        const x = Math.min(point.x + 18, ctx.canvas.width - width - 16);
        const y = Math.max(point.y - 16, 18);
        ctx.fillStyle = "rgba(255,255,255,0.94)";
        roundRect(ctx, x, y, width, 30, 8);
        ctx.fill();
        ctx.fillStyle = "#1d2b2a";
        ctx.fillText(label.slice(0, 14), x + 12, y + 20);
      }

      state.canvasPoints.push({ x: point.x, y: point.y, index });
    });
  }

  function drawNumberedDot(ctx, x, y, index, active) {
    ctx.fillStyle = "#ffffff";
    ctx.strokeStyle = active ? "#c85f49" : "#117c76";
    ctx.lineWidth = active ? 3 : 2;
    ctx.beginPath();
    ctx.arc(x, y, active ? 15 : 13, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = active ? "#a6422d" : "#117c76";
    ctx.font = "900 12px " + getComputedStyle(document.body).fontFamily;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(index), x, y + 0.5);
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
  }

  function projectRoutePoints(steps, w, h) {
    const lats = steps.map((step) => Number(step.poi.lat));
    const lngs = steps.map((step) => Number(step.poi.lng));
    const padLat = 0.018;
    const padLng = 0.018;
    const bounds = {
      minLat: Math.min(...lats) - padLat,
      maxLat: Math.max(...lats) + padLat,
      minLng: Math.min(...lngs) - padLng,
      maxLng: Math.max(...lngs) + padLng,
    };
    return {
      bounds,
      items: steps.map((step) => ({ ...projectPoint(step.poi, w, h, bounds), step })),
    };
  }

  function projectPoint(poi, w, h, bounds) {
    const lat = Number(poi.lat);
    const lng = Number(poi.lng);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
    const xRatio = (lng - bounds.minLng) / Math.max(bounds.maxLng - bounds.minLng, 0.0001);
    const yRatio = (lat - bounds.minLat) / Math.max(bounds.maxLat - bounds.minLat, 0.0001);
    return {
      x: w * 0.14 + xRatio * w * 0.72,
      y: h * 0.16 + (1 - yRatio) * h * 0.66,
    };
  }

  function roundRect(ctx, x, y, width, height, radius) {
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.arcTo(x + width, y, x + width, y + height, radius);
    ctx.arcTo(x + width, y + height, x, y + height, radius);
    ctx.arcTo(x, y + height, x, y, radius);
    ctx.arcTo(x, y, x + width, y, radius);
    ctx.closePath();
  }

  function handleCanvasClick(event) {
    if (!state.canvasPoints.length) return;
    const rect = els.routeCanvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    let best = null;
    for (const point of state.canvasPoints) {
      const distance = Math.hypot(point.x - x, point.y - y);
      if (distance < 28 && (!best || distance < best.distance)) {
        best = { ...point, distance };
      }
    }
    if (best) {
      selectStep(best.index);
      openPOIDialog(state.steps[best.index]);
    }
  }

  function computeMetadata(steps) {
    const list = (steps || []).filter((step) => step && step.poi);
    const totalTime = list.reduce((sum, step) => sum + (step.poi.avg_stay_min || 60), 0) + Math.max(0, list.length - 1) * 18;
    const budget = list.reduce((sum, step) => sum + Number(step.poi.avg_price || 0), 0);
    const distance = list.reduce((sum, step, index) => {
      if (index === 0) return 0;
      return sum + estimateTravel(list[index - 1].poi, step.poi).distance_m;
    }, 0);
    return {
      total_time_min: totalTime,
      estimated_budget: budget,
      total_distance_m: distance,
      poi_count: list.length,
      pace: state.selectedPace,
    };
  }

  function estimateTravel(a, b) {
    const distance = haversine(a.lat, a.lng, b.lat, b.lng) * 1.3;
    return {
      distance_m: Math.round(distance * 1000),
      time_min: Math.max(5, Math.round((distance / 28) * 60)),
    };
  }

  function haversine(lat1, lng1, lat2, lng2) {
    const r = 6371;
    const toRad = (value) => (Number(value) * Math.PI) / 180;
    const dLat = toRad(lat2 - lat1);
    const dLng = toRad(lng2 - lng1);
    const a = Math.sin(dLat / 2) ** 2 +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
    return r * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  function buildEmotionCurve(steps) {
    return (steps || []).map((step) => ({
      poi_id: step.poi.id,
      poi_name: step.poi.name,
      ...(step.poi.emotion_tags || {}),
    }));
  }

  function averageEmotions(steps) {
    const keys = ["excitement", "tranquility", "sociability", "culture_depth", "surprise", "physical_demand"];
    const result = {};
    keys.forEach((key) => {
      const values = (steps || []).map((step) => (step.poi.emotion_tags || {})[key]).filter((value) => Number.isFinite(Number(value)));
      result[key] = values.length ? values.reduce((sum, value) => sum + Number(value), 0) / values.length : 0.5;
    });
    return result;
  }

  function makeReason(poi) {
    const tags = cleanTags(poi._scene_tags || poi.tags || []).slice(0, 2).join("、");
    const base = tags ? `这里的${tags}和当前需求比较匹配` : "这里和当前路线节奏比较匹配";
    const price = Number(poi.avg_price || 0) === 0 ? "，消费压力低" : `，人均约 ${poi.avg_price} 元`;
    const queue = (poi.constraints || {}).queue_time_min != null ? `，预计排队 ${poi.constraints.queue_time_min} 分钟` : "";
    return base + price + queue + "。";
  }

  function getStepNarrative(step) {
    if (!step || !step.poi) return "";
    return narrativeToText(step.narrative) || makeReason(step.poi);
  }

  function narrativeToText(value) {
    if (!value) return "";
    if (typeof value === "string") return value;
    if (typeof value === "object") {
      return String(
        value.description ||
        value.design_intent ||
        value.reason ||
        value.text ||
        value.summary ||
        ""
      ).trim();
    }
    return "";
  }

  function getRouteReason(route) {
    const narrative = route && route.narrative;
    if (narrative && narrative.opening) return narrative.opening;
    const scene = getScene();
    return `这条路线偏向${scene.label}，结合了${state.selectedPace}、预算和低排队约束，优先选择地理上更顺的地点。`;
  }

  function makeRouteTitle() {
    return "珠海" + getScene().label + "路线";
  }

  function getScene() {
    return scenes.find((scene) => scene.id === state.selectedScene) || scenes[0];
  }

  function addMinutes(time, minutes) {
    const parts = String(time || "09:30").split(":");
    let total = Number(parts[0] || 9) * 60 + Number(parts[1] || 30) + Number(minutes || 0);
    total = ((total % 1440) + 1440) % 1440;
    const h = Math.floor(total / 60);
    const m = total % 60;
    return String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0");
  }

  function formatHours(minutes) {
    const value = Number(minutes || 0) / 60;
    return value ? value.toFixed(value >= 10 ? 0 : 1) + "h" : "0h";
  }

  function formatDistance(meters) {
    const km = Number(meters || 0) / 1000;
    return km ? km.toFixed(km >= 10 ? 0 : 1) + "km" : "0km";
  }

  function formatPrice(value) {
    const price = Number(value || 0);
    return price > 0 ? `${Math.round(price)}元` : "免费";
  }

  function formatRating(value) {
    return value ? `评分 ${Number(value).toFixed(1)}` : "暂无评分";
  }

  function toPct(value) {
    return Math.round(Number(value || 0) * 100) + "%";
  }

  function cleanTags(...groups) {
    const seen = new Set();
    const result = [];
    groups.forEach((group) => {
      const items = Array.isArray(group) ? group : [group];
      items.forEach((item) => {
        const text = tagToText(item);
        if (text && !seen.has(text)) {
          seen.add(text);
          result.push(text);
        }
      });
    });
    return result;
  }

  function tagToText(item) {
    if (item == null) return "";
    if (typeof item === "string" || typeof item === "number") return String(item);
    if (typeof item === "object") {
      return String(item.name || item.label || item.tag || item.value || item.title || "").trim();
    }
    return "";
  }

  function escapeHTML(text) {
    const div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  function copyRouteSummary() {
    if (!state.steps.length) return;
    const text = [
      els.routeTitle.textContent,
      ...state.steps.map((step, index) => `${index + 1}. ${step.arrival_time} ${step.poi.name}（${step.poi.category || "地点"}，${formatPrice(step.poi.avg_price)}）`),
    ].join("\n");
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => showToast("路线摘要已复制"));
    } else {
      showToast("当前浏览器不支持自动复制");
    }
  }

  function syncMobileTabs() {
    document.querySelectorAll(".mobile-tab").forEach((button) => {
      button.classList.toggle("active", button.dataset.view === document.body.dataset.mobileView);
    });
  }

  function showToast(text) {
    els.toast.textContent = text;
    els.toast.hidden = false;
    clearTimeout(showToast._timer);
    showToast._timer = setTimeout(() => {
      els.toast.hidden = true;
    }, 2600);
  }

  init();
})();
