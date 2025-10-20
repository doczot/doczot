# DocZot - Open Source Documentation Coverage for APIs

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Tests](https://img.shields.io/badge/tests-56%20passed-brightgreen)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-91%25-brightgreen)](tests/)

> **Like Codecov, but for API documentation.** Automatically detect undocumented endpoints before they reach production.

**100% Open Source** • Self-host or use our managed service (coming soon)

## Why DocZot?

Every software team faces the same challenge: documentation becomes outdated the moment you write it. DocZot ensures your API docs stay synchronized with your code by:

- 🔍 **Scanning** your codebase for API endpoints (FastAPI supported, more coming)
- 📄 **Analyzing** documentation for coverage gaps
- 🤖 **AI-powered** matching to verify documentation quality (coming soon)
- 💬 **PR comments** with coverage reports (coming soon)

**Everything is open source.** No vendor lock-in. Full transparency.

---

## Quick Start

### Option 1: Self-Host (Free Forever)

```bash
# Clone the repository
git clone https://github.com/yourusername/doczot
cd doczot

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Run tests to verify
pytest

# Run analyzer (when ready)
python -m doczot_analyzer /path/to/your/project
```

[Full self-hosting guide →](docs/SELF_HOSTING.md)

### Option 2: Managed Service (Coming Soon)

1. Install our GitHub App
2. Select your repositories
3. Open a PR - DocZot comments automatically

**Free for public repos** • From $29/month for private repos

[Join the waitlist →](#)

---

## Status

🚧 **Week 1-2: MVP Development** - Building core analysis engine

### Completed
- [x] Project structure
- [x] Code scanner (FastAPI endpoint detection)
- [x] Documentation parser (Markdown)
- [x] Data models
- [x] Test suite (56 tests, 91% coverage)
- [ ] LLM integration (Week 2)
- [ ] CLI interface (Week 3)
- [ ] GitHub App (Week 4+)

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

## Why Open Source vs Managed Service?

| Feature | Self-Hosted (Free) | Managed Service |
|---------|-------------------|-----------------|
| **All Features** | ✅ | ✅ |
| **Cost** | $0 (+ infrastructure) | From $29/month |
| **Setup Time** | ~30 minutes | 2 minutes |
| **Maintenance** | You manage | We manage |
| **Updates** | Manual | Automatic |
| **Support** | Community | Priority email |
| **Uptime** | Your responsibility | 99.9% SLA |

**Most teams prefer:** Paying $29-99/month instead of managing infrastructure.

But the choice is yours. Everything is open source, and we'll never lock you in.

---

## Philosophy

DocZot is **100% open source** because we believe in transparency and giving developers full control. Our business model follows companies like GitLab, Plausible, and PostHog: the code is free, but most teams prefer paying for a managed service rather than maintaining infrastructure themselves.

When you self-host, you get:
- ✅ All features, no limitations
- ✅ Full control over your data
- ✅ No vendor lock-in
- ✅ Community support

When you use our managed service, you get:
- ✅ Zero maintenance
- ✅ Automatic updates
- ✅ Priority support
- ✅ Just works

We win by making DocZot so good that teams *want* to pay for the managed experience.

---

## Contributing

We welcome contributions! Whether you're fixing bugs, adding features, or improving docs, we'd love your help.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines (coming soon).

---

## License

DocZot is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

This means you can:
- ✅ Use it commercially
- ✅ Modify it
- ✅ Distribute it
- ✅ Use it privately

With minimal restrictions. Full freedom.
