"""Tests for FastAPI endpoint scanner.

Tests are based on docs/features/endpoint-detection.md specification.
Each test references specific requirements (R1-R5) and edge cases (EC1-EC5).
"""

import pytest
from doczot_analyzer.scanner import scan_python_file
from doczot_analyzer.models import Endpoint, Parameter


class TestBasicEndpointDetection:
    """Test basic endpoint detection patterns."""

    def test_detects_simple_get_endpoint(self):
        """Test Example 1 from specification: Simple GET endpoint.

        Reference: endpoint-detection.md Example 1
        Requirements: R1, R3, R5
        """
        source_code = '''
from fastapi import FastAPI

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    """Retrieve a user by ID."""
    return {"user_id": user_id}
'''
        endpoints = scan_python_file(source_code, "api.py")

        assert len(endpoints) == 1
        endpoint = endpoints[0]

        assert endpoint.method == "GET"
        assert endpoint.path == "/users/{user_id}"
        assert endpoint.function_name == "get_user"
        assert endpoint.file_path == "api.py"
        assert endpoint.line_number == 7  # Line where function definition is
        assert endpoint.docstring == "Retrieve a user by ID."
        assert endpoint.has_docstring is True
        assert endpoint.is_async is True
        assert endpoint.is_deprecated is False

        # Check parameters
        assert len(endpoint.parameters) == 1
        param = endpoint.parameters[0]
        assert param.name == "user_id"
        assert param.type_hint == "int"
        assert param.location == "path"
        assert param.required is True

    def test_detects_post_endpoint_with_body(self):
        """Test Example 2 from specification: POST with request body.

        Reference: endpoint-detection.md Example 2
        Requirements: R1, R3
        """
        source_code = '''
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class UserCreate(BaseModel):
    username: str
    email: str

@app.post("/users", response_model=User)
async def create_user(user: UserCreate):
    """Create a new user."""
    return create_user_in_db(user)
'''
        endpoints = scan_python_file(source_code, "api.py")

        assert len(endpoints) == 1
        endpoint = endpoints[0]

        assert endpoint.method == "POST"
        assert endpoint.path == "/users"
        assert endpoint.function_name == "create_user"
        assert endpoint.response_model == "User"
        assert endpoint.docstring == "Create a new user."
        assert endpoint.has_docstring is True

        # Check body parameter
        assert len(endpoint.parameters) == 1
        param = endpoint.parameters[0]
        assert param.name == "user"
        assert param.type_hint == "UserCreate"
        assert param.location == "body"
        assert param.required is True

    def test_detects_multiple_http_methods(self):
        """Test Example 3 from specification: Multiple HTTP methods.

        Reference: endpoint-detection.md Example 3
        Requirements: R1
        """
        source_code = '''
from fastapi import FastAPI
app = FastAPI()

@app.get("/items")
async def list_items(): pass

@app.post("/items")
async def create_item(): pass

@app.get("/items/{id}")
async def get_item(id: int): pass

@app.put("/items/{id}")
async def update_item(id: int): pass

@app.delete("/items/{id}")
async def delete_item(id: int): pass
'''
        endpoints = scan_python_file(source_code, "api.py")

        assert len(endpoints) == 5

        methods = [ep.method for ep in endpoints]
        assert methods == ["GET", "POST", "GET", "PUT", "DELETE"]

        paths = [ep.path for ep in endpoints]
        assert paths == ["/items", "/items", "/items/{id}", "/items/{id}", "/items/{id}"]

        functions = [ep.function_name for ep in endpoints]
        assert functions == ["list_items", "create_item", "get_item", "update_item", "delete_item"]

    def test_detects_deprecated_flag(self):
        """Test Example 4 from specification: Deprecated endpoint.

        Reference: endpoint-detection.md Example 4
        Requirements: R3 (deprecation status)
        """
        source_code = '''
from fastapi import FastAPI
app = FastAPI()

@app.get("/old-endpoint", deprecated=True)
async def old_endpoint():
    """This endpoint is deprecated."""
    pass
'''
        endpoints = scan_python_file(source_code, "api.py")

        assert len(endpoints) == 1
        endpoint = endpoints[0]

        assert endpoint.method == "GET"
        assert endpoint.path == "/old-endpoint"
        assert endpoint.is_deprecated is True
        assert endpoint.docstring == "This endpoint is deprecated."


