"""Simple FastAPI test fixture with v3 features.

This minimal app tests constraint extraction, nested resources, and concept detection.

Features:
- Public endpoint (no constraints)
- Auth-protected endpoint (Depends injection)
- Rate-limited endpoint
- Nested resource (part_of relationship)
"""

from fastapi import FastAPI, Depends, HTTPException
from typing import Annotated

app = FastAPI(
    title="Simple Test API",
    description="A minimal FastAPI application for testing DocZot v3 features",
)


# =============================================================================
# Dependencies (simulated)
# =============================================================================

def get_current_user():
    """Authentication dependency - simulates checking JWT token."""
    return {"user_id": 1, "username": "testuser"}


# Simulated rate limiter decorator
class limiter:
    """Mock rate limiter for testing."""

    @staticmethod
    def limit(rate: str):
        """Decorator to limit request rate."""
        def decorator(func):
            return func
        return decorator


# =============================================================================
# Public Endpoints (no constraints)
# =============================================================================

@app.get("/health")
def health_check():
    """Check if service is healthy.

    Returns system status without authentication.
    """
    return {"status": "ok", "service": "Simple Test API"}


@app.get("/")
def root():
    """Root endpoint with API information."""
    return {
        "name": "Simple Test API",
        "version": "1.0.0",
        "docs": "/docs",
    }


# =============================================================================
# Auth-Constrained Endpoints
# =============================================================================

@app.get("/users/me")
def get_current_user_profile(
    current_user: Annotated[dict, Depends(get_current_user)]
):
    """Retrieve the current user's profile.

    User profile includes username, email, and preferences.
    Authentication required via JWT token.
    """
    return {
        "user_id": current_user["user_id"],
        "username": current_user["username"],
        "email": f"{current_user['username']}@example.com",
    }


@app.put("/users/me")
def update_current_user(
    user_data: dict,
    current_user: Annotated[dict, Depends(get_current_user)]
):
    """Update the current user's profile.

    Authentication required via JWT token.
    """
    return {
        "message": "Profile updated",
        "user_id": current_user["user_id"],
    }


# =============================================================================
# Rate-Limited Endpoints
# =============================================================================

@app.get("/items")
@limiter.limit("100/hour")
def list_items():
    """List all items with rate limiting.

    Items are products available in the catalog.
    Rate limit: 100 requests per hour per IP.
    """
    return [
        {"id": 1, "name": "Widget", "price": 9.99},
        {"id": 2, "name": "Gadget", "price": 19.99},
    ]


@app.get("/items/{item_id}")
@limiter.limit("200/hour")
def get_item(item_id: int):
    """Get a specific item by ID.

    Item details include name, description, and pricing.
    Rate limit: 200 requests per hour per IP.
    """
    if item_id <= 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"id": item_id, "name": f"Item {item_id}", "price": 9.99}


# =============================================================================
# Nested Resources (part_of relationship)
# =============================================================================

@app.get("/users/{user_id}/projects")
def list_user_projects(
    user_id: int,
    current_user: Annotated[dict, Depends(get_current_user)]
):
    """List all projects belonging to a user.

    Projects are containers for tasks and are owned by users.
    Authentication required.
    """
    return [
        {"id": 1, "name": "Project Alpha", "user_id": user_id},
        {"id": 2, "name": "Project Beta", "user_id": user_id},
    ]


@app.get("/users/{user_id}/projects/{project_id}")
def get_user_project(
    user_id: int,
    project_id: int,
    current_user: Annotated[dict, Depends(get_current_user)]
):
    """Get a specific project belonging to a user.

    Project details include name, description, and task count.
    """
    return {
        "id": project_id,
        "name": f"Project {project_id}",
        "user_id": user_id,
        "description": "A sample project for testing nested resources",
        "task_count": 5,
    }


@app.post("/users/{user_id}/projects")
def create_user_project(
    user_id: int,
    project_data: dict,
    current_user: Annotated[dict, Depends(get_current_user)]
):
    """Create a new project for a user.

    Projects must have a name and optional description.
    """
    return {
        "id": 3,
        "name": project_data.get("name", "New Project"),
        "user_id": user_id,
        "created": True,
    }


# =============================================================================
# Auth Endpoints (prerequisite for protected routes)
# =============================================================================

@app.post("/auth/login")
def login(credentials: dict):
    """Authenticate user and return access token.

    Token is used for accessing protected endpoints.
    """
    return {
        "access_token": "fake_jwt_token_123",
        "token_type": "bearer",
        "expires_in": 3600,
    }


@app.post("/auth/signup")
def signup(user_data: dict):
    """Register a new user account.

    User must provide username, email, and password.
    """
    return {
        "message": "User created successfully",
        "user_id": 99,
        "username": user_data.get("username"),
    }
