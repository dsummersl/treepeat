"""LSH stage for finding similar region pairs."""

import logging
from pathlib import Path
from typing import Hashable

from datasketch import MinHashLSH  # type: ignore[import-untyped]

from treepeat.models.shingle import ShingledRegion
from treepeat.models.similarity import (
    Region,
    RegionSignature,
    SimilarRegionGroup,
    SimilarityResult,
)

logger = logging.getLogger(__name__)


def _create_lsh_index(
    signatures: list[RegionSignature],
    similarity_percent: float,
) -> MinHashLSH:
    """Create and populate LSH index."""
    num_perm = signatures[0].minhash.hashvalues.shape[0]

    # Use a lower threshold for LSH candidate finding to avoid missing matches
    # Cap at 0.5 to avoid being too restrictive with high similarity thresholds
    # For low thresholds, scale down proportionally to find appropriate candidates
    # The actual similarity_percent filtering happens later in the pipeline
    lsh_similarity_percent = min(0.5, 0.7 * similarity_percent)
    lsh = MinHashLSH(lsh_similarity_percent, num_perm)

    for sig in signatures:
        # Create a unique key for each region
        # Include region_name to handle shingle windows which may share line ranges
        key = f"{sig.region.path}:{sig.region.region_name}:{sig.region.start_line}-{sig.region.end_line}"
        lsh.insert(key, sig.minhash)

    logger.debug(
        "Inserted %d region signatures into LSH index (lsh_threshold=%.2f, filter_threshold=%.2f)",
        len(signatures),
        lsh_similarity_percent,
        similarity_percent,
    )
    return lsh


def _find_signature_by_key(
    signatures: list[RegionSignature],
    key: Hashable,
) -> RegionSignature | None:
    """Find signature by region key."""
    return next(
        (
            s
            for s in signatures
            if f"{s.region.path}:{s.region.region_name}:{s.region.start_line}-{s.region.end_line}"
            == key
        ),
        None,
    )


def _regions_overlap(r1: Region, r2: Region) -> bool:
    """Check if two regions overlap in the same file."""
    if r1.path != r2.path:
        return False
    return not (r1.end_line < r2.start_line or r2.end_line < r1.start_line)


class UnionFind:
    """Union-Find data structure for grouping similar regions."""

    def __init__(self) -> None:
        """Initialize union-find structure."""
        self.parent: dict[str, str] = {}
        self.rank: dict[str, int] = {}

    def find(self, key: str) -> str:
        """Find the root of the set containing key with path compression."""
        if key not in self.parent:
            self.parent[key] = key
            self.rank[key] = 0
            return key

        # Path compression
        if self.parent[key] != key:
            self.parent[key] = self.find(self.parent[key])
        return self.parent[key]

    def union(self, key1: str, key2: str) -> None:
        """Union the sets containing key1 and key2 using union by rank."""
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
        """Get all groups as a dictionary mapping root to members."""
        groups: dict[str, list[str]] = {}
        for key in self.parent:
            root = self.find(key)
            if root not in groups:
                groups[root] = []
            groups[root].append(key)
        return groups


def _compute_pair_similarity(sig1: RegionSignature, sig2: RegionSignature) -> float:
    """Compute similarity between two signatures."""
    if sig1.shingle_count == 0 and sig2.shingle_count == 0:
        return 0.0
    return float(sig1.minhash.jaccard(sig2.minhash))


def _calculate_group_similarity(
    group_sigs: list[RegionSignature],
) -> float:
    """Calculate average pairwise similarity for a group."""
    if len(group_sigs) < 2:
        return 1.0

    total_similarity = 0.0
    pair_count = 0

    for i, sig1 in enumerate(group_sigs):
        for sig2 in group_sigs[i + 1 :]:
            total_similarity += _compute_pair_similarity(sig1, sig2)
            pair_count += 1

    return total_similarity / pair_count if pair_count > 0 else 1.0


def _is_pairwise_similar(
    other_key: Hashable,
    sig: RegionSignature,
    signatures: list[RegionSignature],
    similarity_percent: float,
) -> bool:
    similar_sig = _find_signature_by_key(signatures, other_key)
    if similar_sig is None:
        return False

    if _regions_overlap(sig.region, similar_sig.region):
        return False

    pair_similarity_percent = _compute_pair_similarity(sig, similar_sig)
    if pair_similarity_percent < similarity_percent:
        return False

    return True


