import logging
import sys
from fnmatch import fnmatch
from pathlib import Path

from tqdm import tqdm
from tree_sitter_language_pack import get_parser

from treepeat.config import get_settings
from treepeat.models import ParsedFile, ParseResult
from treepeat.pipeline.languages import LANGUAGE_EXTENSIONS, get_grammar

logger = logging.getLogger(__name__)


def detect_language(file_path: Path) -> str | None:

    suffix = file_path.suffix.lower()
    for lang, exts in LANGUAGE_EXTENSIONS.items():
        if suffix in exts:
            return lang
    return None


def read_source_file(file_path: Path) -> bytes:

    try:
        return file_path.read_bytes()
    except Exception as e:
        raise ValueError(f"Failed to read file {file_path}: {e}") from e


def parse_source_code(
    source: bytes, language_name: str, file_path: Path
) -> ParsedFile:

    grammar = get_grammar(language_name)
    try:
        parser = get_parser(grammar)  # type: ignore[arg-type]
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

    try:
        patterns = []
        with ignore_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if line and not line.startswith("#"):
                    patterns.append(line)
        return patterns
    except Exception as e:
        logger.warning(f"Failed to parse ignore file {ignore_file}: {e}")
        return []


def _process_ignore_file(ignore_file: Path, ignore_files_map: dict[Path, list[str]]) -> None:

    patterns = parse_ignore_file(ignore_file)
    if not patterns:
        return

    ignore_dir = ignore_file.parent
    if ignore_dir not in ignore_files_map:
        ignore_files_map[ignore_dir] = []
    ignore_files_map[ignore_dir].extend(patterns)
    logger.debug(f"Loaded {len(patterns)} patterns from {ignore_file}")


def find_ignore_files(target_path: Path, ignore_file_patterns: list[str]) -> dict[Path, list[str]]:

    ignore_files_map: dict[Path, list[str]] = {}

    if not target_path.is_dir():
        return ignore_files_map

    for pattern in ignore_file_patterns:
        for ignore_file in target_path.glob(pattern):
            if ignore_file.is_file():
                _process_ignore_file(ignore_file, ignore_files_map)

    return ignore_files_map


def _match_double_star_pattern(rel_path_str: str, file_name: str, pattern: str) -> bool:

    pattern_parts = pattern.split("**", 1)
    if len(pattern_parts) != 2:
        return False

    prefix = pattern_parts[0].strip("/")
    suffix = pattern_parts[1].strip("/")


    if not prefix:
        return fnmatch(rel_path_str, f"*{suffix}") or fnmatch(file_name, suffix)


    if not suffix:
        return rel_path_str.startswith(prefix)


    return fnmatch(rel_path_str, f"{prefix}*{suffix}")


def _get_relative_path(file_path: Path, base_path: Path) -> str | None:

    try:
        return str(file_path.relative_to(base_path))
    except ValueError:
        return None


def _match_path_component(rel_path_str: str, pattern: str) -> bool:

    if "/" in pattern:
        return False
    return any(fnmatch(part, pattern) for part in Path(rel_path_str).parts)


def _match_simple_pattern(rel_path_str: str, file_name: str, pattern: str) -> bool:

    if fnmatch(rel_path_str, pattern) or fnmatch(file_name, pattern):
        return True
    if "**" in pattern:
        return _match_double_star_pattern(rel_path_str, file_name, pattern)
    return _match_path_component(rel_path_str, pattern)


def _check_directory_pattern(rel_path_str: str, file_path: Path, pattern: str) -> tuple[bool, bool]:

    if pattern.endswith("/"):
        dir_name = pattern.rstrip("/")
        if file_path.is_dir():
            return True, (fnmatch(rel_path_str, dir_name) or fnmatch(file_path.name, dir_name))
        else:
            return True, rel_path_str.startswith(dir_name + "/")

    return False, False


