"""Documentation parser for extracting API endpoint references from markdown.

This module scans markdown files to find references to API endpoints.
Based on docs/features/documentation-parsing.md specification.

Uses markdown-it-py for parsing markdown content.
"""

import re
from pathlib import Path
from typing import List

from markdown_it import MarkdownIt
from doczot_analyzer.models import DocReference


# HTTP methods to detect (R2)
HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}

# Files to skip (R1)
SKIP_FILES = {
    "CHANGELOG.md",
    "LICENSE.md",
    "CONTRIBUTING.md",
}

# Translation directories to skip (common language codes)
TRANSLATION_DIRS = {
    "zh", "ja", "pt", "de", "fr", "ru", "es", "ko", "vi", "uk", "em",
    "fa", "tr", "it", "nl", "pl", "ar", "hi", "id", "th", "cs", "sv",
    "zh-hant", "zh-hans", "pt-br", "es-es", "en-gb",
}


def parse_markdown_file(markdown_content: str, file_path: str) -> List[DocReference]:
    """Parse markdown file for API endpoint references.

    Recognizes these patterns (R2):
    - Code blocks: ```GET /api/users```
    - Inline code: `GET /api/users`
    - Plain text: GET /api/users
    - Tables: | GET | /users | Description |

    Args:
        markdown_content: Markdown content as string
        file_path: Path to the markdown file (for reference)

    Returns:
        List of DocReference objects with endpoint mentions
    """
    if not markdown_content or not markdown_content.strip():
        return []

    # Parse markdown to get structure
    md = MarkdownIt()
    tokens = md.parse(markdown_content)

    # Track current section heading
    current_heading = None
    references = []

    # Also parse raw content line by line to catch all patterns
    lines = markdown_content.split('\n')

    # Track if we're inside an HTML comment
    in_comment = False

    for line_num, line in enumerate(lines, start=1):
        # Handle HTML comments (EC3)
        if '<!--' in line:
            in_comment = True
        if '-->' in line:
            in_comment = False
            continue
        if in_comment:
            continue

        # Update current heading if this line is a heading
        if line.startswith('#'):
            current_heading = line.lstrip('#').strip()
            continue

        # Extract endpoint references from this line
        endpoints = _extract_endpoints_from_text(line)

        if endpoints:
            paths = endpoints.get('paths', [])
            methods = endpoints.get('methods', [])

            if paths or methods:
                references.append(
                    DocReference(
                        file_path=file_path,
                        content=line.strip(),
                        mentioned_paths=paths,
                        mentioned_methods=methods,
                        section_heading=current_heading,
                        line_number=line_num
                    )
                )

    # Deduplicate references that are on the same line or very similar
    # Keep unique references based on content
    unique_refs = []
    seen_content = set()

    for ref in references:
        key = (ref.line_number, tuple(ref.mentioned_paths), tuple(ref.mentioned_methods))
        if key not in seen_content:
            seen_content.add(key)
            unique_refs.append(ref)

    return unique_refs


def _extract_endpoints_from_text(text: str) -> dict:
    """Extract endpoint paths and HTTP methods from text.

    Handles various formats (R2, R4):
    - GET /users
    - POST /api/v1/users
    - PUT /users/{id}
    - DELETE /orgs/{org_id}/repos/{repo_id}
    - GET /users/:id (colon-style params)

    Args:
        text: Text line to parse

    Returns:
        Dict with 'paths' and 'methods' lists
    """
    paths = []
    methods = []

    # Pattern to match HTTP method followed by a path
    # Matches: GET /users, POST /api/v1/users/{id}, etc.
    # Path can contain: letters, numbers, /, {, }, _, -, :
    # Also handles table cells with | separators
    # Use case-insensitive flag for methods
    pattern = r'\b(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s*\|?\s*(/[a-zA-Z0-9/_\-{}:]*)'

    matches = re.findall(pattern, text, re.IGNORECASE)

    for method, path in matches:
        # Normalize method to uppercase
        method_upper = method.upper()

        if method_upper in HTTP_METHODS:
            methods.append(method_upper)

            # Clean up the path
            path = path.rstrip('.,;:')  # Remove trailing punctuation

            if path:
                paths.append(path)

    # Also try to extract paths from inline code or tables
    # Match paths in backticks or table cells: /users, /api/v1/users/{id}
    path_only_pattern = r'[`|]\s*(/[a-zA-Z0-9/_\-{}:]+)\s*[`|]'
    path_matches = re.findall(path_only_pattern, text)

    for path in path_matches:
        path = path.rstrip('.,;:')
        if path and path not in paths:
            # Only add if it looks like an API path (has at least one /)
            if path.count('/') > 0:
                paths.append(path)

    return {
        'paths': list(dict.fromkeys(paths)),  # Remove duplicates while preserving order
        'methods': list(dict.fromkeys(methods))
    }


