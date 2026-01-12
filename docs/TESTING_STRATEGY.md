# DocZot Testing Strategy: Validation Against Real-World Repositories

**Last Updated**: January 2026
**Purpose**: Stratified test suite for validating DocZot v2 and establishing baseline for v3

---

## Overview

Testing DocZot requires more than synthetic examples—it needs real-world repositories with the entropy and edge cases of production software. This document outlines a stratified testing strategy using open-source FastAPI projects.

**Key Insight**: Real repos revealed problems synthetic tests never would (test file pollution, translation noise, implicit entities). Continuing this approach ensures DocZot handles production complexity.

---

## Test Repository Portfolio

### 1. Gold Standard: `seapagan/fastapi-template`

**Purpose**: Baseline for ideal behavior - well-structured code with complete documentation

**Repository**: https://github.com/seapagan/fastapi-template
**License**: MIT
**Stats**: ~98% Python, active maintenance

**Why This Repo**:
- Clean modular structure (`app/routers`, `app/schemas`, `app/models`)
- Full MkDocs documentation with type-first hierarchy (Reference > Concept > Task)
- SQLAlchemy 2.0 + Pydantic models for clear entity detection
- Router prefix patterns testing AST scanner's path resolution
- JWT authentication with refresh tokens (auth constraint patterns)

**What DocZot Should Detect**:
- **Surface Graph**: User, Token entities; authentication endpoints
- **ITM**: Complete hierarchy with Reference (API docs), Concept (entities), Task (how-tos)
- **ATM**: High match rate with MkDocs navigation structure
- **Gap Report**: >60% coverage (well-documented baseline)

**v3 Value**: Contains pre-commit hooks, ruff, mypy for constraint extraction testing

**Test Command**:
```bash
doczot analyze test_repos/seapagan-fastapi-template
```

**Success Criteria**:
- [ ] Scanner resolves all router prefixes correctly
- [ ] Entities extracted: User, Token (minimum)
- [ ] ITM matches MkDocs navigation structure
- [ ] ATM correctly links docs sections to endpoints
- [ ] Coverage >60%
- [ ] No false positive matches from config files

---

### 2. Stress Test: `benavlabs/FastAPI-boilerplate`

**Purpose**: Challenge scanner with modern patterns and partial documentation

**Repository**: https://github.com/benavlabs/FastAPI-boilerplate
**License**: MIT (verify)
**Stats**: Pydantic V2, SQLAlchemy 2.0, fully async

**Why This Repo**:
- **Pydantic V2** syntax tests forward compatibility
- **FastCRUD** generic abstractions challenge entity detection
- **AI-assisted docs** (admitted in README) test semantic matching on machine-generated content
- **Partial coverage** ("rough around the edges") validates Gap Report accuracy
- Production-ready patterns (async, dependency injection)

**What DocZot Should Detect**:
- **Surface Graph**: Must resolve entities despite FastCRUD generics (not just "Model")
- **ITM**: Complex hierarchy with abstract concepts (Performance, Scalability)
- **ATM**: Should identify partial coverage, not hallucinate completeness
- **Gap Report**: Mixed coverage with specific missing topics

**Known Challenges**:
1. **Generic CRUD**: Routes may call `crud.get()` not `crud.get_user()`. Scanner must trace type parameters.
2. **Abstract Concepts**: "Performance & Scalability" pages don't map 1:1 to endpoints. Must be classified as Concepts, not References.
3. **AI-Generated Content**: Tests if semantic matcher handles machine-generated prose patterns.

**Test Command**:
```bash
doczot analyze test_repos/benavlabs-fastapi-boilerplate
```

**Success Criteria**:
- [ ] Scanner extracts specific entities (User, Item) not generic placeholders
- [ ] Pydantic V2 models parsed correctly
- [ ] ATM identifies partial coverage accurately
- [ ] Gap Report shows missing topics where docs are incomplete
- [ ] Abstract concept pages classified as Concept, not Reference
- [ ] No crashes on modern Python/Pydantic syntax

---

### 3. Negative Control: `nsidnev/fastapi-realworld-example-app`

**Purpose**: Validate zero-coverage detection (no hallucinations)

**Repository**: https://github.com/nsidnev/fastapi-realworld-example-app
**License**: MIT
**Stats**: Mature, complex "RealWorld" spec implementation

**Why This Repo**:
- **No docs folder**: Zero markdown documentation
- **README.rst only**: ReStructuredText (not supported by v2)
- **Swagger UI only**: Directs users to auto-generated `/docs`
- **Complex surface**: Articles, Comments, Profiles, Tags entities
- **Clean architecture**: Nested routing, PostgreSQL models

**What DocZot Should Detect**:
- **Surface Graph**: Rich and detailed (many entities and endpoints)
- **ITM**: Large manifest reflecting complex API
- **ATM**: Empty or near-empty (no markdown docs found)
- **Gap Report**: **0% coverage** (critical validation)

