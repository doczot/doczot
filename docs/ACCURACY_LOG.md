# Content-Coverage Accuracy Log

Findings from the hand-labeled accuracy corpus
(`doczot_analyzer/tests/corpus/`) and the fixes made in response. Newest entry
first. The `doczot-tester` agent appends here.

---

## 2026-07-29 (later) — Real repositories contradicted the synthetic fixture

Ran against four cloned FastAPI projects to answer questions the corpus
structurally cannot, since the same author wrote both the code and the labels.
The headline result is a **negative** one: the cross-file `include_router` fix
from earlier today did not work on either real repository it was designed for.

```
repo                                    endpoints  operation coverage
full-stack-fastapi-template (backend/)     23        0.0%  (0/23)
seapagan/fastapi-template                  27       92.6%  (25/27)
benavlabs/FastAPI-boilerplate (backend/)   30        0.0%  (0/30)
mehmetext/fastapi-blog-api                  6      100.0%  (6/6)
```

### The synthetic fixture was too kind

`fastapi_router_prefix` used a literal `prefix="/api/v1"` and no import
aliasing. Both real repos do neither, and both reported paths their services do
not serve:

**Settings-constant prefixes.** FastAPI's own template writes
`app.include_router(api_router, prefix=settings.API_V1_STR)` against
`API_V1_STR: str = "/api/v1"` on a Pydantic settings class. The extractor
accepted only `ast.Constant`, so every path lost `/api/v1`. FIXED —
`_collect_string_constants()` gathers string constants project-wide and
`_resolve_prefix_value()` resolves a literal, a bare name, an attribute such as
`settings.API_V1_STR`, `+` concatenation, and f-strings. Unresolvable values
still yield `""`, leaving the path bare: a visibly incomplete path is better
than a fabricated one that looks authoritative. `scanner.py:398`.

**Alias-imported routers.** `from src.modules.user.routes import router as
users_router` was recorded under the local alias while the declaration is
`router`, so every lookup missed. FastAPI-boilerplate aliases every router it
imports, so it lost every prefix. FIXED — `ImportScope` now carries
(module, original name). `scanner.py:347`.

full-stack-fastapi-template now reports `/api/v1/users/`, `/api/v1/items/{id}`
and so on. Tests: `TestCrossFileRouterPrefixes`, four cases drawn from the
patterns these repos actually use.

**Application-factory wiring — NOT FIXED.** benavlabs passes the router into
`create_application(router: APIRouter)`, which calls
`application.include_router(router)` on a *parameter*. The app and its router are
connected only at the call site, so linking them needs interprocedural analysis:
find calls to the factory and read the argument bound to `router`. Recorded as
corpus case `fastapi_app_factory`, marked `known_failing` with the mechanism.
Implementing it should make that case XPASS.

### Q2 — is the verb rule too strict? Evidence says no

seapagan/fastapi-template, the repo with real mkdocs documentation across 24
files, scores **92.6% (25/27)** under the strict method+path rule. A rule that
credits 25 of 27 operations on genuinely-written documentation is not starving
real docs of credit. blog-api scores 100% (6/6) from a README alone.

Caveat before treating this as settled: seapagan counts `GET /` and
`GET /favicon.ico` as operations, which inflates the denominator with things
nobody would document. Whether such routes belong in `operations_total` is a
separate question worth its own decision.

### Q3 — does the manifest boundary under-reach? Yes, measurably

Analyzing `benavlabs/backend` yields **zero** doc sources: `backend/` has its own
`pyproject.toml`, so the boundary stops there and the project's real
documentation — 21 files under a root `docs/`, including one named
`user-guide/api/endpoints.md` — is excluded. full-stack loses 4 root files the
same way (`README.md`, `development.md`, `deployment.md`).

Coverage did not move when the boundary was widened to the git root in either
case, but that is **not** evidence the boundary is harmless: the endpoint paths
were wrong at the time, so no document could have matched them. The measurement
needs repeating now that paths are correct. A `--doc-root` override, or
preferring the outermost manifest, is the likely resolution.

### Determinism and cost

Two consecutive analyses of the same repo agree exactly on endpoints, nouns,
concepts, operation counts, uncovered operations and doc sources — the recursive
include-graph walk is stable.

Timing is uneven and worth attention: 1.2s (benavlabs, no docs found), 3.5s
(blog-api), 7.7s (full-stack), **341.5s** (seapagan, 24 doc sources). The
semantic strategy performs one model encode per (topic group x node) with no
query-embedding cache, so cost grows multiplicatively with documentation size.
Restricting verbs to referential matching already cut the node count for that
loop; caching the encoded signature per node would cut it much further.

---

## 2026-07-29 — Corpus introduced; nine defects fixed

