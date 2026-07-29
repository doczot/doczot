"""Workspace API — collaboration service with auth and rate limits.

This case exercises the constraint and relationship extractors:

- ``/auth/login`` is a prerequisite for the protected endpoints.
- Every ``/workspaces`` endpoint is auth-protected via ``Depends``.
- ``/workspaces`` listing is rate limited.
- ``/workspaces/{workspace_id}/documents`` nests document under workspace.

The docstrings are deliberately written as ordinary prose. A concept extractor
that slices sentence fragments out of them will produce entries like
"Workspaces Are Shared" — which the answer key forbids.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI

app = FastAPI(title="Workspace API")


def get_current_user():
    """Resolve the caller's identity from the bearer token."""
    return {"user_id": 1}


class limiter:
    """Minimal stand-in for a rate limiting extension."""

    @staticmethod
    def limit(rate: str):
        def decorator(func):
            return func
        return decorator


auth_router = APIRouter(prefix="/auth")
workspace_router = APIRouter(prefix="/workspaces")


@auth_router.post("/login")
def login(credentials: dict):
    """Exchange credentials for an access token.

    Workspaces are shared containers that several users may collaborate in.
    """
    return {"access_token": "token", "token_type": "bearer"}


@workspace_router.get("")
@limiter.limit("60/minute")
def list_workspaces(current_user: Annotated[dict, Depends(get_current_user)]):
    """List every workspace the caller belongs to."""
    return []


@workspace_router.get("/{workspace_id}")
def get_workspace(
    workspace_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Retrieve a single workspace by identifier."""
    return {"id": workspace_id}


@workspace_router.get("/{workspace_id}/documents")
def list_workspace_documents(
    workspace_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """List the documents stored inside a workspace."""
    return []


@workspace_router.post("/{workspace_id}/documents")
def create_workspace_document(
    workspace_id: int,
    payload: dict,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Add a document to a workspace."""
    return {"id": 1}


app.include_router(auth_router)
app.include_router(workspace_router)
