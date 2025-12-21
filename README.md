# DocZot - Open Source Documentation Coverage for APIs

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Tests](https://img.shields.io/badge/tests-56%20passed-brightgreen)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-91%25-brightgreen)](tests/)

> **Like Codecov, but for API documentation.** Automatically detect undocumented endpoints before they reach production.

**100% Open Source** • Self-host or use our managed service (coming soon)

## Why DocZot?

Every software team faces the same challenge: documentation becomes outdated the moment you write it. DocZot ensures your API docs stay synchronized with your code by:

- 🔍 **Surface Graph** - Scans your codebase for API endpoints, entities, and their relationships
- 📋 **ITM (Intended Topic Manifest)** - Auto-generates documentation structure: Reference docs, Concept docs, How-to guides
- 📄 **ATM (Actual Topic Manifest)** - Discovers what documentation actually exists
- 📊 **Gap Report** - Shows what's missing between intended and actual coverage
- 🎯 **Interactive Visualizer** - Explore your API surface with hover-to-highlight topic coverage

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

🚀 **v2 Architecture Complete** - Four-layer documentation coverage model

### Completed
- [x] Code scanner with router prefix tracking and entity detection
- [x] Surface Graph (verbs, nouns, edges)
- [x] ITM generation (Reference/Concept/Task topic hierarchy)
- [x] ATM discovery from markdown with semantic search
- [x] Gap Report with coverage stats and sprint planning
- [x] Interactive HTML visualizer with hover-to-highlight
- [x] How-to inference from API patterns (auth, CRUD, account mgmt)
- [x] CLI interface (`doczot analyze`, `doczot visualize`)
- [ ] GitHub App with PR comments (coming soon)
- [ ] LLM-powered doc quality scoring (coming soon)

## Development

This project follows a **docs-first, tests-first** approach:
1. Write feature documentation (`docs/features/`)
2. Write tests (`tests/test_*.py`)
3. Implement code (with Claude Code assistance)
4. Verify tests pass

## Architecture

DocZot uses a **four-layer model** for documentation coverage:

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Surface Graph                                 │
│  - Verbs (API endpoints)                                │
│  - Nouns (entities extracted from paths + code)         │
│  - Edges (verb operates_on noun)                        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 2: ITM (Intended Topic Manifest)                 │
│  - Reference > API > Entity > Endpoints                 │
│  - Concept > Entity (one per noun)                      │
│  - Task > How-tos (auto-inferred journeys)              │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 3: ATM (Actual Topic Manifest)                   │
│  - Discovered from existing markdown docs               │
│  - Matched to surface elements via semantic search      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 4: Gap Report                                    │
│  - Coverage percentage                                  │
│  - Missing/partial/complete topics                      │
│  - Sprint plan for doc improvements                     │
└─────────────────────────────────────────────────────────┘
```

### Key Files

- `doczot_analyzer/scanner.py` - FastAPI endpoint detection with entity extraction (AST-based)
- `doczot_analyzer/analyzer_v2.py` - Surface graph builder, ATM discovery
- `doczot_analyzer/models_v2.py` - Surface, Topic, and Gap models with ITM generation
- `doczot_analyzer/cli_v2.py` - CLI and interactive HTML visualizer
- `doczot_analyzer/docs_parser.py` - Markdown documentation parser
- `doczot_analyzer/vector_store.py` - Semantic search for doc matching

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

DocZot is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. See [LICENSE](LICENSE) for details.

### What this means:

**You can freely:**
- ✅ Use it for personal projects
- ✅ Use it for open source projects
- ✅ Modify and distribute it
- ✅ Run it as a service (with one requirement below)

**The key requirement:**
- 📢 If you run a modified version as a network service, you must make your source code available to users

### Why AGPL?

We chose AGPL to keep DocZot truly open source while ensuring that improvements benefit the entire community. If you build a hosted service using DocZot, your users deserve access to the code - just like you had access to ours.

**This protects:**
- The open source community from proprietary forks
- Your freedom to inspect and modify the tools you use
- Fair competition (everyone plays by the same rules)

**For businesses:** If you need to keep your modifications private, contact us about commercial licensing options (coming soon).
