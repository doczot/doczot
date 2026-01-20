# DocZot Validation: Phase 4 - Stress Test

**Repository:** benavlabs/FastAPI-boilerplate
**Classification:** Modernity Stress Test
**Date:** 2026-01-20

## Executive Summary

Phase 4 stress test shows DocZot handles modern patterns (Pydantic V2, FastCRUD, async) reasonably well, with expected noun extraction issues.

| Layer | Grade | Key Finding |
|-------|-------|-------------|
| Surface Graph | B- | 36 verbs, but noun extraction has many false positives |
| ITM | B | 76 intended topics generated |
| ATM | B+ | 18 topics from MkDocs docs |
| Gap Analysis | B+ | 92.1% coverage |

---

## 1. Test Repository Profile

```
benavlabs/FastAPI-boilerplate/
├── src/app/
│   ├── api/v1/          # Versioned API routes
│   │   ├── users.py     # User CRUD
│   │   ├── posts.py     # Post CRUD
│   │   ├── tasks.py     # Background tasks
│   │   └── tiers.py     # Tier system
│   ├── core/            # FastCRUD generics
│   └── models/          # SQLAlchemy models
├── docs/                # MkDocs documentation
└── mkdocs.yml
```

**Test Focus:**
- Pydantic V2 syntax
- Generic CRUD patterns (FastCRUD)
- Complex tiered rate limiting
- Background job system

---

## 2. Results

### 2.1 Surface Graph

```
Verbs: 36 endpoints
Nouns: 13 entities (many false positives)
Concepts: 4
Constraints: 16 (auth constraints)
```

### 2.2 Noun Analysis ⚠️

| Noun | Verdict | Notes |
|------|---------|-------|
| `user` | ✅ | Core entity |
| `post` | ✅ | Core entity |
| `task` | ✅ | Background task entity |
| `tier` | ✅ | Tier system entity |
| `job` | ⚠️ | Probably valid |
| `db_user` | ❌ | Database model name prefix |
| `db_post` | ❌ | Database model name prefix |
| `multi` | ❌ | False positive |
| `cookie` | ❌ | From cookie auth pattern |
| `rate_limit` | ❌ | This is a constraint, not a noun |
| `ratelimit` | ❌ | Duplicate of above |
| `usertier` | ❌ | Schema name |
| `readycheck` | ❌ | Internal function/schema |

**Pattern:** DocZot extracts database model names (db_*) and internal schemas as nouns.

### 2.3 ATM Discovery ✅

**18 topics discovered** from MkDocs documentation - good coverage of the docs folder structure.

### 2.4 Gap Report

```
Complete: 70 topics
Partial: 5 topics
Missing: 1 topic
Coverage: 92.1%
```

---

## 3. Stress Test Findings

### 3.1 Pydantic V2 Handling ✅

DocZot correctly parses Pydantic V2 models. No crashes or parsing errors.

### 3.2 Generic CRUD (FastCRUD) ⚠️

The scanner detects endpoints but noun extraction shows some confusion:
- `db_user` and `db_post` suggest the scanner is finding database model references
- This is better than not finding entities at all

### 3.3 Constraint Detection ✅

16 auth constraints detected - the scanner handles `Depends()` patterns correctly.

---

## 4. Validation Verdict

**Phase 4 Status: PASS with known issues**

DocZot handles modern patterns without crashing. The noun extraction issues are consistent with previous phases.

---

## 5. Consolidated Bug List

Across all 4 phases, the following issues were identified:

### P0 - Critical
1. **Database save duplicate ID error** - Storage fails on duplicate node IDs

### P1 - High
2. **ATM single-topic per file** - README sections not parsed individually (Phase 1)
3. **False positive nouns** - Common words extracted (all, multi, cookie)
4. **DTO schemas as nouns** - UserLogin, UserEdit, db_user extracted

### P2 - Medium
5. **Missing verb descriptions** - FastAPI summary/description not extracted
6. **Constraint-noun confusion** - rate_limit extracted as noun not constraint

### P3 - Low
7. **Non-doc files in ATM** - CODE_OF_CONDUCT.md included
8. **Duplicate entities** - blog/post, key/apikey not merged
