"""LSH stage for finding similar region pairs."""

import logging
from pathlib import Path

from datasketch import MinHashLSH  # type: ignore[import-untyped]

from tssim.models.shingle import ShingledRegion
from tssim.models.similarity import Region, RegionSignature, SimilarRegionPair, SimilarRegionGroup, SimilarityResult
from tssim.pipeline.verification import verify_similar_pairs

logger = logging.getLogger(__name__)


def _create_lsh_index(
    signatures: list[RegionSignature],
    threshold: float,
) -> MinHashLSH:
    """Create and populate LSH index. """
    num_perm = signatures[0].minhash.hashvalues.shape[0]

    lsh_threshold = min(threshold, 0.98)
    lsh = MinHashLSH(lsh_threshold, num_perm)

    for sig in signatures:
        # Create a unique key for each region (path + line range)
        key = f"{sig.region.path}:{sig.region.start_line}-{sig.region.end_line}"
        lsh.insert(key, sig.minhash)

    logger.debug(
        "Inserted %d region signatures into LSH index (lsh_threshold=%.2f, filter_threshold=%.2f)",
        len(signatures), lsh_threshold, threshold
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


def _is_valid_pair_candidate(
    sig: RegionSignature,
    similar_sig: RegionSignature,
    current_key: str,
    similar_key: str,
    seen_pairs: set[tuple[str, str]],
) -> bool:
    """Check if a pair is a valid candidate for similarity comparison.

    Args:
        sig: Current signature
        similar_sig: Similar signature
        current_key: Key of current region
        similar_key: Key of similar region
        seen_pairs: Set of already processed pair keys

    Returns:
        True if pair is valid for comparison
    """
    # Skip self-overlapping pairs
    if _regions_overlap(sig.region, similar_sig.region):
        return False

    # Check if already processed
    sorted_keys = sorted([current_key, similar_key])
    pair_key = (sorted_keys[0], sorted_keys[1])
    return pair_key not in seen_pairs


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

    if not _is_valid_pair_candidate(sig, similar_sig, current_key, similar_key, seen_pairs):
        return None

    sorted_keys = sorted([current_key, similar_key])
    pair_key = (sorted_keys[0], sorted_keys[1])
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


def _regions_overlap(r1: Region, r2: Region) -> bool:
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


def _region_size(region: Region) -> int:
    """Get the size of a region in lines.

    Args:
        region: Region to measure

    Returns:
        Number of lines in the region
    """
    return region.end_line - region.start_line + 1


def _pairs_have_overlap(pair1: SimilarRegionPair, pair2: SimilarRegionPair) -> bool:
    """Check if two pairs have any overlapping regions.

    Args:
        pair1: First pair
        pair2: Second pair

    Returns:
        True if any regions overlap
    """
    return any([
        _regions_overlap(pair1.region1, pair2.region1),
        _regions_overlap(pair1.region1, pair2.region2),
        _regions_overlap(pair1.region2, pair2.region1),
        _regions_overlap(pair1.region2, pair2.region2),
    ])


def _pair_overlaps_with_any(
    candidate: SimilarRegionPair, kept_pairs: list[SimilarRegionPair]
) -> bool:
    """Check if a candidate pair overlaps with any kept pairs.

    Args:
        candidate: Candidate pair to check
        kept_pairs: List of already kept pairs

    Returns:
        True if candidate overlaps with any kept pair
    """
    return any(_pairs_have_overlap(candidate, kept) for kept in kept_pairs)


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

    kept_pairs: list[SimilarRegionPair] = []

    for candidate in sorted_pairs:
        if _pair_overlaps_with_any(candidate, kept_pairs):
            logger.debug(
                "Filtering out pair %s:%d-%d ↔ %s:%d-%d (overlaps with kept pair)",
                candidate.region1.region_name, candidate.region1.start_line, candidate.region1.end_line,
                candidate.region2.region_name, candidate.region2.start_line, candidate.region2.end_line,
            )
            continue

        kept_pairs.append(candidate)
        logger.debug(
            "Keeping pair %s:%d-%d ↔ %s:%d-%d (size: %d lines)",
            candidate.region1.region_name, candidate.region1.start_line, candidate.region1.end_line,
            candidate.region2.region_name, candidate.region2.start_line, candidate.region2.end_line,
            _region_size(candidate.region1) + _region_size(candidate.region2),
        )

    return kept_pairs


def _collect_candidate_pairs(
    signatures: list[RegionSignature],
    lsh: MinHashLSH,
    threshold: float,
) -> list[SimilarRegionPair]:
    """Collect all candidate pairs from LSH queries.

    Args:
        signatures: List of region signatures
        lsh: LSH index
        threshold: Similarity threshold

    Returns:
        List of similar pairs above threshold
    """
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

    return pairs


class UnionFind:
    """Union-Find data structure for grouping similar regions."""

    def __init__(self) -> None:
        """Initialize union-find structure."""
        self.parent: dict[str, str] = {}
        self.rank: dict[str, int] = {}

    def find(self, key: str) -> str:
        """Find the root of the set containing key.

        Args:
            key: Key to find

        Returns:
            Root key of the set
        """
        if key not in self.parent:
            self.parent[key] = key
            self.rank[key] = 0
            return key

        # Path compression
        if self.parent[key] != key:
            self.parent[key] = self.find(self.parent[key])
        return self.parent[key]

    def union(self, key1: str, key2: str) -> None:
        """Union the sets containing key1 and key2.

        Args:
            key1: First key
            key2: Second key
        """
        root1 = self.find(key1)
        root2 = self.find(key2)

        if root1 == root2:
            return

        # Union by rank
        if self.rank[root1] < self.rank[root2]:
            self.parent[root1] = root2
        elif self.rank[root1] > self.rank[root2]:
            self.parent[root2] = root1
        else:
            self.parent[root2] = root1
            self.rank[root1] += 1

    def get_groups(self) -> dict[str, list[str]]:
        """Get all groups as a dictionary mapping root to members.

        Returns:
            Dictionary mapping root keys to lists of member keys
        """
        groups: dict[str, list[str]] = {}
        for key in self.parent:
            root = self.find(key)
            if root not in groups:
                groups[root] = []
            groups[root].append(key)
        return groups


def _compute_pair_similarity(sig1: RegionSignature, sig2: RegionSignature) -> float:
    """Compute similarity between two signatures.

    Args:
        sig1: First signature
        sig2: Second signature

    Returns:
        Jaccard similarity (0.0 if both have zero shingles)
    """
    if sig1.shingle_count == 0 and sig2.shingle_count == 0:
        return 0.0
    return float(sig1.minhash.jaccard(sig2.minhash))


def _calculate_group_similarity(
    group_sigs: list[RegionSignature],
) -> float:
    """Calculate average pairwise similarity for a group.

    Args:
        group_sigs: List of signatures in the group

    Returns:
        Average Jaccard similarity across all pairs
    """
    if len(group_sigs) < 2:
        return 1.0

    total_similarity = 0.0
    pair_count = 0

    for i, sig1 in enumerate(group_sigs):
        for sig2 in group_sigs[i + 1:]:
            total_similarity += _compute_pair_similarity(sig1, sig2)
            pair_count += 1

    return total_similarity / pair_count if pair_count > 0 else 1.0


def _union_similar_keys(
    uf: UnionFind,
    current_key: str,
    similar_keys: list[str],
    sig: RegionSignature,
    signatures: list[RegionSignature],
) -> None:
    """Union a signature with its similar keys.

    Args:
        uf: Union-find structure
        current_key: Key of current signature
        similar_keys: Keys of similar signatures
        sig: Current signature
        signatures: All signatures
    """
    for similar_key in similar_keys:
        if similar_key == current_key:
            continue

        similar_sig = _find_signature_by_key(signatures, similar_key)
        if similar_sig is None:
            continue

        if _regions_overlap(sig.region, similar_sig.region):
            continue

        uf.union(current_key, similar_key)


def _build_union_find_from_lsh(
    signatures: list[RegionSignature],
    lsh: MinHashLSH,
) -> tuple[UnionFind, dict[str, RegionSignature]]:
    """Build union-find structure from LSH queries.

    Args:
        signatures: List of region signatures
        lsh: LSH index

    Returns:
        Tuple of (union-find structure, key-to-signature mapping)
    """
    uf = UnionFind()
    key_to_sig: dict[str, RegionSignature] = {}

    for sig in signatures:
        current_key = f"{sig.region.path}:{sig.region.start_line}-{sig.region.end_line}"
        key_to_sig[current_key] = sig

        similar_keys = lsh.query(sig.minhash)
        logger.debug(
            "Query for %s:%d-%d returned %d similar key(s)",
            sig.region.region_name, sig.region.start_line, sig.region.end_line,
            len(similar_keys)
        )

        _union_similar_keys(uf, current_key, similar_keys, sig, signatures)

    return uf, key_to_sig


def _get_valid_group_signatures(
    member_keys: list[str],
    key_to_sig: dict[str, RegionSignature],
) -> list[RegionSignature] | None:
    """Get signatures for member keys if valid.

    Args:
        member_keys: List of region keys
        key_to_sig: Mapping from keys to signatures

    Returns:
        List of signatures if at least 2 valid, None otherwise
    """
    group_sigs = [key_to_sig[key] for key in member_keys if key in key_to_sig]
    return group_sigs if len(group_sigs) >= 2 else None


def _create_group_from_keys(
    member_keys: list[str],
    key_to_sig: dict[str, RegionSignature],
    threshold: float,
) -> SimilarRegionGroup | None:
    """Create a similarity group from member keys.

    Args:
        member_keys: List of region keys in the group
        key_to_sig: Mapping from keys to signatures
        threshold: Similarity threshold

    Returns:
        SimilarRegionGroup if valid, None otherwise
    """
    group_sigs = _get_valid_group_signatures(member_keys, key_to_sig)
    if group_sigs is None:
        return None

    similarity = _calculate_group_similarity(group_sigs)
    if similarity < threshold:
        return None

    regions = [sig.region for sig in group_sigs]
    logger.debug(
        "Found similar group of %d region(s) with %.1f%% similarity",
        len(regions),
        similarity * 100,
    )

    return SimilarRegionGroup(regions=regions, similarity=similarity)


def _collect_candidate_groups(
    signatures: list[RegionSignature],
    lsh: MinHashLSH,
    threshold: float,
) -> list[SimilarRegionGroup]:
    """Collect similar region groups from LSH queries.

    Args:
        signatures: List of region signatures
        lsh: LSH index
        threshold: Similarity threshold

    Returns:
        List of similar region groups above threshold
    """
    # Build union-find structure
    uf, key_to_sig = _build_union_find_from_lsh(signatures, lsh)

    # Extract groups from union-find
    groups_dict = uf.get_groups()
    groups: list[SimilarRegionGroup] = []

    for root, member_keys in groups_dict.items():
        # Skip single-region "groups"
        if len(member_keys) < 2:
            continue

        # Create and validate group
        group = _create_group_from_keys(member_keys, key_to_sig, threshold)
        if group is not None:
            groups.append(group)

    return groups


def find_similar_groups(
    signatures: list[RegionSignature],
    threshold: float = 0.5,
) -> list[SimilarRegionGroup]:
    """Find similar region groups using LSH.

    Args:
        signatures: List of region signatures
        threshold: Jaccard similarity threshold

    Returns:
        List of similar region groups above the threshold
    """
    if len(signatures) < 2:
        logger.info("Need at least 2 regions to find similar groups")
        return []

    logger.info(
        "Finding similar groups using LSH (threshold=%.2f) for %d region(s)",
        threshold,
        len(signatures),
    )

    lsh = _create_lsh_index(signatures, threshold)
    groups = _collect_candidate_groups(signatures, lsh, threshold)

    groups.sort(key=lambda g: g.similarity, reverse=True)
    logger.info(
        "Found %d similar group(s) above threshold",
        len(groups),
    )

    return groups


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
    pairs = _collect_candidate_pairs(signatures, lsh, threshold)

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


def _should_verify_candidates(
    verify_candidates: bool,
    shingled_regions: list[ShingledRegion] | None,
    candidate_pairs: list[SimilarRegionPair],
) -> bool:
    """Check if candidate verification should be performed.

    Args:
        verify_candidates: Whether verification is enabled
        shingled_regions: Shingled regions for verification
        candidate_pairs: Candidate pairs to verify

    Returns:
        True if verification should be performed
    """
    return verify_candidates and shingled_regions is not None and len(candidate_pairs) > 0


def _verify_and_filter_pairs(
    candidate_pairs: list[SimilarRegionPair],
    shingled_regions: list[ShingledRegion],
    threshold: float,
) -> list[SimilarRegionPair]:
    """Verify candidate pairs and filter by threshold.

    Args:
        candidate_pairs: Candidate pairs from LSH
        shingled_regions: Shingled regions for verification
        threshold: Similarity threshold for filtering

    Returns:
        Verified and filtered similar pairs
    """
    logger.info("Verifying %d candidate pair(s)", len(candidate_pairs))
    verified_pairs = verify_similar_pairs(candidate_pairs, shingled_regions)

    similar_pairs = [p for p in verified_pairs if p.similarity >= threshold]
    if len(similar_pairs) < len(verified_pairs):
        logger.info(
            "Filtered %d pair(s) below threshold after verification",
            len(verified_pairs) - len(similar_pairs),
        )
    return similar_pairs


def detect_similarity(
    signatures: list[RegionSignature],
    threshold: float = 0.5,
    failed_files: dict[Path, str] | None = None,
    shingled_regions: list[ShingledRegion] | None = None,
    verify_candidates: bool = True,
) -> SimilarityResult:
    """Detect similar regions using LSH with optional verification.

    Args:
        signatures: List of region signatures
        threshold: Jaccard similarity threshold for LSH and verification
        failed_files: Optional dict of failed files from earlier stages
        shingled_regions: Optional shingled regions for verification
        verify_candidates: If True, verify candidates with order-sensitive similarity

    Returns:
        SimilarityResult with similar region groups
    """
    # Find groups of similar regions
    similar_groups = find_similar_groups(signatures, threshold=threshold)

    # For backwards compatibility, also generate pairs (deprecated)
    # This will be removed in a future version
    candidate_pairs = find_similar_pairs(signatures, threshold=threshold)

    if _should_verify_candidates(verify_candidates, shingled_regions, candidate_pairs):
        # shingled_regions is guaranteed to be non-None by _should_verify_candidates
        assert shingled_regions is not None
        similar_pairs = _verify_and_filter_pairs(candidate_pairs, shingled_regions, threshold)
    else:
        similar_pairs = candidate_pairs

    return SimilarityResult(
        signatures=signatures,
        similar_pairs=similar_pairs,
        similar_groups=similar_groups,
        failed_files=failed_files or {},
    )
