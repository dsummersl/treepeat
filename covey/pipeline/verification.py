import logging
from pathlib import Path
from typing import TYPE_CHECKING

from covey.models.shingle import ShingledRegion

if TYPE_CHECKING:
    from covey.models.similarity import Region, SimilarRegionGroup


logger = logging.getLogger(__name__)

# Threshold above which we verify against raw source text
# Only check signature for near-perfect matches (98%+) to catch false 100% matches
# where only the function/class name differs
SOURCE_VERIFICATION_THRESHOLD = 0.98


def _compute_lcs_length(shingles1: list[str], shingles2: list[str]) -> int:
    """Compute longest common subsequence length using dynamic programming."""
    m, n = len(shingles1), len(shingles2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if shingles1[i - 1] == shingles2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    return dp[m][n]


def _normalize_similarity(lcs_length: int, len1: int, len2: int) -> float:
    """Normalize LCS length to similarity score."""
    avg_length = (len1 + len2) / 2
    return lcs_length / avg_length if avg_length > 0 else 0.0


def _compute_ordered_similarity(shingles1: list[str], shingles2: list[str]) -> float:
    """Compute order-sensitive similarity between two shingle lists using LCS."""
    if not shingles1 or not shingles2:
        return 0.0

    lcs_length = _compute_lcs_length(shingles1, shingles2)
    return _normalize_similarity(lcs_length, len(shingles1), len(shingles2))


def _read_source_lines(file_path: Path, start_line: int, end_line: int) -> list[str]:
    """Read source lines from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            # Convert to 0-indexed
            return [line.rstrip() for line in lines[start_line - 1:end_line]]
    except Exception as e:
        logger.warning("Failed to read source from %s: %s", file_path, e)
        return []


def _compute_source_similarity(
    file_path1: Path, start_line1: int, end_line1: int,
    file_path2: Path, start_line2: int, end_line2: int
) -> float:
    """Compute similarity between two regions based on their actual source text."""
    lines1 = _read_source_lines(file_path1, start_line1, end_line1)
    lines2 = _read_source_lines(file_path2, start_line2, end_line2)

    if not lines1 or not lines2:
        return 0.0

    # Use LCS on actual source lines
    lcs_length = _compute_lcs_length(lines1, lines2)
    return _normalize_similarity(lcs_length, len(lines1), len(lines2))


def _check_signature_match(
    file_path1: Path, start_line1: int,
    file_path2: Path, start_line2: int
) -> bool:
    """Check if the first line (signature) of two regions matches.

    This catches cases where function/class names differ but bodies are similar.
    """
    lines1 = _read_source_lines(file_path1, start_line1, start_line1)
    lines2 = _read_source_lines(file_path2, start_line2, start_line2)

    if not lines1 or not lines2:
        return True  # If we can't read, don't penalize

    # Compare first lines (function/class signatures)
    return lines1[0].strip() == lines2[0].strip()


def _build_region_lookup(
    shingled_regions: list[ShingledRegion],
) -> dict[Path, dict[int, ShingledRegion]]:
    """Build lookup map from region path and start line to shingled region."""
    region_to_shingled: dict[Path, dict[int, ShingledRegion]] = {}
    for sr in shingled_regions:
        if sr.region.path not in region_to_shingled:
            region_to_shingled[sr.region.path] = {}
        region_to_shingled[sr.region.path][sr.region.start_line] = sr
    return region_to_shingled


def _should_verify_signatures(r1: "Region", r2: "Region", similarity: float) -> bool:
    """Determine if signature verification should be performed for these regions."""
    if similarity < SOURCE_VERIFICATION_THRESHOLD:
        return False

    code_region_types = ("function", "class", "method")
    return r1.region_type in code_region_types and r2.region_type in code_region_types


def _compute_pair_similarity_with_verification(
    r1: "Region",
    r2: "Region",
    region_lookup: dict[Path, dict[int, ShingledRegion]],
) -> float:
    """Compute similarity between two regions with signature verification."""
    sr1 = region_lookup.get(r1.path, {}).get(r1.start_line)
    sr2 = region_lookup.get(r2.path, {}).get(r2.start_line)

    if sr1 is None or sr2 is None:
        logger.warning(
            "Could not find shingled regions for %s ↔ %s, using 0.0 similarity",
            r1.region_name,
            r2.region_name,
        )
        return 0.0

    # Compute shingle-based similarity using shingle contents
    shingle_similarity = _compute_ordered_similarity(
        sr1.shingles.get_contents(),
        sr2.shingles.get_contents(),
    )

    # For high similarity code regions, verify that signatures match
    # This catches cases where function/class names differ but bodies are similar
    if not _should_verify_signatures(r1, r2, shingle_similarity):
        return shingle_similarity

    signatures_match = _check_signature_match(
        r1.path, r1.start_line,
        r2.path, r2.start_line
    )

    if not signatures_match:
        # Penalize signature mismatch - treat as 0.0 similarity
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
) -> float:
    """Calculate average pairwise order-sensitive similarity for a group."""
    if len(group_regions) < 2:
        return 1.0

    total_similarity = 0.0
    pair_count = 0

    for i, r1 in enumerate(group_regions):
        for r2 in group_regions[i + 1 :]:
            similarity = _compute_pair_similarity_with_verification(r1, r2, region_lookup)
            total_similarity += similarity
            pair_count += 1

    return total_similarity / pair_count if pair_count > 0 else 1.0


def verify_similar_groups(
    groups: list["SimilarRegionGroup"],
    shingled_regions: list[ShingledRegion],
) -> list["SimilarRegionGroup"]:
    """Verify candidate groups using order-sensitive similarity.

    For each group, recalculates similarity using pairwise LCS comparison
    to ensure matches respect line order (not just set similarity).
    """
    logger.info("Verifying %d candidate group(s) with order-sensitive similarity", len(groups))

    region_lookup = _build_region_lookup(shingled_regions)
    verified_groups = []

    for group in groups:
        # Recalculate group similarity using order-sensitive verification
        verified_similarity = _verify_group_pairwise_similarity(
            group.regions, region_lookup
        )

        logger.debug(
            "Verified group of %d regions: LSH=%.1f%%, Ordered=%.1f%%",
            len(group.regions),
            group.similarity * 100,
            verified_similarity * 100,
        )

        # Import here to avoid circular dependency
        from covey.models.similarity import SimilarRegionGroup

        verified_group = SimilarRegionGroup(
            regions=group.regions,
            similarity=verified_similarity,
        )
        verified_groups.append(verified_group)

    logger.info("Verification complete: %d group(s) verified", len(verified_groups))
    return verified_groups
