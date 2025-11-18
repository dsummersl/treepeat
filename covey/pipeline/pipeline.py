import logging
from pathlib import Path

from covey.config import PipelineSettings, get_settings
from covey.models.ast import ParsedFile, ParseResult
from covey.models.shingle import ShingledRegion
from covey.models.similarity import RegionSignature, SimilarRegionGroup, SimilarRegionPair, SimilarityResult
from covey.pipeline.lsh_stage import detect_similarity
from covey.pipeline.minhash_stage import compute_region_signatures
from covey.pipeline.parse import parse_path
from covey.pipeline.region_extraction import (
    ExtractedRegion,
    extract_all_regions,
)
from covey.pipeline.rules.engine import RuleEngine
from covey.pipeline.rules_factory import build_rule_engine
from covey.pipeline.shingle import shingle_regions

logger = logging.getLogger(__name__)


def _run_parse_stage(target_path: Path) -> ParseResult:
    """Run parsing stage."""
    logger.info("Stage 1/5: Parsing...")
    parse_result = parse_path(target_path)
    logger.info(
        "Parse complete: %d succeeded, %d failed",
        parse_result.success_count,
        parse_result.failure_count,
    )
    return parse_result


def _run_extract_stage(
    parsed_files: list[ParsedFile],
    rule_engine: RuleEngine,
) -> list[ExtractedRegion]:
    """Run region extraction stage."""
    logger.info("Stage 2/5: Extracting regions...")
    extracted_regions = extract_all_regions(parsed_files, rule_engine)
    logger.info("Extracted %d region(s) from %d file(s)", len(extracted_regions), len(parsed_files))
    return extracted_regions


def _filter_groups_by_min_lines(
    groups: list[SimilarRegionGroup], min_lines: int
) -> list[SimilarRegionGroup]:
    """Filter similar groups to only include those meeting the minimum line count in all regions."""
    filtered = []
    for group in groups:
        # Check if all regions meet the min_lines threshold
        all_meet_threshold = all(
            region.end_line - region.start_line + 1 >= min_lines
            for region in group.regions
        )
        if all_meet_threshold:
            filtered.append(group)
        else:
            logger.debug(
                "Filtered out group with %d regions - at least one region below min_lines threshold",
                len(group.regions),
            )
    return filtered


def _filter_pairs_by_min_lines(
    pairs: list[SimilarRegionPair], min_lines: int
) -> list[SimilarRegionPair]:
    """Filter similar pairs to only include those meeting the minimum line count."""
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


def _run_shingle_stage(
    extracted_regions: list[ExtractedRegion],
    parsed_files: list[ParsedFile],
    rule_engine: RuleEngine,
    settings: PipelineSettings,
) -> list[ShingledRegion]:
    """Run shingling stage."""
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
    """Run MinHash signature computation stage."""
    logger.info("Stage 4/5: Computing MinHash signatures...")
    signatures = compute_region_signatures(shingled_regions, num_perm=num_perm)
    logger.info("Created %d signature(s)", len(signatures))
    return signatures


def _run_lsh_stage(
    signatures: list[RegionSignature],
    shingled_regions: list[ShingledRegion],
    threshold: float,
    min_similarity: float,
    failed_files: dict[Path, str],
) -> SimilarityResult:
    """Run LSH similarity detection stage.

    Args:
        signatures: Region signatures to compare
        shingled_regions: Shingled regions for verification
        threshold: LSH threshold for finding approximate matches
        min_similarity: Minimum verified similarity to keep after verification
        failed_files: Dictionary of failed files
    """
    logger.info("Stage 5/5: Finding similar pairs...")
    similarity_result = detect_similarity(
        signatures,
        threshold=threshold,
        min_similarity=min_similarity,
        failed_files=failed_files,
        shingled_regions=shingled_regions,
    )
    logger.info(
        "Similarity detection complete: found %d similar group(s) (%d self-similar)",
        len(similarity_result.similar_groups),
        similarity_result.self_similarity_count,
    )
    return similarity_result