def _append_pairwise_similar(
    uf: UnionFind,
    current_key: str,
    similar_keys: list[Hashable],
    sig: RegionSignature,
    signatures: list[RegionSignature],
    similarity_percent: float,
) -> None:
    pairwise_similar_keys = [
        sk
        for sk in similar_keys
        if _is_pairwise_similar(sk, sig, signatures, similarity_percent)
        if sk != current_key
    ]
    for similar_key in pairwise_similar_keys:
        uf.union(current_key, str(similar_key))


def _build_union_find_from_lsh(
    signatures: list[RegionSignature],
    lsh: MinHashLSH,
    similarity_percent: float,
) -> tuple[UnionFind, dict[str, RegionSignature]]:
    """Build union-find structure from LSH queries."""
    uf = UnionFind()
    key_to_sig: dict[str, RegionSignature] = {}

    # Use a lower threshold for pairwise filtering since LSH similarity is approximate
    # The actual verified similarity may be higher than the MinHash Jaccard similarity
    min_pair_similarity = 0.8 * similarity_percent

    for sig in signatures:
        # Use same key format as LSH index
        current_key = f"{sig.region.path}:{sig.region.region_name}:{sig.region.start_line}-{sig.region.end_line}"
        key_to_sig[current_key] = sig

        similar_keys = lsh.query(sig.minhash)
        logger.debug(
            "Query for %s:%d-%d returned %d similar key(s)",
            sig.region.region_name,
            sig.region.start_line,
            sig.region.end_line,
            len(similar_keys),
        )

        _append_pairwise_similar(
            uf, current_key, similar_keys, sig, signatures, min_pair_similarity
        )

    return uf, key_to_sig


def _get_valid_group_signatures(
    member_keys: list[str],
    key_to_sig: dict[str, RegionSignature],
) -> list[RegionSignature] | None:
    """Get signatures for member keys if at least 2 valid signatures exist."""
    group_sigs = [key_to_sig[key] for key in member_keys if key in key_to_sig]
    return group_sigs if len(group_sigs) >= 2 else None


def _create_group_from_keys(
    member_keys: list[str],
    key_to_sig: dict[str, RegionSignature],
    similarity_percent: float,
) -> SimilarRegionGroup | None:
    """Create a similarity group from member keys."""
    group_sigs = _get_valid_group_signatures(member_keys, key_to_sig)
    if group_sigs is None:
        return None

    group_similarity_percent = _calculate_group_similarity(group_sigs)
    # Filter by a lower threshold (0.8 * similarity_percent) to avoid large groups with low average similarity
    # This can happen when union-find transitively connects many regions
    # We use 0.8 here because LSH similarity is approximate - the actual verified similarity may be higher
    # Final filtering by the full similarity_percent happens after verification
    min_lsh_similarity = 0.8 * similarity_percent
    if group_similarity_percent < min_lsh_similarity:
        logger.debug(
            "Filtered out group of %d regions with %.1f%% LSH similarity (below min threshold %.1f%%)",
            len(member_keys),
            group_similarity_percent * 100,
            min_lsh_similarity * 100,
        )
        return None

    regions = [sig.region for sig in group_sigs]
    logger.debug(
        "Found similar group of %d region(s) with %.1f%% similarity",
        len(regions),
        group_similarity_percent * 100,
    )
    for region in regions:
        logger.debug(
            "  - %s [%d:%d] from %s",
            region.region_name,
            region.start_line,
            region.end_line,
            region.path.name,
        )

    return SimilarRegionGroup(regions=regions, similarity=group_similarity_percent)


def _collect_candidate_groups(
    signatures: list[RegionSignature],
    lsh: MinHashLSH,
    similarity_percent: float,
) -> list[SimilarRegionGroup]:
    """Collect similar region groups from LSH queries."""
    # Build union-find structure
    uf, key_to_sig = _build_union_find_from_lsh(signatures, lsh, similarity_percent)

    # Extract groups from union-find
    groups_dict = uf.get_groups()
    groups: list[SimilarRegionGroup] = []

    for root, member_keys in groups_dict.items():
        # Skip single-region "groups"
        if len(member_keys) < 2:
            continue

        # Create and validate group
        group = _create_group_from_keys(member_keys, key_to_sig, similarity_percent)
        if group is not None:
            groups.append(group)

    return groups


