# DocZot Validation: Phase 2 - Gold Standard

**Repository:** seapagan/fastapi-template
**Classification:** Gold Standard Control
**Date:** 2026-01-20

## Executive Summary

Phase 2 validation on a well-documented MkDocs project shows **significant improvement** over Phase 1. The ATM correctly discovers multiple documentation files and the constraint detection is working well.

| Layer | Grade | Key Finding |
|-------|-------|-------------|
| Surface Graph | B | 27 verbs, 28 constraints detected; noun extraction has false positives |
| ITM | B+ | 105 topics generated with good hierarchy |
| ATM | B | 13 topics from MkDocs structure (vs 1 in Phase 1) |
| Gap Analysis | B+ | 93% coverage with meaningful per-topic quality scores |

---

## 1. Test Repository Profile

```
seapagan/fastapi-template/
├── app/
│   ├── resources/          # 6 router files
│   │   ├── auth.py         # login, register, verify, etc.
│   │   ├── user.py         # user CRUD
│   │   ├── api_key.py      # API key management
│   │   ├── heartbeat.py    # health check
│   │   └── home.py         # root endpoint
│   ├── models/             # User, APIKey entities
│   └── managers/           # Business logic
├── docs/                   # MkDocs documentation
│   ├── index.md
│   ├── quick-start.md
│   ├── important.md
│   ├── troubleshooting.md
│   ├── usage/              # 5+ files
│   ├── reference/
│   │   └── api.md          # API reference
│   └── customization/
└── mkdocs.yml              # MkDocs configuration
```

**Expected Surface:**
- ~25-30 endpoints (auth, user management, API keys)
- 2-3 core entities (User, APIKey)
- Comprehensive MkDocs documentation with API reference

---

## 2. Surface Graph Analysis

### 2.1 Verbs (Endpoints) ✅

**Detected: 27 endpoints**

Sample endpoints correctly identified:
| Endpoint | Status |
|----------|--------|
| POST /register/ | ✅ |
| POST /login/ | ✅ |
| POST /refresh/ | ✅ |
| GET /verify/ | ✅ |
| GET /users/me | ✅ |
| PUT /users/{user_id} | ✅ |
| POST /users/keys/ | ✅ |
| DELETE /users/keys/{key_id} | ✅ |

### 2.2 Constraints ✅ EXCELLENT

**Detected: 28 constraints**

This is a major improvement - DocZot correctly detects auth constraints from `Depends(get_current_user)` patterns:

```
constraint:auth_required:verb:GET:/users/me
constraint:auth_required:verb:PUT:/users/{user_id}
constraint:auth_required:verb:POST:/users/{user_id}/make-admin
constraint:auth_required:verb:POST:/users/{user_id}/ban
constraint:auth_required:verb:DELETE:/users/{user_id}
... etc
```

### 2.3 Nouns (Entities) ⚠️

**Detected: 8 nouns (Expected: 2-3)**

| Noun | Source | Verdict |
|------|--------|---------|
| `user` | Model name | ✅ Correct |
| `apikey` | Model name | ✅ Correct |
| `key` | URL path `/keys/` | ⚠️ Should merge with `apikey` |
| `userlogin` | Pydantic schema | ❌ False positive |
| `useredit` | Pydantic schema | ❌ False positive |
| `myuser` | Pydantic schema | ❌ False positive |
| `context` | Unknown | ❌ False positive |
| `root` | "/" endpoint | ⚠️ Questionable |

**Issue:** Pydantic schema names (UserLogin, UserEdit, MyUser) are being extracted as nouns. These are DTOs, not domain entities.

**Recommendation:** Filter nouns that end with common DTO suffixes: `Login`, `Create`, `Update`, `Edit`, `Read`, `Response`, `Request`.

### 2.4 Concepts ✅

**Detected: 25 concepts** from README headers and documentation.

Sample concepts:
- `login`, `refresh`, `register`, `verify` (auth flow)
- `admin`, `search`, `token` (user management)
- `docker`, `testing` (infrastructure)

---

## 3. ITM Analysis

### 3.1 Structure ✅

**Generated: 105 topics**
- Reference: 62 topics
- Concept: 35 topics
- Task: 8 topics

The ITM correctly generates a comprehensive topic hierarchy from the surface graph.

---

