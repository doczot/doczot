"""Version 1 router assembly."""

from fastapi import APIRouter

from src.modules.orders import router as orders_router

router = APIRouter(prefix="/v1")
router.include_router(orders_router, prefix="/orders")
