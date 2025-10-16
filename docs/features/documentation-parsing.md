# Feature: Documentation Parsing

## Overview

DocZot scans markdown files to find references to API endpoints.

## Requirements

### R1: Find Markdown Files
Must scan these locations:
- `README.md` (root)
- `/docs/**/*.md`
- `/documentation/**/*.md`
- Any file matching `*api*.md`

Skip these files:
- `CHANGELOG.md`
- `LICENSE.md`
- `CONTRIBUTING.md`
- Hidden files (starting with `.`)

### R2: Extract Endpoint References
Must recognize these patterns:

**Code blocks:**
```
GET /api/users
```

**Inline code:**
`GET /api/users`

**HTTP method + path:**
- GET /users
- POST /api/v1/users
- PUT /users/{id}

**Markdown tables:**
| Method | Path | Description |
|--------|------|-------------|
| GET | /users | List users |

### R3: Capture Context
For each reference, extract:
1. **File path** - Which markdown file
2. **Line number** - Where in the file
3. **Section heading** - The ## or ### above it
4. **Content** - The surrounding text
5. **Mentioned paths** - List of endpoint paths found
6. **Mentioned methods** - List of HTTP methods found

### R4: Handle Various Path Formats
Must recognize:
- `/users` (simple)
- `/users/{id}` (with path param)
- `/users/{user_id}` (named param)
- `/api/v1/users` (with prefix)
- `/orgs/{org_id}/repos/{repo_id}` (multiple params)

## Examples

### Example 1: Code Block with Endpoint

**Input Markdown:**
```markdown
## Authentication

To get an access token:

\`\`\`
POST /api/auth/token
Content-Type: application/json
\`\`\`
```

**Expected Output:**
```python
DocReference(
    file_path="docs/auth.md",
    section_heading="Authentication",
    mentioned_paths=["/api/auth/token"],
    mentioned_methods=["POST"],
    content="POST /api/auth/token\nContent-Type: application/json",
    line_number=5
)
```

### Example 2: Inline Documentation

**Input Markdown:**
```markdown
## Quick Start

First, create a user with `POST /api/users`. 
Then retrieve it using `GET /api/users/{id}`.
```

**Expected Output:**
```python
DocReference(
    file_path="docs/quickstart.md",
    section_heading="Quick Start",
    mentioned_paths=["/api/users", "/api/users/{id}"],
    mentioned_methods=["POST", "GET"],
    content="First, create a user with `POST /api/users`. Then retrieve it using `GET /api/users/{id}`.",
    line_number=3
)
```

### Example 3: Table Format

**Input Markdown:**
```markdown
## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /users | List all users |
| POST | /users | Create a user |
| DELETE | /users/{id} | Delete a user |
```

**Expected Output:**
```python
DocReference(
    file_path="docs/api.md",
    section_heading="Endpoints",
    mentioned_paths=["/users", "/users/{id}"],
    mentioned_methods=["GET", "POST", "DELETE"],
    content="<table content>",
    line_number=3
)
```

## Edge Cases

### EC1: Empty File
Empty markdown should return empty list

### EC2: No Endpoint References
Markdown without API references should return empty list

### EC3: Commented Code
HTML comments might contain endpoints but shouldn't be extracted:
```markdown
<!--
GET /api/internal
-->
```

### EC4: Similar Path Variations
Must capture all variations:
- `/users/{id}`
- `/users/{user_id}`
- `/users/:id` (different style)

## Implementation Notes

- Use `markdown-it-py` for parsing
- Apply regex patterns for endpoint extraction
- Track line numbers for context
- Deduplicate paths and methods
- Preserve section context

## Testing Strategy

- Test each markdown format separately
- Include edge cases as test cases
- Test on real documentation files
- Verify no false positives

## Success Criteria

- ✅ All requirements implemented
- ✅ All examples produce correct output
- ✅ All edge cases handled
- ✅ Tests pass with >85% coverage
- ✅ Works on real documentation files
