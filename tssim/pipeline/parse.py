"""Parse stage of the tssim pipeline."""

import logging
from pathlib import Path
from typing import Literal

from tree_sitter_language_pack import get_parser

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


def collect_source_files(target_path: Path) -> list[Path]:
    """Collect all source files from a path."""
    if target_path.is_file():
        return [target_path]

    if target_path.is_dir():
        files: list[Path] = []
        for ext in LANGUAGE_MAP.keys():
            files.extend(target_path.rglob(f"*{ext}"))
        logger.info(f"Found {len(files)} source files in directory")
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
