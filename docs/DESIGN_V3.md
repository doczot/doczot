# DocZot v3 Design Document: Documentation as Enterprise Ontology

**Status**: Vision Document
**Author**: Sharon Campbell-Crow
**Date**: January 2026
**Version**: 3.0

> **Note**: For the **current state** of DocZot's architecture and product design, see [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md). This document describes the **future vision** for v3.

---

## Executive Summary

DocZot v3 reconceptualizes documentation coverage analysis as **enterprise ontology capture and reliability measurement**. In an AI-era where both humans and agents consume documentation to reason and act, documentation IS the published ontology of a product—not merely content "about" the product.

This design document captures the mental model, architecture, and implementation roadmap for evolving DocZot from a documentation gap analyzer into a comprehensive **ontology reliability platform**.

---

## The Problem

### The Traditional View (Outdated)
```
Code → Docs → Humans read → Humans act
```

Documentation was a support artifact. Coverage meant "did you write help pages for features?"

### The AI-Era Reality
```
Code → Ontology (Surface + Semantic + Procedural) → Published as Docs
                                                  → Exposed via MCP/embeddings
                                                  ↓
                            Humans read + Agents query → Both act
```

Documentation is now the **canonical map of the enterprise's functional surface**—the "kinetic layer" that defines:
- What objects exist (nouns/entities)
- What can be done with them (verbs/operations)  
- What things mean (concepts/definitions)
- What constraints govern interactions (permissions, prerequisites, limits)

**Documentation reliability = degree of synchronization between code reality and documented understanding.**

A documentation gap isn't missing content—it's a **broken link in an agent's reasoning chain**.

---

## Mental Model: The Kinetic Documentation Ontology

### Core Principle: Dual-Reader Mandate

Every documentation artifact must serve two distinct consumption patterns:

| Dimension | Human Reader | Agentic Reader |
|-----------|--------------|----------------|
| **Goal** | Understand "why" and "how" | Build context window for execution |
| **Navigation** | Information architecture, search | MCP queries, embeddings, llms.txt |
| **Success metric** | Can complete task after reading | Can plan and execute programmatically |
| **Failure mode** | Confusion, support ticket | Hallucination, failed execution |

### The Four Layers (Evolved from v2)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PRODUCT REALITY (code, APIs, behaviors, constraints)                       │
└─────────────────────────────────────────────────────────────────────────────┘
                              ↓ scanned into
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: SURFACE GRAPH (immutable scan of code)                            │
│  • Nouns: entities the product operates on                                  │
│  • Verbs: operations that can be performed                                  │
│  • Concepts: ideas needed to understand the product                         │
│  • Constraints: permissions, rate limits, prerequisites [NEW]               │
│  • Edges: operates_on, part_of, related_to, prerequisite, constrained_by    │
└─────────────────────────────────────────────────────────────────────────────┘
                              ↓ organized into
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: ITM (Intended Topic Manifest)                                     │
│  The PLAN: Topics that SHOULD exist                                         │
│  • Auto-generated from Surface Graph                                        │
│  • Human-curated for priority and organization                              │
│  • Type-first hierarchy: Reference > Concept > Task > Onboarding            │
└─────────────────────────────────────────────────────────────────────────────┘
                              ↓ compared against
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: ATM (Actual Topic Manifest)                                       │
│  The REALITY: Topics that DO exist in documentation                         │
│  • Discovered via parsing + semantic matching                               │
│  • Quality assessed per topic                                               │
│  • Linked to Surface Graph elements                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                              ↓ produces
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4: RELIABILITY REPORT (evolved from Gap Report)                      │
│  • Coverage gaps: missing topics                                            │
│  • Accuracy gaps: documented ≠ actual behavior                              │
│  • Constraint gaps: undocumented permissions/prerequisites [NEW]            │
│  • Agent navigability score: can an agent succeed? [NEW]                    │
│  • Sprint plan: prioritized actions                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture Changes from v2

### 1. Enhanced Surface Graph

The Surface Graph becomes a true lightweight ontology, not just a verb→noun connection forest.

