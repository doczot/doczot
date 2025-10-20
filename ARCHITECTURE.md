# DocZot Architecture

## Project Structure

```
doczot/
├── doczot_analyzer/          # Core product (SHIPS)
│   ├── __init__.py
│   ├── models.py            # Pydantic data models
│   ├── scanner.py           # FastAPI endpoint detection
│   ├── docs_parser.py       # Markdown documentation parser
│   └── tests/               # Test suite
│
├── docs/                     # Documentation (SHIPS)
│   ├── features/            # Feature specifications
│   ├── BACKLOG.md          # Product backlog (future ideas)
│   └── DATASET_LICENSES.md # License tracking for research
│
├── research/                 # Development tools (GITIGNORED)
│   ├── build_dataset.py    # Extract pairs from repos
│   ├── rate_pairs.py        # Rating UI for golden dataset
│   ├── sample_pairs.py      # Sample large datasets
│   └── find_repos.md        # Repo recommendations
│
├── scripts/                  # Empty (moved to research/)
│
└── pyproject.toml           # Package configuration
```

## What Ships vs What Stays Internal

### Ships to Users (Public)
- `/doczot_analyzer/` - Core analysis engine
- `/docs/features/` - Feature specifications
- `/tests/` - Test suite
- `README.md` - Project documentation
- `LICENSE` - Apache 2.0

### Internal Development (Gitignored)
- `/research/` - Dataset building tools
- `rating_pairs.json` - Unrated endpoint/doc pairs
- `golden_dataset.json` - Your expert ratings
- `~/doczot-data/` - External repo clones

## Core Components

### 1. Models (`doczot_analyzer/models.py`)
Pydantic v2 models for type safety:
- `Parameter` - Function parameter metadata
- `Endpoint` - Detected API endpoint
- `DocReference` - Documentation mention
- `ScanResult` - Scan results
- `AnalysisReport` - Coverage report

### 2. Scanner (`doczot_analyzer/scanner.py`)
AST-based FastAPI endpoint detection:
- Parses Python files for `@app.get()` patterns
- Extracts method, path, parameters, docstring
- Smart parameter location detection (path/query/body)
- Zero external dependencies (uses built-in `ast`)

### 3. Docs Parser (`doczot_analyzer/docs_parser.py`)
Markdown documentation scanner:
- Regex-based endpoint extraction
- Multiple formats (code blocks, inline, tables)
- Context capture (section headings, line numbers)
- Uses markdown-it-py

## Development Workflow

### Building the Product
```bash
# Run tests
pytest -v --cov

# Type checking
mypy doczot_analyzer

# Formatting
black doczot_analyzer
ruff doczot_analyzer
```

### Research/Validation (Internal)
```bash
# Build golden dataset
python research/build_dataset.py ~/doczot-data/repos/some-project

# Rate pairs
python research/rate_pairs.py

# Validate LLM accuracy (coming soon)
python research/validate_llm.py
```

## Design Principles

1. **Separation of Concerns**
   - Product code is clean, tested, documented
   - Research code is gitignored, experimental
   - No research artifacts in shipped code

2. **Test-First Development**
   - Write specs → Write tests → Implement
   - 91% code coverage on core modules
   - All examples from specs have tests

3. **Type Safety**
   - Full type hints everywhere
   - Pydantic for runtime validation
   - mypy for static checking

4. **Zero Config**
   - Works out of the box
   - Smart defaults
   - Conventional directory discovery

## Future Architecture

### Week 2-3: LLM Integration
```python
doczot_analyzer/
├── llm/
│   ├── matcher.py          # LLM-based endpoint/doc matching
│   ├── classifier.py       # Confidence scoring
│   └── prompts.py          # Prompt templates
```

### Week 4+: CLI & Reporting
```python
doczot_analyzer/
├── cli.py                  # Command-line interface
├── reporters/
│   ├── markdown.py         # Markdown reports
│   ├── json.py            # JSON output
│   └── html.py            # HTML reports
```

## External Data

All external data lives in `~/doczot-data/`:
```
~/doczot-data/
├── repos/                  # Cloned repos for analysis
│   ├── fastapi/           # FastAPI (MIT)
│   ├── project1/
│   └── project2/
└── datasets/              # Golden datasets (future)
    └── golden_v1.json
```

This keeps the project repo clean and ensures no accidental commits of external code.

## License Strategy

- **DocZot**: Apache 2.0 (permissive, business-friendly)
- **Research data**: Only use MIT/Apache 2.0 licensed repos
- **Golden dataset**: Your proprietary annotations
- **Documentation**: See `docs/DATASET_LICENSES.md`
