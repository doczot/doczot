# DocZot Product Overview and Architecture

**Last Updated**: January 2026
**Current Version**: v2 (Complete)
**Next Version**: v3 (In Design)

---

## Table of Contents

1. [What is DocZot?](#what-is-docZot)
2. [Product Vision](#product-vision)
3. [Current Architecture (v2)](#current-architecture-v2)
4. [How We Got Here: Evolution from v1 to v2](#how-we-got-here-evolution-from-v1-to-v2)
5. [The Four-Layer Model](#the-four-layer-model)
6. [Key Design Principles](#key-design-principles)
7. [What's Next: v3 Direction](#whats-next-v3-direction)
8. [Implementation Status](#implementation-status)

---

## What is DocZot?

DocZot is an **open-source documentation coverage analyzer** for API codebases. Like Codecov measures test coverage, DocZot measures documentation coverage—but with a critical difference: it understands that documentation isn't just content about your API, it's a **map of your API's functional surface**.

### The Core Insight

In the AI era, documentation serves two consumers:

1. **Humans** who read to understand and complete tasks
2. **AI agents** who query to build context and execute programmatically

When documentation is incomplete or inaccurate, it's not just an annoyance—it's a **broken link in an agent's reasoning chain**. DocZot treats documentation as **enterprise ontology capture**: the structured knowledge of what objects exist (nouns), what operations are possible (verbs), what concepts matter, and what constraints govern interactions.

### What DocZot Does

```
Code → Scan → Surface Graph → Generate ITM → Discover ATM → Gap Report → Action Plan
```

1. **Scans your codebase** to discover API endpoints, entities, and relationships
2. **Builds a Surface Graph** of your API's structure
3. **Generates an Intended Topic Manifest (ITM)** - what docs SHOULD exist
4. **Discovers the Actual Topic Manifest (ATM)** - what docs DO exist
5. **Produces a Gap Report** showing missing coverage with quality scores
6. **Creates an interactive visualizer** with hover-to-highlight topic coverage

**Result**: A clear, actionable report showing exactly what's undocumented and how to fix it.

---

## Product Vision

### Short-term (v2 - Complete)

DocZot as a **self-hosted documentation coverage tool**:
- Deterministic code scanning (no LLM required)
- Semantic matching for doc discovery
- Interactive visualization
- CI/CD integration ready
- Works with FastAPI projects

### Mid-term (v3 - In Design)

DocZot as an **ontology reliability platform**:
- Persistent ontology storage with drift detection
- Constraint extraction (auth, rate limits, prerequisites)
- Concept mining from docstrings and README files
- Agent-oriented outputs (MCP resources, llms.txt, JSON-LD)
- Enhanced quality scoring for agent readiness

### Long-term (v4+)

DocZot as **enterprise knowledge infrastructure**:
- Multi-framework support (Flask, Django, Express, Spring)
- Cross-product ontology linking
- GitHub App with automated PR comments
- Managed service option
- LLM-powered quality assessment
- Documentation template generation

---

## Current Architecture (v2)

### The Four-Layer Model

DocZot's architecture is organized around four distinct layers, each with a clear purpose:

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: SURFACE GRAPH                                     │
│  Immutable snapshot of code structure                       │
│  • Verbs: API endpoints discovered via AST scanning         │
│  • Nouns: Entities extracted from paths AND code analysis   │
│  • Edges: operates_on relationships between verbs and nouns │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2: ITM (INTENDED TOPIC MANIFEST)                     │
│  The PLAN for what documentation should exist               │
│  • Reference > API > Entity > Individual endpoints          │
│  • Concept > Entity (one per discovered noun)               │
│  • Task > How-tos (inferred from API patterns)              │
│  • Auto-generated, human-reviewable                         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 3: ATM (ACTUAL TOPIC MANIFEST)                       │
│  The REALITY of what documentation exists                   │
│  • Discovered by parsing markdown files                     │
│  • Matched to surface elements via semantic search          │
│  • Quality assessed per topic                               │
│  • Linked back to Surface Graph                             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 4: GAP REPORT                                        │
│  Actionable insights and sprint planning                    │
│  • Coverage percentage (topics documented / topics needed)  │
│  • Missing topics with priorities                           │
│  • Partial topics needing enhancement                       │
│  • Sprint plan for doc improvements                         │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| **Scanner** | `scanner.py` | AST-based FastAPI endpoint detection with entity extraction |
| **Analyzer** | `analyzer_v2.py` | Surface graph builder, ATM discovery, gap analysis |
| **Models** | `models_v2.py` | Pydantic models for Surface, ITM, ATM, Gap reports |
| **CLI** | `cli_v2.py` | Command-line interface and HTML visualizer |
| **Docs Parser** | `docs_parser.py` | Markdown documentation parser (excludes tests, translations) |
| **Vector Store** | `vector_store.py` | Semantic search for matching docs to endpoints |
| **Matcher** | `matcher.py` | Logic for endpoint-to-documentation matching |
| **Storage** | `storage.py` | SQLite persistence for manifests (v3: will store full graph) |

### Technology Stack

- **Language**: Python 3.11+
- **Core Libraries**:
  - Pydantic for data models
  - FastAPI for type analysis
  - sentence-transformers for embeddings
  - SQLite for storage
  - Click for CLI
- **Testing**: pytest with 91% coverage
- **No LLM required**: All extraction is deterministic (LLM planned for v3 quality scoring)

---

## How We Got Here: Evolution from v1 to v2

### Early Concept: Entity-Centric Organization

**Initial approach**: Organize documentation around entities (nouns), like "User Management" containing all user-related docs.

**Problem discovered**: This doesn't match how developers actually navigate documentation. Developers think in terms of content **types** first (API reference vs conceptual guides vs how-tos), then drill into entities.

**Solution**: Type-first hierarchy introduced in v2.

### Early Extraction: URL-Only Entity Detection

**Initial approach**: Extract entities purely from URL paths.

Example: `POST /password-recovery/{email}` → entity: "password-recovery"

**Problem discovered**: Many endpoints don't reveal their true entity in the URL. Password recovery, login, and signup all operate on the **user** entity, but none mention "user" in their paths.

**Solution**: AST-based code analysis to detect entities from:
- Variable assignments: `user = crud.get_user_by_email(...)`
- CRUD function calls: `crud.create_item(...)`
- Type hints: `def get_user(user: UserPublic)`
- Response models: `response_model=User`

### Early Assumption: All Docs Are Valuable

**Initial approach**: Parse all markdown files found in the repository.

**Problem discovered**:
1. Test files create fixture endpoints that pollute the dataset
2. Translation directories create 15x duplicate documentation
3. FastAPI project had 823 doc references; 87% were translations

**Solution**:
- Exclude `tests/`, `test_*.py`, `*_test.py`
- Exclude translation directories (zh/, ja/, pt/, etc.)
- Keep only English docs or language-neutral paths

### Early Visualization: Show Everything

**Initial approach**: Display all nodes and edges equally.

**Problem discovered**: Users couldn't tell what was documented vs undocumented at a glance.

**Solution**: Hover-to-highlight interaction where hovering ITM topics dims non-covered nodes and highlights covered ones.

### Testing Philosophy: Real Repos Reveal Truth

**Key insight**: Testing on real open-source projects (full-stack-fastapi-template, fastapi-users) revealed problems synthetic examples never would.

**Example discovery**: The full-stack-fastapi-template has **zero API documentation**—it relies entirely on FastAPI's auto-generated Swagger UI. This is a valid, realistic scenario DocZot must handle gracefully.

---

## The Four-Layer Model

### Layer 1: Surface Graph

The Surface Graph is an **immutable snapshot** of all documentable elements in your code at scan time.

#### Nodes

| Node Type | What It Represents | Example |
|-----------|-------------------|---------|
| **Verb** | An API endpoint | `POST /api/users` |
| **Noun** | An entity/resource | `user`, `item`, `project` |

#### Edges

| Edge Type | Relationship | Detection Method |
|-----------|--------------|------------------|
| **operates_on** | verb → noun | Code analysis of what entities the endpoint manipulates |

#### Node Classes

- **user-facing**: Public API endpoints intended for external consumption
- **internal**: Private or admin endpoints
- **auth**: Authentication and authorization endpoints

#### Detection Method

1. **AST scanning** of Python files to find FastAPI decorators
2. **Router prefix tracking** to resolve final mounted paths
3. **Entity extraction** from code, not just URLs:
   - Parse function bodies for CRUD operations
   - Analyze type hints and response models
   - Singularize entity names for consistency

#### Example

```python
# Code
@router.post("")
async def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    user = crud.create_user(db, user_in)
    return user

# Surface Graph nodes created
Verb: id="verb:POST/api/users", name="create_user", http_method="POST", http_path="/api/users"
Noun: id="noun:user", name="user"

# Edge created
operates_on: verb:POST/api/users → noun:user
```

---

### Layer 2: ITM (Intended Topic Manifest)

The ITM is the **plan** for what documentation should exist, auto-generated from the Surface Graph.

#### Type-First Hierarchy

```
Reference
└── API
    ├── User (entity grouping)
    │   ├── Create user (POST /api/users)
    │   ├── Get user (GET /api/users/{id})
    │   ├── Update user (PUT /api/users/{id})
    │   └── Delete user (DELETE /api/users/{id})
    └── Item
        └── ...

Concept
└── Entity
    ├── User (conceptual documentation about what a user is)
    └── Item (conceptual documentation about what an item is)

Task
├── How to authenticate (inferred from auth endpoints)
├── How to work with users (inferred from CRUD pattern)
└── How to manage account settings (inferred from /me endpoints)

Onboarding
├── Getting started
└── Quick start guide
```

#### Topic Types

| Type | Purpose | When Created | Covers |
|------|---------|--------------|--------|
| **Reference** | API endpoint documentation | One per verb | Single endpoint |
| **Concept** | Entity explanation | One per noun | Single entity |
| **Task** | How-to guides | Pattern-based inference | Multiple related endpoints |
| **Onboarding** | Getting started content | Manual curation | Entire product |

#### How-To Inference

DocZot conservatively infers how-to topics from recognizable patterns:

| Pattern | Detection Method | Example |
|---------|-----------------|---------|
| Auth flow | `signup`, `login`, `access-token` in paths | "How to authenticate" |
| Account mgmt | `/me`, `/self`, `/current` endpoints | "How to manage account" |
| Password recovery | `password-recovery`, `reset-password` in paths | "How to reset password" |
| CRUD journey | Entity with POST + (GET or PUT) | "How to work with {entity}" |

**Design principle**: Better to miss a how-to than suggest irrelevant ones.

#### Coverage Tracking

Each ITM topic tracks:
- `covers`: List of Surface Graph node IDs this topic should document
- `status`: `missing`, `partial`, `complete`, `complete_with_quality_issues`
- `priority`: `high`, `medium`, `low`

---

### Layer 3: ATM (Actual Topic Manifest)

The ATM represents the **reality** of what documentation exists, discovered by parsing markdown files.

#### Discovery Process

1. **Parse markdown files** in the repository (excluding tests and translations)
2. **Extract documentation elements**:
   - Endpoint references: `POST /api/users`
   - Code examples
   - Parameter descriptions
   - Response formats
3. **Semantic matching** via embeddings to link docs to Surface Graph nodes
4. **Quality assessment** for each discovered topic

#### Quality Assessment

```python
class TopicQuality(BaseModel):
    # Technical completeness
    has_parameters: Literal["yes", "partial", "no"] = "no"
    has_returns: Literal["yes", "partial", "no"] = "no"
    has_errors: Literal["yes", "partial", "no"] = "no"
    has_warnings: bool = False

    # Semantic completeness
    has_description: bool = False
    has_use_cases: bool = False
    has_examples: bool = False

    # Overall score
    coverage_score: float = 0.0  # 0.0 to 1.0
```

#### Matching Strategy

DocZot uses **semantic search** with sentence transformers to match documentation to endpoints, not just regex. This allows matching:
- `POST /api/users` in docs → `POST /api/users` endpoint ✓
- "Creating a new user via the API" → `POST /api/users` endpoint ✓
- "User creation endpoint" → `POST /api/users` endpoint ✓

---

### Layer 4: Gap Report

The Gap Report is the **actionable output** showing what's missing and how to fix it.

#### Coverage Metrics

```
Total Topics: 47
├── Complete: 12 (26%)
├── Partial: 8 (17%)
└── Missing: 27 (57%)

Coverage by Type:
├── Reference (API): 34% (16/47 endpoints)
├── Concept (Entity): 0% (0/8 entities)
└── Task (How-to): 50% (2/4 guides)
```

#### Gap Types

| Gap Type | Meaning | Action Required |
|----------|---------|-----------------|
| **Missing** | No documentation found | Create new doc |
| **Partial** | Documentation exists but incomplete | Enhance existing doc |
| **Outdated** | Documentation exists but may not match current code | Review and update |
| **Quality Issue** | Documentation exists but has quality problems | Improve quality |

#### Sprint Plan

The Gap Report includes a prioritized action plan:

```markdown
Sprint Plan:

High Priority (Core User Flows):
- [ ] Document POST /api/users (create user endpoint)
- [ ] Document GET /api/users/{id} (get user endpoint)
- [ ] Write "How to authenticate" guide

Medium Priority (Secondary Features):
- [ ] Document PUT /api/users/{id} (update user endpoint)
- [ ] Write "User" concept documentation
- [ ] Enhance "How to manage account" (currently partial)

Low Priority (Admin/Internal):
- [ ] Document DELETE /api/users/{id}
- [ ] Document internal admin endpoints
```

---

## Key Design Principles

These principles emerged from real-world testing and inform all design decisions:

### 1. Code-Aware Entity Detection

**Principle**: URLs alone are insufficient to determine what entities an endpoint operates on.

**Why**: Authentication, password recovery, and account management endpoints often don't mention their entity (user) in the URL path.

**How**: AST analysis of function bodies, type hints, and CRUD operations.

---

### 2. Type-First Information Architecture

**Principle**: Content type (Reference, Concept, Task) comes before entity grouping.

**Why**: Developers navigate documentation by asking "Do I need API reference, or a how-to guide?" before asking "What entity am I working with?"

**How**: ITM organizes topics as Reference > API > Entity > Endpoints, not Entity > All Topics.

---

### 3. Deterministic First, LLM Later

**Principle**: Use deterministic extraction (regex, AST) first. Reserve LLM for enhancements, not core functionality.

**Why**:
- Predictable behavior
- No API costs
- Fast execution
- Transparent logic

**Current state**: v2 uses NO LLM calls. v3 will add optional LLM-assisted quality scoring.

---

### 4. Conservative Topic Inference

**Principle**: Only infer topics (especially how-tos) when patterns are clearly recognizable.

**Why**: False positive topics create noise and erode trust. Better to miss an edge case than suggest irrelevant content.

**How**: Only infer how-tos from high-confidence patterns (auth flow, CRUD journey, account management).

---

### 5. Real Codebases Are the Truth

**Principle**: Test on real open-source projects, not synthetic examples.

**Why**: Real projects reveal edge cases synthetic examples never will.

**Examples**:
- Discovered test files pollute endpoint detection
- Discovered translations create 15x duplicate documentation
- Discovered many projects have zero API docs (rely on Swagger UI)

**Practice**: Maintain test repos (`full-stack-fastapi-template`, `fastapi-users`) for validation.

---

### 6. Separation of Immutable and Mutable Layers

**Principle**: The Surface Graph is immutable (facts from code). ITM and ATM are mutable (interpretations and plans).

**Why**:
- Clear separation of concerns
- Allows human curation of ITM without affecting detection
- Enables ontology diffing between scans

**Example**: Surface Graph can't be edited. ITM can be manually adjusted (prioritize topics, add custom how-tos).

---

### 7. Hover-to-Highlight for Understanding

**Principle**: Visual feedback makes coverage immediately understandable.

**Why**: Static reports are hard to parse. Interactive visualization shows "what does this topic cover?" instantly.

**How**: Hovering an ITM topic dims non-covered nodes and highlights covered nodes in the Surface Graph visualization.

---

### 8. Quality Over Quantity in Filtering

**Principle**: Precision > Recall. Better to exclude edge cases than overwhelm users with noise.

**Why**: Too much noise makes the tool unusable.

**Examples**:
- Exclude test files by default
- Exclude translation directories
- Filter out infrastructure types (Session, HTTPException, Request)

**Corollary**: Allow configuration to override exclusions when needed (future feature).

---

## What's Next: v3 Direction

The v3 architecture builds on v2's foundation by adding:

### 1. Persistent Ontology Storage

**Current**: Surface Graph is rebuilt on each scan.
**v3**: Store full graph in SQLite with scan history.

**Benefits**:
- Ontology diffing: "3 new entities, 2 renamed, 1 deprecated since last scan"
- Trend analysis: How is the API surface evolving?
- Drift detection: Alert when code changes without doc changes

**Implementation**: New tables `surface_nodes`, `surface_edges`, `scans`.

---

### 2. Enhanced Surface Graph: Concepts and Constraints

**New node types**:
- **Concept**: Ideas/definitions needed for understanding (extracted from docstrings, README)
- **Constraint**: Permissions, rate limits, prerequisites (extracted from decorators)

**New edge types**:
- **part_of**: Nested relationships (`/users/{id}/projects` → project part_of user)
- **prerequisite**: Dependencies (auth required, rate limits)
- **constrained_by**: Verb to constraint relationships

**Example**:
```python
# Code
@router.post("/api/items")
@limiter.limit("100/hour")
@requires_auth
async def create_item(item: ItemCreate, user: User = Depends(get_current_user)):
    ...

# New nodes and edges in v3
Constraint: id="constraint:rate_limit:100/hour"
Constraint: id="constraint:auth_required"
Edge: verb:POST/api/items --constrained_by--> constraint:rate_limit:100/hour
Edge: verb:POST/api/items --constrained_by--> constraint:auth_required
```

---

### 3. Concept Extraction (Two-Track Approach)

**Track A: Deterministic** (always enabled, fast, free)
- Regex patterns for definitions: "X is...", "We define X as..."
- Glossary section detection in markdown
- Docstring mining for class/function descriptions

**Track B: LLM-Assisted** (optional, slow, costs money)
- Cluster related terms across documentation
- Infer concept hierarchy from usage patterns
- Generate concept definitions from code context

**Design principle**: Deterministic provides baseline. LLM suggests enhancements.

---

### 4. Agent-Oriented Outputs

DocZot v3 will export formats designed for AI agent consumption:

#### MCP Resources
```json
{
  "resources": [
    {
      "uri": "doczot://myapp/entity/user",
      "name": "user",
      "description": "The user entity",
      "mimeType": "text/plain"
    }
  ],
  "tools": [
    {
      "name": "create_user",
      "description": "POST /api/users",
      "inputSchema": { ... }
    }
  ]
}
```

#### llms.txt
```
# MyApp

## Entities (nouns)
- user: A person with an account in the system
- item: A resource owned by a user

## Operations (verbs)
### User
- POST /api/users: Create a new user
- GET /api/users/{id}: Retrieve a user by ID

## Constraints
- Authentication required for all endpoints except /login and /signup
- Rate limit: 100 requests per hour
```

#### JSON-LD Ontology
Semantic web-compatible ontology export for advanced tooling.

---

### 5. Enhanced Quality Assessment

Expand quality scoring to include:

- **Constraint coverage**: Are auth requirements documented?
- **Agent readiness**: Is there a machine-readable spec (OpenAPI)?
- **Terminology consistency**: Are entity names used consistently?

**New quality fields**:
```python
has_auth_requirements: Literal["yes", "partial", "no"] = "no"
has_rate_limits: Literal["yes", "partial", "no"] = "no"
has_prerequisites: Literal["yes", "partial", "no"] = "no"
has_machine_readable_spec: bool = False
terminology_consistent: bool = False
agent_readiness_score: float = 0.0
```

---

### 6. Graceful Degradation and Cost Control

**Design principle**: LLM features must be optional and cost-transparent.

**Implementation**:
```python
class ExtractionLevel(str, Enum):
    FAST = "fast"      # AST only, ~1s per file
    STANDARD = "standard"  # + docstrings, ~5s per file
    DEEP = "deep"      # + LLM, ~30s per file + API cost

# Always warn before using expensive features
if level == ExtractionLevel.DEEP:
    click.echo("Warning: Deep extraction uses LLM API calls and may incur costs.")
    if not click.confirm("Continue?"):
        level = ExtractionLevel.STANDARD
```

---

## Implementation Status

### v2 Complete

- [x] AST-based FastAPI scanner with router prefix tracking
- [x] Entity detection from code analysis (not just URLs)
- [x] Surface Graph builder (verbs, nouns, operates_on edges)
- [x] ITM generation with type-first hierarchy
- [x] Conservative how-to inference from patterns
- [x] Markdown documentation parser with exclusions (tests, translations)
- [x] Semantic search for doc-to-endpoint matching
- [x] ATM discovery and quality assessment framework
- [x] Gap Report with coverage stats and sprint planning
- [x] Interactive HTML visualizer with hover-to-highlight
- [x] CLI interface (`doczot analyze`, `doczot visualize`)
- [x] SQLite storage for manifests
- [x] 91% test coverage

### v3 Roadmap

**Phase 1: Core Ontology** (Priority: High)
- [ ] Persist Surface Graph in SQLite (not just manifests)
- [ ] Add `part_of` edge detection (nested paths)
- [ ] Add `prerequisite` edge detection (auth decorators)
- [ ] Add constraint node extraction (rate limits, auth requirements)
- [ ] Concept extraction (deterministic track only)
- [ ] Implement ontology diffing

**Phase 2: Quality & Agent Readiness** (Priority: Medium)
- [ ] Expand TopicQuality model with constraint fields
- [ ] Constraint coverage detection in documentation
- [ ] Terminology consistency checking
- [ ] Machine-readable spec detection (OpenAPI, JSON Schema)

**Phase 3: Agent Outputs** (Priority: Medium)
- [ ] MCP resource definition export
- [ ] llms.txt generation
- [ ] JSON-LD ontology export

**Phase 4: LLM Enhancements** (Priority: Low)
- [ ] Optional LLM-assisted concept extraction
- [ ] LLM-powered doc quality scoring
- [ ] LLM-suggested doc improvements

**Phase 5: Enterprise Features** (Priority: TBD)
- [ ] GitHub App with PR comments
- [ ] CI/CD integration examples (GitHub Actions, GitLab CI)
- [ ] Multi-framework support (Flask, Django, Express)
- [ ] Manual documentation-to-code linking (`.doczot/mappings.yml`)
- [ ] Configuration file support (`.doczot/config.yml`)

---

## Appendix: Project Files

### Core Implementation

| File | Lines | Purpose |
|------|-------|---------|
| `scanner.py` | ~500 | FastAPI endpoint and entity detection |
| `analyzer_v2.py` | ~800 | Surface graph builder, ATM discovery |
| `models_v2.py` | ~700 | Pydantic models for all data structures |
| `cli_v2.py` | ~1200 | CLI interface and HTML visualizer |
| `docs_parser.py` | ~300 | Markdown parsing with exclusions |
| `vector_store.py` | ~100 | Semantic search via embeddings |
| `storage.py` | ~400 | SQLite persistence layer |
| `manifest.py` | ~500 | TopicManifest operations |
| `matcher.py` | ~100 | Doc-to-endpoint matching logic |

### Documentation

| File | Purpose |
|------|---------|
| `README.md` | Project overview, quick start, philosophy |
| `CLAUDE.md` | Implementation guide for Claude Code |
| `docs/DESIGN_V3.md` | Vision document for v3 architecture |
| `docs/LEARNINGS.md` | Real-world testing insights and design evolution |
| `docs/BACKLOG.md` | Feature ideas and prioritization |
| `docs/PRODUCT_OVERVIEW.md` | This document - comprehensive product and architecture |
| `docs/SELF_HOSTING.md` | Self-hosting deployment guide |

### Test Repositories

| Repository | Purpose |
|------------|---------|
| `test_repos/full-stack-fastapi-template` | Primary test target, realistic FastAPI structure |
| `test_repos/fastapi-users` | Well-documented project for ATM validation |

---

## Conclusion

DocZot has evolved from a simple "documentation coverage checker" into a sophisticated **documentation ontology analyzer** that bridges the gap between code reality and documented understanding.

**Where we are**: v2 provides a complete, deterministic, LLM-free solution for understanding documentation coverage in FastAPI projects.

**Where we're going**: v3 will add persistent ontology storage, constraint tracking, concept extraction, and agent-oriented outputs—transforming DocZot into infrastructure for the AI-era where documentation serves both humans and agents.

**Core philosophy**: Open source, self-hostable, deterministic first, with optional LLM enhancements. Real-world testing drives all design decisions.

---

**Questions or feedback?** See the [contributing guide](../CONTRIBUTING.md) or [open an issue](https://github.com/yourusername/doczot/issues).
