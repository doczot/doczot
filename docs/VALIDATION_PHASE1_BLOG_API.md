# DocZot Validation: Phase 1 - Smoke Test

**Repository:** mehmetext/fastapi-blog-api
**Classification:** Micro / Smoke Test
**Date:** 2026-01-20

## Executive Summary

Phase 1 smoke test reveals **fundamental issues** in both Surface Graph extraction and ATM discovery that need to be addressed before validating on more complex repositories.

| Layer | Grade | Key Finding |
|-------|-------|-------------|
| Surface Graph | C+ | False positive nouns, missing descriptions |
| ITM | B | Mechanical but functional |
| ATM | D | Fails to parse README structure |
| Gap Analysis | C | Misleading coverage % |

---

## 1. Test Repository Profile

```
fastapi-blog-api/
├── app/
│   ├── controllers/blog.py    # Business logic
│   ├── models/post.py         # Post entity
│   ├── routers/blog.py        # 6 endpoints
│   └── main.py                # App entry
├── alembic/                   # Migrations
└── README.md                  # 133 lines, 7 sections
```

**Expected Surface:**
- 6 endpoints (CRUD + seed)
- 1 entity (Post/Blog)
- Well-documented README with explicit endpoint list

---

## 2. Surface Graph Analysis

### 2.1 Verbs (Endpoints) ✅

| Endpoint | Detected | Correct |
|----------|----------|---------|
| GET /blog/seed | ✅ | ✅ |
| GET /blog/ | ✅ | ✅ |
| GET /blog/{id} | ✅ | ✅ |
| POST /blog/ | ✅ | ✅ |
| PUT /blog/{id} | ✅ | ✅ |
| DELETE /blog/{id} | ✅ | ✅ |

**Verdict:** All 6 endpoints correctly detected.

### 2.2 Nouns (Entities) ⚠️

| Noun | Source | Verdict |
|------|--------|---------|
| `post` | Model name | ✅ Correct |
| `blog` | URL path `/blog/` | ⚠️ Duplicate of `post` |
| `all` | Function name `get_all_posts` | ❌ False positive |

**Issues:**
1. **False positive "all"**: Extracted from function name pattern `get_all_*`. Words like "all", "single", "new" should be filtered.
2. **Duplicate entities**: "blog" (from URL) and "post" (from model) refer to the same domain entity. Should be merged.

### 2.3 Concepts ✅

7 concepts correctly extracted from README sections:
- overview, tech stack, project structure, getting started
- api endpoints, database migrations, development

### 2.4 Missing Data ❌

**Verb descriptions are null** despite the code containing:
```python
@router.get(
    "/",
    summary="Get all blog posts",  # ← Not extracted
    description="Retrieve a list of all blog posts...",  # ← Not extracted
)
```

**Recommendation:** Parse FastAPI decorator kwargs for `summary` and `description`.

---

## 3. ITM Analysis

### 3.1 Structure

Generated 29 topics with hierarchy:
- Reference (15 topics)
- Concept (12 topics)
- Task (2 topics)

### 3.2 Issues

1. **Duplicate topic names**: "Post" appears as both Entity and Concept
2. **Mechanical naming**: Topics named "Get blog", "Create blog" rather than user-friendly alternatives

---

## 4. ATM Analysis ❌ CRITICAL

### 4.1 Expected vs Actual

**Expected:** README has 7 clear sections (## headers):
1. Overview
2. Features
3. Tech Stack
4. Project Structure
5. Getting Started
6. API Endpoints
7. Database Migrations

**Actual:** Only 1 topic discovered: "Readme"

### 4.2 Root Cause

The ATM discovery treats the entire README as a single document rather than parsing its structure. This is a **critical defect** because:

1. Coverage is artificially inflated (87.5%) when the README merely mentions endpoints
2. Quality gaps cannot be identified per-section
3. The "API Endpoints" section (lines 89-98) explicitly lists all endpoints but isn't recognized as a distinct topic

### 4.3 Recommendation

Implement markdown header parsing in ATM discovery:
```python
# Current: One topic per file
topic = Topic(name="Readme", source_file="README.md")

# Should be: One topic per ## section
topics = [
    Topic(name="Overview", source_file="README.md", source_line=3),
    Topic(name="Features", source_file="README.md", source_line=7),
    Topic(name="API Endpoints", source_file="README.md", source_line=89),
    ...
]
```

---

## 5. Gap Analysis

### 5.1 Reported Metrics

```
Coverage: 87.5%
Complete: 17 topics
Partial: 1 topic
Missing: 2 topics (All, Post concepts)
```

### 5.2 Reality Check

The 87.5% coverage is **misleading** because:
1. It counts the entire README as covering all mentioned endpoints
2. The README's "API Endpoints" section only provides a one-line description per endpoint
3. No parameter docs, no error docs, no examples for individual endpoints

**True coverage** if ATM properly parsed sections:
- API reference: ~30% (one-liners only)
- Concept coverage: ~60% (basic explanations)
- Task coverage: ~20% (no step-by-step guides)

---

## 6. Bugs Discovered

### Bug 1: False Positive Noun Extraction
**Severity:** Medium
**Location:** `scanner.py` noun extraction
**Description:** Function names like `get_all_posts` produce false noun "all"
**Fix:** Add stop-word filter for common words

### Bug 2: Missing Verb Descriptions
**Severity:** Medium
**Location:** `scanner.py` endpoint parsing
**Description:** FastAPI decorator kwargs `summary` and `description` not extracted
**Fix:** Parse decorator arguments

### Bug 3: ATM Single-Topic Per File
**Severity:** High
**Location:** `analyzer_v2.py` ATM discovery
**Description:** README sections not parsed as individual topics
**Fix:** Implement markdown header parsing

### Bug 4: Duplicate Entity Detection
**Severity:** Low
**Location:** `scanner.py` noun detection
**Description:** "blog" (URL) and "post" (model) not merged
**Fix:** Add entity aliasing/merging logic

---

## 7. Validation Verdict

**Phase 1 Status: BLOCKED**

The smoke test reveals issues that will compound in more complex repositories. Before proceeding to Phase 2 (Gold Standard), the following must be addressed:

### P0 (Must Fix)
- [ ] ATM should parse markdown sections as individual topics

### P1 (Should Fix)
- [ ] Filter false positive nouns (all, single, new, etc.)
- [ ] Extract verb descriptions from FastAPI decorators

### P2 (Nice to Have)
- [ ] Merge duplicate entities (blog ≈ post)
- [ ] Improve topic naming for ITM

---

## 8. Golden Reference

For regression testing, here is the expected output for this repository:

### Expected Surface Graph
```json
{
  "verbs": 6,
  "nouns": 1,  // Only "post" (or "blog" as alias)
  "concepts": 7,
  "constraints": 0
}
```

### Expected ATM Topics
```
- Overview (covers: concept:overview)
- Features (covers: concept:crud, concept:search)
- API Endpoints (covers: all 6 verbs)
- Database Migrations (covers: concept:database migrations)
- Development (covers: concept:development)
```

### Expected Coverage
- Per-section granularity
- "API Endpoints" section covers verb:* nodes
- Other sections cover concept:* nodes
