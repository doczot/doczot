# Product Backlog

Ideas and potential features for future consideration. Items here may be promoted to the roadmap, deprioritized, or archived.

## Status Legend
- 🔥 **Hot** - High interest, likely to be prioritized soon
- 💡 **Idea** - Needs more exploration/validation
- 🧊 **Cold** - Low priority, might not implement
- ✅ **Accepted** - Moving to roadmap
- ❌ **Rejected** - Decided not to pursue

---

## Integration & Standards

### Use Officially Recognized Format for "Facts About the Platform"
**Status:** 💡 Idea
**Date Added:** 2025-10-20
**Category:** Architecture, Interoperability

**Description:**
Instead of custom data models, adopt an officially recognized format for representing API metadata and documentation coverage facts.

**Possible Formats:**
- **GraphQL Schema** - Industry standard for API type systems
- **MCP (Model Context Protocol)** - Emerging standard for AI-tool integration
- **OpenAPI/Swagger** - Well-established for REST API documentation
- **JSON Schema** - Language-agnostic schema definition

**Benefits:**
- Better interoperability with other tools
- Standardized tooling/validation
- Easier integration with CI/CD pipelines
- Community familiarity

**Considerations:**
- Migration effort from current Pydantic models
- May be overkill for MVP
- Need to evaluate which standard best fits our use case

**Next Steps:**
- [ ] Research MCP adoption in similar tools
- [ ] Evaluate OpenAPI as a potential format
- [ ] Prototype conversion of current models to chosen format
- [ ] Assess community feedback on preferred format

---

## Scanner Enhancements

### Resolve Router Prefixes for Accurate Paths
**Status:** 🔥 Hot
**Date Added:** 2025-10-22
**Category:** Core Functionality, Accuracy
**Source:** Golden dataset rating session - discovered real endpoints with empty paths

**Problem:**
Scanner captures decorator path (e.g., `@router.put("")`) but doesn't resolve the final mounted path. Real path is `/user` but scanner shows empty string.

**Example:**
```python
# In app/api/routes/users.py
router = APIRouter()

@router.put("")  # Scanner sees ""
async def update_current_user(...): ...

# In app/api/routes/api.py
router.include_router(users.router, prefix="/user")  # Real path is /user
```

**Solution:**
- Parse `include_router()` calls to build prefix mapping
- Resolve full paths by combining router prefix + decorator path
- Handle nested routers (prefix chains)

**Impact:** HIGH - Affects path matching between endpoints and documentation

**Next Steps:**
- [ ] Add router prefix tracking to scanner.py
- [ ] Parse include_router() calls in main app file
- [ ] Update Endpoint model to include resolved_path
- [ ] Add tests for nested router scenarios

---

### Improve Path Regex to Reduce False Positives
**Status:** 🔥 Hot
**Date Added:** 2025-10-22
**Category:** Core Functionality, Accuracy
**Source:** Golden dataset scanning - matched `/app` directory path as API endpoint

**Problem:**
Documentation scanner matches filesystem paths as API endpoints:
- `/app` (directory in Docker instructions) matched as `GET /`
- `/home/user/file.txt` could match as API path

**Current Regex:**
```python
pattern = r'\b(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s*\|?\s*(/[a-zA-Z0-9/_\-{}:]*)'
```

**Solution:**
Add context-aware filtering:
1. Require HTTP method immediately before path (no line break)
2. Reject paths with common filesystem indicators:
   - Multiple dots: `/path/to/file.py`
   - Home directory: `/home/`, `/Users/`
   - System paths: `/var/`, `/etc/`, `/usr/`
3. Require path to be in API context (code block, table, near "endpoint"/"route")

**Impact:** MEDIUM - Reduces noise in doc matching, improves precision

**Next Steps:**
- [ ] Analyze false positive patterns in real repos
- [ ] Update regex with negative lookahead for filesystem paths
- [ ] Add context checking (within code blocks, near API keywords)
- [ ] Add tests for common false positive cases

---

### Support Additional Documentation Formats
**Status:** 💡 Idea
**Date Added:** 2025-10-22
**Category:** Coverage, Completeness
**Source:** RealWorld repo uses .rst (reStructuredText), some repos use Postman

**Current Limitations:**
- Only scans Markdown (.md) files
- Doesn't parse Postman collections (common in FastAPI projects)
- Doesn't support reStructuredText (.rst) used by Python community
- Doesn't scan OpenAPI/Swagger specs (openapi.json, swagger.yaml)

**Potential Additions:**
1. **reStructuredText (.rst)** - Common in Python ecosystem
2. **Postman Collections** (.postman_collection.json) - Many projects document via Postman
3. **OpenAPI Specs** (openapi.json, swagger.yaml) - Can extract endpoint descriptions
4. **Docusaurus/VuePress** - Modern doc frameworks (parse .mdx, .vue)

**Priority Order:**
1. Postman (high value for FastAPI projects)
2. OpenAPI specs (already structured data)
3. reStructuredText (Python ecosystem standard)

**Impact:** MEDIUM - Increases coverage discovery for repos using alternative formats

**Next Steps:**
- [ ] Survey popular FastAPI repos for doc format usage
- [ ] Prototype Postman collection parser
- [ ] Evaluate effort vs value for each format
- [ ] Add confidence_discovery warnings when unsupported formats detected

---

### LLM-Assisted Documentation Discovery
**Status:** 💡 Idea
**Date Added:** 2025-10-22
**Category:** Smart Features, AI Enhancement
**Source:** Discussion during scanner enhancement

