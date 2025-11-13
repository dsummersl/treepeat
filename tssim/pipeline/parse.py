"""Parse stage of the tssim pipeline."""

import logging
from fnmatch import fnmatch
from pathlib import Path
from typing import Literal

from tree_sitter_language_pack import get_parser

from tssim.config import get_settings
from tssim.models import ParsedFile, ParseResult

logger = logging.getLogger(__name__)

# Type alias for supported tree-sitter languages
LanguageName = Literal[
    "python",
    "javascript",
    "markdown",
    "typescript",
    "tsx",
    "java",
    "c",
    "cpp",
    "go",
    "rust",
    "ruby",
    "php",
    "csharp",
    "swift",
    "kotlin",
    "scala",
    "bash",
]

# Mapping of file extensions to tree-sitter language names
LANGUAGE_MAP: dict[str, LanguageName] = {
    ".py": "python",
    ".js": "javascript",
    ".md": "markdown",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "javascript",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sh": "bash",
}


def detect_language(file_path: Path) -> LanguageName | None:
    """
    Detect programming language from file extension.

    Args:
        file_path: Path to the source file

    Returns:
        Language name if detected, None otherwise
    """
    # TODO support a more robust detection mechanism (something like enry maybe or pygments)
    suffix = file_path.suffix.lower()
    return LANGUAGE_MAP.get(suffix)


def read_source_file(file_path: Path) -> bytes:
    """Read source code from file."""
    try:
        return file_path.read_bytes()
    except Exception as e:
        raise ValueError(f"Failed to read file {file_path}: {e}") from e


def parse_source_code(source: bytes, language_name: LanguageName, file_path: Path) -> ParsedFile:
    """Parse source code using tree-sitter."""
    try:
        parser = get_parser(language_name)
    except Exception as e:
        raise RuntimeError(f"Failed to get parser for {language_name}: {e}") from e

    try:
        tree = parser.parse(source)
    except Exception as e:
        raise RuntimeError(f"Failed to parse {file_path}: {e}") from e

    if tree.root_node.has_error:
        logger.warning(f"Parse tree contains errors for {file_path}")

    return ParsedFile(path=file_path, language=language_name, tree=tree, source=source)


def parse_file(file_path: Path) -> ParsedFile:
    """
    Parse a single source file using tree-sitter.

    Args:
        file_path: Path to the source file

    Returns:
        ParsedFile object containing the AST

    Raises:
        ValueError: If language cannot be detected or file cannot be read
        RuntimeError: If parsing fails
    """
    logger.debug(f"Parsing file: {file_path}")

    language_name = detect_language(file_path)
    if not language_name:
        raise ValueError(f"Cannot detect language for file: {file_path}")

    logger.debug(f"Detected language: {language_name}")

    source = read_source_file(file_path)
    parsed = parse_source_code(source, language_name, file_path)

    logger.debug(f"Successfully parsed {file_path}")
    return parsed


def parse_ignore_file(ignore_file: Path) -> list[str]:
    """Parse an ignore file and return list of patterns.

    Args:
        ignore_file: Path to the ignore file (e.g., .gitignore)

    Returns:
        List of ignore patterns (empty lines and comments are filtered out)
    """
    try:
        patterns = []
        with ignore_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    patterns.append(line)
        return patterns
    except Exception as e:
        logger.warning(f"Failed to parse ignore file {ignore_file}: {e}")
        return []


def find_ignore_files(target_path: Path, ignore_file_patterns: list[str]) -> dict[Path, list[str]]:
    """Find all ignore files in the directory hierarchy.

    Args:
        target_path: Root directory to search
        ignore_file_patterns: Glob patterns to find ignore files

    Returns:
        Dictionary mapping directory paths to their ignore patterns
    """
    ignore_files_map: dict[Path, list[str]] = {}

    if not target_path.is_dir():
        return ignore_files_map

    for pattern in ignore_file_patterns:
        for ignore_file in target_path.glob(pattern):
            if ignore_file.is_file():
                patterns = parse_ignore_file(ignore_file)
                if patterns:
                    # Store patterns keyed by the directory containing the ignore file
                    ignore_dir = ignore_file.parent
                    if ignore_dir not in ignore_files_map:
                        ignore_files_map[ignore_dir] = []
                    ignore_files_map[ignore_dir].extend(patterns)
                    logger.debug(f"Loaded {len(patterns)} patterns from {ignore_file}")

    return ignore_files_map