**This Tests**:
1. DocZot doesn't hallucinate coverage from unrelated text
2. Graceful handling of .rst files (ignore, don't crash)
3. Semantic matcher doesn't over-match from README
4. Gap Report correctly reports zero coverage
5. Philosophy validation: Swagger UI ≠ documentation

**Test Command**:
```bash
doczot analyze test_repos/fastapi-realworld-example-app
```

**Success Criteria**:
- [ ] Surface Graph has >10 entities (Articles, Comments, Users, etc.)
- [ ] ITM generates complete manifest
- [ ] ATM shows 0% or near-0% coverage
- [ ] Gap Report explicitly states "0% Reference Coverage"
- [ ] No crashes on .rst file presence
- [ ] No false matches from README.rst content

---

### 4. Semantic Challenge: `fastapi-users`

**Purpose**: Test semantic matching on library (not application) documentation

**Repository**: https://github.com/fastapi-users/fastapi-users
**License**: MIT
**Stats**: Popular auth library with examples

**Why This Repo**:
- **Library vs Application**: Docs describe "how to configure" not "this endpoint does X"
- **Semantic gap**: "Configuration of OAuth2" vs `OAuth2Backend` class
- **Implicit entities**: Auth endpoints that don't mention "User" in URL
- **Complex generics**: `class User(UserBase, SQLAlchemyBaseUserTable, ...)`
- **Extensive MkDocs**: Well-documented but abstract

**What DocZot Should Detect**:
- **Scan target**: Point at `examples/` directory or library source
- **Surface Graph**: User entity from complex generic inheritance
- **ATM**: Can semantic matcher bridge "usage instructions" to "implementation details"?
- **Gap Report**: Tests if library docs match differently than app docs

**This Tests**:
1. CLI configuration flexibility (non-standard scan targets)
2. Entity detection through complex inheritance and generics
3. Semantic matching across wider conceptual gaps
4. Vector store robustness with abstract library documentation

**Test Command**:
```bash
doczot analyze test_repos/fastapi-users/examples/beanie
```

**Success Criteria**:
- [ ] Scanner detects User entity despite complex inheritance
- [ ] Auth endpoints categorized correctly (node_class="auth")
- [ ] Semantic matcher links "configuration docs" to corresponding classes/endpoints
- [ ] No false negatives due to library abstraction patterns

---

### 5. Micro Test: `mehmetext/fastapi-blog-api`

**Purpose**: Fast smoke test and debugging iteration

**Repository**: https://github.com/mehmetext/fastapi-blog-api
**License**: TBD (verify)
**Stats**: Simple blog API, ~10-15 endpoints

**Why This Repo**:
- **Speed**: Scans in seconds for rapid iteration
- **Simplicity**: Textbook FastAPI structure (`app/controllers`, `app/models`, `app/routers`)
- **Single-file docs**: Detailed README.md only
- **Standard CRUD**: Users, Blogs with typical operations

**What DocZot Should Detect**:
- **Surface Graph**: User, Blog entities with standard CRUD verbs
- **ITM**: ~10-15 Reference topics, 2 Concept topics, possible CRUD how-tos
- **ATM**: Tests single-file chunking (parsing one large README)
- **Gap Report**: Likely low coverage (README doesn't replace structured docs)

**This Tests**:
1. Scanner sanity check (if it fails here, core regression exists)
2. README parsing and chunking logic
3. Topic granularity (can it identify distinct topics in one file?)
4. Fast iteration for debugging scanner logic

**Test Command**:
```bash
doczot analyze test_repos/fastapi-blog-api
```

**Success Criteria**:
- [ ] Completes scan in <5 seconds
- [ ] Identifies User and Blog entities
- [ ] ITM lists all ~10-15 endpoints
- [ ] ATM chunks README into distinct topics
- [ ] If this fails, indicates fundamental regression

---

## Phased Validation Plan

### Phase 1: Smoke Test (Week 1)

**Objective**: Verify core functionality works

**Target**: `mehmetext/fastapi-blog-api`

**Steps**:
1. Clone repository
2. Run `doczot analyze test_repos/fastapi-blog-api`
3. Manually inspect Surface Graph output
4. Verify User and Blog entities detected
5. Check ITM lists expected number of endpoints

**Exit Criteria**: Scanner completes without errors, basic entity detection works

---

### Phase 2: Happy Path Baseline (Week 1-2)

**Objective**: Establish "good behavior" baseline

**Target**: `seapagan/fastapi-template`

**Steps**:
1. Clone repository
2. Run full analysis with visualizer
3. Compare ITM hierarchy to `mkdocs.yml` navigation
4. Manually verify 5-10 ATM matches are accurate
5. Review Gap Report for reasonable coverage percentage

**Exit Criteria**: >60% coverage, no false positives, ITM structure matches expectations

---

### Phase 3: Zero State Calibration (Week 2)

**Objective**: Confirm no hallucinated coverage

**Target**: `nsidnev/fastapi-realworld-example-app`

**Steps**:
1. Run analysis
2. Verify Surface Graph is rich (many entities)
3. Verify ATM is empty or near-empty
4. Confirm Gap Report shows 0% coverage
5. Check logs for .rst file handling (no crashes)

**Exit Criteria**: 0% coverage reported correctly, no false matches

---

### Phase 4: Modernity Stress Test (Week 3)

**Objective**: Validate modern Python/Pydantic compatibility

**Target**: `benavlabs/FastAPI-boilerplate`

**Steps**:
1. Run analysis
2. Inspect Surface Graph for generic vs specific entities
3. Verify Pydantic V2 models parsed correctly
4. Check ATM for partial coverage detection
5. Review Gap Report for accuracy on incomplete docs

**Exit Criteria**: Specific entities detected, partial coverage identified correctly

---

### Phase 5: Semantic Validation (Week 4)

**Objective**: Test semantic matching robustness

**Target**: `fastapi-users`

**Steps**:
1. Configure scan target (examples directory)
2. Run analysis
3. Check entity detection through complex inheritance
4. Manually review 5-10 semantic matches for accuracy
5. Assess false positive/negative rate

**Exit Criteria**: Semantic matcher bridges library documentation gap successfully

---

## Success Metrics

### Scanner (Layer 1)
- **Entity Detection Rate**: >80% of manually identified entities detected
- **Path Resolution**: 100% of router prefixes resolved correctly
- **Type Compatibility**: No crashes on Pydantic V1, V2, or SQLAlchemy 2.0

### Matcher (Layer 3)
- **Precision**: >85% of ATM matches are semantically correct (manual review)
- **Recall**: >70% of relevant docs matched to endpoints
- **No Hallucinations**: 0% false matches on negative control repo

### Gap Report (Layer 4)
- **Zero Detection**: Correctly reports 0% on realworld-example-app
- **High Detection**: Reports >60% on seapagan/fastapi-template
- **Partial Detection**: Identifies incomplete coverage on benavlabs

---

## Repository Setup

### Directory Structure
```
test_repos/
├── seapagan-fastapi-template/      # Gold standard
├── benavlabs-fastapi-boilerplate/  # Stress test
├── fastapi-realworld-example-app/  # Negative control
├── fastapi-users/                  # Semantic challenge
├── fastapi-blog-api/               # Micro test
└── README.md                       # Licensing and attribution
```

### Cloning Script
```bash
#!/bin/bash
# scripts/setup_test_repos.sh

cd test_repos

# Gold Standard
git clone https://github.com/seapagan/fastapi-template seapagan-fastapi-template

# Stress Test
git clone https://github.com/benavlabs/FastAPI-boilerplate benavlabs-fastapi-boilerplate

# Negative Control
git clone https://github.com/nsidnev/fastapi-realworld-example-app fastapi-realworld-example-app

# Semantic Challenge
git clone https://github.com/fastapi-users/fastapi-users fastapi-users

# Micro Test
git clone https://github.com/mehmetext/fastapi-blog-api fastapi-blog-api

echo "All test repositories cloned successfully"
```

---

## v3 Implications

These repositories also provide data for v3 feature development:

### Constraint Extraction
- **seapagan/fastapi-template**: Pre-commit hooks, ruff, mypy configurations
- **benavlabs**: Rate limiters, dependency injection patterns
- Look for: `@limiter.limit()`, `Depends(get_current_user)`, config files

### Concept Extraction
- **benavlabs**: Abstract concept pages (Performance, Scalability)
- **fastapi-users**: Library concepts (OAuth2, JWT, Refresh Tokens)
- Test deterministic extraction from docstrings and README

### Agent Readiness
- All repos have Dockerfile → test deployment constraint extraction
- OpenAPI/Swagger presence → test machine-readable spec detection
- README structure → test terminology consistency

---

## Validation Checklist

Before releasing v2 or v3:

- [ ] All 5 repos clone successfully
- [ ] Phase 1-5 tests pass success criteria
- [ ] No regressions on full-stack-fastapi-template (existing test)
- [ ] Manual spot-check of 25 ATM matches across repos (>85% accuracy)
- [ ] Zero coverage correctly detected on negative control
- [ ] Documentation updated with test results
- [ ] Performance benchmarks recorded (scan time per repo)

---

## Maintenance

**Frequency**: Re-run full test suite:
- Before each release (v2.x, v3.0, etc.)
- After major scanner changes
- Quarterly health check

**Repository Updates**:
- Update test repo clones every 6 months
- Document if upstream changes break existing assumptions
- Consider "pinning" to specific commits for reproducibility

**Expansion**:
- Add Django, Flask repos when multi-framework support lands
- Add non-English docs when translation support added
- Add GraphQL when schema support implemented

---

## References

- Original analysis provided by Gemini (January 2026)
- DocZot design philosophy: [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md)
- v3 roadmap: [DESIGN_V3.md](DESIGN_V3.md)
- Historical learnings: [LEARNINGS.md](LEARNINGS.md)
