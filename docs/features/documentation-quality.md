# Feature: Documentation Quality Scoring

## Overview

DocZot doesn't just check if documentation exists - it measures **how well** topics are documented across multiple dimensions. This enables actionable sprint planning, not just coverage percentages.

## Core Concepts

### ITM vs ATM

- **ITM (Intended Topic Manifest)**: What SHOULD be documented - the product surface
- **ATM (Actual Topic Manifest)**: What IS documented - the documentation coverage

The gap between ITM and ATM, plus quality scores, drives DocZot's value.

### Topic Nodes

The product surface consists of three node types:

| Type | Description | Examples |
|------|-------------|----------|
| **Noun** | Entities users interact with | User, Project, Invoice, Document |
| **Verb** | Actions users can perform | create, delete, configure, export |
| **Concept** | Ideas requiring explanation | authentication, rate limiting, permissions |

### Node Classification

Not all nodes should count toward coverage percentages:

| Class | Include in Coverage %? | Description |
|-------|------------------------|-------------|
| `user-facing` | Yes | Normal features users interact with |
| `internal` | No (but tracked) | Health checks, metrics, admin endpoints |
| `meta` | No (but tracked) | /docs, /redoc, /openapi.json endpoints |
| `deprecated` | Configurable | Marked for removal |

---

## Quality Scoring Dimensions

### 1. Technical Completeness

**Question**: Is the "what" documented?

| Component | Values | Description |
|-----------|--------|-------------|
| `has_parameters_docs` | yes/partial/no | Are inputs/arguments documented? |
| `has_return_docs` | yes/partial/no | Are outputs/responses documented? |
| `has_error_docs` | yes/partial/no | Are error codes/exceptions documented? |
| `has_warnings` | yes/no | Are destructive actions flagged? |

**Rubric**:
- **Complete**: All four components are "yes"
- **Partial**: Some components documented, others missing
- **Missing**: No technical documentation

### 2. Semantic Completeness

**Question**: Is the "why/when/how" documented?

| Component | Description |
|-----------|-------------|
| `has_description` | Beyond just the signature - what does this do? |
| `has_use_cases` | When should a user use this? |
| `has_anti_patterns` | When should they NOT use this? Gotchas? |
| `has_context` | How does this relate to other features? |

**Rubric**:
- **Complete**: Explains what, why, when to use, when not to use
- **Partial**: Has description but lacks context or anti-patterns
- **Missing**: Just a signature/reference, no explanation

### 3. Style Adherence (Extensible)

**Question**: Does the documentation meet quality standards?

#### Free Tier (Generic Style)
| Component | Values | Description |
|-----------|--------|-------------|
| `grammar_quality` | good/acceptable/poor | Grammar and spelling |
| `clarity` | clear/acceptable/unclear | Easy to understand? |
| `consistency` | consistent/inconsistent | Matches other docs? |

#### Paid Tier (Custom Brand Voice)
| Component | Description |
|-----------|-------------|
| `brand_voice_adherence` | 0.0-1.0 score against custom style guide |
| `custom_rules_violations` | List of specific rule violations |

This dimension is designed for future extensibility where companies can upload their own brand voice guidelines.

### 4. Example Coverage

| Component | Description |
|-----------|-------------|
| `has_generic_example` | Auto-generated schema example (Swagger) |
| `has_use_case_example` | Curated, realistic example |
| `has_error_example` | Example showing error handling |
| `example_is_runnable` | Can be copy-pasted and executed |

---

## Confidence Scores

Every rating has associated confidence to indicate reliability.

### Discovery Confidence

**Question**: How confident are we that we found the right docs for this topic?

This measures the ATM→ITM mapping accuracy.

| Level | Description |
|-------|-------------|
| `high` | Exact match found, very confident |
| `medium` | Vector/fuzzy match, reasonably confident |
| `low` | May have missed docs (e.g., .rst files, Postman collections) |

### Score Confidence

**Question**: How confident is the rater in the quality scores?

Each quality dimension (technical, semantic, style) has its own confidence:

| Level | Description |
|-------|-------------|
| `high` | Clear-cut case, obvious rating |
| `medium` | Some ambiguity, judgment call |
| `low` | Uncertain, would benefit from second opinion |

---

## Output: Actionable Sprint Plan

The detailed scoring enables generating sprint-ready task lists:

