# Phase 1 Spec: 真实城市 POI 可视化 + L7 渲染引擎

---

## Overview

- **Phase ID**: Phase-1
- **Feature**: F001 3d-visualization
- **Created**: 2026-05-08
- **Updated**: 2026-05-08
- **Status**: Data Ready, Rendering TODO

---

## Objective

基于 OpenStreetMap 真实 POI 数据（3689 条，覆盖珠海/广州/湛江），使用 **@antv/l7 + 高德地图** 实现 3D 柱状可视化，支持品类/评分区分和交互。

---

## Current Status

| Deliverable | Status | Notes |
|------------|--------|-------|
| POI 数据 (3689 条) | **DONE** | `frontend/data/city_poi_db.json` |
| 原始 OSM 数据 | **DONE** | `frontend/data/osm_raw.json` |
| L7 渲染引擎 | TODO | `frontend/js/l7-renderer.js` |
| 前端页面集成 | TODO | `frontend/index.html` |

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    Frontend                           │
│                                                       │
│   index.html                                          │
│     ├── AMap GL (地图底座，由 L7 内部管理)              │
│     ├── @antv/l7 (3D 可视化引擎)                      │
│     │   ├── PointLayer shape='extrude' (3D 柱状图)     │
│     │   ├── PointLayer shape='text' (评分标注)         │
│     │   └── Popup (点击详情)                           │
│     ├── l7-renderer.js (L7 初始化 + 数据绑定)          │
│     ├── llm-chat.js (AI 分析)                         │
│     └── app.js (主控制器)                              │
│                                                       │
│   data/city_poi_db.json (3689 条真实 POI)              │
└──────────────────────────────────────────────────────┘
```

---

## Data Source

**来源**: OpenStreetMap Overpass API (kumi 镜像)
**生成方式**: OSM 真实数据 + Faker 补全属性

| 城市 | POI 数量 | 坐标范围 |
|------|---------|---------|
| 广州 | 2596 | lat 22.95-23.40, lng 113.10-113.60 |
| 珠海 | 999 | lat 22.15-22.40, lng 113.45-113.70 |
| 湛江 | 94 | lat 21.10-21.45, lng 110.20-110.55 |

### Data Schema

```json
{
  "id": "poi_00001",
  "name": "珠海渔女",
  "city": "珠海",
  "category": "文化",
  "rating": 3.9,
  "avg_price": 27,
  "lat": 22.2650277,
  "lng": 113.5830398,
  "business_hours": "09:00-17:00",
  "tags": ["免费", "值得去", "涨知识"],
  "queue_prone": false,
  "avg_stay_min": 75,
  "ugc_comments": [
    {"user": "鲁健", "text": "展品很丰富", "rating": 5}
  ]
}
```

### Category Distribution

| 品类 | 数量 | 颜色 |
|------|------|------|
| 餐饮 | 2524 | `#FF8C00` (橙) |
| 购物 | 758 | `#FFD700` (金) |
| 酒店 | 214 | `#4169E1` (蓝) |
| 文化 | 145 | `#9932CC` (紫) |
| 运动 | 39 | `#228B22` (绿) |

---

## D1: L7 渲染引擎

**File**: `frontend/js/l7-renderer.js`
**Dependency**: `@antv/l7` + `@antv/l7-amap` (CDN)
**Duration**: 4h

### 1.1 L7 初始化

```javascript
import { Scene, PointLayer, Popup } from '@antv/l7';
import { GaodeMap } from '@antv/l7-amap';

const scene = new Scene({
  id: 'map-container',
  map: new GaodeMap({
    center: [113.55, 22.25],  // 珠海
    zoom: 11,
    pitch: 40,
    style: 'dark',
    key: 'e2a4f77a5b16efcf19b88a1e87ab88fd',
  }),
});
```

### 1.2 3D 柱状图 (PointLayer extrude)

```javascript
scene.on('loaded', () => {
  fetch('data/city_poi_db.json')
    .then(r => r.json())
    .then(data => {
      const layer = new PointLayer({})
        .source(data, {
          parser: { type: 'json', x: 'lng', y: 'lat' }
        })
        .shape('category', ['cylinder'])  // 3D 圆柱
        .size('rating', [10, 50])          // 高度 = 评分映射
        .color('category', CATEGORY_COLORS)
        .style({ opacity: 0.8, topsurface: true })
        .active(true);

      scene.addLayer(layer);
    });
});
```

### 1.3 交互: Popup 详情窗

- 点击柱子弹出 Popup
- 显示：店名、评分、品类、均价、营业时间、一条 UGC 短评
- 深色主题样式，与页面一致

### 1.4 城市切换

- 顶部下拉选择城市（珠海/广州/湛江）
- 切换时重新加载对应城市数据
- 地图飞行过渡到新城市中心点

---

## D2: 前端页面更新

**File**: `frontend/index.html`
**Duration**: 1h

### Changes

1. 引入 L7 CDN（`@antv/l7` + `@antv/l7-amap`）
2. 替换原 Three.js 渲染为 L7 渲染
3. 新增城市选择器（下拉框）
4. 保留右侧面板（AI 分析聊天）
5. 添加品类图例（右上角）

### CDN 引入

```html
<script src="https://unpkg.com/@antv/l7@2/dist/l7.js"></script>
<script src="https://unpkg.com/@antv/l7-amap@2/dist/l7-amap.js"></script>
```

---

## Verification Criteria

1. 打开 `index.html`，高德 3D 地图上显示彩色 3D 圆柱 POI
2. 柱子高度和颜色明显区分评分和品类
3. 点击任意柱子弹出详情窗，显示店名/评分/价格/UGC
4. 下拉切换城市，地图飞行过渡，POI 更新
5. 3689 条数据渲染流畅（≥30fps）
6. 可旋转、倾斜、缩放地图，柱子始终锚定在经纬度上

---

## Execution Schedule

| Step | Task | Duration | Output |
|------|------|----------|--------|
| 1 | L7 CDN 引入 + 初始化 | 30min | 地图加载成功 |
| 2 | PointLayer extrude 渲染 | 1h | 3D 柱状图显示 |
| 3 | 品类颜色 + 评分高度映射 | 30min | 视觉区分 |
| 4 | Popup 交互 | 1h | 点击显示详情 |
| 5 | 城市切换 | 30min | 下拉框切换 |
| 6 | 图例 + 样式优化 | 30min | 完整 UI |

---

## Tech Stack

| Layer | Technology | Version | Source |
|-------|-----------|---------|--------|
| Map | AMap JS API | 2.0 | CDN |
| Visualization | @antv/l7 | 2.x | unpkg CDN |
| Map Adapter | @antv/l7-amap | 2.x | unpkg CDN |
| Data | OpenStreetMap | 2026-04 | Overpass API |
| Data Enrichment | Faker | zh_CN | pip |

---

## Risk Notes

- **L7 CDN 版本**: 确保 l7 和 l7-amap 版本匹配，避免兼容问题
- **高德 Key**: L7 内部管理 AMap 实例，需确认 key 和 security code 传递正确
- **3689 条性能**: L7 基于 WebGL，万级数据点无压力，但需测试实际帧率
- **城市数据不均**: 湛江仅 94 条，可考虑补充或标注数据量差异
