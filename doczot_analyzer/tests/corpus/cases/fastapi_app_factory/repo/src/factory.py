"""Application factory.

The router is a parameter, so the app object and the router it serves are only
connected at the call site in interfaces/main.py. Resolving the real URL
requires following that call.
"""

from fastapi import APIRouter, FastAPI


def create_application(router: APIRouter, title: str = "Store API") -> FastAPI:
    """Build the application around a pre-assembled router."""
    application = FastAPI(title=title)
    application.include_router(router)
    return application
