"""美团模拟数据服务器 — 独立启动入口。

模拟美团平台对外提供的数据API，供 Agent 调用获取原始数据。

启动方式:
    python -m backend.meituan_server.main
    或
    uvicorn backend.meituan_server.main:app --reload --port 8001
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.meituan_server.data_loader import load_all
from backend.meituan_server.routers import router as meituan_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger("meituan-mock")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时加载数据。"""
    load_all()
    logger.info("美团模拟数据服务器启动完成")
    yield


app = FastAPI(
    title="美团模拟数据API",
    description=(
        "## 模拟美团平台数据接口\n\n"
        "提供商户搜索、详情、评价、位置、路线距离、热门推荐、商圈范围等数据能力。\n\n"
        "Agent 通过 tool_use 调用这些接口获取原始数据，自行完成路线编排。"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(meituan_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