```
Documentation Coverage: 65% (26/40 user-facing topics)

Missing Error Documentation (8 topics):
  - POST /password-recovery/{email}:55 → Add 404 error response
  - PATCH /me:79 → Add 409 conflict error
  - DELETE /users/{id}:142 → Add 403/404 error responses

Missing Warnings (2 topics):
  - DELETE /me:129 → Add PERMANENT DELETION warning
  - POST /users/{id}/transfer:201 → Add ownership transfer warning

Missing Examples (12 topics):
  - GET /projects:45 → Add realistic list response example
  - POST /invoices:89 → Add complete invoice creation example

Low Semantic Quality (6 topics):
  - PUT /settings:112 → Add why/when explanation
  - GET /reports:156 → Add use case documentation
```

Each item includes:
- Node ID and name
- File:line reference
- Specific action to take

---

## Data Model

See `doczot_analyzer/manifest.py` for the complete implementation.

Key classes:
- `TopicNode`: A node in the product surface graph
- `TopicCoverage`: Documentation coverage for a single node
- `QualityScore`: Complete quality assessment (technical, semantic, style, examples)
- `TopicManifest`: The complete ITM + ATM structure

---

## Rating Process

### Manual Rating Workflow

1. Scanner discovers topic nodes (ITM)
2. Docs parser finds documentation (ATM candidates)
3. Matcher links ATM to ITM
4. Reviewer rates each topic:
   - Technical completeness (4 components)
   - Semantic completeness (4 components)
   - Example coverage (4 components)
   - Confidence levels (discovery + score)

### Automated Rating (Future)

LLM-assisted rating using the same rubric:
- Technical: Check if params/returns/errors are documented
- Semantic: Evaluate explanation quality
- Style: Check grammar, clarity, brand voice
- Examples: Identify example quality

---

## Configuration

### Excluding Topics

Topics can be excluded from coverage calculations:

```yaml
# .doczot/config.yml
excluded_topics:
  - pattern: "internal_*"
    reason: "Internal endpoints"
  - pattern: "*_deprecated"
    reason: "Deprecated, removal planned"
```

### Custom Style Rules (Paid Feature)

```yaml
# .doczot/brand-voice.yml
style_rules:
  - name: "active_voice"
    pattern: "should be|will be|can be"
    suggestion: "Use active voice"
  - name: "terminology"
    banned_terms: ["click", "hit"]
    preferred_terms: ["select", "access"]
```

---

## Success Criteria

- [ ] All topic types (noun/verb/concept) can be scored
- [ ] Technical score captures params, returns, errors, warnings
- [ ] Semantic score captures description, use cases, anti-patterns
- [ ] Style score is extensible for custom brand voice
- [ ] Confidence is tracked for both discovery and scoring
- [ ] Sprint plan can be generated from quality gaps
- [ ] Internal/meta topics are tracked but excluded from %

---

## Examples

### Example 1: Well-Documented Verb

**Topic**: `create_user` (verb)

```json
{
  "is_documented": true,
  "category": "markdown",
  "discovery_confidence": "high",
  "quality": {
    "technical": {
      "has_parameters_docs": "yes",
      "has_return_docs": "yes",
      "has_error_docs": "yes",
      "has_warnings": true,
      "overall": {"level": "complete", "confidence": "high"}
    },
    "semantic": {
      "has_description": true,
      "has_use_cases": true,
      "has_anti_patterns": true,
      "has_context": true,
      "overall": {"level": "complete", "confidence": "high"}
    },
    "examples": {
      "has_generic_example": true,
      "has_use_case_example": true,
      "has_error_example": true,
      "example_is_runnable": true
    }
  }
}
```

### Example 2: Minimally Documented Verb (Common Pattern)

**Topic**: `delete_user` (verb)

```json
{
  "is_documented": true,
  "category": "code-docstring",
  "discovery_confidence": "medium",
  "quality": {
    "technical": {
      "has_parameters_docs": "yes",
      "has_return_docs": "yes",
      "has_error_docs": "no",
      "has_warnings": false,
      "overall": {"level": "partial", "confidence": "high"}
    },
    "semantic": {
      "has_description": false,
      "has_use_cases": false,
      "has_anti_patterns": false,
      "has_context": false,
      "overall": {"level": "missing", "confidence": "high"}
    },
    "examples": {
      "has_generic_example": true,
      "has_use_case_example": false,
      "has_error_example": false,
      "example_is_runnable": false
    }
  }
}
```

**Sprint Plan Entry**:
```
- DELETE /users/{id}:142
  - Add 403/404 error documentation
  - Add PERMANENT DELETION warning
  - Add description explaining when to use
  - Add curated example with realistic data
```

---

## Future Enhancements

1. **LLM-Powered Scoring**: Automated quality assessment
2. **Trend Tracking**: Quality score changes over time
3. **Team Dashboards**: Per-team/per-module quality views
4. **CI/CD Integration**: Fail builds on quality regression
5. **Custom Brand Voice**: Company-specific style checking
