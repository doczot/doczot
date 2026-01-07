# CLI Visualization Fix

**Issue Reported**: Doc Detective visualization only showed 1 node
**Root Cause**: CLI flags were stored as metadata but not converted to graph nodes
**Fixed**: 2026-01-07

---

## Before Fix

```
Nodes: 1 (just the command)
Edges: 0
Visualization: Empty/boring
```

**Problem**: Flags like `--config`, `--input`, etc. were extracted but invisible in the graph.

---

## After Fix

```
Nodes: 6
  - 1 verb: doc-detective (the command)
  - 5 nouns: config, input, output, logLevel, allow-unsafe (the flags)
Edges: 5 (command → each flag)
Visualization: Much more informative!
```

**Solution**: Enhanced `build_surface_graph_nodejs()` to:
1. Create noun nodes for each CLI flag/option
2. Create edges connecting command to flags
3. Store flag descriptions on nodes

---

## Updated Files

**Before**:
- `doc-detective-visualization.html` (1 node - not useful)
- `doc-detective/` (JSON exports)

**After**:
- `doc-detective-visualization-FIXED.html` (6 nodes - useful!) ✅
- `doc-detective-FIXED/` (updated JSON exports) ✅

---

## How to Review

1. **Open the new visualization**:
   ```bash
   open quality-assessment/doc-detective-visualization-FIXED.html
   ```

2. **You should see**:
   - Central node: `doc-detective` (the command)
   - 5 surrounding nodes: `config`, `input`, `output`, `logLevel`, `allow-unsafe`
   - 5 edges connecting command to flags

3. **Hover over nodes** to see flag descriptions

---

## What This Means for CLI Analysis

**Now you can**:
- Visualize CLI surface area
- See all command flags at a glance
- Track flag documentation coverage
- Compare CLI versions (flag additions/removals)

**Example use case**:
- "Did we document all 5 flags?"
- Currently: 1 out of 6 surface elements documented (26.3% coverage)
- Shows which flags lack documentation

---

## Code Changes

**File**: `doczot_analyzer/analyzer_v2.py`
**Function**: `build_surface_graph_nodejs()` (lines 141-165)

**Added**:
```python
# Create noun nodes for each flag/option
for flag in cmd.flags:
    flag_node = SurfaceNode(
        id=f"noun:flag:{flag_name}",
        type=NodeType.NOUN,
        name=flag_name,
        description=flag.get('description'),
    )
    nodes.append(flag_node)

    # Create edge: command operates_on flag
    edge = SurfaceEdge(
        source_id=verb_node.id,
        target_id=flag_node.id,
        edge_type=EdgeType.OPERATES_ON,
    )
    edges.append(edge)
```

---

## Impact

- **Doc Detective**: Now shows meaningful graph (6 nodes vs 1)
- **All yargs CLIs**: Will benefit from improved visualization
- **CLI Documentation**: Can now track flag coverage like API endpoint coverage

---

**Review the new visualization** and let me know if this is better!
