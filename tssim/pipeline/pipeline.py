"""Top-level pipeline orchestration.

This module provides the main pipeline that orchestrates all stages:
Parse → Shingle (with normalization) → MinHash → LSH → ...
"""

import logging
from pathlib import Path

from tssim.config import get_settings
from tssim.models.shingle import ShingleResult
from tssim.pipeline.normalizer_factory import build_normalizers
from tssim.pipeline.parse import parse_path
from tssim.pipeline.shingle import shingle_files

logger = logging.getLogger(__name__)


def run_pipeline(target_path: str | Path) -> ShingleResult:
    """Run the full pipeline on a target path.

    This orchestrates all pipeline stages:
    1. Parse: Extract ASTs from source files
    2. Shingle (with normalization): Extract structural features with normalizers applied

    Args:
        target_path: Path to a file or directory to analyze

    Returns:
        ShingleResult containing shingled files ready for MinHash/LSH
    """
    settings = get_settings()

    logger.info("Starting pipeline for: %s", target_path)

    # Convert to Path if needed
    if isinstance(target_path, str):
        target_path = Path(target_path)

    # Build normalizers based on settings
    normalizers = build_normalizers(settings)

    # Stage 1: Parse
    logger.info("Stage 1/2: Parsing...")
    parse_result = parse_path(target_path)
    logger.info(
        "Parse complete: %d succeeded, %d failed",
        parse_result.success_count,
        parse_result.failure_count,
    )

    # Stage 2: Shingle (applies normalizers during traversal)
    logger.info("Stage 2/2: Shingling (with normalization)...")
    shingle_result = shingle_files(
        parse_result,
        normalizers=normalizers,
        k=settings.shingle.k,
        include_text=settings.shingle.include_text,
    )
    logger.info(
        "Shingling complete: %d succeeded, %d failed",
        shingle_result.success_count,
        shingle_result.failure_count - parse_result.failure_count,
    )

    logger.info("Pipeline complete")
    return shingle_result
