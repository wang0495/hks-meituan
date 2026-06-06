# CityFlow Docker配置（开发用）
# 生产环境请使用 Dockerfile.optimized（多阶段构建 + 非 root 用户）
FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN groupadd -r cityflow && useradd -r -g cityflow -d /app -s /sbin/nologin cityflow

# 复制依赖文件
COPY pyproject.toml .

# 安装Python依赖
RUN pip install --no-cache-dir .

# 复制应用代码
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# 创建数据目录并设置权限
RUN mkdir -p /app/data /app/logs && \
    chown -R cityflow:cityflow /app

# 环境变量
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 切换到非 root 用户
USER cityflow

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8000/api/health || exit 1

# 暴露端口
EXPOSE 8000

# 使用 tini 作为 PID 1，正确处理信号
ENTRYPOINT ["tini", "--"]

# 启动命令
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