#### New Node Types and Extraction

| Node Type | Description | Extraction Method |
|-----------|-------------|-------------------|
| `verb` | API endpoints, operations | AST scanning (existing) |
| `noun` | Entities operated on | Path analysis + code analysis (existing, enhanced) |
| `concept` | Ideas/definitions needed for understanding | **NEW**: Docstring mining, README parsing, LLM clustering |
| `constraint` | Permissions, rate limits, prerequisites | **NEW**: Decorator extraction, code analysis |

#### New Edge Types and Detection

| Edge Type | Relationship | Detection Method |
|-----------|--------------|------------------|
| `operates_on` | verb → noun | Existing |
| `part_of` | noun → noun | **NEW**: Nested path detection (`/users/{id}/projects` → project part_of user) |
| `related_to` | any → any | **NEW**: Co-occurrence analysis, LLM inference |
| `prerequisite` | concept → concept, verb → verb | **NEW**: Auth patterns, dependency analysis |
| `constrained_by` | verb → constraint | **NEW**: Decorator extraction |

#### Constraint Extraction (New)

Extract from FastAPI decorators and code patterns:

```python
# Rate limits
@limiter.limit("100/hour")

# Authentication requirements  
@requires_auth
@Depends(get_current_user)

# Required fields (from Pydantic models)
class UserCreate(BaseModel):
    email: str  # required
    name: str   # required
    bio: Optional[str] = None  # optional

# Response codes and error conditions
raise HTTPException(status_code=403, detail="Not authorized")
```

**Graceful degradation**: Start with decorator-based extraction (fast, reliable). Add deeper code analysis as optional enhancement. Allow cost/permission limits on LLM-assisted extraction.

### 2. Concept Extraction

Two-track approach, tested for quality/cost tradeoff:

**Track A: Deterministic**
- Regex patterns for explicit definitions: "X is...", "We define X as...", "X refers to..."
- Glossary section detection in markdown
- Docstring mining for class/function descriptions
- README section headers as concept indicators

**Track B: LLM-Assisted**
- Cluster related terms across documentation
- Infer concept hierarchy from usage patterns
- Generate concept definitions from code context
- Identify missing concept coverage

**Decision criteria**: Use deterministic for core extraction, LLM for gap identification and enhancement suggestions.

### 3. Persistent Ontology Storage

**Current state**: Surface Graph rebuilt on each scan; only TopicManifest stored.

**v3 change**: Persist the full ontology structure.

```sql
-- New tables for graph persistence
CREATE TABLE surface_nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,  -- verb, noun, concept, constraint
    name TEXT NOT NULL,
    description TEXT,
    node_class TEXT DEFAULT 'user-facing',
    source_file TEXT,
    source_line INTEGER,
    http_method TEXT,
    http_path TEXT,
    metadata JSON,
    scan_id TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE surface_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,  -- operates_on, part_of, related_to, prerequisite, constrained_by
    confidence TEXT DEFAULT 'medium',
    scan_id TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES surface_nodes(id),
    FOREIGN KEY (target_id) REFERENCES surface_nodes(id)
);

CREATE TABLE scans (
    id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    scanned_at TEXT NOT NULL,
    source_paths JSON,
    node_count INTEGER,
    edge_count INTEGER,
    metadata JSON
);
```

**Benefits**:
- Ontology diffing: "3 new entities, 2 renamed, 1 deprecated since last scan"
- Trend analysis: How is the API surface evolving?
- Drift detection: Alert when code changes without doc changes

### 4. Enhanced Quality Assessment

Expand ATM quality scoring to include constraint coverage:

