"""Entry point. Wires the assembled router into the app factory."""

from fastapi import APIRouter

from src.api.v1 import router as v1_router
from src.factory import create_application

root_router = APIRouter(prefix="/api")
root_router.include_router(v1_router)

app = create_application(router=root_router)
