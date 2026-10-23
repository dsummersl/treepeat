import logging
import time
from pathlib import Path

from treepeat.config import get_settings
from treepeat.models.shingle import ShingledRegion
from treepeat.models.similarity import RegionSignature, SimilarityResult
from treepeat.pipeline.lsh_stage import detect_similarity
from treepeat.pipeline.preprocessing import preprocess
from treepeat.pipeline.rules.engine import RuleEngine
from treepeat.pipeline.rules_factory import build_rule_engine
from treepeat.pipeline.verbose_metrics import record_stage_count, record_stage_timing

logger = logging.getLogger(__name__)


def _run_lsh_stage(
    signatures: list[RegionSignature],
    shingled_regions: list[ShingledRegion],
    threshold: float,
    min_lines: int,
    rule_engine: RuleEngine,
    progress: bool = False,
) -> SimilarityResult:
    """Run LSH similarity detection stage."""
    logger.info("Stage 5/5: Finding similar pairs...")
    _t = time.monotonic()
    similarity_result = detect_similarity(
        signatures,
        similarity_percent=threshold,
        shingled_regions=shingled_regions,
        min_lines=min_lines,
        rules=rule_engine.rules,
        progress=progress,
        verification_timeout=get_settings().lsh.verification_timeout,
        max_group_pairs=get_settings().lsh.max_group_pairs,
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



def run_pipeline(target_path: str | Path, progress: bool = False) -> SimilarityResult:
    """Detect similarities globally while preprocessing one file at a time."""
    settings = get_settings()
    engine = build_rule_engine(settings)
    data = preprocess(Path(target_path), engine, settings, progress=progress)
    result = _run_lsh_stage(
        data.signatures, data.shingles, settings.lsh.similarity_percent,
        settings.lsh.min_lines, engine, progress=progress,
    )
    result.issues.extend(data.issues)
    result.files_discovered = data.files_discovered
    result.files_parsed = data.counts["parse"]
    logger.info("Pipeline complete: %d groups found", len(result.similar_groups))
    return result