```python
class TopicQuality(BaseModel):
    # Technical completeness (existing)
    has_parameters: Literal["yes", "partial", "no"] = "no"
    has_returns: Literal["yes", "partial", "no"] = "no"
    has_errors: Literal["yes", "partial", "no"] = "no"
    has_warnings: bool = False
    
    # Semantic completeness (existing)
    has_description: bool = False
    has_use_cases: bool = False
    has_examples: bool = False
    
    # Constraint coverage (NEW)
    has_auth_requirements: Literal["yes", "partial", "no"] = "no"
    has_rate_limits: Literal["yes", "partial", "no"] = "no"
    has_prerequisites: Literal["yes", "partial", "no"] = "no"
    has_required_fields: Literal["yes", "partial", "no"] = "no"
    
    # Agent navigability (NEW)
    has_machine_readable_spec: bool = False  # OpenAPI, JSON schema, etc.
    terminology_consistent: bool = False
    
    # Overall scores
    coverage_score: float = 0.0
    constraint_score: float = 0.0  # NEW
    agent_readiness_score: float = 0.0  # NEW
```

### 5. Agent-Oriented Outputs

New export formats for agent consumption:

#### MCP Resource Definitions
```python
def export_mcp_resources(surface: SurfaceGraph) -> dict:
    """Generate MCP server resource definitions from Surface Graph."""
    resources = []
    for noun in surface.nouns:
        resources.append({
            "uri": f"doczot://{surface.product_name}/{noun.name}",
            "name": noun.name,
            "description": noun.description,
            "mimeType": "text/plain"
        })
    # ... tools from verbs, prompts from how-tos
    return {"resources": resources, "tools": tools, "prompts": prompts}
```

#### llms.txt Generation
```python
def export_llms_txt(surface: SurfaceGraph, itm: TopicManifest) -> str:
    """Generate llms.txt for AI crawler consumption."""
    lines = [
        f"# {surface.product_name}",
        "",
        "## Capabilities",
        # List verbs grouped by noun
        "",
        "## Concepts", 
        # List concept definitions
        "",
        "## Constraints",
        # List auth requirements, rate limits, etc.
    ]
    return "\n".join(lines)
```

#### Structured Ontology Export (JSON-LD)
```python
def export_jsonld(surface: SurfaceGraph) -> dict:
    """Export ontology in JSON-LD format for semantic web compatibility."""
    return {
        "@context": "https://schema.org/",
        "@type": "SoftwareApplication",
        "name": surface.product_name,
        "potentialAction": [verb_to_action(v) for v in surface.verbs],
        # ...
    }
```

---

## Implementation Roadmap

### Phase 1: Strengthen the Core (Weeks 1-4)

**Goal**: Make the Surface Graph a true ontology with persistence and richer relationships.

| Task | Priority | Complexity | Notes |
|------|----------|------------|-------|
| Persist Surface Graph in SQLite | High | Medium | New tables, migration from rebuild-each-time |
| Implement `part_of` edge detection | High | Low | Nested path patterns |
| Implement `prerequisite` edge detection | High | Medium | Auth decorator patterns |
| Add constraint node extraction | High | Medium | Decorators: `@requires_auth`, `@limiter`, etc. |
| Concept extraction (deterministic) | Medium | Medium | Docstring/README mining |
| Implement ontology diffing | Medium | Medium | Compare scans, report changes |

### Phase 2: Enhanced Quality Assessment (Weeks 5-8)

**Goal**: ATM quality scoring includes constraint coverage and agent readiness.

| Task | Priority | Complexity | Notes |
|------|----------|------------|-------|
| Expand TopicQuality model | High | Low | Add constraint and agent fields |
| Constraint coverage detection in docs | High | Medium | Does doc mention auth? Rate limits? |
| Terminology consistency checking | Medium | Medium | Are noun names used consistently? |
| Machine-readable spec detection | Medium | Low | Presence of OpenAPI, JSON schema |

### Phase 3: Agent-Oriented Outputs (Weeks 9-12)

**Goal**: DocZot produces outputs that agents can directly consume.

| Task | Priority | Complexity | Notes |
|------|----------|------------|-------|
| MCP resource definition export | High | Medium | Generate from Surface Graph |
| llms.txt generation | High | Low | Token-efficient summary |
| JSON-LD ontology export | Medium | Medium | For semantic web compatibility |
| Embeddings export with ontology alignment | Medium | High | Chunking strategy matters |

### Phase 4: Reliability Testing (Weeks 13-16)

