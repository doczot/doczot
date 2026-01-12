#!/bin/bash
# Setup test repositories for DocZot validation
# See docs/TESTING_STRATEGY.md for detailed testing plan

set -e

echo "Setting up DocZot test repositories..."
echo ""

# Create test_repos directory if it doesn't exist
mkdir -p test_repos
cd test_repos

# Function to clone or update repo
clone_or_update() {
    local url=$1
    local dir=$2
    local name=$3

    if [ -d "$dir" ]; then
        echo "✓ $name already exists at $dir"
    else
        echo "Cloning $name..."
        git clone "$url" "$dir"
        echo "✓ $name cloned successfully"
    fi
    echo ""
}

# Gold Standard - Ideal structure with complete documentation
clone_or_update \
    "https://github.com/seapagan/fastapi-template" \
    "seapagan-fastapi-template" \
    "Gold Standard (seapagan/fastapi-template)"

# Stress Test - Modern patterns (Pydantic V2, FastCRUD)
clone_or_update \
    "https://github.com/benavlabs/FastAPI-boilerplate" \
    "benavlabs-fastapi-boilerplate" \
    "Stress Test (benavlabs/FastAPI-boilerplate)"

# Micro Test - Fast smoke test
clone_or_update \
    "https://github.com/mehmetext/fastapi-blog-api" \
    "fastapi-blog-api" \
    "Micro Test (mehmetext/fastapi-blog-api)"

echo "=========================================="
echo "Test repository setup complete!"
echo ""
echo "Existing repositories:"
echo "  ✓ full-stack/ (full-stack-fastapi-template)"
echo "  ✓ fastapi-users/ (fastapi-users)"
echo "  ✓ realworld/ (fastapi-realworld-example-app)"
echo ""
echo "Newly added:"
echo "  ✓ seapagan-fastapi-template/"
echo "  ✓ benavlabs-fastapi-boilerplate/"
echo "  ✓ fastapi-blog-api/"
echo ""
echo "Next steps:"
echo "  1. Run smoke test: doczot analyze test_repos/fastapi-blog-api"
echo "  2. Run gold standard: doczot analyze test_repos/seapagan-fastapi-template"
echo "  3. See docs/TESTING_STRATEGY.md for full validation plan"
echo "=========================================="
