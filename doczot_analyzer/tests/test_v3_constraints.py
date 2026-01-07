"""Unit tests for v3 constraint extraction.

Tests extraction of:
- Rate limit decorators (@limiter.limit)
- Auth decorators (@requires_auth)
- Permission decorators (@permission_required)
- Depends injection (Depends(get_current_user))
"""

import pytest
from pathlib import Path
from doczot_analyzer.scanner import scan_python_file, _extract_constraints
from doczot_analyzer.models import Endpoint


class TestRateLimitExtraction:
    """Test rate limit decorator detection."""

    def test_simple_rate_limit(self):
        """Test basic @limiter.limit decorator."""
        source = '''
from fastapi import FastAPI

app = FastAPI()

@limiter.limit("100/hour")
@app.get("/items")
def list_items():
    pass
'''
        endpoints = scan_python_file(source, "test.py")

        assert len(endpoints) == 1
        assert endpoints[0].method == "GET"
        assert endpoints[0].path == "/items"
        assert len(endpoints[0].constraints) >= 1

        rate_limits = [c for c in endpoints[0].constraints if c["type"] == "rate_limit"]
        assert len(rate_limits) == 1
        assert rate_limits[0]["value"] == "100/hour"

    def test_multiple_rate_limits(self):
        """Test multiple endpoints with different rate limits."""
        source = '''
@app.get("/fast")
@limiter.limit("1000/hour")
def fast_endpoint():
    pass

@app.get("/slow")
@limiter.limit("10/hour")
def slow_endpoint():
    pass
'''
        endpoints = scan_python_file(source, "test.py")

        assert len(endpoints) == 2

        fast = [ep for ep in endpoints if ep.path == "/fast"][0]
        fast_limits = [c for c in fast.constraints if c["type"] == "rate_limit"]
        assert len(fast_limits) == 1
        assert fast_limits[0]["value"] == "1000/hour"

        slow = [ep for ep in endpoints if ep.path == "/slow"][0]
        slow_limits = [c for c in slow.constraints if c["type"] == "rate_limit"]
        assert len(slow_limits) == 1
        assert slow_limits[0]["value"] == "10/hour"


class TestAuthDecoratorExtraction:
    """Test auth decorator detection."""

    def test_requires_auth_decorator(self):
        """Test @requires_auth decorator."""
        source = '''
@requires_auth
@app.get("/protected")
def protected_resource():
    pass
'''
        endpoints = scan_python_file(source, "test.py")

        assert len(endpoints) == 1
        assert len(endpoints[0].constraints) >= 1

        auth_constraints = [c for c in endpoints[0].constraints if c["type"] == "auth_required"]
        assert len(auth_constraints) == 1
        assert auth_constraints[0]["value"] is True

    def test_multiple_auth_decorator_forms(self):
        """Test various auth decorator names."""
        source = '''
@requires_auth
@app.get("/endpoint1")
def endpoint1():
    pass

@authenticated
@app.get("/endpoint2")
def endpoint2():
    pass

@login_required
@app.get("/endpoint3")
def endpoint3():
    pass
'''
        endpoints = scan_python_file(source, "test.py")

        assert len(endpoints) == 3
        for ep in endpoints:
            auth_constraints = [c for c in ep.constraints if c["type"] == "auth_required"]
            assert len(auth_constraints) == 1


class TestDependsInjection:
    """Test Depends() parameter detection."""

    def test_depends_with_get_current_user(self):
        """Test Depends(get_current_user) in Annotated type."""
        source = '''
from typing import Annotated
from fastapi import Depends

@app.get("/users/me")
def get_profile(
    current_user: Annotated[dict, Depends(get_current_user)]
):
    pass
'''
        endpoints = scan_python_file(source, "test.py")

        assert len(endpoints) == 1
        auth_constraints = [c for c in endpoints[0].constraints if c["type"] == "auth_required"]
        assert len(auth_constraints) == 1
        assert "user" in auth_constraints[0]["value"].lower()

    def test_depends_with_admin(self):
        """Test Depends(require_admin) detection."""
        source = '''
from typing import Annotated
from fastapi import Depends

@app.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    admin: Annotated[dict, Depends(require_admin)]
):
    pass
'''
        endpoints = scan_python_file(source, "test.py")

        assert len(endpoints) == 1
        auth_constraints = [c for c in endpoints[0].constraints if c["type"] == "auth_required"]
        assert len(auth_constraints) == 1
        assert "admin" in auth_constraints[0]["value"].lower()


class TestPermissionDecorators:
    """Test permission decorator detection."""

    def test_permission_required(self):
        """Test @permission_required decorator."""
        source = '''
@permission_required("admin")
@app.post("/admin/settings")
def update_settings():
    pass
'''
        endpoints = scan_python_file(source, "test.py")

        assert len(endpoints) == 1
        perm_constraints = [c for c in endpoints[0].constraints if c["type"] == "permission"]
        assert len(perm_constraints) == 1
        assert perm_constraints[0]["value"] == "admin"

    def test_role_required(self):
        """Test @role_required decorator."""
        source = '''
@role_required("moderator")
@app.delete("/posts/{post_id}")
def delete_post(post_id: int):
    pass
'''
        endpoints = scan_python_file(source, "test.py")

        assert len(endpoints) == 1
        perm_constraints = [c for c in endpoints[0].constraints if c["type"] == "permission"]
        assert len(perm_constraints) == 1
        assert perm_constraints[0]["value"] == "moderator"


class TestMultipleConstraints:
    """Test endpoints with multiple constraints."""

    def test_auth_and_rate_limit(self):
        """Test endpoint with both auth and rate limiting."""
        source = '''
@requires_auth
@limiter.limit("50/hour")
@app.get("/premium/data")
def get_premium_data():
    pass
'''
        endpoints = scan_python_file(source, "test.py")

        assert len(endpoints) == 1
        assert len(endpoints[0].constraints) >= 2

        auth_constraints = [c for c in endpoints[0].constraints if c["type"] == "auth_required"]
        assert len(auth_constraints) == 1

        rate_constraints = [c for c in endpoints[0].constraints if c["type"] == "rate_limit"]
        assert len(rate_constraints) == 1


class TestFixture:
    """Test the simple_fastapi_app fixture."""

    def test_fixture_has_constraints(self):
        """Test that the fixture file has expected constraints."""
        fixture_path = Path(__file__).parent / "fixtures" / "simple_test_app" / "main.py"
        content = fixture_path.read_text()
        endpoints = scan_python_file(content, str(fixture_path))

        assert len(endpoints) == 11  # Expected endpoint count

        # Check public endpoints (no constraints)
        public_endpoints = [ep for ep in endpoints if ep.path in ["/health", "/"]]
        assert len(public_endpoints) == 2
        for ep in public_endpoints:
            assert len(ep.constraints) == 0

        # Check auth-protected endpoints
        auth_endpoints = [ep for ep in endpoints if ep.path == "/users/me"]
        assert len(auth_endpoints) >= 1
        for ep in auth_endpoints:
            auth_constraints = [c for c in ep.constraints if c["type"] == "auth_required"]
            assert len(auth_constraints) >= 1

        # Check rate-limited endpoints
        items_endpoint = [ep for ep in endpoints if ep.path == "/items"][0]
        rate_constraints = [c for c in items_endpoint.constraints if c["type"] == "rate_limit"]
        assert len(rate_constraints) == 1

        # Check nested resources
        nested_endpoints = [
            ep for ep in endpoints
            if "/users/{user_id}/projects" in ep.path
        ]
        assert len(nested_endpoints) >= 2
