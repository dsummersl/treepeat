import logging
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from tqdm import tqdm

from treepeat.config import PipelineSettings
from treepeat.models.ast import ParsedFile
from treepeat.models.shingle import ShingledRegion
from treepeat.models.similarity import RegionSignature, ScanIssue
from treepeat.pipeline.minhash_stage import create_minhash_signature
from treepeat.pipeline.parse import collect_source_files, parse_file
from treepeat.pipeline.region_extraction import _deduplicate_regions, extract_regions
from treepeat.pipeline.rules.engine import RuleEngine
from treepeat.pipeline.shingle import ASTShingler, _shingle_single_region
from treepeat.pipeline.verbose_metrics import record_stage_count, record_stage_timing

logger = logging.getLogger(__name__)


@dataclass
class Preprocessed:
    """Global fingerprints and compact sequences, without retained parse trees."""

    shingles: list[ShingledRegion] = field(default_factory=list)
    signatures: list[RegionSignature] = field(default_factory=list)
    issues: list[ScanIssue] = field(default_factory=list)
    counts: Counter[str] = field(default_factory=Counter)
    timings: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    files_discovered: int = 0


def _process_regions(
    parsed: ParsedFile, shingler: ASTShingler, settings: PipelineSettings, result: Preprocessed,
) -> None:
    start = time.monotonic()
    regions = _deduplicate_regions(extract_regions(parsed, shingler.rule_engine))
    result.timings["extract"] += time.monotonic() - start
    result.counts["extract"] += len(regions)
    for extracted in regions:
        if extracted.region.end_line - extracted.region.start_line + 1 < settings.lsh.min_lines:
            continue
        start = time.monotonic()
        shingled = _shingle_single_region(extracted, {parsed.path: parsed.source}, shingler)
        result.timings["shingle"] += time.monotonic() - start
        if shingled is not None:
            _append_signature(shingled, settings, result)


def _append_signature(shingled: ShingledRegion, settings: PipelineSettings, result: Preprocessed) -> None:
    start = time.monotonic()
    fingerprint = create_minhash_signature(set(shingled.shingles.get_contents()), settings.minhash.num_perm)
    result.timings["minhash"] += time.monotonic() - start
    result.shingles.append(shingled)
    result.signatures.append(RegionSignature(
        region=shingled.region, minhash=fingerprint, shingle_count=shingled.shingle_count,
    ))
    result.counts["shingle"] += 1
    result.counts["minhash"] += 1


def _process_file(
    path: Path, shingler: ASTShingler, settings: PipelineSettings, result: Preprocessed,
) -> None:
    try:
        start = time.monotonic()
        parsed = parse_file(path)
        result.timings["parse"] += time.monotonic() - start
        result.counts["parse"] += 1
        if parsed.root_node.has_error:
            result.issues.append(ScanIssue(
                code="parse-warning", level="warning", path=path,
                message="Syntax tree contains errors; some source constructs may not be analyzed.",
            ))
        _process_regions(parsed, shingler, settings, result)
    except Exception as error:
        logger.error("Failed to process %s: %s", path, error)
        result.issues.append(ScanIssue(code="processing-error", path=path, message=str(error)))
    finally:
        # Query captures retain Node objects and the engine retains the source bytes.
        shingler.rule_engine.reset_identifiers()


def preprocess(
    target: Path, engine: RuleEngine, settings: PipelineSettings, progress: bool = False,
) -> Preprocessed:
    """Process one file at a time while retaining a global comparison index."""
    files = collect_source_files(target)
    result = Preprocessed(files_discovered=len(files))
    if not target.exists():
        result.issues.append(ScanIssue(code="missing-path", path=target, message="Scan path does not exist"))
    symbols: dict[str, str] = {}
    shingler = ASTShingler(engine, k=settings.shingle.k, symbols=symbols)
    iterable = tqdm(files, desc="Preprocessing", unit="file", file=sys.stderr) if progress else files
    for path in iterable:
        _process_file(path, shingler, settings, result)
    for stage in ("parse", "extract", "shingle", "minhash"):
        record_stage_count(stage, result.counts[stage])
        record_stage_timing(stage, result.timings[stage])
    _log_preprocessing(result)
    return result


def _log_preprocessing(result: Preprocessed) -> None:
    counts, times = result.counts, result.timings
    logger.info("Parse complete: %d succeeded (%.1fs)", counts["parse"], times["parse"])
    logger.info("Extracted %d total region(s)", counts["extract"])
    logger.info("Extracted %d region(s) from %d file(s) (%.1fs)", counts["extract"], counts["parse"], times["extract"])
    logger.info("Shingling %d region(s) across %d file(s)", counts["shingle"], counts["parse"])
    logger.info("Shingling complete: %d region(s) shingled (%.1fs)", counts["shingle"], times["shingle"])
    logger.info("Created %d signature(s) (%.1fs)", counts["minhash"], times["minhash"])