class TestRouterDecorators:
    """Test router-level decorator detection."""

    def test_detects_router_decorators(self):
        """Test R2: Detect router-level decorators.

        Reference: endpoint-detection.md R2
        """
        source_code = '''
from fastapi import APIRouter
router = APIRouter()

@router.get("/users")
async def list_users(): pass

@router.post("/users")
async def create_user(): pass
'''
        endpoints = scan_python_file(source_code, "api.py")

        assert len(endpoints) == 2
        assert endpoints[0].method == "GET"
        assert endpoints[0].path == "/users"
        assert endpoints[1].method == "POST"
        assert endpoints[1].path == "/users"

    def test_detects_all_http_methods_on_router(self):
        """Test all HTTP methods work with router decorators.

        Reference: endpoint-detection.md R1, R2
        """
        source_code = '''
from fastapi import APIRouter
router = APIRouter()

@router.get("/test")
async def get_test(): pass

@router.post("/test")
async def post_test(): pass

@router.put("/test")
async def put_test(): pass

@router.delete("/test")
async def delete_test(): pass

@router.patch("/test")
async def patch_test(): pass

@router.options("/test")
async def options_test(): pass

@router.head("/test")
async def head_test(): pass
'''
        endpoints = scan_python_file(source_code, "api.py")

        assert len(endpoints) == 7
        methods = [ep.method for ep in endpoints]
        assert methods == ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]


class TestEdgeCases:
    """Test edge cases from specification."""

    def test_endpoint_without_docstring(self):
        """Test EC1: No docstring.

        Reference: endpoint-detection.md EC1
        """
        source_code = '''
from fastapi import FastAPI
app = FastAPI()

@app.get("/no-docs")
async def no_docs():
    pass
'''
        endpoints = scan_python_file(source_code, "api.py")

        assert len(endpoints) == 1
        endpoint = endpoints[0]

        assert endpoint.has_docstring is False
        assert endpoint.docstring is None

    def test_handles_sync_functions(self):
        """Test EC2: Sync (non-async) functions.

        Reference: endpoint-detection.md EC2
        """
        source_code = '''
from fastapi import FastAPI
app = FastAPI()

@app.get("/sync")
def sync_endpoint():
    """A synchronous endpoint."""
    return {"status": "ok"}
'''
        endpoints = scan_python_file(source_code, "api.py")

        assert len(endpoints) == 1
        endpoint = endpoints[0]

        assert endpoint.is_async is False
        assert endpoint.function_name == "sync_endpoint"

    def test_detects_multiple_path_parameters(self):
        """Test EC3: Multiple path parameters.

        Reference: endpoint-detection.md EC3, R4
        """
        source_code = '''
from fastapi import FastAPI
app = FastAPI()

@app.get("/orgs/{org_id}/repos/{repo_id}")
async def get_repo(org_id: int, repo_id: int):
    pass
'''
        endpoints = scan_python_file(source_code, "api.py")

        assert len(endpoints) == 1
        endpoint = endpoints[0]

        assert endpoint.path == "/orgs/{org_id}/repos/{repo_id}"
        assert len(endpoint.parameters) == 2

        # Check both parameters are detected as path parameters
        param_names = [p.name for p in endpoint.parameters]
        assert "org_id" in param_names
        assert "repo_id" in param_names

        for param in endpoint.parameters:
            assert param.location == "path"
            assert param.type_hint == "int"

    def test_handles_query_parameters(self):
        """Test EC4: Query parameters with defaults.

        Reference: endpoint-detection.md EC4, R5
        """
        source_code = '''
from fastapi import FastAPI
app = FastAPI()

@app.get("/search")
async def search(q: str = None, limit: int = 10):
    pass
'''
        endpoints = scan_python_file(source_code, "api.py")

        assert len(endpoints) == 1
        endpoint = endpoints[0]

        assert len(endpoint.parameters) == 2

        # Find parameters by name
        q_param = next(p for p in endpoint.parameters if p.name == "q")
        limit_param = next(p for p in endpoint.parameters if p.name == "limit")

        # Query parameters should not be required (have defaults)
        assert q_param.required is False
        assert q_param.default_value == "None"
        assert q_param.location == "query"

        assert limit_param.required is False
        assert limit_param.default_value == "10"
        assert limit_param.location == "query"

    def test_ignores_non_fastapi_decorators(self):
        """Test EC5: Invalid decorators are skipped.

        Reference: endpoint-detection.md EC5
        """
        source_code = '''
from fastapi import FastAPI
app = FastAPI()

@property
def some_property(self):
    pass

@staticmethod
def some_static():
    pass

@app.get("/valid")
async def valid_endpoint():
    pass
'''
        endpoints = scan_python_file(source_code, "api.py")

        # Should only detect the valid FastAPI endpoint
        assert len(endpoints) == 1
        assert endpoints[0].path == "/valid"


