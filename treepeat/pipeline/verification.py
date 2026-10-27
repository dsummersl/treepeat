import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from rapidfuzz.distance import Indel
from tqdm import tqdm

from treepeat.models.shingle import ShingledRegion
from treepeat.pipeline.languages.base import rules_anonymize_region_name

if TYPE_CHECKING:
    from treepeat.models.similarity import Region, SimilarRegionGroup
    from treepeat.pipeline.rules.models import Rule

logger = logging.getLogger(__name__)




SOURCE_VERIFICATION_THRESHOLD = 0.98


def _compute_ordered_similarity(shingles1: list[str], shingles2: list[str]) -> float:

    if not shingles1 or not shingles2:
        return 0.0
    return Indel.normalized_similarity(shingles1, shingles2)


def _read_source_lines(file_path: Path, start_line: int, end_line: int) -> list[str]:

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

            return [line.rstrip() for line in lines[start_line - 1:end_line]]
    except Exception as e:
        logger.warning("Failed to read source from %s: %s", file_path, e)
        return []


def _check_signature_match(
    file_path1: Path, start_line1: int,
    file_path2: Path, start_line2: int
) -> bool:

    lines1 = _read_source_lines(file_path1, start_line1, start_line1)
    lines2 = _read_source_lines(file_path2, start_line2, start_line2)

    if not lines1 or not lines2:
        return True


    return lines1[0].strip() == lines2[0].strip()


def _build_region_lookup(
    shingled_regions: list[ShingledRegion],
) -> dict[Path, dict[int, ShingledRegion]]:

    region_to_shingled: dict[Path, dict[int, ShingledRegion]] = {}
    for sr in shingled_regions:
        if sr.region.path not in region_to_shingled:
            region_to_shingled[sr.region.path] = {}
        region_to_shingled[sr.region.path][sr.region.start_line] = sr
    return region_to_shingled


_CODE_REGION_TYPES = ("function", "class", "method")


def _both_names_anonymized(r1: "Region", r2: "Region", rules: "list[Rule]") -> bool:

    return rules_anonymize_region_name(rules, r1.language, r1.region_type) and (
        rules_anonymize_region_name(rules, r2.language, r2.region_type)
    )


def _should_verify_signatures(
    r1: "Region", r2: "Region", similarity: float, rules: "list[Rule]"
) -> bool:

    if similarity < SOURCE_VERIFICATION_THRESHOLD:
        return False
    if r1.region_type not in _CODE_REGION_TYPES or r2.region_type not in _CODE_REGION_TYPES:
        return False
    return not _both_names_anonymized(r1, r2, rules)


def _compute_pair_similarity_with_verification(
    r1: "Region",
    r2: "Region",
    region_lookup: dict[Path, dict[int, ShingledRegion]],
    rules: "list[Rule]",
) -> float:

    sr1 = region_lookup.get(r1.path, {}).get(r1.start_line)
    sr2 = region_lookup.get(r2.path, {}).get(r2.start_line)

    if sr1 is None or sr2 is None:
        logger.warning(
            "Could not find shingled regions for %s ↔ %s, using 0.0 similarity",
            r1.region_name,
            r2.region_name,
        )
        return 0.0


    shingle_similarity = _compute_ordered_similarity(
        sr1.shingles.get_contents(),
        sr2.shingles.get_contents(),
    )



    if not _should_verify_signatures(r1, r2, shingle_similarity, rules):
        return shingle_similarity

    signatures_match = _check_signature_match(
        r1.path, r1.start_line,
        r2.path, r2.start_line
    )

    if not signatures_match:

        logger.debug(
            "Signature mismatch for %s ↔ %s, treating as 0%% similar",
            r1.region_name,
            r2.region_name,
        )
        return 0.0

    return shingle_similarity


def _verify_group_pairwise_similarity(
    group_regions: list["Region"],
    region_lookup: dict[Path, dict[int, ShingledRegion]],
    rules: "list[Rule]",
) -> float:

    if len(group_regions) < 2:
        return 1.0

    total_similarity = 0.0
    pair_count = 0

    for i, r1 in enumerate(group_regions):
        for r2 in group_regions[i + 1 :]:
            similarity = _compute_pair_similarity_with_verification(
                r1, r2, region_lookup, rules
            )
            total_similarity += similarity
            pair_count += 1

    return total_similarity / pair_count if pair_count > 0 else 1.0


def verify_similar_groups(
    groups: list["SimilarRegionGroup"],
    shingled_regions: list[ShingledRegion],
    rules: "list[Rule]",
    progress: bool = False,
) -> list["SimilarRegionGroup"]:

    logger.info("Verifying %d candidate group(s) with order-sensitive similarity", len(groups))

    region_lookup = _build_region_lookup(shingled_regions)
    verified_groups = []

    iterable = (
        tqdm(groups, desc="Verifying", unit="group", file=sys.stderr)
        if progress
        else groups
    )

    for group in iterable:

        verified_similarity = _verify_group_pairwise_similarity(
            group.regions, region_lookup, rules
        )

        logger.debug(
            "Verified group of %d regions: LSH=%.1f%%, Ordered=%.1f%%",
            len(group.regions),
            group.similarity * 100,
            verified_similarity * 100,
        )


        from treepeat.models.similarity import SimilarRegionGroup

        verified_group = SimilarRegionGroup(
            regions=group.regions,
            similarity=verified_similarity,
        )
        verified_groups.append(verified_group)

    logger.info("Verification complete: %d group(s) verified", len(verified_groups))
    return verified_groups