def find_markdown_files(directory: str) -> List[str]:
    """Find all markdown files in directory following R1 rules.

    Searches in:
    - All README*.md files (recursively)
    - /docs/**/*.md
    - /documentation/**/*.md
    - Common doc files (development.md, deployment.md, API.md, etc.)
    - *api*.md files

    Skips:
    - CHANGELOG.md
    - LICENSE.md
    - CONTRIBUTING.md
    - Hidden files (starting with .)
    - Translation directories (zh/, ja/, pt/, etc.)

    Args:
        directory: Root directory to search

    Returns:
        List of absolute file paths to markdown files
    """
    directory_path = Path(directory)

    if not directory_path.exists():
        return []

    markdown_files = []

    # Common documentation filenames to always include
    COMMON_DOC_FILES = {
        'development.md', 'deployment.md', 'api.md', 'guide.md',
        'tutorial.md', 'setup.md', 'install.md', 'installation.md',
        'getting-started.md', 'quickstart.md', 'usage.md'
    }

    # Find all .md files recursively
    for md_file in directory_path.rglob("*.md"):
        # Skip hidden files
        if any(part.startswith('.') for part in md_file.parts):
            continue

        # Skip files in skip list
        if md_file.name in SKIP_FILES:
            continue

        # Skip translation directories (e.g., docs/zh/, docs/ja/, etc.)
        # Check if any part of the path is a translation directory
        parts = md_file.parts
        if any(part in TRANSLATION_DIRS for part in parts):
            continue

        # Accept files if they match any of these criteria:

        # 1. All README files (README.md, backend/README.md, etc.)
        if md_file.name.upper().startswith('README'):
            markdown_files.append(str(md_file))
            continue

        # 2. In docs/ or documentation/ directories
        if 'docs' in parts or 'documentation' in parts:
            markdown_files.append(str(md_file))
            continue

        # 3. Common documentation files (case-insensitive)
        if md_file.name.lower() in COMMON_DOC_FILES:
            markdown_files.append(str(md_file))
            continue

        # 4. Filename contains 'api'
        if 'api' in md_file.name.lower():
            markdown_files.append(str(md_file))
            continue

        # 5. Direct child of root directory (not in subdirectories, except docs/)
        # This catches other files like visible.md in the root
        try:
            relative = md_file.relative_to(directory_path)
            # If file is directly in root (no parent dirs except root)
            if len(relative.parts) == 1:
                markdown_files.append(str(md_file))
        except ValueError:
            pass

    return markdown_files


def scan_documentation(directory: str) -> List[DocReference]:
    """Scan all markdown documentation in directory.

    Finds all markdown files using find_markdown_files(),
    then parses each one for endpoint references.

    Args:
        directory: Root directory to scan

    Returns:
        List of all DocReference objects found across all files
    """
    markdown_files = find_markdown_files(directory)

    all_references = []

    for file_path in markdown_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Use relative path from the scan directory for cleaner output
            try:
                relative_path = Path(file_path).relative_to(directory)
                display_path = str(relative_path)
            except ValueError:
                # If relative path fails, use absolute
                display_path = file_path

            references = parse_markdown_file(content, display_path)
            all_references.extend(references)

        except (OSError, UnicodeDecodeError):
            # Skip files that can't be read
            continue

    return all_references
