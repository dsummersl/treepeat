"""Top-level pipeline orchestration.

This module provides the main pipeline that orchestrates all stages:
Parse → Extract Regions → Shingle Regions → MinHash → LSH
"""

import logging
from pathlib import Path

from tssim.config import get_settings
from tssim.models.similarity import SimilarityResult
from tssim.pipeline.lsh_stage import detect_similarity
from tssim.pipeline.minhash_stage import compute_region_signatures
from tssim.pipeline.normalizer_factory import build_normalizers
from tssim.pipeline.parse import parse_path
from tssim.pipeline.region_extraction import extract_all_regions
from tssim.pipeline.shingle import shingle_regions

logger = logging.getLogger(__name__)


def run_pipeline(target_path: str | Path) -> SimilarityResult:
    """Run the full pipeline on a target path.

    This orchestrates all pipeline stages:
    1. Parse: Extract ASTs from source files
    2. Extract Regions: Identify functions, methods, classes, etc.
    3. Shingle Regions: Extract structural features from each region
    4. MinHash: Create signatures for similarity estimation
    5. LSH: Find candidate similar pairs (including self-similarity)

    Args:
        target_path: Path to a file or directory to analyze

    Returns:
        SimilarityResult with similar region pairs
    """
    settings = get_settings()

    logger.info("Starting pipeline for: %s", target_path)

    # Convert to Path if needed
    if isinstance(target_path, str):
        target_path = Path(target_path)

    # Build normalizers based on settings
    normalizers = build_normalizers(settings)

    # Stage 1: Parse
    logger.info("Stage 1/5: Parsing...")
    parse_result = parse_path(target_path)
    logger.info(
        "Parse complete: %d succeeded, %d failed",
        parse_result.success_count,
        parse_result.failure_count,
    )

    if parse_result.success_count == 0:
        logger.warning("No files successfully parsed, returning empty result")
        return SimilarityResult(failed_files=parse_result.failed_files)

    # Stage 2: Extract Regions
    logger.info("Stage 2/5: Extracting regions...")
    extracted_regions = extract_all_regions(parse_result.parsed_files)
    logger.info("Extracted %d region(s) from %d file(s)", len(extracted_regions), len(parse_result.parsed_files))

    if len(extracted_regions) < 2:
        logger.warning("Need at least 2 regions for similarity detection, returning empty result")
        return SimilarityResult(failed_files=parse_result.failed_files)

    # Stage 3: Shingle Regions (applies normalizers during traversal)
    logger.info("Stage 3/5: Shingling regions (with normalization)...")
    shingled_regions = shingle_regions(
        extracted_regions,
        parse_result.parsed_files,
        normalizers=normalizers,
        k=settings.shingle.k,
        include_text=settings.shingle.include_text,
    )
    logger.info("Shingling complete: %d region(s) shingled", len(shingled_regions))

    if len(shingled_regions) < 2:
        logger.warning("Need at least 2 shingled regions, returning empty result")
        return SimilarityResult(failed_files=parse_result.failed_files)

    # Stage 4: MinHash
    logger.info("Stage 4/5: Computing MinHash signatures...")
    signatures = compute_region_signatures(shingled_regions, num_perm=settings.minhash.num_perm)
    logger.info("Created %d signature(s)", len(signatures))

    # Stage 5: LSH
    logger.info("Stage 5/5: Finding similar pairs...")
    similarity_result = detect_similarity(
        signatures,
        threshold=settings.lsh.threshold,
        failed_files=parse_result.failed_files,
    )
    logger.info(
        "Similarity detection complete: found %d similar pair(s) (%d self-similar)",
        similarity_result.pair_count,
        similarity_result.self_similarity_count,
    )

    logger.info("Pipeline complete")
    return similarity_result
