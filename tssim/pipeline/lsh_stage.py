"""LSH stage for finding similar region pairs."""

import logging
from pathlib import Path

from datasketch import MinHashLSH  # type: ignore[import-untyped]

from tssim.models.similarity import RegionSignature, SimilarRegionPair, SimilarityResult

logger = logging.getLogger(__name__)


def _create_lsh_index(
    signatures: list[RegionSignature],
    threshold: float,
) -> MinHashLSH:
    """Create and populate LSH index. """
    num_perm = signatures[0].minhash.hashvalues.shape[0]

    lsh = MinHashLSH(threshold, num_perm)

    for sig in signatures:
        # Create a unique key for each region (path + line range)
        key = f"{sig.region.path}:{sig.region.start_line}-{sig.region.end_line}"
        lsh.insert(key, sig.minhash)

    logger.debug(
        "Inserted %d region signatures into LSH index (lsh_threshold=%.2f, filter_threshold=%.2f)",
        len(signatures), threshold, threshold
    )
    return lsh


def _find_signature_by_key(
    signatures: list[RegionSignature],
    key: str,
) -> RegionSignature | None:
    """Find signature by region key.

    Args:
        signatures: List of signatures to search
        key: Region key (path:start-end) to find

    Returns:
        Matching signature or None
    """
    return next(
        (
            s
            for s in signatures
            if f"{s.region.path}:{s.region.start_line}-{s.region.end_line}" == key
        ),
        None,
    )


def _create_similar_pair(
    sig1: RegionSignature,
    sig2: RegionSignature,
) -> SimilarRegionPair:
    """Create a similar region pair with computed similarity.

    Args:
        sig1: First signature
        sig2: Second signature

    Returns:
        SimilarRegionPair with Jaccard similarity

    Note:
        If both signatures have zero shingles, similarity is set to 0.0
        (not 1.0) because empty regions shouldn't be considered similar.
    """
    # If both regions have no shingles, they should not be considered similar
    # (even though mathematically Jaccard(∅, ∅) = 1.0)
    if sig1.shingle_count == 0 and sig2.shingle_count == 0:
        similarity = 0.0
    else:
        similarity = sig1.minhash.jaccard(sig2.minhash)

    return SimilarRegionPair(
        region1=sig1.region,
        region2=sig2.region,
        similarity=similarity,
    )


def _process_candidate_pair(
    sig: RegionSignature,
    similar_key: str,
    current_key: str,
    signatures: list[RegionSignature],
    seen_pairs: set[tuple[str, str]],
    threshold: float,
) -> SimilarRegionPair | None:
    """Process a candidate similar pair.

    Args:
        sig: Current signature
        similar_key: Key of potentially similar region
        current_key: Key of current region
        signatures: All signatures
        seen_pairs: Set of already processed pair keys
        threshold: Similarity threshold

    Returns:
        SimilarRegionPair if valid and above threshold, None otherwise
    """
    if similar_key == current_key:
        return None

    similar_sig = _find_signature_by_key(signatures, similar_key)
    if similar_sig is None:
        return None

    # Filter out self-overlapping pairs (regions in the same file with overlapping line ranges)
    if _regions_overlap(sig.region, similar_sig.region):
        return None

    sorted_keys = sorted([current_key, similar_key])
    pair_key = (sorted_keys[0], sorted_keys[1])
    if pair_key in seen_pairs:
        return None

    seen_pairs.add(pair_key)
    pair = _create_similar_pair(sig, similar_sig)

    if pair.similarity < threshold:
        return None

    logger.debug(
        "Found similar pair: %s ↔ %s (%.1f%% similar)",
        sig.region.region_name,
        similar_sig.region.region_name,
        pair.similarity * 100,
    )

    return pair


def _process_signature_candidates(
    sig: RegionSignature,
    lsh: MinHashLSH,
    signatures: list[RegionSignature],
    seen_pairs: set[tuple[str, str]],
    threshold: float,
) -> list[SimilarRegionPair]:
    """Process all candidate pairs for a signature.

    Args:
        sig: Signature to find candidates for
        lsh: LSH index
        signatures: All signatures
        seen_pairs: Set of already processed pair keys
        threshold: Similarity threshold

    Returns:
        List of valid similar pairs
    """
    pairs: list[SimilarRegionPair] = []
    similar_keys = lsh.query(sig.minhash)
    current_key = f"{sig.region.path}:{sig.region.start_line}-{sig.region.end_line}"

    for similar_key in similar_keys:
        pair = _process_candidate_pair(
            sig, similar_key, current_key, signatures, seen_pairs, threshold
        )
        if pair is not None:
            pairs.append(pair)

    return pairs


