"""JSON formatter for tssim results."""

import json
from typing import Any

from tssim.models.similarity import Region, SimilarRegionGroup, SimilarRegionPair, SimilarityResult


def _region_to_dict(region: Region) -> dict[str, Any]:
    """Convert a Region to a dictionary."""
    return {
        "file_path": str(region.path),
        "language": region.language,
        "region_type": region.region_type,
        "name": region.region_name,
        "start_line": region.start_line,
        "end_line": region.end_line,
    }


def _group_to_dict(group: SimilarRegionGroup) -> dict[str, Any]:
    """Convert a SimilarRegionGroup to a dictionary."""
    return {
        "regions": [_region_to_dict(region) for region in group.regions],
        "similarity": group.similarity,
        "size": group.size,
    }


def _pair_to_dict(pair: SimilarRegionPair) -> dict[str, Any]:
    """Convert a SimilarRegionPair to a dictionary."""
    return {
        "region1": _region_to_dict(pair.region1),
        "region2": _region_to_dict(pair.region2),
        "similarity": pair.similarity,
    }


def format_as_json(result: SimilarityResult, *, pretty: bool = True) -> str:
    """Format similarity detection results as JSON.

    This formatter outputs the complete similarity result including similar groups
    and metadata in a structured JSON format. Note: MinHash signatures are excluded
    as they are not JSON-serializable.

    Args:
        result: The similarity detection result to format
        pretty: If True, format with indentation for readability

    Returns:
        JSON-formatted string
    """
    # Build JSON structure manually to avoid MinHash serialization issues
    data = {
        "total_files": result.total_files,
        "total_regions": result.total_regions,
        "total_similar_groups": len(result.similar_groups),
        "failed_files": len(result.failed_files),
        "similar_groups": [_group_to_dict(group) for group in result.similar_groups],
        "similar_pairs": [_pair_to_dict(pair) for pair in result.similar_pairs],
        "parse_errors": [
            {"file_path": str(path), "error": error}
            for path, error in result.failed_files.items()
        ],
    }

    if pretty:
        return json.dumps(data, indent=2)
    return json.dumps(data)
