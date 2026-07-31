# Accuracy Corpus

Hand-labeled test repositories with answer keys, used to measure whether DocZot
**correctly identifies content coverage** — not merely whether it runs without
crashing.

The existing unit suite (`doczot_analyzer/tests/test_*.py`) checks mechanics.
This corpus checks *judgment*: given a repo whose documentation state a human
has labeled, does DocZot arrive at the same answer?

## Layout

```
corpus/
├── _harness.py          # runner + scorer
├── cases/
│   └── <case_name>/
│       ├── expected.json   # the answer key (hand-written, authoritative)
│       └── repo/           # the fixture repository to analyze
└── README.md
```

## Why each case is copied to a temp dir

`discover_content_inventory()` walks *up* from the scan path to the enclosing
git root and treats every markdown file it finds along the way as candidate
documentation. If a case were analyzed in place, DocZot's own `README.md`,
`ARCHITECTURE.md` and `docs/*.md` would be credited as coverage for the fixture,
which makes every measurement meaningless.

The harness therefore copies `repo/` into an isolated temp directory and creates
a `.git` marker inside it, so the git-root walk terminates at the fixture. This
mirrors how a real user analyzes a real repository.

## Answer key schema

Every field is optional; the harness only scores what a case declares. This lets
a case stay narrowly focused (e.g. a Node.js case need not label edges).

| Field | Meaning |
|---|---|
| `name`, `description` | Documentation for humans reading failures. |
| `repo_type` | Expected result of `detect_repo_type()` (`python` / `nodejs`). |
| `endpoints` | Exact set of `{method, path}` the scanner must find. Scored as precision/recall — extras are as much a bug as misses. |
| `cli_commands` | Exact set of CLI command names (Node.js cases). |
| `nouns` | Exact set of expected noun names. |
| `required_concepts` | Concepts that must be present (case-insensitive). |
| `forbidden_concepts` | Strings that must **not** appear as concepts. Guards against sentence-fragment noise like `"user must"`. |
| `constraints` | `{method, path, type}` triples the constraint extractor must find. |
| `edges` | `{type, source, target}` triples using raw node IDs. |
| `documented_endpoints` | **The core label.** Endpoints a human judges to be genuinely documented. |
| `undocumented_endpoints` | Endpoints a human judges to be genuinely undocumented. Must be disjoint from the above; together they should cover `endpoints`. |
| `coverage_percentage` | `{min, max}` band the reported coverage figure must land in. |
| `max_duplicate_topic_names` | Upper bound on repeated checklist topic titles. |

`documented_endpoints` / `undocumented_endpoints` are the labels that matter
most. The harness converts them into a binary classification problem — for each
endpoint, did DocZot credit it as covered? — and reports precision, recall and
F1 against the human label. A tool that reports a plausible-looking coverage
*percentage* while classifying individual endpoints wrongly will fail here even
though the headline number looks fine.

## Adding a case

1. Create `cases/<name>/repo/` containing a small but realistic project.
2. Read the code and docs yourself and write `expected.json` by hand. **Do not
   generate the answer key by running DocZot** — that would encode current
   behavior as correct and defeat the entire purpose.
3. Run `python -m doczot_analyzer.tests.corpus._harness --case <name>`.
4. Any disagreement is either a bug in DocZot or an error in your label. Decide
   which, deliberately.

## Running

```bash
# Full corpus, human-readable report
python -m doczot_analyzer.tests.corpus._harness

# One case, verbose
python -m doczot_analyzer.tests.corpus._harness --case fastapi_partial -v

# Machine-readable, for diffing between runs
python -m doczot_analyzer.tests.corpus._harness --json report.json
```

The corpus also runs under pytest via `test_corpus_accuracy.py`.
