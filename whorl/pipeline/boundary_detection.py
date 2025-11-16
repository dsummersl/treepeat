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


def merge_similar_window_groups(
    groups: list[SimilarRegionGroup],
) -> list[SimilarRegionGroup]:
    """Merge overlapping windows in similar groups to find contiguous boundaries.

    For each group, merge overlapping or adjacent windows from the same file
    to produce clean boundary ranges.

    Args:
        groups: Similar region groups with potentially overlapping windows

    Returns:
        Groups with merged regions showing clean boundaries
    """
    merged_groups: list[SimilarRegionGroup] = []

    for group in groups:
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
