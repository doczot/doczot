# DocZot v3 Implementation Guide for Claude Code

This document provides instructions for implementing the DocZot v3 architecture as defined in `docs/DESIGN_V3.md`. When working on DocZot, Claude Code should follow these guidelines.

---

## Project Context

DocZot is a documentation coverage analysis tool that treats documentation as **enterprise ontology capture**. It measures how completely and accurately documentation captures the nouns, verbs, concepts, and constraints that both humans and AI agents need to reason and act.

**Core philosophy**: A documentation gap isn't missing content—it's a broken link in an agent's reasoning chain.

---

## Architecture Overview

```
doczot/
├── doczot_analyzer/           # Core analysis engine
│   ├── models_v2.py           # Pydantic models (Surface Graph, ITM, ATM, etc.)
│   ├── scanner.py             # FastAPI endpoint + entity detection (AST-based)
│   ├── analyzer_v2.py         # Surface graph builder, ATM discovery
│   ├── docs_parser.py         # Markdown documentation parser
│   ├── vector_store.py        # Semantic search for doc matching
│   ├── matcher.py             # Endpoint-to-doc matching
│   ├── storage.py             # SQLite persistence for manifests
│   ├── manifest.py            # TopicManifest operations
│   └── cli_v2.py              # CLI and HTML visualizer
├── docs/
│   ├── PRODUCT_OVERVIEW.md    # Current product & architecture (comprehensive)
│   ├── DESIGN_V3.md           # Vision for v3 architecture
│   ├── LEARNINGS.md           # Design evolution from real-world testing
│   └── features/              # Feature specifications
└── scripts/                   # Development and debug scripts
```

---

## Implementation Priorities

When working on DocZot, prioritize in this order:

### Phase 1: Core Ontology (Current Focus)

1. **Persist Surface Graph** - Store nodes and edges in SQLite, not just manifests
2. **Add `part_of` edges** - Detect from nested URL paths
3. **Add `prerequisite` edges** - Detect from auth decorator patterns
4. **Add constraint extraction** - Rate limits, auth requirements from decorators
5. **Concept extraction (deterministic)** - Mine docstrings and README files

### Phase 2: Quality Assessment

1. Expand `TopicQuality` model with constraint and agent-readiness fields
2. Detect constraint coverage in documentation
3. Check terminology consistency across docs

### Phase 3: Agent Outputs

1. MCP resource definition export
2. llms.txt generation
3. JSON-LD ontology export

---

## Code Patterns and Guidelines

### Adding New Node Types

When adding a new node type (e.g., `constraint`):

1. Add to `NodeType` enum in `models_v2.py`:
```python
class NodeType(str, Enum):
    NOUN = "noun"
    VERB = "verb"
    CONCEPT = "concept"
    CONSTRAINT = "constraint"  # NEW
```

2. Create extraction function in `scanner.py`:
```python
def extract_constraints(func_node: ast.FunctionDef) -> list[dict]:
    """Extract constraint information from decorators and code."""
    constraints = []
    for decorator in func_node.decorator_list:
        # Check for rate limit decorators
        if _is_rate_limit_decorator(decorator):
            constraints.append({
                "type": "rate_limit",
                "value": _extract_rate_limit_value(decorator)
            })
        # Check for auth decorators
        if _is_auth_decorator(decorator):
            constraints.append({
                "type": "auth_required",
                "value": _extract_auth_type(decorator)
            })
    return constraints
```

3. Create constraint nodes in `build_surface_graph()` in `analyzer_v2.py`:
```python
for constraint in ep.constraints:
    constraint_id = f"constraint:{constraint['type']}:{verb_node.id}"
    constraint_node = SurfaceNode(
        id=constraint_id,
        type=NodeType.CONSTRAINT,
        name=f"{constraint['type']}: {constraint['value']}",
    )
    nodes.append(constraint_node)
    
    # Create constrained_by edge
    edge = SurfaceEdge(
        source_id=verb_node.id,
        target_id=constraint_id,
        edge_type=EdgeType.CONSTRAINED_BY,
    )
    edges.append(edge)
```

### Adding New Edge Types

When adding a new edge type (e.g., `part_of`):

1. Add to `EdgeType` enum in `models_v2.py`:
```python
class EdgeType(str, Enum):
    OPERATES_ON = "operates_on"
    PART_OF = "part_of"  # NEW
    RELATED_TO = "related_to"
    PREREQUISITE = "prerequisite"
    CONSTRAINED_BY = "constrained_by"  # NEW
```

2. Add detection logic in `analyzer_v2.py`:
```python
def detect_part_of_relationships(path: str, nouns: list[str]) -> list[tuple[str, str]]:
    """Detect part_of relationships from nested URL paths.
    
    Example: /users/{id}/projects → project part_of user
    """
    relationships = []
    segments = [s for s in path.split('/') if s and not s.startswith('{')]
    
    for i in range(len(segments) - 1):
        parent_candidate = singularize(segments[i])
        child_candidate = singularize(segments[i + 1])
        
        if parent_candidate in nouns and child_candidate in nouns:
            relationships.append((child_candidate, parent_candidate))
    
    return relationships
```