def matches_pattern(file_path: Path, pattern: str, base_path: Path) -> bool:
    """Check if a file matches an ignore pattern.

    Args:
        file_path: Path to check
        pattern: Ignore pattern (supports glob patterns)
        base_path: Base directory for relative pattern matching

    Returns:
        True if the file matches the pattern
    """
    # Handle negation patterns
    if pattern.startswith("!"):
        # Negation patterns are handled separately in should_ignore_file
        return False

    # Get the relative path from the base
    try:
        rel_path = file_path.relative_to(base_path)
    except ValueError:
        # File is not under base_path
        return False

    rel_path_str = str(rel_path)

    # Handle directory-only patterns (ending with /)
    if pattern.endswith("/"):
        pattern = pattern.rstrip("/")
        # Only match directories
        if not file_path.is_dir():
            return False

    # Handle patterns starting with /
    if pattern.startswith("/"):
        # Anchor to base directory
        pattern = pattern.lstrip("/")
        return fnmatch(rel_path_str, pattern)

    # Check if pattern matches the full path or any part of it
    # Pattern can match anywhere in the path
    if fnmatch(rel_path_str, pattern):
        return True

    # Check if pattern matches any component
    if fnmatch(file_path.name, pattern):
        return True

    # Handle ** style patterns
    if "**" in pattern:
        # Convert ** to a regex-like pattern
        pattern_parts = pattern.split("**")
        if len(pattern_parts) == 2:
            prefix, suffix = pattern_parts
            prefix = prefix.strip("/")
            suffix = suffix.strip("/")

            if prefix and suffix:
                # Pattern like "foo/**/bar"
                if fnmatch(rel_path_str, f"{prefix}*{suffix}"):
                    return True
            elif prefix:
                # Pattern like "foo/**"
                if rel_path_str.startswith(prefix):
                    return True
            elif suffix:
                # Pattern like "**/bar"
                if fnmatch(rel_path_str, f"*{suffix}") or fnmatch(file_path.name, suffix):
                    return True

    return False


def should_ignore_file(
    file_path: Path,
    target_path: Path,
    ignore_patterns: list[str],
    ignore_files_map: dict[Path, list[str]],
) -> bool:
    """Check if a file should be ignored based on patterns.

    Args:
        file_path: File to check
        target_path: Root directory being analyzed
        ignore_patterns: Direct ignore patterns from CLI
        ignore_files_map: Map of directory to ignore patterns from ignore files

    Returns:
        True if the file should be ignored
    """
    # Check direct ignore patterns from CLI
    for pattern in ignore_patterns:
        if matches_pattern(file_path, pattern, target_path):
            logger.debug(f"File {file_path} matched CLI ignore pattern: {pattern}")
            return True

    # Check hierarchical ignore patterns from ignore files
    # Walk up the directory tree to find applicable ignore files
    current = file_path.parent
    while True:
        # Check if there are ignore patterns for this directory
        if current in ignore_files_map:
            for pattern in ignore_files_map[current]:
                if matches_pattern(file_path, pattern, current):
                    logger.debug(f"File {file_path} matched ignore pattern '{pattern}' from {current}")
                    return True

        # Stop if we've reached the target path
        if current == target_path:
            break

        # Move up to parent directory
        try:
            if current.parent == current:
                # Reached filesystem root
                break
            current = current.parent
        except Exception:
            break

    return False


def collect_source_files(target_path: Path) -> list[Path]:
    """Collect all source files from a path, applying ignore patterns."""
    # Get ignore patterns from settings
    settings = get_settings()
    ignore_patterns = settings.ignore_patterns
    ignore_file_patterns = settings.ignore_file_patterns

    if target_path.is_file():
        # For a single file, check if it should be ignored
        if ignore_patterns or ignore_file_patterns:
            # Find ignore files relative to the file's directory
            ignore_files_map = find_ignore_files(target_path.parent, ignore_file_patterns)
            if should_ignore_file(target_path, target_path.parent, ignore_patterns, ignore_files_map):
                logger.info(f"File {target_path} is ignored by patterns")
                return []
        return [target_path]

    if target_path.is_dir():
        # Find all ignore files in the directory hierarchy
        ignore_files_map = find_ignore_files(target_path, ignore_file_patterns)

        files: list[Path] = []
        for ext in LANGUAGE_MAP.keys():
            for file in target_path.rglob(f"*{ext}"):
                # Check if file should be ignored
                if not should_ignore_file(file, target_path, ignore_patterns, ignore_files_map):
                    files.append(file)

        logger.info(f"Found {len(files)} source files in directory (after applying ignore patterns)")
        return files

    return []


def parse_files(files: list[Path], result: ParseResult) -> None:
    """Parse a list of files and update the result."""
    for file_path in files:
        try:
            parsed = parse_file(file_path)
            result.parsed_files.append(parsed)
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            result.failed_files[file_path] = str(e)


def parse_path(target_path: Path) -> ParseResult:
    """
    Parse a file or directory of source files.

    Args:
        target_path: Path to a file or directory to parse

    Returns:
        ParseResult containing all parsed files and any failures
    """
    logger.info(f"Starting parse of: {target_path}")

    result = ParseResult()
    files = collect_source_files(target_path)

    if not files:
        logger.error(f"Path does not exist or contains no source files: {target_path}")
        result.failed_files[target_path] = "Path does not exist or contains no source files"
        return result

    parse_files(files, result)

    logger.info(f"Parse complete: {result.success_count} succeeded, {result.failure_count} failed")

    return result
