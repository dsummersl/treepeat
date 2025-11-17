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
    create_unmatched_regions,
    extract_all_regions,
    get_matched_line_ranges,
)
from whorl.pipeline.boundary_detection import merge_similar_window_groups
from whorl.pipeline.rules.engine import RuleEngine
from whorl.pipeline.rules_factory import build_rule_engine
from whorl.pipeline.shingle import shingle_regions, create_shingle_windows

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


def _filter_file_type_regions(extracted_regions: list[ExtractedRegion]) -> list[ExtractedRegion]:
    """Filter out 'file' type regions that should use line matching instead.

    Args:
        extracted_regions: All extracted regions

    Returns:
        Only code regions (functions, classes, etc.) excluding file-type regions
    """
    code_regions = [r for r in extracted_regions if r.region.region_type != "file"]
    file_type_count = len(extracted_regions) - len(code_regions)

    if file_type_count > 0:
        logger.info("Skipping %d 'file' type region(s) - will process with line matching", file_type_count)

    return code_regions


def _run_region_matching(
    parsed_files: list[ParsedFile],
    rule_engine: RuleEngine,
    settings: PipelineSettings,
) -> tuple[list[SimilarRegionGroup], list[RegionSignature]]:
    """Run region matching for functions and classes."""
    logger.info("===== REGION MATCHING: Functions and Classes =====")

    # Extract and filter regions
    all_extracted = _run_extract_stage(parsed_files, rule_engine)
    region_regions = _filter_file_type_regions(all_extracted)

    # If no code regions, skip region matching entirely
    if not region_regions:
        logger.info("No code regions found, skipping region matching")
        return [], []

    # Shingle region regions
    region_shingled = _run_shingle_stage(region_regions, parsed_files, rule_engine, settings)

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


def _run_line_matching(
    parsed_files: list[ParsedFile],
    region_filtered_groups: list[SimilarRegionGroup],
    rule_engine: RuleEngine,
    settings: PipelineSettings,
) -> tuple[list[SimilarRegionGroup], list[RegionSignature]]:
    """Run line matching for unmatched sections using shingle-based sliding windows.

    This builds windows from the remaining shingles that were not matched
    by the region matching process that preceded it.
    """
    logger.info("===== LINE MATCHING: Unmatched Sections =====")

    # Track matched lines from region matching
    region_matched_regions = _get_matched_regions_from_groups(region_filtered_groups)
    matched_lines_by_file = get_matched_line_ranges(region_matched_regions)
    logger.info("Tracked %d matched regions from region matching", len(region_matched_regions))

    # Step 1: Create regions for unmatched sections (one region per unmatched range)
    unmatched_regions = create_unmatched_regions(
        parsed_files,
        matched_lines_by_file,
        settings.lsh.min_lines,
    )

    if len(unmatched_regions) == 0:
        logger.info("No unmatched sections found for line matching, skipping")
        return [], []

    # Step 2: Shingle the unmatched regions to get their shingles
    logger.info("Shingling %d unmatched region(s)...", len(unmatched_regions))
    unmatched_shingled = _run_shingle_stage(unmatched_regions, parsed_files, rule_engine, settings)

    # Step 3: Create sliding windows from the shingles (not from line ranges)
    # This builds windows from the remaining shingles, as intended
    logger.info("Creating sliding windows from shingles (window_size=%d, stride=%d)...",
                settings.lsh.window_size, settings.lsh.stride)
    # Estimate min_shingles from min_lines (rough heuristic: 1 line ≈ k shingles)
    min_shingles = max(1, settings.lsh.min_lines // settings.shingle.k)
    windowed_shingled = create_shingle_windows(
        unmatched_shingled,
        window_size=settings.lsh.window_size,
        stride=settings.lsh.stride,
        min_shingles=min_shingles,
    )

    if len(windowed_shingled) == 0:
        logger.info("No valid shingle windows created, skipping line matching")
        return [], []

    # Step 4: MinHash and LSH on shingle windows
    line_signatures = _run_minhash_stage(windowed_shingled, settings.minhash.num_perm)
    line_result = _run_lsh_stage(
        line_signatures,
        windowed_shingled,
        settings.lsh.line_threshold,
        settings.lsh.line_min_similarity,
        {},
    )

    # Merge overlapping windows to find clean boundaries
    if len(line_result.similar_groups) > 0:
        logger.info("Merging %d overlapping window groups to find boundaries", len(line_result.similar_groups))
        merged_groups = merge_similar_window_groups(line_result.similar_groups)
    else:
        merged_groups = line_result.similar_groups

    # Filter by min_lines after merging
    line_filtered_groups = _filter_groups_by_min_lines(merged_groups, settings.lsh.min_lines)
    logger.info("Line matching complete: %d groups after merging and filtering (was %d windows in %d groups)",
                len(line_filtered_groups), len(line_result.similar_groups), len(line_result.similar_groups))

    return line_filtered_groups, line_signatures


def run_pipeline(target_path: str | Path) -> SimilarityResult:
    """Run the full two-stage pipeline on a target path."""
    settings = get_settings()
    logger.info("Starting two-stage pipeline for: %s (min_lines=%d)", target_path, settings.lsh.min_lines)

    if isinstance(target_path, str):
        target_path = Path(target_path)

    rule_engine = build_rule_engine(settings)

    # Stage 1: Parse
    parse_result = _run_parse_stage(target_path)
    if parse_result.success_count == 0:
        logger.warning("No files successfully parsed, returning empty result")
        return SimilarityResult(failed_files=parse_result.failed_files)

    # Run Region Matching (functions/classes)
    region_filtered_groups, region_signatures = _run_region_matching(
        parse_result.parsed_files, rule_engine, settings
    )

    # Run Line Matching (unmatched sections)
    line_filtered_groups, line_signatures = _run_line_matching(
        parse_result.parsed_files, region_filtered_groups, rule_engine, settings
    )

    # Combine results
    all_groups = region_filtered_groups + line_filtered_groups
    all_signatures = region_signatures + line_signatures if line_signatures else region_signatures
    logger.info("Combined results: %d total groups (%d from region matching, %d from line matching)",
                len(all_groups), len(region_filtered_groups), len(line_filtered_groups))

    # Create final result
    final_result = SimilarityResult(
        signatures=all_signatures,
        similar_groups=all_groups,
        failed_files=parse_result.failed_files,
    )

    logger.info("Pipeline complete")
    return final_result