### Concept Extraction Pattern

Use a two-track approach:

```python
def extract_concepts_deterministic(content: str) -> list[dict]:
    """Extract concepts using regex patterns (fast, reliable)."""
    concepts = []
    
    # Pattern: "X is..." or "X refers to..."
    definition_patterns = [
        r'(?:^|\n)#+\s*(.+?)\n+(.+?(?:is|refers to|means|describes).+?)(?:\n|$)',
        r'(?:^|\n)\*\*(.+?)\*\*[:\s]+(.+?)(?:\n|$)',
    ]
    
    for pattern in definition_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for term, definition in matches:
            concepts.append({
                "name": term.strip(),
                "definition": definition.strip(),
                "source": "deterministic",
            })
    
    return concepts


def extract_concepts_llm(content: str, existing_concepts: list[dict]) -> list[dict]:
    """Use LLM to identify additional concepts (expensive, thorough).
    
    Only call this when:
    1. User explicitly requests deep analysis
    2. Cost/permission budget allows
    """
    # Implementation uses external LLM API
    # Should include rate limiting and cost tracking
    pass
```

### Persistence Pattern

When persisting Surface Graph to SQLite:

```python
def save_surface_graph(self, surface: SurfaceGraph) -> str:
    """Save a surface graph to the database.
    
    Returns the scan_id for reference.
    """
    scan_id = f"{surface.product_name}:{surface.scanned_at.isoformat()}"
    
    with sqlite3.connect(self.db_path) as conn:
        # Save scan metadata
        conn.execute("""
            INSERT INTO scans (id, product_name, scanned_at, source_paths, node_count, edge_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            scan_id,
            surface.product_name,
            surface.scanned_at.isoformat(),
            json.dumps(surface.source_paths),
            len(surface.nodes),
            len(surface.edges),
        ))
        
        # Save nodes
        for node in surface.nodes:
            conn.execute("""
                INSERT INTO surface_nodes (id, type, name, description, node_class, 
                                          source_file, source_line, http_method, http_path, scan_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node.id, node.type.value, node.name, node.description, node.node_class.value,
                node.source_file, node.source_line, node.http_method, node.http_path, scan_id
            ))
        
        # Save edges
        for edge in surface.edges:
            conn.execute("""
                INSERT INTO surface_edges (source_id, target_id, edge_type, confidence, scan_id)
                VALUES (?, ?, ?, ?, ?)
            """, (
                edge.source_id, edge.target_id, edge.edge_type.value, edge.confidence.value, scan_id
            ))
        
        conn.commit()
    
    return scan_id
```

### Ontology Diffing Pattern

```python
def diff_surface_graphs(old: SurfaceGraph, new: SurfaceGraph) -> dict:
    """Compare two surface graphs and report changes."""
    old_node_ids = {n.id for n in old.nodes}
    new_node_ids = {n.id for n in new.nodes}
    
    old_edge_keys = {(e.source_id, e.target_id, e.edge_type) for e in old.edges}
    new_edge_keys = {(e.source_id, e.target_id, e.edge_type) for e in new.edges}
    
    return {
        "nodes_added": list(new_node_ids - old_node_ids),
        "nodes_removed": list(old_node_ids - new_node_ids),
        "nodes_unchanged": list(old_node_ids & new_node_ids),
        "edges_added": list(new_edge_keys - old_edge_keys),
        "edges_removed": list(old_edge_keys - new_edge_keys),
        "summary": {
            "total_added": len(new_node_ids - old_node_ids),
            "total_removed": len(old_node_ids - new_node_ids),
            "total_changed": len(new_node_ids - old_node_ids) + len(old_node_ids - new_node_ids),
        }
    }
```

---

## Testing Guidelines

### Unit Tests

Place tests in `doczot_analyzer/tests/`. Follow existing patterns:

```python
def test_extract_part_of_relationships():
    """Test that nested paths produce part_of edges."""
    path = "/users/{user_id}/projects/{project_id}"
    nouns = ["user", "project"]
    
    relationships = detect_part_of_relationships(path, nouns)
    
    assert ("project", "user") in relationships


def test_constraint_extraction():
    """Test that rate limit decorators are extracted."""
    source = '''
@router.get("/items")
@limiter.limit("100/hour")
async def list_items():
    pass
'''
    endpoints = scan_python_file(source, "test.py")
    
    assert len(endpoints) == 1
    assert any(c["type"] == "rate_limit" for c in endpoints[0].constraints)
```

### Integration Tests

Test against real FastAPI projects:
- `full-stack-fastapi-template` (primary test target)
- Simple test fixtures in `tests/fixtures/`

---

## CLI Commands

When adding new features, extend the CLI in `cli_v2.py`:

```python
@click.command()
@click.argument('repo_path')
@click.option('--format', type=click.Choice(['json', 'text', 'mcp', 'llms']), default='text')
@click.option('--deep', is_flag=True, help='Use LLM-assisted extraction (costs money)')
def export(repo_path: str, format: str, deep: bool):
    """Export ontology in various formats."""
    surface, itm, atm, gap = analyze_repository(repo_path, deep=deep)
    
    if format == 'mcp':
        output = export_mcp_resources(surface)
    elif format == 'llms':
        output = export_llms_txt(surface, itm)
    elif format == 'json':
        output = surface.model_dump_json(indent=2)
    else:
        output = format_text_report(surface, itm, atm, gap)
    
    click.echo(output)
```

---

## Quality/Cost Tradeoffs

### Extraction Levels

```python
class ExtractionLevel(str, Enum):
    FAST = "fast"      # AST only, ~1s per file
    STANDARD = "standard"  # + docstrings, ~5s per file
    DEEP = "deep"      # + LLM, ~30s per file + API cost

def analyze_repository(repo_path: str, level: ExtractionLevel = ExtractionLevel.STANDARD):
    """Run analysis at specified extraction level."""
    if level == ExtractionLevel.DEEP:
        click.echo("Warning: Deep extraction uses LLM API calls and may incur costs.")
        if not click.confirm("Continue?"):
            level = ExtractionLevel.STANDARD
    # ...
```

### Graceful Degradation

When features require unavailable resources:

```python
def extract_concepts(content: str, use_llm: bool = False) -> list[dict]:
    """Extract concepts with graceful degradation."""
    # Always do deterministic extraction
    concepts = extract_concepts_deterministic(content)
    
    # Try LLM if requested and available
    if use_llm:
        try:
            llm_concepts = extract_concepts_llm(content, concepts)
            concepts.extend(llm_concepts)
        except (APIError, RateLimitError, CostLimitError) as e:
            logger.warning(f"LLM extraction failed, using deterministic only: {e}")
    
    return concepts
```

---

## Output Formats

### MCP Resource Definition

```python
def export_mcp_resources(surface: SurfaceGraph) -> dict:
    """Generate MCP server resource definitions."""
    return {
        "resources": [
            {
                "uri": f"doczot://{surface.product_name}/entity/{noun.name}",
                "name": noun.name,
                "description": noun.description or f"The {noun.name} entity",
                "mimeType": "text/plain"
            }
            for noun in surface.nouns
        ],
        "tools": [
            {
                "name": verb.name,
                "description": f"{verb.http_method} {verb.http_path}",
                "inputSchema": {
                    "type": "object",
                    "properties": {}  # Could be populated from Pydantic models
                }
            }
            for verb in surface.verbs
        ]
    }
```

### llms.txt

```python
def export_llms_txt(surface: SurfaceGraph, itm: TopicManifest) -> str:
    """Generate llms.txt for AI crawler consumption."""
    lines = [
        f"# {surface.product_name}",
        "",
        "## What this product does",
        "",
        "## Entities (nouns)",
    ]
    
    for noun in surface.nouns:
        desc = noun.description or f"A {noun.name} in the system"
        lines.append(f"- **{noun.name}**: {desc}")
    
    lines.extend(["", "## Operations (verbs)", ""])
    
    for noun in surface.nouns:
        verbs = surface.verbs_for_noun(noun.id)
        if verbs:
            lines.append(f"### {noun.name}")
            for verb in verbs:
                lines.append(f"- {verb.http_method} {verb.http_path}")
    
    lines.extend(["", "## Constraints", ""])
    
    for node in surface.nodes:
        if node.type == NodeType.CONSTRAINT:
            lines.append(f"- {node.name}")
    
    return "\n".join(lines)
```

---

## Common Pitfalls

1. **Don't rebuild the graph unnecessarily** - Check if a recent scan exists before rescanning
2. **Singularize consistently** - Use the `_singularize()` function from scanner.py
3. **Filter infrastructure types** - Skip Session, HTTPException, Request, etc. (see `skip_types` in scanner.py)
4. **Test on real repos** - The full-stack-fastapi-template is the canonical test case
5. **Preserve v1 compatibility** - The v1 models in `models.py` may still be used by some code paths

---

## Definition of Done

A feature is complete when:

1. Code is implemented following patterns in this document
2. Unit tests pass with >80% coverage on new code
3. Integration test on full-stack-fastapi-template succeeds
4. CLI help text is updated
5. PRODUCT_OVERVIEW.md is updated if architecture changed
6. No regressions in existing tests

---

## Getting Help

- Read `docs/PRODUCT_OVERVIEW.md` for comprehensive product & architecture documentation
- Read `docs/DESIGN_V3.md` for v3 vision and roadmap
- Read `docs/LEARNINGS.md` for past design decisions and their rationale
- Check `scripts/` for debugging and validation utilities
