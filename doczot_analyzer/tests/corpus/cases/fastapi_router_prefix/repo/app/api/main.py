"""Aggregate router. Collects the per-resource routers."""

from fastapi import APIRouter

from app.api.routes import invoices, subscriptions

api_router = APIRouter()

api_router.include_router(invoices.router)
api_router.include_router(subscriptions.router)
