"""Verification stage for refining candidate similar pairs.

This module implements the verification step that comes after LSH candidate detection.
Per ADR 2, the full pipeline should be:
    Parse → Normalize → Shingles → MinHash → LSH → Candidates → PQ-Gram → TED

This module implements a lightweight verification using order-sensitive shingle comparison
as a pragmatic alternative to full PQ-Gram/TED verification.
"""

import logging
from pathlib import Path

from tssim.models.shingle import ShingledRegion
from tssim.models.similarity import SimilarRegionPair


logger = logging.getLogger(__name__)


def _compute_lcs_length(shingles1: list[str], shingles2: list[str]) -> int:
    """Compute longest common subsequence length using dynamic programming.

    Args:
        shingles1: First list of shingles
        shingles2: Second list of shingles

    Returns:
        Length of longest common subsequence
    """
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
    """Normalize LCS length to similarity score.

    Args:
        lcs_length: Length of longest common subsequence
        len1: Length of first sequence
        len2: Length of second sequence

    Returns:
        Normalized similarity score between 0.0 and 1.0
    """
    avg_length = (len1 + len2) / 2
    return lcs_length / avg_length if avg_length > 0 else 0.0


def _compute_ordered_similarity(shingles1: list[str], shingles2: list[str]) -> float:
    """Compute order-sensitive similarity between two shingle lists.

    Uses longest common subsequence (LCS) to measure similarity while
    accounting for order. This is more accurate than set-based Jaccard
    for detecting when code blocks appear in different order.

    Args:
        shingles1: First list of shingles
        shingles2: Second list of shingles

    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not shingles1 or not shingles2:
        return 0.0

    lcs_length = _compute_lcs_length(shingles1, shingles2)
    return _normalize_similarity(lcs_length, len(shingles1), len(shingles2))


def _build_region_lookup(
    shingled_regions: list[ShingledRegion],
) -> dict[Path, dict[int, ShingledRegion]]:
    """Build lookup map from region path and start line to shingled region.

    Args:
        shingled_regions: List of shingled regions

    Returns:
        Nested dict mapping path -> start_line -> shingled region
    """
    region_to_shingled: dict[Path, dict[int, ShingledRegion]] = {}
    for sr in shingled_regions:
        if sr.region.path not in region_to_shingled:
            region_to_shingled[sr.region.path] = {}
        region_to_shingled[sr.region.path][sr.region.start_line] = sr
    return region_to_shingled


def _verify_single_pair(
    pair: SimilarRegionPair,
    region_lookup: dict[Path, dict[int, ShingledRegion]],
) -> SimilarRegionPair:
    """Verify a single candidate pair using order-sensitive similarity.

    Args:
        pair: Candidate similar pair
        region_lookup: Lookup map for shingled regions

    Returns:
        Verified pair with updated similarity score
    """
    sr1 = region_lookup.get(pair.region1.path, {}).get(pair.region1.start_line)
    sr2 = region_lookup.get(pair.region2.path, {}).get(pair.region2.start_line)

    if sr1 is None or sr2 is None:
        logger.warning(
            "Could not find shingled regions for pair %s ↔ %s, skipping verification",
            pair.region1.region_name,
            pair.region2.region_name,
        )
        return pair

    ordered_similarity = _compute_ordered_similarity(
        sr1.shingles.shingles,
        sr2.shingles.shingles,
    )

    logger.debug(
        "Verified pair %s ↔ %s: LSH=%.1f%%, Ordered=%.1f%%",
        pair.region1.region_name,
        pair.region2.region_name,
        pair.similarity * 100,
        ordered_similarity * 100,
    )

    return SimilarRegionPair(
        region1=pair.region1,
        region2=pair.region2,
        similarity=ordered_similarity,
    )


def verify_similar_pairs(
    pairs: list[SimilarRegionPair],
    shingled_regions: list[ShingledRegion],
) -> list[SimilarRegionPair]:
    """Verify candidate pairs using order-sensitive similarity.

    Recomputes similarity for each candidate pair using ordered shingle comparison,
    which accounts for the sequence of code patterns rather than just their presence.

    Args:
        pairs: Candidate similar pairs from LSH
        shingled_regions: Shingled regions for lookup

    Returns:
        Verified pairs with updated similarity scores
    """
    logger.info("Verifying %d candidate pair(s) with order-sensitive similarity", len(pairs))

    region_lookup = _build_region_lookup(shingled_regions)
    verified_pairs = [_verify_single_pair(pair, region_lookup) for pair in pairs]

    logger.info("Verification complete: %d pair(s) verified", len(verified_pairs))
    return verified_pairs