The unit suite was fully green (250 passed, 1 skipped) while the tool reported
**98.3% coverage** for `tests/fixtures/simple_test_app`, whose README documents
five concepts and none of its eleven endpoints. Mechanics tests cannot catch
that, so this session added a corpus of seven repositories with hand-written
answer keys and a harness that scores DocZot's documented/undocumented verdict
per operation against the human label.

### Result

```
                          baseline          after
corpus cases              2/7 passing       7/7 passing
classification mean F1    0.60              1.00
invented coverage          6                 0
missed coverage            4                 0
known-failing cases        1                 0
unit suite                250 passed        321 passed
```

`simple_test_app`, the repo that motivated the work, now reports **0% operation
coverage (0/11)** instead of 98.3%.

### The central change: attribution over proximity

The old matcher credited an operation as documented when nearby prose scored
above `SEMANTIC_THRESHOLD = 0.35` — close to noise for `all-mpnet-base-v2`. It
also grouped every non-README file into a single topic and skipped the
section-equality filter for those, so a passage about purchasing tickets could
credit `DELETE /tickets/{ticket_id}`.

Similarity can establish that a document is *about* tickets. It cannot establish
that a specific operation is documented. Operations now require **referential
evidence**:

- HTTP endpoints are covered only by `direct_reference`, which requires the
  method and path to appear together on one line.
- CLI commands, which have no method or path to anchor on, are covered by
  `cli_direct_reference` — the command name appearing verbatim, matched
  word-bounded against section headers as well as body prose.
- Semantic and title matching remain, restricted to nouns and concepts, where
  topical prose genuinely is the documentation.

This single change removed all six invented-coverage cases. It also made the
containment problem mostly self-solving: an unrelated parent repo's docs cannot
fake endpoint coverage, because they never name the endpoints.

### Defects fixed

**1. `_singularize` truncated every noun whose stem ends in "e".**
The `-es` branch stripped two characters unconditionally: `warehouses` →
`warehous`, `invoices` → `invoic`, `venues` → `venu`, `workspaces` →
`workspac`. A trailing `es` is a two-letter suffix only after a stem that cannot
take a bare `s` (sibilants, affricates, double-s, `-oes`). The `-uses` group is
genuinely ambiguous — `buses` → `bus` but `warehouses` → `warehouse` — and is
resolved with an explicit set of `-us` singulars.

The rules were duplicated three times (`scanner._singularize`, an inline copy in
`analyzer_v2.extract_nouns_from_path`, and `doc_graph._singularize`) and had
drifted, so a path segment and a model name for one entity reduced to different
spellings and became two nodes. `extract_nouns_from_path` now delegates to the
canonical helper. `scanner.py:47`. Tests: `TestSingularize`.

Fixing this also restored the missing `document part_of workspace` edge, which
had failed because `detect_part_of_relationships` compares singularized
segments against noun names.

**2. `router.get("")` on a prefixed router reported a trailing slash.**
FastAPI mounts an empty route path at the bare prefix, so
`@router.get("")` on `APIRouter(prefix="/workspaces")` serves `/workspaces`; the
join produced `/workspaces/`. `scanner.py:566`. Tests:
`TestRouterPrefixPathJoining`.

**3. Cross-file `include_router` prefixes were never applied.**
`_extract_router_prefixes` took a single `ast.Module`, so a prefix applied at
include time in one file could not combine with an `APIRouter(prefix=...)` in
another. Paths came out as `/invoices/` for a service serving
`/api/v1/invoices/`, and all three documented endpoints in that case were
consequently misreported as gaps (F1 0.0).

New `build_router_prefix_map()` does a project-wide pre-pass: it resolves
`include_router` arguments through import aliases (both
`from x import router` and `from pkg import mod` + `mod.router`), builds the
include graph, and accumulates prefixes from each FastAPI app downward.
`scan_directory` feeds the result to `scan_python_file`. This is the
full-stack-fastapi-template layout, so the canonical integration target was
being read wrong. `scanner.py:395`.

**4. Coverage was topic-weighted, so concept sections lifted the number.**
`coverage_stats()` counted checklist topics, mixing endpoint topics with
concept and task topics; a repo with well-titled concept sections scored well
while its API stayed undocumented. `DriftReport` now carries
`operations_total` / `operations_covered` / `uncovered_operations`, counted over
the graph's actual operations, and exposes
`operation_coverage_percentage()` — the figure the CLI shows first, alongside a
by-name list of undocumented operations. The old `coverage_percentage` is
retained because the dashboard and exports read it. `models_v2.py:453`.

This made the corpus bands exact rather than approximate: the earlier wide
tolerances (`30-70`, `20-90`) existed only because the metric was ill-defined.
Each case now asserts a single value derived directly from its labels — 3 of 6
operations documented is 50%, not "somewhere between 30 and 70". **These bands
were tightened, not loosened**; the notes in each `expected.json` record why.

