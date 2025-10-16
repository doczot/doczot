# Feature: FastAPI Endpoint Detection

## Overview

DocZot scans Python files to detect FastAPI API endpoints using Abstract Syntax Tree (AST) parsing.

## Requirements

### R1: Detect Application-Level Decorators
Must detect these patterns:
- `@app.get(path)`
- `@app.post(path)`
- `@app.put(path)`
- `@app.delete(path)`
- `@app.patch(path)`
- `@app.options(path)`
- `@app.head(path)`

### R2: Detect Router-Level Decorators
Must also detect:
- `@router.get(path)`
- `@router.post(path)`
- etc.

### R3: Extract Endpoint Information
For each endpoint, extract:
1. **HTTP Method** (GET, POST, etc.)
2. **Path** (URL path including parameters)
3. **Function Name** (Python function that handles request)
4. **File Location** (file path and line number)
5. **Docstring** (function docstring if present)
6. **Parameters** (function parameters with type hints)
7. **Response Model** (if specified in decorator)
8. **Deprecation Status** (if `deprecated=True`)
9. **Async Status** (whether function is async)

### R4: Handle Path Parameters
Must correctly parse paths with parameters:
- `/users/{user_id}`
- `/orgs/{org_id}/repos/{repo_id}`
- `/items/{item_id:int}`

### R5: Handle Type Hints
Must extract type hints from function parameters:
```python
async def get_user(user_id: int, include_posts: bool = False):
    pass
```
Should extract:
- `user_id`: type=`int`, required=`True`
- `include_posts`: type=`bool`, required=`False`, default=`False`

## Examples

### Example 1: Simple GET Endpoint

**Input Code:**
```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    """Retrieve a user by ID."""
    return {"user_id": user_id}
```

**Expected Output:**
```python
Endpoint(
    method="GET",
    path="/users/{user_id}",
    function_name="get_user",
    file_path="api.py",
    line_number=5,
    docstring="Retrieve a user by ID.",
    has_docstring=True,
    parameters=[
        Parameter(name="user_id", type_hint="int", location="path", required=True)
    ],
    is_async=True,
    is_deprecated=False
)
```

### Example 2: POST with Request Body

**Input Code:**
```python
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
```

**Expected Output:**
```python
Endpoint(
    method="POST",
    path="/users",
    function_name="create_user",
    parameters=[
        Parameter(name="user", type_hint="UserCreate", location="body", required=True)
    ],
    response_model="User",
    docstring="Create a new user.",
    has_docstring=True
)
```

### Example 3: Multiple HTTP Methods

**Input Code:**
```python
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
```

**Expected Output:**
5 separate Endpoint objects with methods: GET, POST, GET, PUT, DELETE

### Example 4: Deprecated Endpoint

**Input Code:**
```python
@app.get("/old-endpoint", deprecated=True)
async def old_endpoint():
    """This endpoint is deprecated."""
    pass
```

**Expected Output:**
```python
Endpoint(
    method="GET",
    path="/old-endpoint",
    is_deprecated=True,
    docstring="This endpoint is deprecated."
)
```

## Edge Cases

### EC1: No Docstring
Endpoint without docstring should have `has_docstring=False` and `docstring=None`

### EC2: Sync Functions
Non-async functions should have `is_async=False`

### EC3: Multiple Path Parameters
Must extract all parameters from path like `/orgs/{org_id}/repos/{repo_id}`

### EC4: Query Parameters
Parameters with default values are typically query parameters:
```python
async def search(q: str = None, limit: int = 10):
    pass
```

### EC5: Invalid Decorator
Should skip decorators that aren't FastAPI patterns:
```python
@property
def some_property(self):
    pass
```

## Implementation Notes

- Use Python's built-in `ast` module (no external dependencies)
- Walk AST tree looking for function definitions with decorators
- Decorator must be a `Call` node with `Attribute` access pattern
- Extract path from first positional argument (must be string literal)
- Use `ast.get_docstring()` to extract docstrings
- Parse function signature from `FunctionDef.args`

## Testing Strategy

- Test each requirement separately
- Include examples and edge cases as test cases
- Aim for >90% code coverage
- Test on real FastAPI code as integration tests

## Success Criteria

- ✅ All requirements implemented
- ✅ All examples produce correct output
- ✅ All edge cases handled
- ✅ Tests pass with >90% coverage
- ✅ Works on real FastAPI projects
