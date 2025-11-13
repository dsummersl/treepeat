"""Top-level pipeline orchestration.

This module provides the main pipeline that orchestrates all stages:
Parse → Extract Regions → Shingle Regions → MinHash → LSH
"""

import logging
from pathlib import Path

from tssim.config import PipelineSettings, get_settings
from tssim.models.ast import ParsedFile, ParseResult
from tssim.models.shingle import ShingledRegion
from tssim.models.similarity import Region, RegionSignature, SimilarRegionPair, SimilarityResult
from tssim.pipeline.lsh_stage import detect_similarity
from tssim.pipeline.minhash_stage import compute_region_signatures
from tssim.pipeline.parse import parse_path
from tssim.pipeline.region_extraction import (
    ExtractedRegion,
    create_line_based_regions,
    extract_all_regions,
    get_matched_line_ranges,
)
from tssim.pipeline.rules import RuleEngine
from tssim.pipeline.rules_factory import build_rule_engine
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


def _run_extract_stage(
    parsed_files: list[ParsedFile], include_sections: bool = True
) -> list[ExtractedRegion]:
    """Run region extraction stage.

    Args:
        parsed_files: List of parsed source files
        include_sections: If True, create section regions for non-target code

    Returns:
        List of extracted regions
    """
    logger.info("Stage 2/5: Extracting regions...")
    extracted_regions = extract_all_regions(parsed_files, include_sections)
    logger.info("Extracted %d region(s) from %d file(s)", len(extracted_regions), len(parsed_files))
    return extracted_regions


def _filter_pairs_by_min_lines(
    pairs: list[SimilarRegionPair], min_lines: int
) -> list[SimilarRegionPair]:
    """Filter similar pairs to only include those with at least min_lines.

    Args:
        pairs: List of similar region pairs
        min_lines: Minimum number of lines for a match

    Returns:
        Filtered list of pairs
    """
    filtered = []
    for pair in pairs:
        lines1 = pair.region1.end_line - pair.region1.start_line + 1
        lines2 = pair.region2.end_line - pair.region2.start_line + 1
        if lines1 >= min_lines and lines2 >= min_lines:
            filtered.append(pair)
        else:
            logger.debug(
                "Filtered out match: %s:%d-%d (%d lines) ↔ %s:%d-%d (%d lines) - below min_lines threshold",
                pair.region1.path,
                pair.region1.start_line,
                pair.region1.end_line,
                lines1,
                pair.region2.path,
                pair.region2.start_line,
                pair.region2.end_line,
                lines2,
            )
    return filtered


def _get_matched_regions_from_pairs(pairs: list[SimilarRegionPair]) -> list[Region]:
    """Extract all matched regions from similar pairs.

    Args:
        pairs: List of similar region pairs

    Returns:
        List of all regions that were matched
    """
    matched_regions: list[Region] = []
    for pair in pairs:
        matched_regions.append(pair.region1)
        matched_regions.append(pair.region2)
    return matched_regions


