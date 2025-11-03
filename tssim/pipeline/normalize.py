"""Normalization pipeline stage.

This module provides the normalize stage of the pipeline, which applies
various normalizers to reduce noise and focus on structural similarities.
"""

import logging

from tssim.models.ast import ParsedFile, ParseResult
from tssim.pipeline.normalizers import Normalizer
from tssim.pipeline.normalizers.python import PythonImportNormalizer

logger = logging.getLogger(__name__)


# Registry of all available normalizers
DEFAULT_NORMALIZERS: list[Normalizer] = [
    PythonImportNormalizer(),
]


def normalize_file(parsed_file: ParsedFile, normalizers: list[Normalizer]) -> ParsedFile:
    """Apply all applicable normalizers to a single parsed file.

    Args:
        parsed_file: The parsed file to normalize
        normalizers: List of normalizers to apply

    Returns:
        The normalized parsed file
    """
    result = parsed_file

    for normalizer in normalizers:
        if normalizer.should_apply(result):
            try:
                result = normalizer.normalize(result)
            except Exception as e:
                logger.error(
                    "Error applying %s to %s: %s",
                    normalizer.__class__.__name__,
                    parsed_file.path,
                    e,
                )
                # Continue with the current result rather than failing completely

    return result


def normalize_files(
    parse_result: ParseResult,
    normalizers: list[Normalizer] | None = None,
) -> ParseResult:
    """Normalize all parsed files in a ParseResult.

    Args:
        parse_result: The parse result containing files to normalize
        normalizers: List of normalizers to apply (uses DEFAULT_NORMALIZERS if None)

    Returns:
        A new ParseResult with normalized files
    """
    if normalizers is None:
        normalizers = DEFAULT_NORMALIZERS

    logger.info("Normalizing %d file(s)", len(parse_result.parsed_files))

    normalized_files = []
    for parsed_file in parse_result.parsed_files:
        normalized_file = normalize_file(parsed_file, normalizers)
        normalized_files.append(normalized_file)

    # Return a new ParseResult with normalized files
    # Failed files remain unchanged
    return ParseResult(
        parsed_files=normalized_files,
        failed_files=parse_result.failed_files,
    )


def normalize_path(target_path: str) -> ParseResult:
    """Parse and normalize files at the given path.

    This is a convenience function that combines parsing and normalization.

    Args:
        target_path: Path to a file or directory to analyze

    Returns:
        ParseResult with normalized files
    """
    from tssim.pipeline.parse import parse_path

    parse_result = parse_path(target_path)
    return normalize_files(parse_result)
