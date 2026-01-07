"""Node.js CLI scanner for oclif-based tools like Doc Detective.

Extracts commands, flags, and arguments from oclif command structure.
"""

import json
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class CliCommand:
    """Represents a CLI command."""
    name: str
    description: str
    file_path: str
    line_number: int = 0
    flags: list[dict] = field(default_factory=list)
    args: list[dict] = field(default_factory=list)


def detect_cli_framework(repo_path: str) -> Optional[str]:
    """Detect which CLI framework is used.

    Args:
        repo_path: Path to the repository

    Returns:
        Framework name ('oclif', 'commander', 'yargs') or None
    """
    package_json = Path(repo_path) / "package.json"

    if not package_json.exists():
        return None

    try:
        data = json.loads(package_json.read_text())
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

        if "@oclif/core" in deps or "@oclif/command" in deps:
            return "oclif"
        elif "commander" in deps:
            return "commander"
        elif "yargs" in deps:
            return "yargs"
    except Exception:
        pass

    return None


def scan_oclif_commands(repo_path: str) -> list[CliCommand]:
    """Scan oclif-based CLI for commands.

    Looks for command files in src/commands/ directory.

    Args:
        repo_path: Path to the repository

    Returns:
        List of CliCommand objects
    """
    commands = []
    repo_path = Path(repo_path)

    # Find commands directory
    commands_dir = repo_path / "src" / "commands"
    if not commands_dir.exists():
        return commands

    # Scan .js and .ts files
    for cmd_file in commands_dir.rglob("*"):
        if cmd_file.suffix not in ['.js', '.ts']:
            continue

        if not cmd_file.is_file():
            continue

        try:
            content = cmd_file.read_text(encoding='utf-8')

            # Parse basic structure (simplified - full implementation would use JS parser)
            # Look for: static description = "..."
            description = ""
            if 'static description' in content:
                # Regex to extract description
                match = re.search(r'static\s+description\s*=\s*["\'](.+?)["\']', content, re.MULTILINE)
                if match:
                    description = match.group(1)

            # Command name from file path
            try:
                rel_path = cmd_file.relative_to(commands_dir)
                cmd_name = str(rel_path.with_suffix('')).replace('\\', ':').replace('/', ':')
            except ValueError:
                cmd_name = cmd_file.stem

            command = CliCommand(
                name=cmd_name,
                description=description or f"Command: {cmd_name}",
                file_path=str(cmd_file),
            )
            commands.append(command)

        except Exception:
            continue

    return commands


def scan_yargs_commands(repo_path: str) -> list[CliCommand]:
    """Scan yargs-based CLI for commands and options.

    Looks for yargs.option() calls in JavaScript/TypeScript files.

    Args:
        repo_path: Path to the repository

    Returns:
        List of CliCommand objects (one per option/flag)
    """
    commands = []
    repo_path = Path(repo_path)

    # Find all JS/TS files that might contain yargs config
    for js_file in repo_path.rglob("*"):
        if js_file.suffix not in ['.js', '.ts']:
            continue

        if not js_file.is_file():
            continue

        try:
            content = js_file.read_text(encoding='utf-8')

            # Skip files that don't use yargs
            if 'yargs' not in content:
                continue

            # Extract option definitions using regex
            # Pattern: .option("name", { ... }) or .option('name', { ... })
            option_pattern = r'\.option\(["\']([^"\']+)["\'],\s*\{[^}]*description:\s*["\']([^"\']*)["\']'
            matches = re.finditer(option_pattern, content, re.MULTILINE | re.DOTALL)

            for match in matches:
                option_name = match.group(1)
                description = match.group(2)

                command = CliCommand(
                    name=f"--{option_name}",
                    description=description or f"Option: {option_name}",
                    file_path=str(js_file),
                    flags=[{
                        "name": option_name,
                        "description": description
                    }]
                )
                commands.append(command)

        except Exception:
            continue

    # If we found options, create a main command entry
    if commands:
        # Group all options under a main command
        main_command = CliCommand(
            name="doc-detective",
            description="Documentation testing CLI tool",
            file_path=str(repo_path),
            flags=[{
                "name": cmd.name.lstrip('-'),
                "description": cmd.description
            } for cmd in commands]
        )
        return [main_command]

    return []


def scan_nodejs_directory(repo_path: str) -> list[CliCommand]:
    """Scan a Node.js repository for CLI commands.

    Args:
        repo_path: Path to the repository

    Returns:
        List of CliCommand objects
    """
    framework = detect_cli_framework(repo_path)

    if framework == "oclif":
        return scan_oclif_commands(repo_path)
    elif framework == "yargs":
        return scan_yargs_commands(repo_path)
    elif framework == "commander":
        # Placeholder for future implementation
        return []
    else:
        return []