def _run_shingle_stage(
    extracted_regions: list[ExtractedRegion],
    parsed_files: list[ParsedFile],
    rule_engine: RuleEngine,
    settings: PipelineSettings,
) -> list[ShingledRegion]:
    """Run shingling stage.

    Returns:
        List of shingled regions
    """
    logger.info("Stage 3/5: Shingling regions (with rules)...")
    shingled_regions = shingle_regions(
        extracted_regions,
        parsed_files,
        rule_engine=rule_engine,
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


def _run_level1_matching(
    parsed_files: list[ParsedFile],
    rule_engine: RuleEngine,
    settings: PipelineSettings,
) -> tuple[list[SimilarRegionPair], list[RegionSignature]]:
    """Run Level 1: Region-Level Matching (functions/classes).

    Args:
        parsed_files: List of parsed source files
        rule_engine: Rule engine for applying transformation rules
        settings: Pipeline settings

    Returns:
        Tuple of (filtered pairs, signatures)
    """
    logger.info("===== LEVEL 1: Region-Level Matching =====")

    # Extract only functions/classes (no section regions)
    level1_regions = _run_extract_stage(parsed_files, include_sections=False)

    # Shingle level 1 regions
    level1_shingled = _run_shingle_stage(level1_regions, parsed_files, rule_engine, settings)

    # MinHash level 1
    level1_signatures = _run_minhash_stage(level1_shingled, settings.minhash.num_perm)

    # LSH level 1
    level1_result = _run_lsh_stage(level1_signatures, settings.lsh.threshold, {})

    # Filter by min_lines
    level1_filtered_pairs = _filter_pairs_by_min_lines(level1_result.similar_pairs, settings.lsh.min_lines)
    logger.info("Level 1 complete: %d pairs after filtering (was %d)", len(level1_filtered_pairs), len(level1_result.similar_pairs))

    return level1_filtered_pairs, level1_signatures


def _run_level2_matching(
    parsed_files: list[ParsedFile],
    level1_filtered_pairs: list[SimilarRegionPair],
    rule_engine: RuleEngine,
    settings: PipelineSettings,
) -> tuple[list[SimilarRegionPair], list[RegionSignature]]:
    """Run Level 2: Line-Level Matching (unmatched sections).

    Args:
        parsed_files: List of parsed source files
        level1_filtered_pairs: Filtered pairs from Level 1
        rule_engine: Rule engine for applying transformation rules
        settings: Pipeline settings

    Returns:
        Tuple of (filtered pairs, signatures)
    """
    logger.info("===== LEVEL 2: Line-Level Matching =====")

    # Track matched lines from level 1
    level1_matched_regions = _get_matched_regions_from_pairs(level1_filtered_pairs)
    matched_lines_by_file = get_matched_line_ranges(level1_matched_regions)
    logger.info("Tracked %d matched regions from level 1", len(level1_matched_regions))

    # Create line-based regions for unmatched sections
    level2_regions = create_line_based_regions(
        parsed_files,
        matched_lines_by_file,
        settings.lsh.min_lines,
    )

    if len(level2_regions) == 0:
        logger.info("No unmatched sections found for level 2, skipping")
        return [], []

    # Shingle, MinHash, LSH on level 2 regions
    level2_shingled = _run_shingle_stage(level2_regions, parsed_files, rule_engine, settings)
    level2_signatures = _run_minhash_stage(level2_shingled, settings.minhash.num_perm)
    level2_result = _run_lsh_stage(level2_signatures, settings.lsh.threshold, {})

    # Filter by min_lines
    level2_filtered_pairs = _filter_pairs_by_min_lines(level2_result.similar_pairs, settings.lsh.min_lines)
    logger.info("Level 2 complete: %d pairs after filtering (was %d)", len(level2_filtered_pairs), len(level2_result.similar_pairs))

    return level2_filtered_pairs, level2_signatures


def run_pipeline(target_path: str | Path) -> SimilarityResult:
    """Run the full two-level pipeline on a target path. """
    settings = get_settings()
    logger.info("Starting two-level pipeline for: %s (min_lines=%d)", target_path, settings.lsh.min_lines)

    if isinstance(target_path, str):
        target_path = Path(target_path)

    rule_engine = build_rule_engine(settings)

    # Stage 1: Parse
    parse_result = _run_parse_stage(target_path)
    if parse_result.success_count == 0:
        logger.warning("No files successfully parsed, returning empty result")
        return SimilarityResult(failed_files=parse_result.failed_files)

    # Run Level 1: Region-Level Matching (functions/classes)
    level1_filtered_pairs, level1_signatures = _run_level1_matching(
        parse_result.parsed_files, rule_engine, settings
    )

    # Run Level 2: Line-Level Matching (unmatched sections)
    level2_filtered_pairs, level2_signatures = _run_level2_matching(
        parse_result.parsed_files, level1_filtered_pairs, rule_engine, settings
    )

    # Combine results
    all_pairs = level1_filtered_pairs + level2_filtered_pairs
    all_signatures = level1_signatures + level2_signatures if level2_signatures else level1_signatures
    logger.info("Combined results: %d total pairs (%d from level 1, %d from level 2)",
                len(all_pairs), len(level1_filtered_pairs), len(level2_filtered_pairs))

    # Create final result
    final_result = SimilarityResult(
        signatures=all_signatures,
        similar_pairs=all_pairs,
        failed_files=parse_result.failed_files,
    )

    logger.info("Pipeline complete")
    return final_result