**Concept:**
Use LLM to intelligently find and match documentation to endpoints:
1. **Smart discovery** - Find unconventional doc locations (wiki/, tutorials/, examples/)
2. **Fuzzy matching** - Match endpoints to docs even with naming variations
3. **Semantic understanding** - Identify that "user profile update" docs relate to `PATCH /me`

**Use Cases:**
- Documentation in non-standard locations
- Docs that reference endpoints conceptually, not literally
- Multi-language docs (map English docs to endpoints)
- Legacy projects with scattered documentation

**Challenges:**
- Cost (LLM API calls per endpoint)
- Speed (slower than regex)
- Reliability (false positives/negatives)
- Configuration complexity

**Approach:**
- Start with deterministic scanning (current)
- Offer LLM-assisted mode as optional enhancement
- Use LLM only for low-confidence matches
- Cache results to reduce cost

**Impact:** HIGH potential, but needs validation

**Next Steps:**
- [ ] Prototype with 5-10 endpoints from golden dataset
- [ ] Measure precision/recall vs deterministic approach
- [ ] Estimate cost per endpoint at scale
- [ ] Define when LLM mode should be suggested to users

---

## Accuracy & Customization

### Manual Documentation-to-Code Linking
**Status:** 🔥 Hot
**Date Added:** 2025-10-20
**Category:** Accuracy, Enterprise Features

**Description:**
Allow organizations to manually create explicit links between code endpoints and documentation sections, improving coverage accuracy for complex cases.

**Use Cases:**
- Documentation in non-standard locations
- Endpoints documented in external systems (Confluence, Notion, etc.)
- Complex monorepo structures
- Endpoints with non-obvious naming patterns

**Proposed Solution:**
```yaml
# .doczot/mappings.yml
manual_links:
  - endpoint:
      method: POST
      path: /api/v1/users
    documentation:
      - file: docs/user-management.md
        section: "Creating Users"
      - file: external/confluence-export.md
        section: "User API"

  - endpoint:
      method: GET
      path: /internal/health
    documentation:
      - file: ops/monitoring.md
        reason: "Internal endpoint, documented in ops guide"
```

**Benefits:**
- Increased accuracy for edge cases
- Handles non-standard documentation
- Enterprise-friendly (supports complex org structures)
- Gradual adoption (can start with just problem endpoints)

**Considerations:**
- Maintenance burden (manual links can become stale)
- Need validation/warning when links break
- Could become crutch instead of improving auto-detection
- Version control complexity

**Implementation Ideas:**
- YAML configuration file (`.doczot/mappings.yml`)
- CLI command: `doczot link <endpoint> <doc-file> [--section]`
- Validation: Warn when linked endpoints/docs don't exist
- Reporting: Show manual vs auto-detected coverage separately

**Next Steps:**
- [ ] Design configuration file schema
- [ ] Implement parser for manual links
- [ ] Add validation logic
- [ ] Create CLI commands for link management
- [ ] Add to coverage report (manual vs auto metrics)

---

## Future Ideas (Unsorted)

### LLM-Powered Documentation Quality Scoring
**Status:** 💡 Idea
**Date Added:** 2025-10-20

Beyond just "exists/doesn't exist", use LLM to score documentation quality:
- Completeness (covers all parameters?)
- Clarity (easy to understand?)
- Examples (has working code samples?)
- Up-to-date (matches current implementation?)

### GitHub Actions Integration
**Status:** 💡 Idea
**Date Added:** 2025-10-20

Pre-built GitHub Action for CI/CD:
```yaml
- uses: doczot/analyze@v1
  with:
    fail-below: 80
    output-format: markdown
```

### VS Code Extension
**Status:** 💡 Idea
**Date Added:** 2025-10-20

Show documentation coverage inline in editor:
- Highlight undocumented endpoints
- Quick links to relevant docs
- "Create documentation" quick action

### Multi-Framework Support
**Status:** 💡 Idea
**Date Added:** 2025-10-20

Expand beyond FastAPI:
- Flask
- Django REST Framework
- Express.js
- Spring Boot

### Documentation Templates
**Status:** 💡 Idea
**Date Added:** 2025-10-20

Generate documentation stubs for undocumented endpoints:
```markdown
## POST /api/users

<!-- Auto-generated by DocZot -->

**Description:** [TODO: Add description]

**Parameters:**
- `username` (string, required): [TODO: Add description]
- `email` (string, required): [TODO: Add description]

**Response:**
[TODO: Add response format]

**Example:**
[TODO: Add example]
```

### Confluence/Notion Integration
**Status:** 💡 Idea
**Date Added:** 2025-10-20

Scan external documentation platforms, not just markdown files.

### Breaking Change Detection
**Status:** 💡 Idea
**Date Added:** 2025-10-20

Compare two commits/branches:
- Detect removed endpoints
- Detect changed signatures
- Flag documentation that needs updates

---

## Process Notes

### How to Use This Document

1. **Adding Ideas:** Anyone can add ideas with status 💡
2. **Promoting Ideas:** Move to 🔥 when validated/prioritized
3. **Moving to Roadmap:** Change status to ✅ and create tracking issue
4. **Rejecting Ideas:** Change status to ❌ and document why

### Review Cadence

- **Weekly:** Review 🔥 items, promote best candidates to roadmap
- **Monthly:** Review 💡 items, promote promising ones to 🔥
- **Quarterly:** Archive ❌ items, clean up backlog

### Template for New Ideas

```markdown
### [Feature Name]
**Status:** 💡 Idea
**Date Added:** YYYY-MM-DD
**Category:** [Architecture/Features/Integration/etc.]

**Description:**
[What is the feature?]

**Benefits:**
- [Why would this be valuable?]

**Considerations:**
- [What challenges or tradeoffs?]

**Next Steps:**
- [ ] [What research/validation needed?]
```