## 4. ATM Analysis ✅ IMPROVED

### 4.1 Topics Discovered

**13 topics** (vs 1 in Phase 1) - significant improvement!

| Topic | Source File | Coverage |
|-------|-------------|----------|
| Security Review | SECURITY-REVIEW.md | 1 element |
| Code Of Conduct | CODE_OF_CONDUCT.md | 1 element |
| Readme | README.md | 2 concepts |
| Troubleshooting | docs/troubleshooting.md | 9 constraints |
| Quick Start | docs/quick-start.md | 1 verb |
| Important | docs/important.md | 3 concepts |
| Index | docs/index.md | 2 concepts |
| Templates | docs/customization/templates.md | 3 concepts |
| User Management | docs/usage/user-management.md | 4 nouns |
| User Control | docs/usage/user-control.md | 2 concepts |
| Installation | docs/usage/installation.md | 1 concept |
| Environment | docs/usage/configuration/environment.md | 1 concept |
| **Api** | docs/reference/api.md | **52 elements** |

### 4.2 Quality Scores

The Api topic has excellent quality metrics:
```json
{
  "coverage_score": 0.7,
  "constraint_score": 1.0,
  "agent_readiness_score": 0.85,
  "has_auth_requirements": "yes",
  "has_rate_limits": "yes",
  "has_examples": true
}
```

### 4.3 Remaining Issues

1. **File-level granularity only** - Still not parsing markdown sections within files
2. **Non-doc files included** - CODE_OF_CONDUCT.md, SECURITY-REVIEW.md shouldn't count as API docs
3. **Uneven distribution** - The Api topic covers 52 elements while others cover 1-4

---

## 5. Gap Analysis

### 5.1 Reported Metrics

```
Coverage: 93.0%
Complete: 78 topics
Partial: 4 topics
Missing: 4 topics
Extra: 1 topic
```

### 5.2 Missing Topics

1. `List resource` - root endpoint "/"
2. `List favicon.ico` - static asset endpoint (should be filtered)
3. `Root` concept - should be covered by home docs

### 5.3 Coverage Reality

The 93% coverage is **reasonably accurate** for this well-documented project:
- The `docs/reference/api.md` provides comprehensive endpoint documentation
- Quality scores correctly reflect that most docs have examples and auth requirements
- Constraint coverage is excellent

---

## 6. Bugs Discovered

### Bug 1: Duplicate Node IDs (Database Error)
**Severity:** High
**Location:** `storage.py:374`
**Description:** UNIQUE constraint failed when saving nodes with same ID
**Root Cause:** Likely duplicate noun extraction (e.g., both "key" and "apikey")
**Fix:** Deduplicate nodes before saving, or use UPSERT

### Bug 2: DTO Schema Names as Nouns
**Severity:** Medium
**Location:** `scanner.py` noun extraction
**Description:** Pydantic schemas (UserLogin, UserEdit) extracted as domain nouns
**Fix:** Filter nouns ending with DTO suffixes

### Bug 3: Non-Doc Files in ATM
**Severity:** Low
**Location:** ATM discovery
**Description:** CODE_OF_CONDUCT.md counted as documentation
**Fix:** Add exclude patterns for non-doc markdown files

---

## 7. Validation Verdict

**Phase 2 Status: PASS with issues**

The Gold Standard test shows DocZot working well on a production-quality codebase:

✅ **Working Well:**
- Constraint detection (auth_required)
- Multi-file ATM discovery
- Quality scoring
- Overall coverage calculation

⚠️ **Needs Improvement:**
- Noun extraction (filter DTOs)
- Database duplicate handling
- Section-level doc parsing

---

## 8. Comparison with Phase 1

| Metric | Phase 1 (Blog) | Phase 2 (Seapagan) | Improvement |
|--------|----------------|---------------------|-------------|
| ATM Topics | 1 | 13 | +1200% |
| Constraints | 0 | 28 | New feature working |
| Coverage % | 87.5% | 93.0% | More accurate |
| False Nouns | 2 | 5 | Needs work |

---

## 9. Proceed to Phase 3?

**Recommendation: YES**

The core functionality is working. Proceed to Phase 3 (Negative Control) to verify:
1. DocZot correctly reports 0% coverage when no docs exist
2. The tool doesn't hallucinate matches from README.rst or other non-doc files