**Goal**: Generate test specifications for agent task completion.

| Task | Priority | Complexity | Notes |
|------|----------|------------|-------|
| Test spec generation for how-tos | High | Medium | Output pytest/similar specs |
| Drift detection alerts | High | Medium | Code changed, docs didn't |
| Constraint validation specs | Medium | Medium | Do doc constraints match code? |

### Phase 5: Feedback Loops (Ongoing)

**Goal**: Close the loop between failures and gap detection.

| Task | Priority | Complexity | Notes |
|------|----------|------------|-------|
| CI integration (PR gate) | High | Medium | Coverage threshold checks |
| Failure → gap suggestion | Medium | High | Parse agent failures, suggest doc gaps |
| Query clustering integration | Medium | High | What are people asking that docs don't answer? |

---

## Quality/Cost Tradeoffs

### Extraction Depth vs. Performance

| Level | What's Extracted | Performance | Accuracy |
|-------|------------------|-------------|----------|
| **Fast** | AST verbs, path nouns, decorators | ~1s per file | High for explicit patterns |
| **Standard** | + Docstring concepts, nested paths | ~5s per file | Good |
| **Deep** | + LLM-assisted concepts, inferred relationships | ~30s per file + API cost | Best, but expensive |

**Recommendation**: Default to Standard; Deep as opt-in with cost warnings.

### Concept Extraction Approach

| Approach | Pros | Cons | Use When |
|----------|------|------|----------|
| Deterministic | Fast, predictable, no cost | Misses implicit concepts | Always (baseline) |
| LLM-assisted | Catches nuance, clusters well | Slow, costs money, may hallucinate | Gap identification, enrichment |

**Recommendation**: Deterministic for core; LLM for "suggest missing concepts" feature.

---

## Success Metrics

### For DocZot as a Product

| Metric | Target | Measurement |
|--------|--------|-------------|
| Surface Graph completeness | >95% of endpoints captured | Manual audit on test repos |
| Edge accuracy | >90% edges are semantically correct | Sampling + human review |
| ATM matching precision | >85% doc-to-surface matches are correct | Golden dataset evaluation |
| Quality score correlation | Scores predict agent success | Agent testing correlation |

### For Users of DocZot

| Metric | What It Measures |
|--------|------------------|
| Coverage % | Topics published / topics in ITM |
| Constraint coverage % | Constraints documented / constraints in code |
| Agent readiness score | Composite of machine-readable, consistent terminology, constraint docs |
| Drift alerts | Code changes without doc changes |

---

## Open Questions

1. **Framework expansion**: Should v3 support frameworks beyond FastAPI? (Flask, Django, Express, etc.)

2. **Multi-language support**: Python-only for now, but TypeScript/Go SDKs are common. Scope creep or necessary?

3. **Enterprise features**: Multi-repo scanning, cross-product ontology linking—defer to v4?

4. **Pricing model implications**: Deep extraction costs money. How does this affect open-source vs. commercial?

---

## Appendix: Terminology

| Term | Definition |
|------|------------|
| **Surface Graph** | Immutable snapshot of all documentable elements in code: nouns, verbs, concepts, constraints, and their relationships |
| **ITM** | Intended Topic Manifest—the plan for what documentation SHOULD exist |
| **ATM** | Actual Topic Manifest—what documentation DOES exist, discovered from parsing |
| **Reliability Report** | The gap between ITM and ATM, plus quality scores and sprint plan |
| **Kinetic Layer** | The actions and permissions connecting objects (Palantir terminology) |
| **Intelition** | Human-AI co-production of reasoning and action (Mulconrey terminology) |
| **Dual-Reader Mandate** | Requirement that docs serve both human and agentic consumption |

---

## References

- Mulconrey, B. (2025). "AI is evolving faster than our vocabulary for describing it."
- Karp, A. (2025). Palantir shareholder letter on ontology and AI.
- LeCun, Y. (2022). "A Path Towards Autonomous Machine Intelligence."
- Rosner, S. (2025). "Documentation Operations in the AI Era."
