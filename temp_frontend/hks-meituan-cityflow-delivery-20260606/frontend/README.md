# CityFlow Frontend V2

这是独立于 `hks-meituan-master` 的新版前端界面。

## 打开方式

推荐用本地静态服务器打开本文件夹，入口是：

```text
index.html
```

当前本地预览地址：

```text
http://127.0.0.1:5174/
```

## 后端接入

页面默认连接：

```text
http://127.0.0.1:8000
```

优先使用：

- `POST /api/v2/plan`
- `POST /api/v2/dialogue/{route_id}`
- `GET /api/v2/poi/detail/{poi_id}`

如果 V2 接口不存在，会尝试降级到：

- `POST /api/plan`
- `POST /api/dialogue/{route_id}`
- `GET /api/poi/detail/{poi_id}`

如果后端暂时不可用，页面会使用 `assets/data/city_poi_db.json` 做本地路线预览。

本文件夹额外提供 `dev_backend.py`，用于本地前端联调真实 V2 后端路由：

```text
python -m uvicorn dev_backend:app --host 127.0.0.1 --port 8000
```

这个入口挂载的是 `hks-meituan-master` 中的真实 V2 路由，避免完整主应用启动时依赖本机 Redis。

## 高德地图接入

中间地图区已接入高德 JavaScript API 2.0。

首次打开时，在地图上方填写：

- 高德 Web 端 JS API Key
- securityJsCode（新 Key 通常需要）

点击“加载地图”后会加载真实高德地图，并把后端返回或本地预览生成的 POI 坐标渲染为路线折线和站点标记。Key 和安全码只保存在当前浏览器的 `localStorage` 中，没有硬编码进项目文件。