def _filter_regions_by_min_lines(
    regions: list[ExtractedRegion], min_lines: int
) -> list[ExtractedRegion]:
    """Filter regions that are too short before processing."""
    filtered = []
    for region in regions:
        lines = region.region.end_line - region.region.start_line + 1
        if lines >= min_lines:
            filtered.append(region)
        else:
            logger.debug(
                "Filtered out region %s [%d:%d] (%d lines) - below min_lines threshold",
                region.region.region_name,
                region.region.start_line,
                region.region.end_line,
                lines,
            )
    if len(filtered) < len(regions):
        logger.info(
            "Filtered %d region(s) below min_lines=%d before processing",
            len(regions) - len(filtered),
            min_lines,
        )
    return filtered


def _run_region_matching(
    parsed_files: list[ParsedFile],
    rule_engine: RuleEngine,
    settings: PipelineSettings,
) -> tuple[list[SimilarRegionGroup], list[RegionSignature]]:
    """Run region matching for functions and classes."""
    logger.info("===== REGION MATCHING =====")

    # Extract regions
    extracted_regions = _run_extract_stage(parsed_files, rule_engine)

    # If no regions, skip region matching entirely
    if not extracted_regions:
        logger.info("No regions found, skipping region matching")
        return [], []

    # Filter out regions that are too short before processing
    extracted_regions = _filter_regions_by_min_lines(extracted_regions, settings.lsh.min_lines)
    if not extracted_regions:
        logger.info("No regions above min_lines threshold, skipping region matching")
        return [], []

    # Shingle regions
    region_shingled = _run_shingle_stage(extracted_regions, parsed_files, rule_engine, settings)

    # MinHash region
    region_signatures = _run_minhash_stage(region_shingled, settings.minhash.num_perm)

    # LSH region - use higher threshold for region matching
    region_result = _run_lsh_stage(
        region_signatures,
        region_shingled,
        settings.lsh.region_threshold,
        settings.lsh.region_min_similarity,
        {},
    )

    # Filter by min_lines
    logger.debug("Region matching: Filtering %d groups by min_lines=%d", len(region_result.similar_groups), settings.lsh.min_lines)
    for group in region_result.similar_groups:
        logger.debug("  Group: %d regions, similarity=%.2f%%", len(group.regions), group.similarity * 100)
        for region in group.regions:
            lines = region.end_line - region.start_line + 1
            logger.debug("    - %s [%d:%d] (%d lines)", region.region_name, region.start_line, region.end_line, lines)
    region_filtered_groups = _filter_groups_by_min_lines(region_result.similar_groups, settings.lsh.min_lines)
    logger.info("Region matching complete: %d groups after filtering (was %d)",
                len(region_filtered_groups), len(region_result.similar_groups))

    return region_filtered_groups, region_signatures


def run_pipeline(target_path: str | Path) -> SimilarityResult:
    """Run the similarity detection pipeline on a target path."""
    settings = get_settings()
    logger.info("Starting pipeline for: %s (min_lines=%d)", target_path, settings.lsh.min_lines)

    if isinstance(target_path, str):
        target_path = Path(target_path)

    rule_engine = build_rule_engine(settings)

    # Stage 1: Parse
    parse_result = _run_parse_stage(target_path)
    if parse_result.success_count == 0:
        logger.warning("No files successfully parsed, returning empty result")
        return SimilarityResult(failed_files=parse_result.failed_files)

    # Run Region Matching
    similar_groups, signatures = _run_region_matching(
        parse_result.parsed_files, rule_engine, settings
    )

    # Create final result
    final_result = SimilarityResult(
        signatures=signatures,
        similar_groups=similar_groups,
        failed_files=parse_result.failed_files,
    )

    logger.info("Pipeline complete: %d groups found", len(similar_groups))
    return final_result
