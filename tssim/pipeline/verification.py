"""Verification stage for refining candidate similar groups.

This module implements the verification step that comes after LSH candidate detection.
Per ADR 2, the full pipeline should be:
    Parse → Normalize → Shingles → MinHash → LSH → Candidates → PQ-Gram → TED

This module implements a lightweight verification using order-sensitive shingle comparison
(LCS-based) as a pragmatic alternative to full PQ-Gram/TED verification. It verifies that
regions matched by minhash-LSH (which is order-insensitive) actually have matching line
order using Longest Common Subsequence (LCS).
"""

import logging
from pathlib import Path

from tssim.models.shingle import ShingledRegion


logger = logging.getLogger(__name__)


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


def _verify_group_pairwise_similarity(
    group_regions: list,
    region_lookup: dict[Path, dict[int, ShingledRegion]],
) -> float:
    """Calculate average pairwise order-sensitive similarity for a group."""
    if len(group_regions) < 2:
        return 1.0

    total_similarity = 0.0
    pair_count = 0

    for i, r1 in enumerate(group_regions):
        for r2 in group_regions[i + 1 :]:
            sr1 = region_lookup.get(r1.path, {}).get(r1.start_line)
            sr2 = region_lookup.get(r2.path, {}).get(r2.start_line)

            if sr1 is None or sr2 is None:
                logger.warning(
                    "Could not find shingled regions for %s ↔ %s, using 0.0 similarity",
                    r1.region_name,
                    r2.region_name,
                )
                similarity = 0.0
            else:
                similarity = _compute_ordered_similarity(
                    sr1.shingles.shingles,
                    sr2.shingles.shingles,
                )

            total_similarity += similarity
            pair_count += 1

    return total_similarity / pair_count if pair_count > 0 else 1.0


def verify_similar_groups(
    groups: list,
    shingled_regions: list[ShingledRegion],
) -> list:
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
        from tssim.models.similarity import SimilarRegionGroup

        verified_group = SimilarRegionGroup(
            regions=group.regions,
            similarity=verified_similarity,
        )
        verified_groups.append(verified_group)

    logger.info("Verification complete: %d group(s) verified", len(verified_groups))
    return verified_groups