**5. `commander` CLI framework was unsupported.**
`detect_cli_framework` identified commander correctly but
`scan_nodejs_directory` returned `[]` for it, so a project using the most widely
used Node CLI library produced an empty graph and no coverage signal.
`scan_commander_commands()` now parses `program.command().description().option()`
chains, including inline arguments (`command('migrate <target>')`), long/short
flag specs, and `.argument()` calls. `scanner_nodejs.py:196`.

**6. Concept extraction captured sentence fragments.**
Definition-pattern matching produced concepts named *Projects Are Containers
For Tasks And*, *Check If Service*, *User Must*. These pollute the graph, the
checklist and every export, and because no documentation ever matches them they
appear as permanent phantom gaps. `is_concept_name_plausible()` rejects names
over four words, names containing function words, names beginning with a bare
verb, and names ending in punctuation. Applied to both the docstring and
markdown extractors. `simple_test_app` went from 9 concepts to 3, all
legitimate. `analyzer_v2.py:614`. Tests: `TestConceptNamePlausibility`.

**7. Plural concepts shadowed existing nouns.**
A `## Users` section minted `concept:users` alongside `noun:user`, splitting one
entity into two nodes — listed twice in the checklist, counted twice in
coverage. Concepts whose singular form matches a known noun are now dropped in
favour of the noun, which is the better node because verbs attach to it.
`analyzer_v2.py:508`. Tests: `TestConceptNounShadowing`.

**8. Documentation credit escaped the analyzed project.**
`discover_content_inventory` walked to the *git* root and harvested markdown
from every ancestor, so analyzing `tests/fixtures/simple_test_app` credited
DocZot's own `ARCHITECTURE.md`, `docs/DESIGN_V3.md` and `PRODUCT_OVERVIEW.md` —
the direct cause of the 98.3%.

The upward walk itself is correct: projects legitimately keep `docs/` at the
root and code in `backend/app`. The defect was the absence of a boundary. New
`find_doc_scope_root()` stops at the **nearest** enclosing project manifest
(`pyproject.toml`, `package.json`, `go.mod`, …), falling back to the git root
only when none exists. In a monorepo that stops at the component under
analysis; where code is merely nested inside its own project, the nearest
manifest *is* the project root, so both layouts resolve correctly.
`analyzer_v2.py:1046`. Tests: `TestFindDocScopeRoot`.

**9. Ancestor search reached sideways into sibling components.**
Even with a scope boundary, `find_markdown_files` recursed the full subtree of
each ancestor, so ascending one level pulled in every sibling's markdown —
analyzing one corpus fixture picked up a neighbouring fixture's README. An
ancestor now contributes only the markdown at its own level plus its
conventional `docs/` directories. `analyzer_v2.py:1136`. Tests:
`TestAncestorDocFiles`, `TestInventoryContainment`.

**10. Coverage figures were untraceable.**
The 98.3% could not be diagnosed from the number alone. `TopicManifest` gained
`coverage_provenance()` (per-file summary of topics, nodes covered and the
strategies that matched) and `evidence_for(node_id)` (why DocZot thinks one
specific thing is documented). `doczot analyze` and `doczot gaps` print a
**Coverage Sources** block, flagging any source outside the analyzed tree.
Building this first is what made the threshold work measurable instead of
guessed. `models_v2.py:405`.

### Known tradeoffs

- **Verbs now require an explicit method+path mention.** Prose like "to list
  your invoices, call the invoices endpoint" no longer counts. This is
  deliberate — false positives are the worse failure for a gap report — but it
  will read as strict on projects whose docs are narrative rather than
  reference-style. If that proves too tight, the fix is a stronger lexical
  anchor, not a lower similarity threshold.
- **The manifest boundary can under-reach.** A repo with `backend/pyproject.toml`
  and shared docs at the git root will scope to `backend/` and miss the root
  docs. Erring toward under-counting is the right default for a tool whose worst
  failure is inventing coverage, but a `--doc-root` override is the natural
  follow-up.
- `MatchEvidence.strategy` gained `cli_direct_reference`. Any consumer
  exhaustively matching on that literal needs updating.

### Still open

- `compute_drift_report` picks the inventory topic with maximum node overlap, so
  one large catch-all document can absorb many checklist topics and mark them
  `complete`. This inflates the legacy `coverage_percentage` but no longer
  affects the operation figure, which is why it was left.
- Duplicate checklist topic titles: `generate_default_itm` still names both
  `GET /users/{id}/projects` and `GET /users/{id}/projects/{project_id}` "Get
  projects", and lists endpoints under multiple owner entities.
  `max_duplicate_topic_names` is asserted in three cases and passes, so no
  corpus case currently reproduces it.
- `doczot surface/itm/atm/gaps` each re-run the whole pipeline, reloading the
  embedding model.
- `.doczot/manifests.db` is checked into git and dirties on every `analyze`.
- No Express/route scanning for Node.js — only CLI frameworks.
