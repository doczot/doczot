# DocZot Analyzer

LLM-powered documentation coverage analysis for FastAPI projects.

## Status

🚧 **Week 1: MVP Development** - Building core analysis engine

### Completed
- [x] Project structure
- [ ] Code scanner (FastAPI endpoint detection)
- [ ] Documentation parser (Markdown)
- [ ] Data models
- [ ] Test suite
- [ ] LLM integration

## Quick Start
```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run analyzer (when ready)
python -m doczot_analyzer /path/to/project
```

## Development

This project follows a **docs-first, tests-first** approach:
1. Write feature documentation (`docs/features/`)
2. Write tests (`tests/test_*.py`)
3. Implement code (with Claude Code assistance)
4. Verify tests pass

## Architecture

- `doczot_analyzer/scanner.py` - FastAPI endpoint detection (AST-based)
- `doczot_analyzer/docs_parser.py` - Markdown documentation parser
- `doczot_analyzer/models.py` - Pydantic data models
- `doczot_analyzer/tests/` - Comprehensive test suite

## Installation

### Prerequisites
- Python 3.11 or higher
- pip

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd doczot
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Upgrade pip and install build tools:
```bash
pip install --upgrade pip setuptools wheel
```

4. Install the package in editable mode with development dependencies:
```bash
pip install -e .
```

To install with development dependencies (testing, linting, type checking):
```bash
pip install -e ".[dev]"
```

### Troubleshooting

If you encounter issues with pip's build isolation (especially on newer Python versions), try:
```bash
pip install "pip<24" "setuptools==69.5.1"
pip install -e .
```

## License

DocZot is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
