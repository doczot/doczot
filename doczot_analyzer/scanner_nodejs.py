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
        # Find the main entry point file for better source reference
        main_file = str(repo_path)
        potential_entries = [
            repo_path / "src" / "index.js",
            repo_path / "src" / "cli.js",
            repo_path / "index.js",
            repo_path / "cli.js",
        ]
        for entry in potential_entries:
            if entry.exists():
                main_file = str(entry)
                break

        # Group all options under a main command
        main_command = CliCommand(
            name="doc-detective",
            description="Documentation testing CLI tool",
            file_path=main_file,
            line_number=1,  # Set to 1 instead of 0/None
            flags=[{
                "name": cmd.name.lstrip('-'),
                "description": cmd.description
            } for cmd in commands]
        )
        return [main_command]

    return []


def scan_commander_commands(repo_path: str) -> list[CliCommand]:
    """Scan a commander-based CLI for commands, options and arguments.

    Commander declares commands as a fluent chain:

        program
          .command('migrate')
          .description('Apply all pending migrations')
          .option('--dry-run', 'Print the plan without applying it')
          .argument('<target>', 'Migration target')

    The chain may be broken across lines and interleaved with other calls, so
    each ``.command(...)`` starts a new command and the ``.description``,
    ``.option`` and ``.argument`` calls that follow — up to the next
    ``.command(...)`` or the end of the statement — belong to it.

    Commander is the most widely used Node CLI library; this branch previously
    returned an empty list, so such projects produced no graph and no coverage
    signal at all.
    """
    commands: list[CliCommand] = []
    repo = Path(repo_path)

    skip_dirs = {"node_modules", ".git", "dist", "build", "coverage", ".next"}

    for js_file in sorted(repo.rglob("*")):
        if js_file.suffix not in ['.js', '.ts', '.mjs', '.cjs']:
            continue
        if not js_file.is_file():
            continue
        try:
            if any(part in skip_dirs for part in js_file.relative_to(repo).parts):
                continue
        except ValueError:
            continue

        try:
            content = js_file.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue

        if 'commander' not in content and '.command(' not in content:
            continue

        commands.extend(_parse_commander_chains(content, str(js_file)))

    # Deduplicate by name, keeping the first (and richest) declaration.
    seen: dict[str, CliCommand] = {}
    for command in commands:
        if command.name not in seen:
            seen[command.name] = command
    return list(seen.values())


# .command('name <arg>') — the name is the first token, the rest are arguments.
_COMMAND_CALL = re.compile(r'\.command\(\s*["\'`]([^"\'`]+)["\'`]')
_DESCRIPTION_CALL = re.compile(r'\.description\(\s*["\'`]([^"\'`]*)["\'`]')
_OPTION_CALL = re.compile(
    r'\.option\(\s*["\'`]([^"\'`]+)["\'`]\s*(?:,\s*["\'`]([^"\'`]*)["\'`])?'
)
_ARGUMENT_CALL = re.compile(
    r'\.argument\(\s*["\'`]([^"\'`]+)["\'`]\s*(?:,\s*["\'`]([^"\'`]*)["\'`])?'
)


def _parse_commander_chains(content: str, file_path: str) -> list[CliCommand]:
    """Split source on .command() calls and parse each resulting chain."""
    commands = []
    matches = list(_COMMAND_CALL.finditer(content))

    for index, match in enumerate(matches):
        # The chain runs to the next .command() call, or to end of file.
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        chain = content[start:end]

        # `.command('migrate <target>')` declares the name plus inline args.
        raw = match.group(1).strip()
        parts = raw.split()
        name = parts[0]
        inline_args = [
            {"name": token.strip('<>[]'), "description": "", "required": token.startswith('<')}
            for token in parts[1:]
        ]

        # A commander program also names itself via .name('tool'); that is the
        # binary, not a subcommand, so only .command() results are collected.
        desc_match = _DESCRIPTION_CALL.search(chain)
        description = desc_match.group(1) if desc_match else ""

        flags = [
            {
                "name": _flag_name(flag.group(1)),
                "description": flag.group(2) or "",
                "spec": flag.group(1),
            }
            for flag in _OPTION_CALL.finditer(chain)
        ]

        args = inline_args + [
            {
                "name": arg.group(1).strip('<>[]'),
                "description": arg.group(2) or "",
                "required": arg.group(1).startswith('<'),
            }
            for arg in _ARGUMENT_CALL.finditer(chain)
        ]

        line_number = content[:match.start()].count('\n') + 1

        commands.append(CliCommand(
            name=name,
            description=description or f"Command: {name}",
            file_path=file_path,
            line_number=line_number,
            flags=flags,
            args=args,
        ))

    return commands


def _flag_name(spec: str) -> str:
    """Extract the canonical long-form name from a commander option spec.

    ``"-d, --dry-run"`` -> ``dry-run``; ``"--steps <n>"`` -> ``steps``.
    """
    for token in spec.split(','):
        token = token.strip()
        if token.startswith('--'):
            return token[2:].split()[0]
    # No long form; fall back to the short flag.
    first = spec.strip().split()[0] if spec.strip() else spec
    return first.lstrip('-')


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
        return scan_commander_commands(repo_path)
    else:
        return []
