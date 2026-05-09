# CityFlow 部署指南

## 快速部署（Docker）

### 前置要求
- Docker >= 20.10
- Docker Compose >= 2.0

### 部署步骤

1. **克隆项目**
```bash
git clone https://github.com/yourusername/cityflow.git
cd cityflow
```

2. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env，填入你的 OPENAI_API_KEY
```

3. **启动服务**
```bash
docker-compose up -d
```

4. **访问服务**
- API: http://localhost:8000
- 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/api/health

### 常用命令

```bash
# 查看日志
docker-compose logs -f cityflow

# 重启服务
docker-compose restart cityflow

# 停止服务
docker-compose down

# 重新构建
docker-compose build
docker-compose up -d
```

## 手动部署

### 环境要求
- Python >= 3.10
- pip

### 部署步骤

1. **安装依赖**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

2. **配置环境变量**
```bash
export OPENAI_API_KEY=your_key_here
export OPENAI_BASE_URL=https://api.openai.com/v1
```

3. **启动服务**
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## 生产环境配置

### Nginx反向代理

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # SSE支持
        proxy_buffering off;
        proxy_cache off;
    }
}
```

### Systemd服务

创建 `/etc/systemd/system/cityflow.service`:

```ini
[Unit]
Description=CityFlow API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/cityflow
Environment="PATH=/opt/cityflow/venv/bin"
ExecStart=/opt/cityflow/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl enable cityflow
sudo systemctl start cityflow
```

## 监控

### 健康检查

```bash
curl http://localhost:8000/api/health
```

### 日志查看

```bash
# Docker
docker-compose logs -f cityflow

# Systemd
journalctl -u cityflow -f
```

### 性能监控

建议使用：
- Prometheus + Grafana
- Sentry（错误追踪）
- New Relic（APM）

## 故障排查

### 常见问题

1. **端口被占用**
```bash
lsof -i :8000
kill -9 <PID>
```

2. **依赖安装失败**
```bash
pip install --upgrade pip
pip install -r requirements.txt --no-cache-dir
```

3. **API Key错误**
检查 `.env` 文件中的 `OPENAI_API_KEY` 是否正确。

4. **数据文件缺失**
确保 `backend/data/city_poi_db.json` 存在。

## 扩展

### 水平扩展

使用 Docker Swarm 或 Kubernetes 进行水平扩展：

```bash
# Docker Swarm
docker swarm init
docker stack deploy -c docker-compose.yml cityflow
```

### 负载均衡

使用 Nginx 或 HAProxy 进行负载均衡。

---

更多问题，请查看 [GitHub Issues](https://github.com/yourusername/cityflow/issues)。
