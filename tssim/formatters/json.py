"""JSON formatter for tssim results."""

import json
from typing import Any, Dict
from pathlib import Path

from tssim.models.similarity import SimilarityResult


def format_as_json(result: SimilarityResult, *, pretty: bool = True) -> str:
    """Format similarity detection results as JSON.

    This formatter outputs the complete similarity result including similar pairs
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
        "total_similar_pairs": len(result.similar_pairs),
        "failed_files": len(result.failed_files),
        "similar_pairs": [
            {
                "region1": {
                    "file_path": str(pair.region1.path),
                    "language": pair.region1.language,
                    "region_type": pair.region1.region_type,
                    "name": pair.region1.region_name,
                    "start_line": pair.region1.start_line,
                    "end_line": pair.region1.end_line,
                },
                "region2": {
                    "file_path": str(pair.region2.path),
                    "language": pair.region2.language,
                    "region_type": pair.region2.region_type,
                    "name": pair.region2.region_name,
                    "start_line": pair.region2.start_line,
                    "end_line": pair.region2.end_line,
                },
                "similarity": pair.similarity,
            }
            for pair in result.similar_pairs
        ],
        "parse_errors": [
            {
                "file_path": str(path),
                "error": error,
            }
            for path, error in result.failed_files.items()
        ],
    }

    if pretty:
        return json.dumps(data, indent=2)
    return json.dumps(data)
