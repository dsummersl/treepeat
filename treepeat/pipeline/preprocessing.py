"""Streaming parse → extract → shingle → MinHash, one file at a time.

Retaining every parse tree (and every region's tree-sitter nodes) until all
files are processed dominates memory on large scans. Here each file's tree is
released as soon as its regions are fingerprinted; only compact, interned
shingle strings and MinHash signatures are kept for the global comparison.
"""

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
from treepeat.models.similarity import RegionSignature
from treepeat.pipeline.minhash_stage import create_minhash_signature
from treepeat.pipeline.parse import collect_source_files, parse_file
from treepeat.pipeline.region_extraction import _deduplicate_regions, extract_regions
from treepeat.pipeline.rules.engine import RuleEngine
from treepeat.pipeline.shingle import ASTShingler, _shingle_single_region
from treepeat.pipeline.verbose_metrics import record_stage_count, record_stage_timing

logger = logging.getLogger(__name__)

STAGES = ("parse", "extract", "shingle", "minhash")


@dataclass
class Preprocessed:
    """Comparison inputs retained after all parse trees have been released."""

    shingled_regions: list[ShingledRegion] = field(default_factory=list)
    signatures: list[RegionSignature] = field(default_factory=list)
    files_parsed: int = 0
    counts: Counter[str] = field(default_factory=Counter)
    timings: dict[str, float] = field(default_factory=lambda: defaultdict(float))


def _process_parsed_file(
    parsed: ParsedFile, shingler: ASTShingler, settings: PipelineSettings, out: Preprocessed
) -> None:
    start = time.monotonic()
    regions = _deduplicate_regions(extract_regions(parsed, shingler.rule_engine))
    out.timings["extract"] += time.monotonic() - start
    out.counts["extract"] += len(regions)

    for extracted in regions:
        region = extracted.region
        if region.end_line - region.start_line + 1 < settings.lsh.min_lines:
            continue
        start = time.monotonic()
        shingled = _shingle_single_region(extracted, {parsed.path: parsed.source}, shingler)
        out.timings["shingle"] += time.monotonic() - start
        if shingled is None:
            continue

        start = time.monotonic()
        minhash = create_minhash_signature(
            set(shingled.shingles.get_contents()), settings.minhash.num_perm
        )
        out.timings["minhash"] += time.monotonic() - start
        out.shingled_regions.append(shingled)
        out.signatures.append(
            RegionSignature(region=region, minhash=minhash, shingle_count=shingled.shingle_count)
        )
        out.counts["shingle"] += 1
        out.counts["minhash"] += 1


def _process_file(
    path: Path, shingler: ASTShingler, settings: PipelineSettings, out: Preprocessed
) -> None:
    try:
        start = time.monotonic()
        parsed = parse_file(path)
        out.timings["parse"] += time.monotonic() - start
        out.counts["parse"] += 1
        _process_parsed_file(parsed, shingler, settings, out)
    except Exception as e:
        logger.warning("Failed to process %s: %s", path, e)
    finally:
        # Query captures hold tree-sitter Nodes and the engine holds the source bytes.
        shingler.rule_engine.reset_identifiers()
        shingler.rule_engine.release_source()


def preprocess(
    target_path: Path,
    rule_engine: RuleEngine,
    settings: PipelineSettings,
    progress: bool = False,
) -> Preprocessed:
    """Fingerprint every source file under target_path without retaining its parse tree."""
    files = collect_source_files(target_path)
    if not files:
        logger.warning("Path does not exist or contains no source files: %s", target_path)

    out = Preprocessed()
    # Shared by every region so equal shingle strings are stored once.
    shingler = ASTShingler(rule_engine, k=settings.shingle.k, symbols={})
    iterable = tqdm(files, desc="Preprocessing", unit="file", file=sys.stderr) if progress else files
    for path in iterable:
        _process_file(path, shingler, settings, out)

    out.files_parsed = out.counts["parse"]
    for stage in STAGES:
        record_stage_count(stage, out.counts[stage])
        record_stage_timing(stage, out.timings[stage])
    _log_summary(out)
    return out


def _log_summary(out: Preprocessed) -> None:
    c, t = out.counts, out.timings
    logger.info("Parse complete: %d succeeded (%.1fs)", c["parse"], t["parse"])
    logger.info("Extracted %d region(s) from %d file(s) (%.1fs)", c["extract"], c["parse"], t["extract"])
    logger.info("Shingling complete: %d region(s) shingled (%.1fs)", c["shingle"], t["shingle"])
    logger.info("Created %d signature(s) (%.1fs)", c["minhash"], t["minhash"])
