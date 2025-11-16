import logging
from pathlib import Path

from whorl.config import PipelineSettings, get_settings
from whorl.models.ast import ParsedFile, ParseResult
from whorl.models.shingle import ShingledRegion
from whorl.models.similarity import Region, RegionSignature, SimilarRegionGroup, SimilarRegionPair, SimilarityResult
from whorl.pipeline.lsh_stage import detect_similarity
from whorl.pipeline.minhash_stage import compute_region_signatures
from whorl.pipeline.parse import parse_path
from whorl.pipeline.region_extraction import (
    ExtractedRegion,
    create_line_based_regions,
    extract_all_regions,
    get_matched_line_ranges,
)
from whorl.pipeline.rules.engine import RuleEngine
from whorl.pipeline.rules_factory import build_rule_engine
from whorl.pipeline.shingle import shingle_regions

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


def _get_matched_regions_from_groups(groups: list[SimilarRegionGroup]) -> list[Region]:
    """Extract all matched regions from similar groups."""
    matched_regions: list[Region] = []
    for group in groups:
        matched_regions.extend(group.regions)
    return matched_regions


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
    failed_files: dict[Path, str],
) -> SimilarityResult:
    """Run LSH similarity detection stage."""
    logger.info("Stage 5/5: Finding similar pairs...")
    similarity_result = detect_similarity(
        signatures,
        threshold=threshold,
        failed_files=failed_files,
        shingled_regions=shingled_regions,
        verify_candidates=True,
    )
    logger.info(
        "Similarity detection complete: found %d similar group(s) (%d self-similar)",
        len(similarity_result.similar_groups),
        similarity_result.self_similarity_count,
    )
    return similarity_result


def _run_level1_matching(
    parsed_files: list[ParsedFile],
    rule_engine: RuleEngine,
    settings: PipelineSettings,
) -> tuple[list[SimilarRegionGroup], list[RegionSignature]]:
    """Run Level 1 region-level matching for functions and classes."""
    logger.info("===== LEVEL 1: Region-Level Matching =====")

    # Extract only functions/classes (no section regions)
    level1_regions = _run_extract_stage(parsed_files, rule_engine)

    # Shingle level 1 regions
    level1_shingled = _run_shingle_stage(level1_regions, parsed_files, rule_engine, settings)

    # MinHash level 1
    level1_signatures = _run_minhash_stage(level1_shingled, settings.minhash.num_perm)

    # LSH level 1
    level1_result = _run_lsh_stage(level1_signatures, level1_shingled, settings.lsh.threshold, {})

    # Filter by min_lines
    logger.debug("Level 1: Filtering %d groups by min_lines=%d", len(level1_result.similar_groups), settings.lsh.min_lines)
    for group in level1_result.similar_groups:
        logger.debug("  Group: %d regions, similarity=%.2f%%", len(group.regions), group.similarity * 100)
        for region in group.regions:
            lines = region.end_line - region.start_line + 1
            logger.debug("    - %s [%d:%d] (%d lines)", region.region_name, region.start_line, region.end_line, lines)
    level1_filtered_groups = _filter_groups_by_min_lines(level1_result.similar_groups, settings.lsh.min_lines)
    logger.info("Level 1 complete: %d groups after filtering (was %d)",
                len(level1_filtered_groups), len(level1_result.similar_groups))

    return level1_filtered_groups, level1_signatures


def _run_level2_matching(
    parsed_files: list[ParsedFile],
    level1_filtered_groups: list[SimilarRegionGroup],
    rule_engine: RuleEngine,
    settings: PipelineSettings,
) -> tuple[list[SimilarRegionGroup], list[RegionSignature]]:
    """Run Level 2 line-level matching for unmatched sections."""
    logger.info("===== LEVEL 2: Line-Level Matching =====")

    # Track matched lines from level 1
    level1_matched_regions = _get_matched_regions_from_groups(level1_filtered_groups)
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
    level2_result = _run_lsh_stage(level2_signatures, level2_shingled, settings.lsh.threshold, {})

    # Filter by min_lines
    level2_filtered_groups = _filter_groups_by_min_lines(level2_result.similar_groups, settings.lsh.min_lines)
    logger.info("Level 2 complete: %d groups after filtering (was %d)",
                len(level2_filtered_groups), len(level2_result.similar_groups))

    return level2_filtered_groups, level2_signatures


def run_pipeline(target_path: str | Path) -> SimilarityResult:
    """Run the full two-level pipeline on a target path."""
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
    level1_filtered_groups, level1_signatures = _run_level1_matching(
        parse_result.parsed_files, rule_engine, settings
    )

    # Run Level 2: Line-Level Matching (unmatched sections)
    level2_filtered_groups, level2_signatures = _run_level2_matching(
        parse_result.parsed_files, level1_filtered_groups, rule_engine, settings
    )

    # Combine results
    all_groups = level1_filtered_groups + level2_filtered_groups
    all_signatures = level1_signatures + level2_signatures if level2_signatures else level1_signatures
    logger.info("Combined results: %d total groups (%d from level 1, %d from level 2)",
                len(all_groups), len(level1_filtered_groups), len(level2_filtered_groups))

    # Create final result
    final_result = SimilarityResult(
        signatures=all_signatures,
        similar_groups=all_groups,
        failed_files=parse_result.failed_files,
    )

    logger.info("Pipeline complete")
    return final_result
