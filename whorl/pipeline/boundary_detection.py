"""Boundary detection for merging overlapping similar windows."""

import logging
from collections import defaultdict
from pathlib import Path

from whorl.models.similarity import Region, SimilarRegionGroup

logger = logging.getLogger(__name__)


def _regions_are_adjacent_or_overlapping(r1: Region, r2: Region, max_gap: int = 5) -> bool:
    """Check if two regions from the same file are adjacent or overlapping.

    Args:
        r1: First region
        r2: Second region
        max_gap: Maximum gap in lines to still consider regions as adjacent

    Returns:
        True if regions overlap or are within max_gap lines of each other
    """
    if r1.path != r2.path:
        return False

    # Sort regions by start line
    if r1.start_line > r2.start_line:
        r1, r2 = r2, r1

    # Check if regions overlap: r1 ends after or at r2 starts (with allowed gap)
    # r2.start_line - r1.end_line gives the gap between regions
    # If gap is <= max_gap (including negative for overlap), they should be merged
    gap = r2.start_line - r1.end_line
    return gap <= max_gap


def _merge_regions(regions: list[Region]) -> Region:
    """Merge a list of regions into a single region spanning their combined range.

    Args:
        regions: List of regions to merge (must be from same file)

    Returns:
        Merged region
    """
    if not regions:
        raise ValueError("Cannot merge empty list of regions")

    # All regions should be from the same file
    path = regions[0].path
    language = regions[0].language

    # Find min start and max end
    start_line = min(r.start_line for r in regions)
    end_line = max(r.end_line for r in regions)

    return Region(
        path=path,
        language=language,
        region_type="lines",
        region_name=f"lines_{start_line}_{end_line}",
        start_line=start_line,
        end_line=end_line,
    )


def _should_merge_with_group(region: Region, group: list[Region]) -> bool:
    """Check if a region should be merged with a group of regions."""
    return any(_regions_are_adjacent_or_overlapping(region, r) for r in group)


def _merge_overlapping_regions_for_file(regions: list[Region]) -> list[Region]:
    """Merge overlapping or adjacent regions from the same file.

    Args:
        regions: List of regions from the same file, sorted by start_line

    Returns:
        List of merged regions
    """
    if not regions:
        return []

    sorted_regions = sorted(regions, key=lambda r: r.start_line)
    merged: list[Region] = []
    current_group: list[Region] = [sorted_regions[0]]

    for region in sorted_regions[1:]:
        if _should_merge_with_group(region, current_group):
            current_group.append(region)
        else:
            merged.append(_merge_regions(current_group))
            current_group = [region]

    # Don't forget the last group
    if current_group:
        merged.append(_merge_regions(current_group))

    return merged


def _get_regions_for_file(group: SimilarRegionGroup, file_path: Path) -> list[Region]:
    """Get all regions from a group for a specific file."""
    return [r for r in group.regions if r.path == file_path]


def _files_have_overlapping_regions(
    g1_regions: list[Region], g2_regions: list[Region]
) -> bool:
    """Check if two region lists have any overlapping regions."""
    for r1 in g1_regions:
        for r2 in g2_regions:
            if _regions_are_adjacent_or_overlapping(r1, r2):
                return True
    return False


def _groups_have_overlapping_regions(g1: SimilarRegionGroup, g2: SimilarRegionGroup) -> bool:
    """Check if two groups have overlapping regions in any common files."""
    # Get common files between groups
    files_g1 = {r.path for r in g1.regions}
    files_g2 = {r.path for r in g2.regions}
    common_files = files_g1 & files_g2

    # Check each common file for overlaps using any()
    return any(
        _files_have_overlapping_regions(
            _get_regions_for_file(g1, fpath),
            _get_regions_for_file(g2, fpath)
        )
        for fpath in common_files
    )


