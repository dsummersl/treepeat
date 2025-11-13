"""Verification stage for refining candidate similar pairs.

This module implements the verification step that comes after LSH candidate detection.
Per ADR 2, the full pipeline should be:
    Parse → Normalize → Shingles → MinHash → LSH → Candidates → PQ-Gram → TED

This module implements a lightweight verification using order-sensitive shingle comparison
as a pragmatic alternative to full PQ-Gram/TED verification.
"""

import logging
from tssim.models.shingle import ShingledRegion
from tssim.models.similarity import SimilarRegionPair


logger = logging.getLogger(__name__)


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

    # Compute LCS length using dynamic programming
    m, n = len(shingles1), len(shingles2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if shingles1[i - 1] == shingles2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    lcs_length = dp[m][n]

    # Similarity is LCS length divided by average of both lengths
    # This gives a score between 0 and 1
    avg_length = (m + n) / 2
    return lcs_length / avg_length if avg_length > 0 else 0.0


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

    # Create lookup map from region to shingled region
    region_to_shingled: dict = {}
    for sr in shingled_regions:
        if sr.region.path not in region_to_shingled:
            region_to_shingled[sr.region.path] = {}
        region_to_shingled[sr.region.path][sr.region.start_line] = sr

    verified_pairs = []
    for pair in pairs:
        # Look up shingled regions for both regions in the pair
        path1 = pair.region1.path
        path2 = pair.region2.path

        sr1_map = region_to_shingled.get(path1, {})
        sr2_map = region_to_shingled.get(path2, {})

        sr1 = sr1_map.get(pair.region1.start_line)
        sr2 = sr2_map.get(pair.region2.start_line)

        if sr1 is None or sr2 is None:
            logger.warning(
                "Could not find shingled regions for pair %s ↔ %s, skipping verification",
                pair.region1.region_name,
                pair.region2.region_name,
            )
            verified_pairs.append(pair)
            continue

        # Compute order-sensitive similarity
        ordered_similarity = _compute_ordered_similarity(
            sr1.shingles.shingles,
            sr2.shingles.shingles,
        )

        # Create new pair with verified similarity
        verified_pair = SimilarRegionPair(
            region1=pair.region1,
            region2=pair.region2,
            similarity=ordered_similarity,
        )

        logger.debug(
            "Verified pair %s ↔ %s: LSH=%.1f%%, Ordered=%.1f%%",
            pair.region1.region_name,
            pair.region2.region_name,
            pair.similarity * 100,
            ordered_similarity * 100,
        )

        verified_pairs.append(verified_pair)

    logger.info("Verification complete: %d pair(s) verified", len(verified_pairs))
    return verified_pairs
