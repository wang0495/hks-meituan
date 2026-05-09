"""CityFlow API v1 路由。"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

from . import dialogue, plan, poi  # noqa: E402

router.include_router(plan.router)
router.include_router(poi.router)
router.include_router(dialogue.router)