def _merge_group_list(groups: list[SimilarRegionGroup]) -> SimilarRegionGroup:
    """Merge a list of groups into a single group."""
    all_regions = []
    total_similarity = 0.0

    for group in groups:
        all_regions.extend(group.regions)
        total_similarity += group.similarity

    # Average similarity across merged groups
    avg_similarity = total_similarity / len(groups) if groups else 1.0

    return SimilarRegionGroup(
        regions=all_regions,
        similarity=avg_similarity,
    )


def _find_overlapping_merged_list(
    group: SimilarRegionGroup, merged_lists: list[list[SimilarRegionGroup]]
) -> list[SimilarRegionGroup] | None:
    """Find the merged list that overlaps with the given group, if any."""
    for merged_list in merged_lists:
        if any(_groups_have_overlapping_regions(group, g) for g in merged_list):
            return merged_list
    return None


def _coalesce_groups(groups: list[SimilarRegionGroup]) -> list[list[SimilarRegionGroup]]:
    """Coalesce overlapping groups into lists of groups that should be merged."""
    merged_group_lists: list[list[SimilarRegionGroup]] = []

    for group in groups:
        overlapping_list = _find_overlapping_merged_list(group, merged_group_lists)
        if overlapping_list is not None:
            overlapping_list.append(group)
        else:
            merged_group_lists.append([group])

    return merged_group_lists


def _convert_to_merged_groups(
    merged_lists: list[list[SimilarRegionGroup]]
) -> list[SimilarRegionGroup]:
    """Convert lists of groups into single merged groups."""
    result = []
    for merged_list in merged_lists:
        if len(merged_list) == 1:
            result.append(merged_list[0])
        else:
            merged_group = _merge_group_list(merged_list)
            logger.debug(
                "Merged %d overlapping groups into one (avg similarity: %.1f%%)",
                len(merged_list),
                merged_group.similarity * 100,
            )
            result.append(merged_group)
    return result


def _merge_overlapping_groups(groups: list[SimilarRegionGroup]) -> list[SimilarRegionGroup]:
    """Merge groups that have overlapping regions in common files.

    Args:
        groups: List of similar region groups

    Returns:
        List of merged groups where overlapping groups are combined
    """
    if not groups:
        return []

    coalesced = _coalesce_groups(groups)
    return _convert_to_merged_groups(coalesced)


def merge_similar_window_groups(
    groups: list[SimilarRegionGroup],
) -> list[SimilarRegionGroup]:
    """Merge overlapping windows in similar groups to find contiguous boundaries.

    Merges overlapping or adjacent windows within each group to find clean boundaries.
    Does NOT merge separate groups together, preserving distinct similar sections.

    Args:
        groups: Similar region groups with potentially overlapping windows

    Returns:
        Groups with merged regions showing clean boundaries
    """
    # Skip group-level merging to preserve separate similar sections
    # (e.g., sections before and after a deletion)
    coalesced_groups = groups
    logger.debug(
        "Processing %d groups (skipping group-level merging to preserve separate sections)",
        len(groups),
    )

    merged_groups: list[SimilarRegionGroup] = []

    for group in coalesced_groups:
        # Group regions by file
        regions_by_file: dict[Path, list[Region]] = defaultdict(list)
        for region in group.regions:
            regions_by_file[region.path].append(region)

        # Merge regions for each file
        merged_regions: list[Region] = []
        for file_path, file_regions in regions_by_file.items():
            merged_file_regions = _merge_overlapping_regions_for_file(file_regions)
            merged_regions.extend(merged_file_regions)

            logger.debug(
                "Merged %d windows into %d contiguous region(s) for %s",
                len(file_regions),
                len(merged_file_regions),
                file_path.name,
            )

        # Create new group with merged regions
        if len(merged_regions) >= 2:
            merged_group = SimilarRegionGroup(
                regions=merged_regions,
                similarity=group.similarity,
            )
            merged_groups.append(merged_group)

            logger.info(
                "Merged group from %d windows to %d contiguous regions (%.1f%% similarity)",
                len(group.regions),
                len(merged_regions),
                group.similarity * 100,
            )

    return merged_groups
