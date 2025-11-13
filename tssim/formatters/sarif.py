"""SARIF (Static Analysis Results Interchange Format) formatter for tssim.

SARIF is a standard format for static analysis tool output.
Specification: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
"""

import json
from typing import Any, Dict, List

from tssim.models.similarity import Region, SimilarityResult


def format_as_sarif(result: SimilarityResult, *, pretty: bool = True) -> str:
    """Format similarity detection results as SARIF JSON.

    Args:
        result: The similarity detection result to format
        pretty: If True, format with indentation for readability

    Returns:
        SARIF-formatted JSON string
    """
    sarif_log = _create_sarif_log(result)

    if pretty:
        return json.dumps(sarif_log, indent=2)
    return json.dumps(sarif_log)


def _create_sarif_log(result: SimilarityResult) -> Dict[str, Any]:
    """Create a SARIF log object from similarity results."""
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [_create_run(result)]
    }


def _create_run(result: SimilarityResult) -> Dict[str, Any]:
    """Create a SARIF run object."""
    return {
        "tool": _create_tool(),
        "results": _create_results(result),
        "invocations": [_create_invocation(result)]
    }


def _create_tool() -> Dict[str, Any]:
    """Create the SARIF tool descriptor."""
    return {
        "driver": {
            "name": "tssim",
            "informationUri": "https://github.com/dsummersl/tssim",
            "version": "1.0.0",
            "semanticVersion": "1.0.0",
            "rules": [
                {
                    "id": "similar-code",
                    "name": "SimilarCode",
                    "shortDescription": {
                        "text": "Structurally similar code detected"
                    },
                    "fullDescription": {
                        "text": "This rule identifies code blocks that are structurally similar based on Abstract Syntax Tree (AST) analysis using MinHash and Locality-Sensitive Hashing (LSH). Similar code may indicate opportunities for refactoring or potential code duplication issues."
                    },
                    "help": {
                        "text": "Consider refactoring similar code blocks into shared functions or modules to improve maintainability and reduce duplication."
                    },
                    "defaultConfiguration": {
                        "level": "warning"
                    },
                    "properties": {
                        "tags": [
                            "maintainability",
                            "code-duplication",
                            "refactoring"
                        ],
                        "precision": "high"
                    }
                }
            ]
        }
    }


def _create_results(similarity_result: SimilarityResult) -> List[Dict[str, Any]]:
    """Create SARIF result objects from similar region pairs."""
    results = []

    for pair in similarity_result.similar_pairs:
        # Calculate similarity percentage
        similarity_percent = pair.similarity * 100

        # Determine severity based on similarity
        level = _get_level(pair.similarity)

        # Create message
        message = (
            f"Code similarity detected ({similarity_percent:.1f}% similar). "
            f"Region 1: {pair.region1.path}:{pair.region1.start_line}-{pair.region1.end_line} "
            f"({pair.region1.end_line - pair.region1.start_line + 1} lines). "
            f"Region 2: {pair.region2.path}:{pair.region2.start_line}-{pair.region2.end_line} "
            f"({pair.region2.end_line - pair.region2.start_line + 1} lines)."
        )

        result_obj = {
            "ruleId": "similar-code",
            "level": level,
            "message": {
                "text": message
            },
            "locations": [
                _create_location(pair.region1)
            ],
            "relatedLocations": [
                {
                    "id": 1,
                    "physicalLocation": _create_physical_location(pair.region2),
                    "message": {
                        "text": f"Similar code block ({similarity_percent:.1f}% match)"
                    }
                }
            ],
            "properties": {
                "similarity": pair.similarity,
                "similarityPercent": similarity_percent,
                "region1Lines": pair.region1.end_line - pair.region1.start_line + 1,
                "region2Lines": pair.region2.end_line - pair.region2.start_line + 1,
                "region1Type": pair.region1.region_type,
                "region2Type": pair.region2.region_type,
                "region1Name": pair.region1.region_name,
                "region2Name": pair.region2.region_name
            }
        }

        results.append(result_obj)

    return results


def _get_level(similarity: float) -> str:
    """Determine SARIF severity level based on similarity score."""
    if similarity >= 0.95:
        return "error"  # Very high similarity
    elif similarity >= 0.85:
        return "warning"  # High similarity
    else:
        return "note"  # Moderate similarity


def _create_location(region: Region) -> Dict[str, Any]:
    """Create a SARIF location object from a region."""
    return {
        "physicalLocation": _create_physical_location(region)
    }


def _create_physical_location(region: Region) -> Dict[str, Any]:
    """Create a SARIF physical location object."""
    # Convert path to relative if possible, otherwise use absolute
    file_path = str(region.path)

    return {
        "artifactLocation": {
            "uri": file_path,
            "uriBaseId": "%SRCROOT%"
        },
        "region": {
            "startLine": region.start_line,
            "endLine": region.end_line,
            "startColumn": 1  # We don't track columns currently
        }
    }


def _create_invocation(result: SimilarityResult) -> Dict[str, Any]:
    """Create SARIF invocation object with execution metadata."""
    invocation = {
        "executionSuccessful": True,
        "properties": {
            "processedFiles": result.total_files,
            "failedFiles": len(result.failed_files),
            "processedRegions": result.total_regions,
            "similarPairs": len(result.similar_pairs)
        }
    }

    # Add failed file information if any
    if result.failed_files:
        invocation["toolExecutionNotifications"] = [
            {
                "level": "error",
                "message": {
                    "text": f"Failed to parse file: {path}"
                },
                "descriptor": {
                    "id": "parse-error"
                },
                "properties": {
                    "filePath": str(path),
                    "error": error
                }
            }
            for path, error in result.failed_files.items()
        ]

    return invocation
