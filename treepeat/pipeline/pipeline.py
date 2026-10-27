import logging
import time
from pathlib import Path

from treepeat.config import get_settings
from treepeat.models.shingle import ShingledRegion
from treepeat.models.similarity import (
    RegionSignature,
    SimilarityResult,
    SimilarRegionGroup,
)
from treepeat.pipeline.lsh_stage import detect_similarity
from treepeat.pipeline.preprocessing import preprocess
from treepeat.pipeline.rules.engine import RuleEngine
from treepeat.pipeline.rules_factory import build_rule_engine
from treepeat.pipeline.verbose_metrics import record_stage_count, record_stage_timing

logger = logging.getLogger(__name__)


def _filter_groups_by_min_lines(
    groups: list[SimilarRegionGroup], min_lines: int
) -> list[SimilarRegionGroup]:

    filtered = []
    for group in groups:

        all_meet_threshold = all(
            region.end_line - region.start_line + 1 >= min_lines for region in group.regions
        )
        if all_meet_threshold:
            filtered.append(group)
        else:
            logger.debug(
                "Filtered out group with %d regions - at least one region below min_lines threshold",
                len(group.regions),
            )
    return filtered


def _run_lsh_stage(
    signatures: list[RegionSignature],
    shingled_regions: list[ShingledRegion],
    threshold: float,
    min_lines: int,
    rule_engine: RuleEngine,
    progress: bool = False,
) -> SimilarityResult:

    logger.info("Stage 5/5: Finding similar pairs...")
    _t = time.monotonic()
    similarity_result = detect_similarity(
        signatures,
        similarity_percent=threshold,
        shingled_regions=shingled_regions,
        min_lines=min_lines,
        rules=rule_engine.rules,
        progress=progress,
    )
    elapsed = time.monotonic() - _t
    record_stage_timing("lsh", elapsed)
    record_stage_count("lsh", len(similarity_result.similar_groups))
    logger.info(
        "Similarity detection complete: found %d similar group(s) (%d self-similar) (%.1fs)",
        len(similarity_result.similar_groups),
        similarity_result.self_similarity_count,
        elapsed,
    )
    return similarity_result


def _filter_and_log_groups(
    result: SimilarityResult, min_lines: int
) -> list[SimilarRegionGroup]:
    for group in result.similar_groups:
        logger.debug(
            "  Group: %d regions, similarity=%.2f%%", len(group.regions), group.similarity * 100
        )
    filtered = _filter_groups_by_min_lines(result.similar_groups, min_lines)
    logger.info(
        "Region matching complete: %d groups after filtering (was %d)",
        len(filtered),
        len(result.similar_groups),
    )
    return filtered


def run_pipeline(target_path: str | Path, progress: bool = False) -> SimilarityResult:

    settings = get_settings()
    logger.info("Starting pipeline for: %s (min_lines=%d)", target_path, settings.lsh.min_lines)

    if isinstance(target_path, str):
        target_path = Path(target_path)

    rule_engine = build_rule_engine(settings)


    logger.info("Stages 1-4/5: Parsing, extracting, shingling and fingerprinting...")
    pre = preprocess(target_path, rule_engine, settings, progress=progress)
    if pre.files_parsed == 0:
        logger.warning("No files successfully parsed, returning empty result")
        return SimilarityResult()
    if not pre.signatures:
        logger.info("No regions above min_lines threshold, skipping region matching")
        return SimilarityResult()

    region_result = _run_lsh_stage(
        pre.signatures,
        pre.shingled_regions,
        settings.lsh.similarity_percent,
        settings.lsh.min_lines,
        rule_engine,
        progress=progress,
    )
    similar_groups = _filter_and_log_groups(region_result, settings.lsh.min_lines)

    logger.info("Pipeline complete: %d groups found", len(similar_groups))
    return SimilarityResult(signatures=pre.signatures, similar_groups=similar_groups)
