# DocZot Architecture

## Overview

DocZot uses a **four-layer model** for documentation coverage analysis:

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: SURFACE GRAPH (auto-scanned)                          │
│  Raw product elements from code: endpoints, entities, concepts  │
│  Immutable snapshot of the codebase at a point in time          │
└─────────────────────────────────────────────────────────────────┘
                              ↓ grouped into
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: ITM - INTENDED TOPIC MANIFEST                         │
│  Topics that SHOULD exist, covering surface elements            │
│  Auto-suggested from surface, then human-curated                │
└─────────────────────────────────────────────────────────────────┘
                              ↓ compared against
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: ATM - ACTUAL TOPIC MANIFEST                           │
│  Topics that DO exist, discovered from docs                     │
│  Auto-parsed from actual documentation                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓ produces
┌─────────────────────────────────────────────────────────────────┐
│  Layer 4: GAP REPORT                                            │
│  Missing topics, coverage %, quality scores, sprint plan        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Surface Graph

The Surface Graph is an immutable snapshot of all documentable elements in the codebase.

### Node Types

| Type | Description | Examples |
|------|-------------|----------|
| **Verb** | API endpoints (actions) | `POST /users`, `GET /items/{id}` |
| **Noun** | Entities (things operated on) | `user`, `item`, `order` |
| **Concept** | Abstract ideas | `authentication`, `rate limiting` |

### Edge Types

| Type | Description | Example |
|------|-------------|---------|
| `operates_on` | Verb → Noun | `create_user` operates_on `user` |
| `part_of` | Noun → Noun | `address` part_of `user` |
| `related_to` | Any → Any | `oauth` related_to `authentication` |

### Entity Detection

Entities (nouns) are extracted from multiple sources:

1. **URL Path Analysis**
   - Plural segments before path params: `/users/{id}` → `user`
   - Resource names: `/items`, `/orders` → `item`, `order`

2. **Code Analysis (AST-based)**
   - Variable assignments: `user = crud.get_user_by_email(...)` → `user`
   - CRUD patterns: `crud.create_item(...)` → `item`
   - Type hints: `user: UserPublic` → `user`
   - Response models: `response_model=User` → `user`

3. **Filtering**
   - Skip infrastructure types: `Session`, `HTTPException`, `Request`
   - Skip compound names: `UserCreate`, `ItemUpdate` (keep base entity)
   - Skip action words: `login`, `verify`, `health`

### Router Prefix Resolution

The scanner tracks FastAPI router prefixes to build complete paths:

```python
# Router definition
router = APIRouter(prefix="/users")

@router.get("/{user_id}")  # Scanned path: /users/{user_id}
async def get_user(user_id: int): ...
```

---

## Layer 2: ITM (Intended Topic Manifest)

The ITM defines what documentation SHOULD exist, organized in a type-first hierarchy.

### Topic Hierarchy

```
Reference
└── API
    ├── User
    │   ├── Create user
    │   ├── Get user
    │   ├── Update user
    │   └── Delete user
    └── Item
        ├── Create item
        └── List items

Concept
└── Entity
    ├── User
    └── Item

Task
├── How to authenticate
├── How to manage your account
├── How to recover your password
└── How to work with Users
```

### Topic Types

| Type | Purpose | Coverage |
|------|---------|----------|
| **Reference** | API endpoint documentation | One topic per endpoint |
| **Concept** | Entity explanations | One topic per noun |
| **Task** | How-to guides | Inferred from patterns |
| **Onboarding** | Getting started | Manual curation |
| **Changes** | Releases, deprecations | Manual curation |

### How-To Inference

DocZot automatically infers how-to topics from common API patterns:

| Pattern | Detection | Example Topic |
|---------|-----------|---------------|
| **Auth Flow** | `signup`, `login`, `access-token` in paths | "How to authenticate" |
| **Account Management** | `/me`, `/self`, `/current` endpoints | "How to manage your account" |
| **Password Recovery** | `password-recovery`, `reset-password` in paths | "How to recover your password" |
| **CRUD Journeys** | Entity with POST + (GET or PUT) | "How to work with Users" |

**Design Principle:** How-tos cover both the verbs (endpoints) AND the nouns (entities) they operate on. This ensures hovering over "How to work with Users" highlights both the User entity and all its related endpoints.

---

## Layer 3: ATM (Actual Topic Manifest)

The ATM discovers what documentation actually exists by parsing markdown files.

### Discovery Process

1. **Find markdown files** in `docs/`, `README.md`, etc.
2. **Parse into chunks** by heading structure
3. **Build vector embeddings** for semantic search
4. **Match to surface elements** using similarity scoring

### Quality Assessment

Each discovered topic is assessed for:

| Dimension | Check |
|-----------|-------|
| `has_parameters` | Documents function parameters? |
| `has_returns` | Documents return values? |
| `has_errors` | Documents error conditions? |
| `has_warnings` | Includes cautions/warnings? |
| `has_description` | Has substantial description? |
| `has_examples` | Includes code examples? |

---

## Layer 4: Gap Report

The Gap Report computes `ITM - ATM` to identify documentation gaps.

### Gap Statuses

| Status | Meaning | Action |
|--------|---------|--------|
| **Missing** | ITM topic has no ATM match | Create new documentation |
| **Partial** | ATM covers some surface elements | Expand existing docs |
| **Complete** | Full coverage with good quality | No action needed |
| **Extra** | ATM topic not in ITM | Review for relevance |

### Sprint Plan Generation

Gaps are prioritized into actionable sprint items:
- Missing topics → "Create new [type] topic: [name]"
- Partial topics → "Add coverage for [N] missing elements"
- Quality gaps → "Add examples", "Document errors", etc.

---

## Project Structure

```
doczot/
├── doczot_analyzer/              # Core product (SHIPS)
│   ├── __init__.py
│   ├── models.py                 # Legacy v1 models
│   ├── models_v2.py              # v2 Surface/ITM/ATM/Gap models
│   ├── scanner.py                # FastAPI endpoint + entity detection
│   ├── analyzer_v2.py            # Surface graph builder, ATM discovery
│   ├── cli_v2.py                 # CLI and HTML visualizer
│   ├── docs_parser.py            # Markdown documentation parser
│   ├── vector_store.py           # Semantic search for doc matching
│   └── matcher.py                # Endpoint-to-doc matching
│
├── docs/                         # Documentation (SHIPS)
│   ├── features/                 # Feature specifications
│   ├── BACKLOG.md                # Product backlog
│   ├── LEARNINGS.md              # Design insights and decisions
│   └── SELF_HOSTING.md           # Self-hosting guide
│
├── tests/                        # Test suite
│   └── test_*.py
│
├── research/                     # Development tools (GITIGNORED)
│   ├── build_dataset.py          # Extract pairs from repos
│   └── rate_pairs.py             # Rating UI for golden dataset
│
└── pyproject.toml                # Package configuration
```

---

## Interactive Visualization

The `doczot visualize` command generates an interactive HTML visualization:

### Features

- **Force-directed graph** of surface elements (verbs + nouns)
- **Color coding**: Green = documented, Red = undocumented
- **Shape coding**: Rectangles = verbs, Ellipses = nouns
- **Hover-to-highlight**: Hover ITM topics to see which surface elements they cover
- **Zoom/pan**: Scroll to zoom, Shift+drag to pan
- **Smart labels**: Long names truncated with middle ellipsis
- **Sidebar tabs**: Surface list, ITM tree, ATM list, Gap report

### Usage

```bash
doczot visualize /path/to/repo --output viz.html --open
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `doczot analyze` | Run full analysis (surface, ITM, ATM, gaps) |
| `doczot surface` | Explore the product surface graph |
| `doczot itm` | View/manage intended topic manifest |
| `doczot atm` | View actual topic manifest from docs |
| `doczot gaps` | View gap report and sprint plan |
| `doczot visualize` | Generate interactive HTML visualization |

---

## Design Principles

### 1. Separation of Concerns
- Surface Graph = raw facts about code (immutable)
- ITM = documentation plan (curated)
- ATM = documentation reality (discovered)
- Gap Report = actionable insights (computed)

### 2. Type-First Information Architecture
- Group by content type first (Reference, Concept, Task)
- Then by entity/resource
- Then by specific endpoint/operation
- Matches industry best practices for API documentation

### 3. Conservative How-To Inference
- Only suggest how-tos for clearly recognizable patterns
- Avoid over-abundance of topics
- Better to miss a how-to than suggest irrelevant ones
- How-tos cover both verbs AND nouns for complete highlighting

### 4. Entity Detection from Code
- URLs alone miss many entity relationships
- Password recovery endpoints operate on users (via code)
- AST analysis reveals true entity dependencies
- Filter infrastructure types to keep domain entities clean

### 5. Test-First Development
- Write specs → Write tests → Implement
- 91% code coverage on core modules
- Real-world validation on open source projects

---

## Future Architecture

### GitHub App Integration
```
PR Opened → Webhook → Analyze Changes → Comment on PR
                                      ↓
                          "3 new endpoints need docs"
```

### LLM Quality Scoring
```
ATM Topic → LLM Analysis → Quality Scores
                         ↓
              "Missing error documentation"
              "Examples are outdated"
```

---

## License

DocZot is licensed under **AGPL-3.0**. See [LICENSE](LICENSE) for details.