def find_similar_groups(
    signatures: list[RegionSignature], similarity_percent: float
) -> list[SimilarRegionGroup]:
    """Find similar region groups using LSH."""
    if len(signatures) < 2:
        logger.info("Need at least 2 regions to find similar groups")
        return []

    logger.info(
        "Finding similar groups using LSH (similarity_percent=%.2f) for %d region(s)",
        similarity_percent,
        len(signatures),
    )

    lsh = _create_lsh_index(signatures, similarity_percent)
    groups = _collect_candidate_groups(signatures, lsh, similarity_percent)

    groups.sort(key=lambda g: g.similarity, reverse=True)
    logger.info(
        "Found %d similar group(s) above similarity_percent",
        len(groups),
    )

    return groups


def _verify_and_filter_groups(
    candidate_groups: list[SimilarRegionGroup],
    shingled_regions: list[ShingledRegion],
    similarity_percent: float,
) -> list[SimilarRegionGroup]:
    """Verify candidate groups and filter by minimum similarity similarity_percent."""
    from treepeat.pipeline.verification import verify_similar_groups

    logger.info("Verifying %d candidate group(s)", len(candidate_groups))
    verified_groups = verify_similar_groups(candidate_groups, shingled_regions)

    # Filter groups that fall below minimum similarity after verification
    similar_groups = [g for g in verified_groups if g.similarity >= similarity_percent]
    if len(similar_groups) < len(verified_groups):
        logger.info(
            "Filtered %d group(s) below similarity_percent similarity_percent (%.1f%%) after verification",
            len(verified_groups) - len(similar_groups),
            similarity_percent * 100,
        )
    return similar_groups


def _line_count(region: Region) -> int:
    return region.end_line - region.start_line + 1


def _should_keep_signature(sig: RegionSignature, min_lines: int) -> bool:
    lines = _line_count(sig.region)
    if lines >= min_lines:
        return True
    logger.debug(
        "Skipping region %s [%d:%d] (%d lines) below min_lines=%d",
        sig.region.region_name,
        sig.region.start_line,
        sig.region.end_line,
        lines,
        min_lines,
    )
    return False


def _filter_signatures_by_min_lines(
    signatures: list[RegionSignature], min_lines: int
) -> tuple[list[RegionSignature], set[tuple[Path, int]]]:
    filtered: list[RegionSignature] = []
    kept_keys: set[tuple[Path, int]] = set()

    for sig in signatures:
        if _should_keep_signature(sig, min_lines):
            filtered.append(sig)
            kept_keys.add((sig.region.path, sig.region.start_line))

    return filtered, kept_keys


def _filter_by_min_lines(
    signatures: list[RegionSignature],
    shingled_regions: list[ShingledRegion],
    min_lines: int,
) -> tuple[list[RegionSignature], list[ShingledRegion]]:
    if min_lines <= 1:
        return signatures, shingled_regions

    filtered_signatures, kept_keys = _filter_signatures_by_min_lines(signatures, min_lines)

    if not filtered_signatures:
        return [], []

    filtered_shingled = [
        sr for sr in shingled_regions if (sr.region.path, sr.region.start_line) in kept_keys
    ]

    return filtered_signatures, filtered_shingled


def detect_similarity(
    signatures: list[RegionSignature],
    similarity_percent: float,
    shingled_regions: list[ShingledRegion],
    min_lines: int = 5,
) -> SimilarityResult:
    """Detect similar regions using LSH."""
    filtered_signatures, filtered_shingled = _filter_by_min_lines(
        signatures, shingled_regions, min_lines
    )

    if len(filtered_signatures) < len(signatures):
        logger.info(
            "Filtered out %d region(s) below min_lines=%d before similarity detection",
            len(signatures) - len(filtered_signatures),
            min_lines,
        )

    if not filtered_signatures:
        return SimilarityResult(signatures=[], similar_groups=[])

    candidate_groups = find_similar_groups(filtered_signatures, similarity_percent)

    if not candidate_groups:
        return SimilarityResult(
            signatures=filtered_signatures,
            similar_groups=[],
        )

    similar_groups = _verify_and_filter_groups(
        candidate_groups, filtered_shingled, similarity_percent
    )

    return SimilarityResult(
        signatures=filtered_signatures,
        similar_groups=similar_groups,
    )
