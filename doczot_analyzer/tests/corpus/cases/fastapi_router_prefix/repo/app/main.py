"""Application entry point.

The API version prefix is applied here, at include time, rather than on the
individual routers. This is the layout used by the full-stack-fastapi-template
and is extremely common in production FastAPI projects, so DocZot must resolve
paths across files to report the real URLs.
"""

from fastapi import FastAPI

from app.api.main import api_router

app = FastAPI(title="Billing API")

app.include_router(api_router, prefix="/api/v1")
