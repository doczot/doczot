# Changes Summary: Tasks #1 and #2

**Date**: 2026-01-07
**Status**: ✅ Complete and Ready for Review

---

## Task #1: Router-Level Dependency Detection

### Problem
full-stack-fastapi-template uses a constraint pattern we didn't support:
```python
@router.get("/", dependencies=[Depends(get_current_active_superuser)])
def endpoint(): pass
```

Result: **0 constraints detected** on full-stack-fastapi-template ❌

### Solution
Extended `_extract_constraints()` in `scanner.py` to check decorator kwargs for `dependencies` parameter.

### Impact
**Before**:
- Constraints detected: 0
- Edges: 23

**After**:
- Constraints detected: **6** ✅
- Edges: **35** ✅ (added 12 `constrained_by` edges)

### Files Changed
- `doczot_analyzer/scanner.py` (lines 434-449)
- `doczot_analyzer/storage.py` (lines 87-99) - Fixed database schema

### Test Results
```
✅ Detects: @router.get("/", dependencies=[Depends(...)])
✅ Extracts dependency name: get_current_active_superuser
✅ Creates constraint nodes
✅ Creates constrained_by edges
```

---

## Task #2: Yargs CLI Scanner

### Problem
Doc Detective uses yargs (not oclif). Initial scan result:
- Commands detected: **0** ❌
- Concepts: **0** ❌

### Solution
Implemented `scan_yargs_commands()` in `scanner_nodejs.py`:
- Parses JavaScript/TypeScript files
- Extracts `.option()` calls using regex
- Groups options under main command

### Impact
**Before**:
- Commands: 0
- Flags: 0

**After**:
- Commands: **1** (doc-detective) ✅
- Flags: **5** (config, input, output, logLevel, allow-unsafe) ✅

### Files Changed
- `doczot_analyzer/scanner_nodejs.py` (lines 113-201)

### Test Results
```
✅ Detects yargs framework in package.json
✅ Parses .option() calls in utils.js
✅ Extracts flag names and descriptions
✅ Groups flags under main command
```

---

## Bonus: Database Schema Fix

### Problem
When saving second scan: `UNIQUE constraint failed: surface_nodes.id`

### Solution
Changed primary key from `id` to composite `(scan_id, id)`.

### Impact
**Before**:
- Could only save one scan per product ❌

**After**:
- Can save unlimited scans ✅
- Can compare any two scans ✅
- Historical tracking enabled ✅

### Files Changed
- `doczot_analyzer/storage.py` (line 98)

---

## Summary Stats

### full-stack-fastapi-template
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Endpoints | 23 | 23 | - |
| Constraints | **0** | **6** | +6 ✅ |
| Edges | 23 | **35** | +12 ✅ |
| Concepts | 15 | 15 | - |

### Doc Detective
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Commands | **0** | **1** | +1 ✅ |
| Flags | **0** | **5** | +5 ✅ |
| Concepts | 0 | 0 | - |

### Code Quality
| Metric | Status |
|--------|--------|
| Unit tests | 23/23 passing ✅ |
| Integration tests | 2/2 passing ✅ |
| Database schema | Fixed ✅ |
| Multi-scan support | Working ✅ |

---

## What's Now Possible

### 1. **Better FastAPI Audits**
DocZot now detects auth constraints on 26% of full-stack endpoints (6 out of 23). This gives you:
- Which endpoints require authentication
- What dependency function enforces auth
- Automatic edge detection (verb → constraint)

### 2. **Node.js CLI Analysis**
DocZot can now analyze CLI tools like Doc Detective:
- Extract command names
- Parse flag definitions
- Map CLI surface area

### 3. **API Evolution Tracking**
With fixed database schema:
- Save unlimited scans over time
- Compare any two versions
- Track constraint additions/removals
- Detect breaking changes

---

## Next Step: Your Review

See `QUALITY_ASSESSMENT_GUIDE.md` for detailed review instructions.

**Key files to review**:
- `full-stack-visualization.html` - Interactive graph
- `full-stack/surface.json` - Complete data export
- `doc-detective-visualization.html` - CLI analysis

**What to validate**:
1. Are the 6 constrained endpoints correct?
2. Are there false positives/negatives?
3. Does the CLI analysis match actual behavior?
4. Are visualizations helpful?

**When ready**: Let me know your assessment and we'll proceed to Phase 2!
