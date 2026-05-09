/* 3D 地图 POI 可视化：AMap GLCustomLayer + Three.js */
class Chart3D {
  constructor(container, onHover, onClick) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.onHover = onHover;
    this.onClick = onClick;
    this.data = [];
    this.currentCity = null;
    this.map = null;
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.glLayer = null;
    this.customCoords = null;
    this.meshes = [];
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();
    this.glReady = false;
    this.hoveredMesh = null;
    this.infoWindow = null;

    // 流量可视化
    this.orderData = null;
    this.orderMode = false;
    this._orderAnimId = null;
    this._pulseRings = [];        // 脉冲光环对象池
    this._pulseAnimId = null;
    this.heatmap = null;           // AMap 热力图实例
    this._heatmapVisible = false;

    // 路况可视化
    this.roadTrafficData = null;
    this.roadTrafficMode = false;
    this._roadPolylines = [];  // AMap.Polyline 对象池

    // 品类颜色 (hex)
    this.COLORS = {
      '餐饮': 0xFF8C00, '购物': 0xFFD700, '酒店': 0x4169E1,
      '文化': 0x9932CC, '运动': 0x228B22, '其他': 0x888888,
    };

    // 城市中心
    this.CITY_CENTER = {
      '珠海': [113.55, 22.27], '广州': [113.27, 23.13], '湛江': [110.36, 21.27],
    };

