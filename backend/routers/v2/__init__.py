"""CityFlow API v2 路由（增强版）。"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v2")

from . import dialogue, plan, poi  # noqa: E402

router.include_router(plan.router)
router.include_router(poi.router)
router.include_router(dialogue.router)
