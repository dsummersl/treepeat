"""Top-level pipeline orchestration.

This module provides the main pipeline that orchestrates all stages:
Parse → Extract Regions → Shingle Regions → MinHash → LSH
"""

import logging
from pathlib import Path

from tssim.config import PipelineSettings, get_settings
from tssim.models.ast import ParsedFile, ParseResult
from tssim.models.shingle import ShingledRegion
from tssim.models.similarity import RegionSignature, SimilarityResult
from tssim.pipeline.lsh_stage import detect_similarity
from tssim.pipeline.minhash_stage import compute_region_signatures
from tssim.pipeline.normalizer_factory import build_normalizers
from tssim.pipeline.normalizers import Normalizer
from tssim.pipeline.parse import parse_path
from tssim.pipeline.region_extraction import ExtractedRegion, extract_all_regions
from tssim.pipeline.shingle import shingle_regions

logger = logging.getLogger(__name__)


def _run_parse_stage(target_path: Path) -> ParseResult:
    """Run parsing stage.

    Returns:
        Parse result with parsed files and failures
    """
    logger.info("Stage 1/5: Parsing...")
    parse_result = parse_path(target_path)
    logger.info(
        "Parse complete: %d succeeded, %d failed",
        parse_result.success_count,
        parse_result.failure_count,
    )
    return parse_result


def _run_extract_stage(parsed_files: list[ParsedFile]) -> list[ExtractedRegion]:
    """Run region extraction stage.

    Returns:
        List of extracted regions
    """
    logger.info("Stage 2/5: Extracting regions...")
    extracted_regions = extract_all_regions(parsed_files)
    logger.info("Extracted %d region(s) from %d file(s)", len(extracted_regions), len(parsed_files))
    return extracted_regions


def _run_shingle_stage(
    extracted_regions: list[ExtractedRegion],
    parsed_files: list[ParsedFile],
    normalizers: list[Normalizer],
    settings: PipelineSettings,
) -> list[ShingledRegion]:
    """Run shingling stage.

    Returns:
        List of shingled regions
    """
    logger.info("Stage 3/5: Shingling regions (with normalization)...")
    shingled_regions = shingle_regions(
        extracted_regions,
        parsed_files,
        normalizers=normalizers,
        k=settings.shingle.k,
    )
    logger.info("Shingling complete: %d region(s) shingled", len(shingled_regions))
    return shingled_regions


def _run_minhash_stage(shingled_regions: list[ShingledRegion], num_perm: int) -> list[RegionSignature]:
    """Run MinHash signature computation stage.

    Returns:
        List of region signatures
    """
    logger.info("Stage 4/5: Computing MinHash signatures...")
    signatures = compute_region_signatures(shingled_regions, num_perm=num_perm)
    logger.info("Created %d signature(s)", len(signatures))
    return signatures


def _run_lsh_stage(
    signatures: list[RegionSignature],
    threshold: float,
    failed_files: dict[Path, str],
) -> SimilarityResult:
    """Run LSH similarity detection stage.

    Returns:
        SimilarityResult with similar pairs
    """
    logger.info("Stage 5/5: Finding similar pairs...")
    similarity_result = detect_similarity(
        signatures,
        threshold=threshold,
        failed_files=failed_files,
    )
    logger.info(
        "Similarity detection complete: found %d similar pair(s) (%d self-similar)",
        similarity_result.pair_count,
        similarity_result.self_similarity_count,
    )
    return similarity_result


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

    if isinstance(target_path, str):
        target_path = Path(target_path)

    normalizers = build_normalizers(settings)

    parse_result = _run_parse_stage(target_path)
    if parse_result.success_count == 0:
        logger.warning("No files successfully parsed, returning empty result")
        return SimilarityResult(failed_files=parse_result.failed_files)

    extracted_regions = _run_extract_stage(parse_result.parsed_files)
    shingled_regions = _run_shingle_stage(extracted_regions, parse_result.parsed_files, normalizers, settings)
    signatures = _run_minhash_stage(shingled_regions, settings.minhash.num_perm)
    similarity_result = _run_lsh_stage(signatures, settings.lsh.threshold, parse_result.failed_files)

    logger.info("Pipeline complete")
    return similarity_result