    this._init();
  }

  _init() {
    window._AMapSecurityConfig = {
      securityJsCode: '8e6d3a6134d4516497913a5e295b5610',
    };

    AMapLoader.load({
      key: 'e2a4f77a5b16efcf19b88a1e87ab88fd',
      version: '2.0',
      plugins: ['AMap.Scale', 'AMap.ToolBar', 'AMap.HeatMap'],
    }).then((AMap) => {
      this.AMap = AMap;
      this.map = new AMap.Map(this.container, {
        viewMode: '3D', zoom: 11, center: this.CITY_CENTER['珠海'],
        pitch: 45, rotation: 0, mapStyle: 'amap://styles/dark',
      });

      this.map.addControl(new AMap.Scale());
      this.map.addControl(new AMap.ToolBar({ position: 'bottomRight' }));

      this.map.on('complete', () => {
        this.customCoords = this.map.customCoords;
        this._initGLLayer();
        this._initInteraction();
      });
    }).catch((e) => {
      console.error('高德地图加载失败:', e);
      this.container.innerHTML = `<div style="color:#fff;padding:20px;">地图加载失败: ${e.message}</div>`;
    });
  }

  _initGLLayer() {
    const self = this;
    this.glLayer = new this.AMap.GLCustomLayer({
      zIndex: 10,
      init: (gl) => {
        self.camera = new THREE.PerspectiveCamera(
          60, self.container.clientWidth / self.container.clientHeight, 100, 1 << 30
        );
        self.renderer = new THREE.WebGLRenderer({ context: gl });
        self.renderer.autoClear = false;
        self.renderer.setSize(self.container.clientWidth, self.container.clientHeight);
        self.scene = new THREE.Scene();
        // 光照
        const aLight = new THREE.AmbientLight(0xffffff, 0.4);
        const dLight = new THREE.DirectionalLight(0xffffff, 0.8);
        dLight.position.set(1000, -100, 900);
        self.scene.add(aLight);
        self.scene.add(dLight);
        self.glReady = true;
        if (self.data.length) self._render();
      },
      render: () => {
        if (!self.renderer || !self.camera) return;
        self.renderer.resetState();
        const center = self.CITY_CENTER[self.currentCity] || self.CITY_CENTER['珠海'];
        self.customCoords.setCenter(center);
        const { near, far, fov, up, lookAt, position } = self.customCoords.getCameraParams();
        self.camera.near = near;
        self.camera.far = far;
        self.camera.fov = fov;
        self.camera.position.set(...position);
        self.camera.up.set(...up);
        self.camera.lookAt(...lookAt);
        self.camera.updateProjectionMatrix();
        self.renderer.render(self.scene, self.camera);
        self.renderer.resetState();
      },
    });
    this.map.add(this.glLayer);
  }

  _initInteraction() {
    this.container.addEventListener('mousemove', (e) => {
      if (!this.glReady || !this.meshes.length) return;
      const rect = this.container.getBoundingClientRect();
      this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      this.raycaster.setFromCamera(this.mouse, this.camera);
      const intersects = this.raycaster.intersectObjects(this.meshes);
      if (intersects.length > 0) {
        const mesh = intersects[0].object;
        if (this.hoveredMesh !== mesh) {
          if (this.hoveredMesh) this.hoveredMesh.material.emissive.setHex(0x000000);
          this.hoveredMesh = mesh;
          mesh.material.emissive.setHex(0x333333);
        }
        if (this.onHover) this.onHover({ x: e.clientX, y: e.clientY, data: mesh.userData.poi });
      } else {
        if (this.hoveredMesh) {
          this.hoveredMesh.material.emissive.setHex(0x000000);
          this.hoveredMesh = null;
        }
        if (this.onHover) this.onHover(null);
      }
    });

    this.container.addEventListener('click', (e) => {
      if (!this.glReady || !this.meshes.length) return;
      const rect = this.container.getBoundingClientRect();
      this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      this.raycaster.setFromCamera(this.mouse, this.camera);
      const intersects = this.raycaster.intersectObjects(this.meshes);
      if (intersects.length > 0 && this.onClick) {
        this.onClick(intersects[0].object.userData.poi);
      }
    });
  }

  async loadData(city = '珠海', category = '') {
    this.currentCity = city;
    const params = new URLSearchParams();
    if (city) params.set('city', city);
    if (category) params.set('category', category);
    const url = `${API_BASE}/api/poi/${params.toString() ? '?' + params : ''}`;
    const resp = await fetch(url);
    const json = await resp.json();
    this.data = json.data;
    console.log(`加载 ${city} POI: ${this.data.length} 条`);
    if (this.glReady) {
      this._flyToCity(city);
      this._render();
    }
    return this.data.length;
  }

  _flyToCity(city) {
    const center = this.CITY_CENTER[city];
    if (!center || !this.map) return;
    this.map.setPitch(45);
    this.map.setZoomAndCenter(11, center);
  }

  _render() {
    if (!this.scene || !this.glReady) return;
    this.meshes.forEach((m) => this.scene.remove(m));
    this.meshes = [];
    this.hoveredMesh = null;
    if (!this.data.length) return;

    const maxRating = Math.max(...this.data.map((d) => d.rating));
    const minRating = Math.min(...this.data.map((d) => d.rating));
    const ratingRange = maxRating - minRating || 1;

    const lnglats = this.data.map((d) => [d.lng, d.lat]);
    const coords = this.customCoords.lngLatsToCoords(lnglats);

    const group = new THREE.Group();
    this.scene.add(group);

    this.data.forEach((poi, i) => {
      const x = coords[i][0];
      const y = coords[i][1];
      const height = 10 + ((poi.rating - minRating) / ratingRange) * 50;
      const radius = 50;
      const geo = new THREE.CylinderGeometry(radius, radius, height, 8, 1);
      const color = this.COLORS[poi.category] || this.COLORS['其他'];
      const mat = new THREE.MeshPhongMaterial({
        color: color, emissive: 0x000000,
        transparent: true, opacity: 0.85, depthTest: true,
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set(x, y, height / 2);
      mesh.userData = { poi };
      group.add(mesh);
      this.meshes.push(mesh);
    });

    this.map.render();
  }

  // ========== 流量数据 ==========

  async loadOrder(city, dayOfYear, hour) {
    const params = new URLSearchParams();
    if (city) params.set('city', city);
    if (dayOfYear != null) params.set('day_of_year', dayOfYear);
    if (hour != null) params.set('hour', hour);
    const url = `${API_BASE}/api/order/?${params.toString()}`;
    try {
      const resp = await fetch(url);
      const json = await resp.json();
      this.orderData = json;
      if (this.orderMode) {
        this._applyOrderVis();
        this._updateHeatmap();
      }
    } catch (e) {
      console.error('加载订单数据失败:', e);
    }
  }

  setOrderMode(enabled) {
    this.orderMode = enabled;
    if (enabled && this.orderData) {
      this._applyOrderVis();
      this._showHeatmap(true);
      this._updateHeatmap();
    } else if (!enabled) {
      this._stopPulse();
      this._showHeatmap(false);
      this._render();
    }
  }

  // ========== 1. 颜色 + 底面积 + 发光 ==========

  _applyOrderVis() {
    if (!this.orderData || !this.orderData.data || !this.meshes.length) return;
    const orderMap = {};
    for (const item of this.orderData.data) {
      orderMap[item.poi_id] = item;
    }
    let maxVal = 1;
    const vals = [];
    for (const mesh of this.meshes) {
      const t = orderMap[mesh.userData.poi.id];
      const val = t ? (t.hourly_orders || t.daily_orders) : 0;
      vals.push(val);
      if (val > maxVal) maxVal = val;
    }

    if (this._orderAnimId) cancelAnimationFrame(this._orderAnimId);
    const startH = this.meshes.map(m => m.scale.y * m.geometry.parameters.height);
    const startScaleX = this.meshes.map(m => m.scale.x);
    const startColor = this.meshes.map(m => m.material.color.clone());
    const startOpacity = this.meshes.map(m => m.material.opacity);
    const duration = 400;
    const startTime = performance.now();
    const self = this;

    const animate = (now) => {
      const elapsed = now - startTime;
      const t = Math.min(elapsed / duration, 1);
      const ease = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;

      for (let i = 0; i < self.meshes.length; i++) {
        const ratio = vals[i] / maxVal;
        const mesh = self.meshes[i];

        // 高度 10-40
        const targetH = 10 + ratio * 30;
        const currentH = startH[i] + (targetH - startH[i]) * ease;
        const geoH = mesh.geometry.parameters.height;
        mesh.scale.y = currentH / geoH;
        mesh.position.z = currentH / 2;

        // 底面积：0.6-1.4
        const targetScaleX = 0.6 + ratio * 0.8;
        mesh.scale.x = startScaleX[i] + (targetScaleX - startScaleX[i]) * ease;
        mesh.scale.z = mesh.scale.x;

        // 颜色：蓝→青→绿→黄→红
        const targetColor = self._orderColor(ratio);
        mesh.material.color.copy(startColor[i]).lerp(targetColor, ease);

        // 发光
        mesh.material.emissive.copy(targetColor).multiplyScalar(0.1 + ratio * 0.4);

        // 透明度
        const targetOp = 0.5 + ratio * 0.5;
        mesh.material.opacity = startOpacity[i] + (targetOp - startOpacity[i]) * ease;
      }

      if (t < 1) {
        self._orderAnimId = requestAnimationFrame(animate);
      } else {
        self._orderAnimId = null;
        // 动画结束后启动脉冲光环
        self._startPulse(vals, maxVal);
      }
    };
    this._orderAnimId = requestAnimationFrame(animate);
  }

  _orderColor(ratio) {
    const stops = [
      [0, 0x22, 0x66, 0xff], [0.25, 0x00, 0xcc, 0xaa],
      [0.5, 0x44, 0xbb, 0x22], [0.75, 0xff, 0xaa, 0x00],
      [1.0, 0xff, 0x22, 0x22],
    ];
    for (let i = 0; i < stops.length - 1; i++) {
      if (ratio <= stops[i + 1][0]) {
        const local = (ratio - stops[i][0]) / (stops[i + 1][0] - stops[i][0]);
        const r = Math.round(stops[i][1] + (stops[i + 1][1] - stops[i][1]) * local);
        const g = Math.round(stops[i][2] + (stops[i + 1][2] - stops[i][2]) * local);
        const b = Math.round(stops[i][3] + (stops[i + 1][3] - stops[i][3]) * local);
        return new THREE.Color(r / 255, g / 255, b / 255);
      }
    }
    return new THREE.Color(1, 0.13, 0.13);
  }

  // ========== 2. 脉冲光环（雷达扫描效果）==========

  _startPulse(vals, maxVal) {
    this._stopPulse();
    if (!this.scene) return;

    // 只给 Top30 的点加脉冲
    const indexed = vals.map((v, i) => ({ v, i }));
    indexed.sort((a, b) => b.v - a.v);
    const topN = indexed.slice(0, 30);

    for (const { v, i } of topN) {
      const ratio = v / maxVal;
      if (ratio < 0.4) continue; // 低流量不加

      const mesh = this.meshes[i];
      const color = this._orderColor(ratio);

      // 内圈
      const ring1 = this._createRing(mesh, color, 0);
      // 外圈（延迟）
      const ring2 = this._createRing(mesh, color, 0.5);

      this._pulseRings.push(ring1, ring2);
      this.scene.add(ring1);
      this.scene.add(ring2);
    }

    this._pulseAnimId = requestAnimationFrame(this._animatePulse.bind(this));
  }

  _createRing(mesh, color, phaseOffset) {
    const geo = new THREE.RingGeometry(40, 55, 32);
    const mat = new THREE.MeshBasicMaterial({
      color: color, transparent: true, opacity: 0.6,
      side: THREE.DoubleSide, depthTest: false,
    });
    const ring = new THREE.Mesh(geo, mat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.copy(mesh.position);
    ring.userData = { phase: phaseOffset, mesh: mesh };
    return ring;
  }

  _animatePulse(now) {
    const t = now * 0.001; // 秒
    for (const ring of this._pulseRings) {
      if (!ring.parent) continue;
      const phase = ring.userData.phase;
      const cycle = ((t + phase) % 1.5) / 1.5; // 0-1 每 1.5 秒循环
      const scale = 1.0 + cycle * 2.0; // 1x → 3x
      ring.scale.set(scale, scale, scale);
      ring.material.opacity = 0.6 * (1.0 - cycle); // 渐隐
      // 跟随 mesh 位置
      ring.position.copy(ring.userData.mesh.position);
    }
    this._pulseAnimId = requestAnimationFrame(this._animatePulse.bind(this));
  }

  _stopPulse() {
    if (this._pulseAnimId) {
      cancelAnimationFrame(this._pulseAnimId);
      this._pulseAnimId = null;
    }
    for (const ring of this._pulseRings) {
      if (ring.parent) ring.parent.remove(ring);
      ring.geometry.dispose();
      ring.material.dispose();
    }
    this._pulseRings = [];
  }

  // ========== 3. AMap 热力图层 ==========

  _initHeatmap() {
    if (this.heatmap || !this.AMap) return;
    try {
      this.heatmap = new this.AMap.HeatMap(this.map, {
        radius: 25, opacity: [0, 0.8],
        gradient: {
          0.2: '#2266ff', 0.4: '#00ccaa', 0.6: '#44bb22',
          0.8: '#ffaa00', 1.0: '#ff2222',
        },
      });
      this.heatmapVisible = false;
    } catch (e) {
      console.warn('HeatMap 插件加载失败:', e);
    }
  }

  _showHeatmap(show) {
    this._initHeatmap();
    if (!this.heatmap) return;
    this.heatmapVisible = show;
    try {
      this.heatmap.setMap(show ? this.map : null);
    } catch (e) { /* ignore */ }
  }

  _updateHeatmap() {
    if (!this.heatmap || !this.heatmapVisible || !this.orderData) return;
    const data = this.orderData.data || [];
    let maxVal = 1;
    const points = data.map(d => {
      const val = d.hourly_orders || d.daily_orders || 0;
      if (val > maxVal) maxVal = val;
      return { lng: d.lng, lat: d.lat, count: val };
    });
    this.heatmap.setDataSet({ data: points, max: maxVal });
  }

  // ========== 路况 Polyline ==========

  async loadRoadTraffic(city, dayOfYear, hour) {
    const params = new URLSearchParams();
    if (city) params.set('city', city);
    if (dayOfYear != null) params.set('day_of_year', dayOfYear);
    if (hour != null) params.set('hour', hour);
    const url = `${API_BASE}/api/road-traffic/?${params.toString()}`;
    try {
      const resp = await fetch(url);
      const json = await resp.json();
      this.roadTrafficData = json;
      if (this.roadTrafficMode) this._updateRoadLayer();
    } catch (e) {
      console.error('加载路况数据失败:', e);
    }
  }

  async setRoadTrafficMode(enabled) {
    this.roadTrafficMode = enabled;
    if (!enabled) {
      this._showRoadLayer(false);
      return;
    }
    // 等 map 和 customCoords 就绪（最多等 10 秒）
    for (let i = 0; i < 100; i++) {
      if (this.map && this.customCoords && this.glReady) break;
      await new Promise(r => setTimeout(r, 100));
    }
    // 如果还没数据就先加载
    if (!this.roadTrafficData) {
      const city = this.currentCity || '珠海';
      const params = new URLSearchParams();
      params.set('city', city);
      try {
        const resp = await fetch(`${API_BASE}/api/road-traffic/?${params.toString()}`);
        const json = await resp.json();
        this.roadTrafficData = json;
      } catch (e) {
        console.error('加载路况失败:', e);
        return;
      }
    }
    console.log('[路况] map:', !!this.map, 'customCoords:', !!this.customCoords, 'glReady:', this.glReady, 'roads:', this.roadTrafficData?.total);
    // 先渲染 POI 确保场景正常
    if (this.data.length) this._render();
    this._updateRoadLayer();
  }

  _ttiColor(tti) {
    if (tti == null) return '#666666';
    if (tti < 1.2) return '#22cc44';  // 畅通-绿
    if (tti < 1.5) return '#ffaa00';  // 缓行-黄
    if (tti < 2.0) return '#ff6600';  // 拥堵-橙
    return '#ff2200';                 // 严重拥堵-红
  }

  _ttiWeight(tti) {
    if (tti == null) return 3;
    if (tti < 1.2) return 4;
    if (tti < 1.5) return 5;
    if (tti < 2.0) return 6;
    return 8;
  }

  _showRoadLayer(show) {
    for (const obj of this._roadPolylines) {
      obj.visible = show;
    }
  }

  _updateRoadLayer() {
    if (!this.scene || !this.glReady || !this.roadTrafficData || !this.roadTrafficData.data) {
      console.warn('[路况] 跳过渲染:', !!this.scene, !!this.glReady, !!this.roadTrafficData);
      return;
    }
    this._clearRoadLayer();
    const data = this.roadTrafficData.data;
    const validRoads = data.filter(r => r.lng != null && r.lat != null);
    if (!validRoads.length) { console.warn('[路况] 无有效路段'); return; }

    // 转换坐标
    const lngLats = validRoads.map(r => [r.lng, r.lat]);
    const coords = this.customCoords.lngLatsToCoords(lngLats);

    // 用 POI 同样的方式转换一个已知 POI 坐标做对比
    const poiCoords = this.data.length ? this.customCoords.lngLatsToCoords([[this.data[0].lng, this.data[0].lat]]) : [[0,0]];
    console.log('[路况] 首条路段 lnglat:', lngLats[0], '→ coord:', coords[0]);
    console.log('[路况] 首条 POI   lnglat:', [this.data[0]?.lng, this.data[0]?.lat], '→ coord:', poiCoords[0]);
    console.log('[路况] coord差值 dx:', coords[0][0]-poiCoords[0][0], 'dy:', coords[0][1]-poiCoords[0][1]);

    validRoads.forEach((road, i) => {
      const color = this._ttiColor(road.tti);
      const weight = this._ttiWeight(road.tti);
      // 和 POI 相同的材质方式
      const radius = weight * 20;
      const geo = new THREE.CylinderGeometry(radius, radius, 20, 16, 1);
      const mat = new THREE.MeshPhongMaterial({
        color: new THREE.Color(color),
        emissive: new THREE.Color(color),
        emissiveIntensity: 0.5,
        transparent: true, opacity: 0.9,
        depthTest: true,
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set(coords[i][0], coords[i][1], 10);
      this.scene.add(mesh);
      this._roadPolylines.push(mesh);
    });

    // 添加一个巨大的测试球在珠海市中心，确认渲染管线工作
    const testLngLats = [[113.55, 22.27]];
    const testCoords = this.customCoords.lngLatsToCoords(testLngLats);
    const testGeo = new THREE.SphereGeometry(500, 16, 16);
    const testMat = new THREE.MeshBasicMaterial({ color: 0xff00ff });
    const testMesh = new THREE.Mesh(testGeo, testMat);
    testMesh.position.set(testCoords[0][0], testCoords[0][1], 100);
    this.scene.add(testMesh);
    this._roadPolylines.push(testMesh);

    console.log('[路况] 已添加', this._roadPolylines.length, '个对象, test coord:', testCoords[0]);
    this.map.render();
  }

  _clearRoadLayer() {
    for (const obj of this._roadPolylines) {
      this.scene.remove(obj);
      obj.geometry.dispose();
      obj.material.dispose();
    }
    this._roadPolylines = [];
  }

  // ========== 工具方法 ==========

  setChartType(type) { /* 保留接口 */ }

  destroy() {
    this._stopPulse();
    this._showHeatmap(false);
    this._clearRoadLayer();
    if (this.map) this.map.destroy();
  }
}