def matches_pattern(file_path: Path, pattern: str, base_path: Path) -> bool:

    if pattern.startswith("!"):
        return False

    rel_path_str = _get_relative_path(file_path, base_path)
    if rel_path_str is None:
        return False

    should_return, is_match = _check_directory_pattern(rel_path_str, file_path, pattern)
    if should_return:
        return is_match

    if pattern.startswith("/"):
        return fnmatch(rel_path_str, pattern.lstrip("/"))

    return _match_simple_pattern(rel_path_str, file_path.name, pattern)


def _check_patterns_in_directory(file_path: Path, directory: Path, patterns: list[str]) -> bool:

    for pattern in patterns:
        if matches_pattern(file_path, pattern, directory):
            logger.debug(f"File {file_path} matched pattern '{pattern}' from {directory}")
            return True
    return False


def _should_stop_traversal(current: Path, target: Path) -> bool:

    return current in (target, current.parent)


def _get_parent_directories(file_path: Path, target_path: Path) -> list[Path]:

    directories = []
    current = file_path.parent
    while not _should_stop_traversal(current, target_path):
        directories.append(current)
        try:
            current = current.parent
        except Exception:
            break

    directories.append(current)
    return directories


def _check_hierarchical_ignores(
    file_path: Path, target_path: Path, ignore_files_map: dict[Path, list[str]]
) -> bool:

    for directory in _get_parent_directories(file_path, target_path):
        if directory in ignore_files_map:
            if _check_patterns_in_directory(file_path, directory, ignore_files_map[directory]):
                return True
    return False


def should_ignore_file(
    file_path: Path,
    target_path: Path,
    ignore_patterns: list[str],
    ignore_files_map: dict[Path, list[str]],
) -> bool:


    for pattern in ignore_patterns:
        if matches_pattern(file_path, pattern, target_path):
            logger.debug(f"File {file_path} matched CLI ignore pattern: {pattern}")
            return True


    return _check_hierarchical_ignores(file_path, target_path, ignore_files_map)


def _collect_single_file(
    target_path: Path, ignore_patterns: list[str], ignore_file_patterns: list[str]
) -> list[Path]:

    if not (ignore_patterns or ignore_file_patterns):
        return [target_path]

    ignore_files_map = find_ignore_files(target_path.parent, ignore_file_patterns)
    if should_ignore_file(target_path, target_path.parent, ignore_patterns, ignore_files_map):
        logger.info(f"File {target_path} is ignored by patterns")
        return []
    return [target_path]


def _collect_directory_files(
    target_path: Path, ignore_patterns: list[str], ignore_file_patterns: list[str]
) -> list[Path]:

    ignore_files_map = find_ignore_files(target_path, ignore_file_patterns)

    files: list[Path] = []
    for _lang, exts in LANGUAGE_EXTENSIONS.items():
        for ext in exts:
            for file in target_path.rglob(f"*{ext}"):
                if not should_ignore_file(file, target_path, ignore_patterns, ignore_files_map):
                    files.append(file)

    logger.info(f"Found {len(files)} source files in directory (after applying ignore patterns)")
    return files


def collect_source_files(target_path: Path) -> list[Path]:

    settings = get_settings()
    ignore_patterns = settings.ignore_patterns
    ignore_file_patterns = settings.ignore_file_patterns

    if target_path.is_file():
        return _collect_single_file(target_path, ignore_patterns, ignore_file_patterns)

    if target_path.is_dir():
        return _collect_directory_files(target_path, ignore_patterns, ignore_file_patterns)

    return []


def parse_files(files: list[Path], result: ParseResult, progress: bool = False) -> None:

    iterable = (
        tqdm(files, desc="Parsing", unit="file", file=sys.stderr)
        if progress
        else files
    )
    for file_path in iterable:
        try:
            parsed = parse_file(file_path)
            result.parsed_files.append(parsed)
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")


def parse_path(target_path: Path, progress: bool = False) -> ParseResult:

    logger.info(f"Starting parse of: {target_path}")

    result = ParseResult()
    files = collect_source_files(target_path)

    if not files:
        logger.warning(f"Path does not exist or contains no source files: {target_path}")
        return result

    parse_files(files, result, progress=progress)

    logger.info(f"Parse complete: {result.success_count} succeeded")

    return result