class TestParameterDetection:
    """Test parameter extraction and type hints."""

    def test_extracts_parameter_type_hints(self):
        """Test R5: Handle type hints.

        Reference: endpoint-detection.md R5
        """
        source_code = '''
from fastapi import FastAPI
app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int, include_posts: bool = False):
    pass
'''
        endpoints = scan_python_file(source_code, "api.py")

        assert len(endpoints) == 1
        endpoint = endpoints[0]

        assert len(endpoint.parameters) == 2

        user_id_param = next(p for p in endpoint.parameters if p.name == "user_id")
        assert user_id_param.type_hint == "int"
        assert user_id_param.required is True
        assert user_id_param.location == "path"

        include_posts_param = next(p for p in endpoint.parameters if p.name == "include_posts")
        assert include_posts_param.type_hint == "bool"
        assert include_posts_param.required is False
        assert include_posts_param.default_value == "False"
        assert include_posts_param.location == "query"

    def test_handles_complex_type_hints(self):
        """Test complex type annotations."""
        source_code = '''
from fastapi import FastAPI
from typing import Optional, List
app = FastAPI()

@app.get("/items")
async def get_items(
    tags: Optional[List[str]] = None,
    limit: int = 100
):
    pass
'''
        endpoints = scan_python_file(source_code, "api.py")

        assert len(endpoints) == 1
        endpoint = endpoints[0]

        # Should extract type hints even if complex
        tags_param = next(p for p in endpoint.parameters if p.name == "tags")
        assert tags_param.type_hint is not None
        assert tags_param.required is False

    def test_detects_pydantic_model_parameters(self):
        """Test body parameters with Pydantic models."""
        source_code = '''
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Item(BaseModel):
    name: str
    price: float

@app.post("/items")
async def create_item(item: Item):
    pass
'''
        endpoints = scan_python_file(source_code, "api.py")

        assert len(endpoints) == 1
        endpoint = endpoints[0]

        assert len(endpoint.parameters) == 1
        param = endpoint.parameters[0]
        assert param.name == "item"
        assert param.type_hint == "Item"
        assert param.location == "body"


class TestPathParameterFormats:
    """Test various path parameter formats."""

    def test_handles_typed_path_parameters(self):
        """Test R4: Path parameters with type constraints.

        Reference: endpoint-detection.md R4
        """
        source_code = '''
from fastapi import FastAPI
app = FastAPI()

@app.get("/items/{item_id:int}")
async def get_item(item_id: int):
    pass
'''
        endpoints = scan_python_file(source_code, "api.py")

        assert len(endpoints) == 1
        endpoint = endpoints[0]

        # Path should preserve the type constraint syntax
        assert "{item_id" in endpoint.path

    def test_handles_multiple_path_segments(self):
        """Test complex path structures."""
        source_code = '''
from fastapi import FastAPI
app = FastAPI()

@app.get("/api/v1/orgs/{org_id}/repos/{repo_id}/issues/{issue_id}")
async def get_issue(org_id: str, repo_id: str, issue_id: int):
    pass
'''
        endpoints = scan_python_file(source_code, "api.py")

        assert len(endpoints) == 1
        endpoint = endpoints[0]

        assert endpoint.path == "/api/v1/orgs/{org_id}/repos/{repo_id}/issues/{issue_id}"
        assert len(endpoint.parameters) == 3


class TestResponseModels:
    """Test response model extraction."""

    def test_extracts_response_model(self):
        """Test R3: Response model extraction."""
        source_code = '''
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class UserResponse(BaseModel):
    id: int
    username: str

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    pass
'''
        endpoints = scan_python_file(source_code, "api.py")

        assert len(endpoints) == 1
        endpoint = endpoints[0]

        assert endpoint.response_model == "UserResponse"

    def test_handles_missing_response_model(self):
        """Test endpoints without response_model."""
        source_code = '''
from fastapi import FastAPI
app = FastAPI()

@app.get("/users")
async def get_users():
    pass
'''
        endpoints = scan_python_file(source_code, "api.py")

        assert len(endpoints) == 1
        endpoint = endpoints[0]

        assert endpoint.response_model is None


class TestFileLocation:
    """Test file path and line number tracking."""

    def test_tracks_line_numbers(self):
        """Test R3: File location tracking."""
        source_code = '''
from fastapi import FastAPI
app = FastAPI()

# Some comments

@app.get("/first")
async def first(): pass

# More comments

@app.get("/second")
async def second(): pass
'''
        endpoints = scan_python_file(source_code, "test.py")

        assert len(endpoints) == 2

        # Line numbers should be different
        assert endpoints[0].line_number < endpoints[1].line_number
        assert endpoints[0].file_path == "test.py"
        assert endpoints[1].file_path == "test.py"


class TestEmptyAndInvalidInput:
    """Test handling of empty or invalid input."""

    def test_handles_empty_file(self):
        """Test empty source code."""
        source_code = ""
        endpoints = scan_python_file(source_code, "empty.py")

        assert endpoints == []

    def test_handles_no_endpoints(self):
        """Test file with no FastAPI endpoints."""
        source_code = '''
def regular_function():
    pass

class RegularClass:
    def method(self):
        pass
'''
        endpoints = scan_python_file(source_code, "regular.py")

        assert endpoints == []

    def test_handles_syntax_errors_gracefully(self):
        """Test that syntax errors don't crash the scanner."""
        source_code = '''
from fastapi import FastAPI
app = FastAPI(

# Syntax error - unclosed parenthesis
'''
        # Should either return empty list or raise a clear error
        # Implementation will determine exact behavior
        try:
            endpoints = scan_python_file(source_code, "invalid.py")
            assert endpoints == []
        except SyntaxError:
            # Acceptable to raise SyntaxError for invalid Python
            pass
