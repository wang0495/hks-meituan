/* L7 渲染器：基于 @antv/l7 + 高德地图的 3D POI 可视化 */
class L7Renderer {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.scene = null;
    this.mapInstance = null;
    this.poiLayer = null;
    this.popup = null;
    this.currentCity = null;

    // 品类颜色映射
    this.CATEGORY_COLORS = {
      '餐饮': '#FF8C00',
      '购物': '#FFD700',
      '酒店': '#4169E1',
      '文化': '#9932CC',
      '运动': '#228B22',
      '其他': '#888888',
    };

    // 城市中心点
    this.CITY_CENTERS = {
      '珠海': { center: [113.55, 22.27], zoom: 11 },
      '广州': { center: [113.27, 23.13], zoom: 11 },
      '湛江': { center: [110.36, 21.27], zoom: 11 },
    };
  }

  /* 初始化 L7 Scene */
  async init() {
    const { Scene, GaodeMap } = L7;

    this.mapInstance = new GaodeMap({
      center: [113.55, 22.27], // 珠海
      zoom: 11,
      pitch: 45,
      style: 'amap://styles/dark',
      key: 'e2a4f77a5b16efcf19b88a1e87ab88fd',
      securityJsCode: '8e6d3a6134d4516497913a5e295b5610',
    });

    this.scene = new Scene({
      id: this.container,
      map: this.mapInstance,
    });

    // 等待地图加载完成
    await new Promise((resolve) => {
      this.scene.on('loaded', () => resolve());
    });

    console.log('L7 Scene loaded');
  }

  /* 加载 POI 数据并渲染 */
  async loadPOIData(city = '', category = '') {
    if (!this.scene) await this.init();

    // 从后端 API 加载数据
    const params = new URLSearchParams();
    if (city) params.set('city', city);
    if (category) params.set('category', category);
    const url = `${API_BASE}/api/poi/${params.toString() ? '?' + params : ''}`;
    const resp = await fetch(url);
    const json = await resp.json();
    let data = json.data;

    this.currentCity = city || '全城市';
    console.log(`加载 ${this.currentCity} POI: ${data.length} 条`);

    // 移除旧图层
    if (this.poiLayer) {
      this.scene.removeLayer(this.poiLayer);
    }

    // 创建新的 PointLayer（3D 圆柱）
    this.poiLayer = new L7.PointLayer({})
      .source(data, {
        parser: { type: 'json', x: 'lng', y: 'lat' },
      })
      .shape('cylinder') // 3D 圆柱
      .size('rating', [5, 40]) // 高度映射评分 (5-40)
      .color('category', this.CATEGORY_COLORS)
      .style({
        opacity: 0.85,
        topsurface: true,
        sidesurface: true,
        lightEnable: true,
      })
      .active(true) // 允许选中高亮
      .select(true); // 允许多选

    // 点击交互：弹出详情
    this.poiLayer.on('click', (e) => {
      this._showPopup(e);
    });

    // 悬停高亮
    this.poiLayer.on('mousemove', (e) => {
      this.container.style.cursor = 'pointer';
    });
    this.poiLayer.on('mouseout', () => {
      this.container.style.cursor = '';
    });

    this.scene.addLayer(this.poiLayer);
  }

  /* ================== 路线标记（route markers） ================== */

  /**
   * 高亮路线上的某个 POI 标记
   * @param {string} poiId
   */
  highlightMarker(poiId) {
    if (!this.routeLayer) return;
    // Reset all route markers to default
    const features = this.routeLayer.getSource().data.dataArray || [];
    const colors = features.map(f => {
      return f.id === poiId ? '#e94560' : (this.CATEGORY_COLORS[f.category] || '#888888');
    });
    this.routeLayer.color(colors).update();
  }

  /**
   * 飞行到指定 POI 位置
   * @param {string} poiId
   */
  flyTo(poiId) {
    if (!this.routeLayer) return;
    const features = this.routeLayer.getSource().data.dataArray || [];
    const target = features.find(f => f.id === poiId);
    if (target && target.lng && target.lat) {
      const mapService = this.scene.getMapService();
      if (mapService && mapService.map) {
        mapService.map.setZoomAndCenter(15, [target.lng, target.lat]);
      }
    }
  }

  /**
   * 根据步骤数组更新路线标记
   * @param {Array} steps - 含 poi 对象的步骤数组
   */
  updateMarkers(steps) {
    if (!steps || !steps.length) return;

    // 构造路线标记数据
    const routeData = steps.map((step, i) => {
      const poi = step.poi;
      return {
        ...poi,
        _order: i + 1,
        _arrival: step.arrival_time || '',
        _departure: step.departure_time || '',
      };
    });

    // 移除旧路线图层
    if (this.routeLayer) {
      this.scene.removeLayer(this.routeLayer);
      this.routeLayer = null;
    }

    // 创建路线标记 PointLayer
    this.routeLayer = new L7.PointLayer({
      zIndex: 20, // 高于 POI 散点
    })
      .source(routeData, {
        parser: { type: 'json', x: 'lng', y: 'lat' },
      })
      .shape('circle')
      .size(12)
      .color('#e94560')
      .style({
        opacity: 1,
        strokeWidth: 2,
        stroke: '#ffffff',
      })
      .active(true);

    // 添加序号文字图层
    this.routeLabelLayer = new L7.PointLayer({
      zIndex: 21,
    })
      .source(routeData, {
        parser: { type: 'json', x: 'lng', y: 'lat' },
      })
      .shape('_order', 'text')
      .size(10)
      .color('#ffffff')
      .style({
        textAnchor: 'center',
        textOffset: [0, 0],
        padding: [0, 0],
      });

    // 点击事件
    this.routeLayer.on('click', (e) => {
      const poi = e.feature;
      if (poi && poi.id) {
        this._emit('marker-click', { poiId: poi.id, poi });
      }
    });

    this.scene.addLayer(this.routeLayer);
    this.scene.addLayer(this.routeLabelLayer);

    // 自动缩放到路线范围
    if (routeData.length > 0) {
      const lngs = routeData.map(d => d.lng);
      const lats = routeData.map(d => d.lat);
      const minLng = Math.min(...lngs);
      const maxLng = Math.max(...lngs);
      const minLat = Math.min(...lats);
      const maxLat = Math.max(...lats);
      const center = [(minLng + maxLng) / 2, (minLat + maxLat) / 2];
      const lngDiff = maxLng - minLng || 0.1;
      const latDiff = maxLat - minLat || 0.1;
      const zoom = Math.min(14, Math.max(10, Math.round(11 - Math.log2(Math.max(lngDiff, latDiff) * 100))));
      const mapService = this.scene.getMapService();
      if (mapService && mapService.map) {
        mapService.map.setZoomAndCenter(zoom, center);
      }
    }
  }

  /**
   * 清除路线标记
   */
  clearRouteMarkers() {
    if (this.routeLayer) {
      this.scene.removeLayer(this.routeLayer);
      this.routeLayer = null;
    }
    if (this.routeLabelLayer) {
      this.scene.removeLayer(this.routeLabelLayer);
      this.routeLabelLayer = null;
    }
  }

  // ================================================================
  //  事件发射
  // ================================================================

  _emit(eventName, detail) {
    const evt = new CustomEvent(eventName, {
      detail,
      bubbles: true,
    });
    this.container.dispatchEvent(evt);
  }

  /**
   * 绑定事件监听
   * @param {string} eventName
   * @param {Function} callback
   */
  on(eventName, callback) {
    this.container.addEventListener(eventName, callback);
  }

  /**
   * 移除事件监听
   * @param {string} eventName
   * @param {Function} callback
   */
  off(eventName, callback) {
    this.container.removeEventListener(eventName, callback);
  }

  /* 切换城市 */
  async switchCity(city, category = '') {
    if (city === this.currentCity) return;

    const meta = this.CITY_CENTERS[city];
    if (!meta) return;

    // 飞行动画到新城市
    this.scene.getMapService().map.setCenter(meta.center);
    this.scene.getMapService().map.setZoom(meta.zoom);

    // 重新加载数据
    await this.loadPOIData(city, category);
  }

  /* 显示详情弹窗 */
  _showPopup(e) {
    const d = e.feature;
    if (!d) return;

    // 关闭旧弹窗
    if (this.popup) {
      this.popup.close();
    }

    // 构造 UGC 短评
    const comment = d.ugc_comments && d.ugc_comments[0];
    const commentHtml = comment
      ? `<div class="popup-comment"><span class="comment-user">【${comment.user}】</span>${comment.text}</div>`
      : '';

    const html = `
      <div class="poi-popup">
        <div class="popup-header">
          <span class="popup-name">${d.name}</span>
          <span class="popup-rating">★ ${d.rating}</span>
        </div>
        <div class="popup-meta">
          <span class="popup-category">${d.category}</span>
          <span class="popup-price">人均 ¥${d.avg_price}</span>
          <span class="popup-hours">${d.business_hours}</span>
        </div>
        <div class="popup-tags">
          ${(d.tags || []).map((t) => `<span class="tag">${t}</span>`).join('')}
        </div>
        ${commentHtml}
      </div>
    `;

    this.popup = new L7.Popup({
      closeButton: true,
      closeOnClick: true,
      anchor: 'bottom',
      offset: [0, -10],
    })
      .setLngLat([d.lng, d.lat])
      .setHTML(html);

    this.scene.addPopup(this.popup);
  }

  /* 销毁 */
  destroy() {
    if (this.scene) {
      this.scene.removeLayer(this.poiLayer);
      if (this.popup) this.popup.close();
    }
  }
}
