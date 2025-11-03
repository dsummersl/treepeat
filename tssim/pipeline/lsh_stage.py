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
    """Create and populate LSH index.

    Args:
        signatures: List of region signatures
        threshold: Jaccard similarity threshold

    Returns:
        Populated LSH index
    """
    num_perm = signatures[0].minhash.hashvalues.shape[0]
    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)

    for sig in signatures:
        # Create a unique key for each region (path + line range)
        key = f"{sig.region.path}:{sig.region.start_line}-{sig.region.end_line}"
        lsh.insert(key, sig.minhash)

    logger.debug("Inserted %d region signatures into LSH index", len(signatures))
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
    """
    similarity = sig1.minhash.jaccard(sig2.minhash)
    return SimilarRegionPair(
        region1=sig1.region,
        region2=sig2.region,
        similarity=similarity,
    )


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

    pairs = []
    seen_pairs = set()

    for sig in signatures:
        similar_keys = lsh.query(sig.minhash)
        current_key = f"{sig.region.path}:{sig.region.start_line}-{sig.region.end_line}"

        for similar_key in similar_keys:
            # Skip exact self-matches (same region)
            if similar_key == current_key:
                continue

            # Find the corresponding signature
            similar_sig = _find_signature_by_key(signatures, similar_key)
            if similar_sig is None:
                continue

            # Create canonical pair key (sorted to avoid duplicates)
            # Use unique region keys to distinguish different regions in same file
            pair_key = tuple(sorted([current_key, similar_key]))
            if pair_key in seen_pairs:
                continue

            seen_pairs.add(pair_key)
            pair = _create_similar_pair(sig, similar_sig)

            # Filter by actual threshold (LSH returns candidates that may be below threshold)
            if pair.similarity < threshold:
                continue

            pairs.append(pair)

            logger.debug(
                "Found similar pair: %s ↔ %s (%.1%% similar)",
                sig.region.region_name,
                similar_sig.region.region_name,
                pair.similarity * 100,
            )

    pairs.sort(key=lambda p: p.similarity, reverse=True)
    logger.info(
        "Found %d similar pair(s) above threshold (%d self-similar)",
        len(pairs),
        sum(1 for p in pairs if p.is_self_similarity),
    )
    return pairs


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