def _regions_overlap(r1, r2) -> bool:
    """Check if two regions overlap in the same file.

    Args:
        r1: First region
        r2: Second region

    Returns:
        True if regions are in the same file and have overlapping line ranges
    """
    if r1.path != r2.path:
        return False
    return not (r1.end_line < r2.start_line or r2.end_line < r1.start_line)


def _region_size(region) -> int:
    """Get the size of a region in lines.

    Args:
        region: Region to measure

    Returns:
        Number of lines in the region
    """
    return region.end_line - region.start_line + 1


def _filter_overlapping_pairs(pairs: list[SimilarRegionPair]) -> list[SimilarRegionPair]:
    """Filter out overlapping pairs, keeping only the largest regions.

    When multiple pairs have overlapping regions, keeps only the pair(s) with
    the largest regions (most lines). This implements greedy matching where
    larger code structures take precedence over nested smaller ones.

    Args:
        pairs: List of similar pairs

    Returns:
        Filtered list with overlapping pairs removed
    """
    if not pairs:
        return []

    # Sort by size (largest first) for greedy selection
    sorted_pairs = sorted(
        pairs,
        key=lambda p: (_region_size(p.region1) + _region_size(p.region2)),
        reverse=True
    )

    kept_pairs = []

    for candidate in sorted_pairs:
        # Check if this candidate overlaps with any already kept pair
        has_overlap = False
        for kept in kept_pairs:
            # Check if any regions overlap
            if (_regions_overlap(candidate.region1, kept.region1) or
                _regions_overlap(candidate.region1, kept.region2) or
                _regions_overlap(candidate.region2, kept.region1) or
                _regions_overlap(candidate.region2, kept.region2)):
                has_overlap = True
                logger.debug(
                    "Filtering out pair %s:%d-%d ↔ %s:%d-%d (overlaps with kept pair)",
                    candidate.region1.region_name, candidate.region1.start_line, candidate.region1.end_line,
                    candidate.region2.region_name, candidate.region2.start_line, candidate.region2.end_line,
                )
                break

        if not has_overlap:
            kept_pairs.append(candidate)
            logger.debug(
                "Keeping pair %s:%d-%d ↔ %s:%d-%d (size: %d lines)",
                candidate.region1.region_name, candidate.region1.start_line, candidate.region1.end_line,
                candidate.region2.region_name, candidate.region2.start_line, candidate.region2.end_line,
                _region_size(candidate.region1) + _region_size(candidate.region2),
            )

    return kept_pairs


def find_similar_pairs(
    signatures: list[RegionSignature],
    threshold: float = 0.5,
) -> list[SimilarRegionPair]:
    """Find similar region pairs using LSH.

    Args:
        signatures: List of region signatures
        threshold: Jaccard similarity threshold

    Returns:
        List of similar region pairs above the threshold (including self-similarity)
    """
    if len(signatures) < 2:
        logger.info("Need at least 2 regions to find similar pairs")
        return []

    logger.info(
        "Finding similar pairs using LSH (threshold=%.2f) for %d region(s)",
        threshold,
        len(signatures),
    )

    lsh = _create_lsh_index(signatures, threshold)
    seen_pairs: set[tuple[str, str]] = set()
    pairs: list[SimilarRegionPair] = []

    for sig in signatures:
        sig_pairs = _process_signature_candidates(sig, lsh, signatures, seen_pairs, threshold)
        if sig_pairs:
            logger.debug(
                "Query for %s:%d-%d returned %d candidate pair(s)",
                sig.region.region_name, sig.region.start_line, sig.region.end_line,
                len(sig_pairs)
            )
        pairs.extend(sig_pairs)

    pairs.sort(key=lambda p: p.similarity, reverse=True)
    logger.info(
        "Found %d similar pair(s) above threshold (%d self-similar)",
        len(pairs),
        sum(1 for p in pairs if p.is_self_similarity),
    )

    # Apply greedy filtering to remove overlapping matches
    filtered_pairs = _filter_overlapping_pairs(pairs)
    if len(filtered_pairs) < len(pairs):
        logger.info(
            "Filtered %d overlapping pair(s), keeping %d largest region(s)",
            len(pairs) - len(filtered_pairs),
            len(filtered_pairs),
        )

    return filtered_pairs


def detect_similarity(
    signatures: list[RegionSignature],
    threshold: float = 0.5,
    failed_files: dict[Path, str] | None = None,
) -> SimilarityResult:
    """Detect similar regions using LSH.

    Args:
        signatures: List of region signatures
        threshold: Jaccard similarity threshold for LSH
        failed_files: Optional dict of failed files from earlier stages

    Returns:
        SimilarityResult with similar region pairs
    """
    # Find similar pairs using LSH
    similar_pairs = find_similar_pairs(signatures, threshold=threshold)

    return SimilarityResult(
        signatures=signatures,
        similar_pairs=similar_pairs,
        failed_files=failed_files or {},
    )
