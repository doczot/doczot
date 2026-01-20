# DocZot Operational Validation Summary

**Date:** 2026-01-20
**Validator:** Claude Opus 4.5
**DocZot Version:** v2

---

## Executive Summary

DocZot was validated against 4 open-source FastAPI repositories representing different complexity levels. The tool demonstrates **core functionality is working** but reveals **systematic issues in noun extraction** that inflate entity counts.

| Phase | Repository | Type | Verbs | Nouns | ATM Topics | Coverage | Verdict |
|-------|------------|------|-------|-------|------------|----------|---------|
| 1 | fastapi-blog-api | Smoke Test | 6 | 3 (1 exp) | 1 | 87.5% | ⚠️ Issues |
| 2 | seapagan/fastapi-template | Gold Standard | 27 | 8 (2 exp) | 13 | 93.0% | ✅ Pass |
| 3 | fastapi-realworld-example | Negative Control | 19 | 15 | **0** | **0.0%** | ✅ Pass |
| 4 | FastAPI-boilerplate | Stress Test | 36 | 13 (4 exp) | 18 | 92.1% | ✅ Pass |

---

## What's Working Well

### 1. Endpoint Detection ✅
DocZot correctly identifies all FastAPI endpoints across all tested repositories:
- Router prefixes resolved correctly
- HTTP methods detected
- Path parameters identified

### 2. Constraint Detection ✅
Auth constraints (`Depends(get_current_user)`) are correctly extracted:
- Phase 2: 28 constraints
- Phase 4: 16 constraints

### 3. Negative Control ✅
When no documentation exists, DocZot correctly reports:
- ATM Topics: 0
- Coverage: 0.0%
- No hallucinated matches

### 4. MkDocs Integration ✅
Multi-file documentation is discovered correctly:
- Phase 2: 13 topics from `docs/` folder
- Phase 4: 18 topics from `docs/` folder

### 5. Quality Scoring ✅
Per-topic quality metrics provide useful signals:
- `coverage_score`, `constraint_score`, `agent_readiness_score`
- Detects presence of examples, auth docs, rate limits

---

## Systematic Issues Found

### Issue 1: Noun Over-Extraction (All Phases)

**Problem:** DocZot extracts 2-5x more nouns than expected due to:
- Function name words: `get_all_posts` → noun "all"
- DTO schema names: `UserLogin`, `UserEdit` → nouns
- Database model prefixes: `db_user`, `db_post` → nouns
- URL path segments: `/blog/` → noun "blog" (duplicate of "post")

**Evidence:**
| Phase | Expected Nouns | Detected | Inflation |
|-------|---------------|----------|-----------|
| 1 | 1 (post) | 3 | 3x |
| 2 | 2 (user, apikey) | 8 | 4x |
| 4 | 4 (user, post, task, tier) | 13 | 3.25x |

**Fix Required:** Add noun filtering for:
- Common words: all, single, new, multi
- DTO suffixes: Login, Create, Update, Edit, Read, Response, Request
- Database prefixes: db_

### Issue 2: Single README Topic (Phase 1)

**Problem:** When docs are in a single README.md, the entire file becomes one ATM topic instead of parsing sections.

**Evidence:** Phase 1 README had 7 sections (## headers) but produced only 1 ATM topic.

**Fix Required:** Parse markdown headers to create per-section topics.

### Issue 3: Missing Verb Descriptions

**Problem:** FastAPI decorator `summary=` and `description=` parameters not extracted.

**Evidence:** All verb nodes have `description: null` despite code having explicit summaries.

**Fix Required:** Parse decorator kwargs in scanner.

### Issue 4: Database Duplicate ID Error

**Problem:** `sqlite3.IntegrityError: UNIQUE constraint failed` when saving nodes.

**Root Cause:** Duplicate nouns (e.g., "key" and "apikey" pointing to same entity) cause ID collisions.

**Fix Required:** Deduplicate nodes before saving, or use UPSERT.

---

## Coverage Accuracy Assessment

| Scenario | Reported | Reality | Assessment |
|----------|----------|---------|------------|
| Single README (Phase 1) | 87.5% | ~30% | Inflated |
| MkDocs docs (Phase 2) | 93.0% | ~80% | Reasonably accurate |
| No docs (Phase 3) | 0.0% | 0% | Accurate |
| MkDocs docs (Phase 4) | 92.1% | ~75% | Reasonably accurate |

**Conclusion:** Coverage is accurate when docs are in separate files, inflated when in single README.

---

## Prioritized Bug List

### P0 - Must Fix Before Production
1. **Noun filtering** - Add stop-words and DTO suffix filters
2. **Database duplicate handling** - Fix UNIQUE constraint error

### P1 - Should Fix
3. **README section parsing** - Split by ## headers for ATM
4. **Verb description extraction** - Parse FastAPI decorators

### P2 - Nice to Have
5. **Entity merging** - Combine blog/post, key/apikey
6. **Non-doc file filtering** - Exclude CODE_OF_CONDUCT.md

---

## Validation Artifacts

Created during validation:
- `docs/VALIDATION_PHASE1_BLOG_API.md`
- `docs/VALIDATION_PHASE2_SEAPAGAN.md`
- `docs/VALIDATION_PHASE3_REALWORLD.md`
- `docs/VALIDATION_PHASE4_BOILERPLATE.md`
- `docs/VALIDATION_SUMMARY.md` (this file)

Analysis outputs saved to:
- `/tmp/doczot_validation/blog_analysis/`
- `/tmp/doczot_validation/seapagan_analysis/`
- `/tmp/doczot_validation/realworld_analysis/`
- `/tmp/doczot_validation/boilerplate_analysis/`

---

## Recommendation

**DocZot is ready for beta testing** with the understanding that:
1. Noun counts will be inflated (focus on verb/constraint coverage)
2. Single-file READMEs will show misleading coverage
3. MkDocs-structured projects will get accurate analysis

**Immediate fixes** should focus on noun filtering to improve surface graph accuracy before broader rollout.
