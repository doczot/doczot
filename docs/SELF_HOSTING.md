# Self-Hosting DocZot

This guide will help you self-host DocZot on your own infrastructure.

## Why Self-Host?

Self-hosting gives you:
- ✅ **Full control** over your data
- ✅ **Zero recurring costs** (just infrastructure)
- ✅ **Complete customization** ability
- ✅ **No vendor lock-in**

## Prerequisites

- Python 3.11 or higher
- Git
- (Optional) Docker for containerized deployment

## Quick Start (Local Development)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/doczot.git
cd doczot
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip and install dependencies
pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"
```

### 3. Verify Installation

```bash
# Run tests
pytest

# Check coverage
pytest --cov=doczot_analyzer --cov-report=html
```

### 4. Run the Analyzer

```bash
# Analyze a FastAPI project
python -m doczot_analyzer /path/to/your/fastapi/project

# (Once CLI is ready) Use the CLI
doczot analyze /path/to/project
doczot report --format markdown
```

---

## Production Deployment Options

### Option 1: Docker (Recommended)

**Coming Soon:** Full Docker setup with docker-compose.yml

```bash
# Clone and configure
git clone https://github.com/yourusername/doczot.git
cd doczot
cp .env.example .env
# Edit .env with your settings

# Run with Docker Compose
docker-compose up -d
```

### Option 2: Traditional Server

#### Requirements
- Ubuntu 20.04+ or similar Linux distribution
- Python 3.11+
- systemd for process management
- nginx for reverse proxy (optional)

#### Setup Steps

1. **Install Python 3.11**
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip
```

2. **Clone and Install**
```bash
cd /opt
sudo git clone https://github.com/yourusername/doczot.git
cd doczot
sudo python3.11 -m venv venv
sudo venv/bin/pip install -e .
```

3. **Configure Environment**
```bash
sudo cp .env.example .env
sudo nano .env
# Add your configuration
```

4. **Create systemd Service**
```bash
sudo nano /etc/systemd/system/doczot.service
```

Add:
```ini
[Unit]
Description=DocZot Documentation Coverage Analyzer
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/doczot
Environment="PATH=/opt/doczot/venv/bin"
ExecStart=/opt/doczot/venv/bin/python -m doczot_analyzer
Restart=always

[Install]
WantedBy=multi-user.target
```

5. **Start Service**
```bash
sudo systemctl daemon-reload
sudo systemctl enable doczot
sudo systemctl start doczot
sudo systemctl status doczot
```

### Option 3: GitHub Actions (CI/CD)

Run DocZot as part of your CI pipeline:

```yaml
# .github/workflows/doczot.yml
name: Documentation Coverage

on:
  pull_request:
    branches: [main]

jobs:
  doczot:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install DocZot
        run: |
          pip install git+https://github.com/yourusername/doczot.git

      - name: Run DocZot
        run: |
          doczot analyze . --format json > coverage.json
          doczot report --format markdown > coverage.md

      - name: Comment on PR
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs');
            const coverage = fs.readFileSync('coverage.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: coverage
            });
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# API Keys (for LLM-powered analysis)
ANTHROPIC_API_KEY=your_api_key_here

# Analysis Settings
DOCZOT_MIN_COVERAGE=80
DOCZOT_FAIL_ON_MISSING=true

# Output Settings
DOCZOT_OUTPUT_FORMAT=markdown
DOCZOT_REPORT_PATH=./docs-coverage.md
```

### Configuration File

Alternatively, use `doczot.config.json`:

```json
{
  "scan": {
    "include": ["*.py"],
    "exclude": ["tests/*", "venv/*"],
    "frameworks": ["fastapi"]
  },
  "docs": {
    "paths": ["docs/**/*.md", "README.md"],
    "formats": ["markdown"]
  },
  "analysis": {
    "min_coverage": 80,
    "fail_on_missing": true,
    "llm_enabled": true
  },
  "output": {
    "format": "markdown",
    "path": "./docs-coverage.md"
  }
}
```

---

## Updating

### Local Development

```bash
cd doczot
git pull origin main
source venv/bin/activate
pip install -e ".[dev]"
pytest  # Verify everything still works
```

### Docker

```bash
cd doczot
docker-compose down
git pull origin main
docker-compose build
docker-compose up -d
```

### Production Server

```bash
cd /opt/doczot
sudo git pull origin main
sudo venv/bin/pip install -e .
sudo systemctl restart doczot
```

---

## Monitoring and Maintenance

### Logs

**Docker:**
```bash
docker-compose logs -f doczot
```

**systemd:**
```bash
journalctl -u doczot -f
```

### Health Checks

```bash
# Check service status
systemctl status doczot

# Test analyzer
python -m doczot_analyzer --version
python -m doczot_analyzer --help
```

### Backups

**Important files to back up:**
- `.env` - Your configuration
- `doczot.config.json` - Custom settings
- Any custom scripts or integrations

**Not needed:**
- `venv/` - Can be recreated
- `__pycache__/` - Generated files
- `.pytest_cache/` - Test artifacts

---

## Troubleshooting

### Common Issues

**Import errors:**
```bash
# Reinstall dependencies
pip install -e ".[dev]"
```

**Permission errors:**
```bash
# Fix ownership
sudo chown -R www-data:www-data /opt/doczot
```

**Python version issues:**
```bash
# Verify Python version
python --version  # Should be 3.11+
```

### Getting Help

- 📖 [Documentation](https://docs.doczot.com)
- 💬 [GitHub Discussions](https://github.com/yourusername/doczot/discussions)
- 🐛 [Report Issues](https://github.com/yourusername/doczot/issues)
- 📧 Community support: community@doczot.com

---

## Migration to Managed Service

If you decide self-hosting isn't for you, we make migration easy:

1. Sign up at [app.doczot.com](https://app.doczot.com)
2. Install our GitHub App
3. Your settings and configuration are automatically imported
4. No data migration needed - we scan directly from your repos

**You can switch back to self-hosting anytime.** No lock-in.

---

## Cost Comparison

**Self-Hosting Costs (Estimated):**
- Small VPS (2GB RAM): $10-20/month
- Your time (setup): 2-4 hours ($200-800)
- Your time (maintenance): 1-2 hours/month ($100-400/month)
- **Total Year 1:** $1,500-$5,000 (mostly time)

**Managed Service:**
- Solo plan: $29/month ($348/year)
- Team plan: $99/month ($1,188/year)
- **Total Year 1:** $348-1,188 (zero time)

Self-hosting makes sense if:
- ✅ You have strict data residency requirements
- ✅ You enjoy infrastructure management
- ✅ You have free infrastructure available
- ✅ You want to customize heavily

Managed service makes sense if:
- ✅ You value your time
- ✅ You want zero maintenance
- ✅ You need guaranteed uptime
- ✅ You want priority support

**Both options include all features.** Choose what fits your needs.
