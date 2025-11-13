"""SARIF (Static Analysis Results Interchange Format) formatter for tssim.

SARIF is a standard format for static analysis tool output.
Specification: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
"""

from sarif_pydantic import (  # type: ignore[import-untyped]
    ArtifactLocation,
    Level,
    Location,
    Message,
    PhysicalLocation,
    Region,
    ReportingDescriptor,
    Result,
    Run,
    Sarif,
    Tool,
    ToolDriver,
)

from tssim.models.similarity import SimilarityResult


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
        json_output: str = sarif_log.model_dump_json(indent=2, exclude_none=True)
        return json_output
    json_output = sarif_log.model_dump_json(exclude_none=True)
    return json_output


def _create_sarif_log(result: SimilarityResult) -> Sarif:
    """Create a SARIF log object from similarity results."""
    return Sarif(
        version="2.1.0",
        schema_uri="https://json.schemastore.org/sarif-2.1.0.json",
        runs=[_create_run(result)],
    )


def _create_run(result: SimilarityResult) -> Run:
    """Create a SARIF run object."""
    return Run(
        tool=_create_tool(),
        results=_create_results(result),
    )


def _create_tool() -> Tool:
    """Create the SARIF tool descriptor."""
    return Tool(
        driver=ToolDriver(
            name="tssim",
            informationUri="https://github.com/dsummersl/tssim",
            version="1.0.0",
            semanticVersion="1.0.0",
            rules=[
                ReportingDescriptor(
                    id="similar-code",
                    name="SimilarCode",
                    shortDescription=Message(text="Structurally similar code detected"),
                    fullDescription=Message(
                        text="This rule identifies code blocks that are structurally similar based on Abstract Syntax Tree (AST) analysis using MinHash and Locality-Sensitive Hashing (LSH). Similar code may indicate opportunities for refactoring or potential code duplication issues."
                    ),
                    help=Message(
                        text="Consider refactoring similar code blocks into shared functions or modules to improve maintainability and reduce duplication."
                    ),
                    defaultConfiguration={"level": "warning"},
                    properties={
                        "tags": ["maintainability", "code-duplication", "refactoring"],
                        "precision": "high",
                    },
                )
            ],
        )
    )


def _create_results(similarity_result: SimilarityResult) -> list[Result]:
    """Create SARIF result objects from similar region pairs."""
    results = []

    for pair in similarity_result.similar_pairs:
        # Calculate similarity percentage
        similarity_percent = pair.similarity * 100

        # Determine severity based on similarity
        level = _get_level(pair.similarity)

        # Create message
        message_text = (
            f"Code similarity detected ({similarity_percent:.1f}% similar). "
            f"Region 1: {pair.region1.path}:{pair.region1.start_line}-{pair.region1.end_line} "
            f"({pair.region1.end_line - pair.region1.start_line + 1} lines). "
            f"Region 2: {pair.region2.path}:{pair.region2.start_line}-{pair.region2.end_line} "
            f"({pair.region2.end_line - pair.region2.start_line + 1} lines)."
        )

        result_obj = Result(
            ruleId="similar-code",
            level=level,
            message=Message(text=message_text),
            locations=[
                Location(
                    physicalLocation=PhysicalLocation(
                        artifactLocation=ArtifactLocation(
                            uri=str(pair.region1.path),
                            uriBaseId="%SRCROOT%",
                        ),
                        region=Region(
                            startLine=pair.region1.start_line,
                            endLine=pair.region1.end_line,
                            startColumn=1,
                        ),
                    )
                )
            ],
            relatedLocations=[
                {
                    "id": 1,
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": str(pair.region2.path),
                            "uriBaseId": "%SRCROOT%",
                        },
                        "region": {
                            "startLine": pair.region2.start_line,
                            "endLine": pair.region2.end_line,
                            "startColumn": 1,
                        },
                    },
                    "message": {"text": f"Similar code block ({similarity_percent:.1f}% match)"},
                }
            ],
            properties={
                "similarity": pair.similarity,
                "similarityPercent": similarity_percent,
                "region1Lines": pair.region1.end_line - pair.region1.start_line + 1,
                "region2Lines": pair.region2.end_line - pair.region2.start_line + 1,
                "region1Type": pair.region1.region_type,
                "region2Type": pair.region2.region_type,
                "region1Name": pair.region1.region_name,
                "region2Name": pair.region2.region_name,
            },
        )

        results.append(result_obj)

    return results


def _get_level(similarity: float) -> Level:
    """Determine SARIF severity level based on similarity score."""
    if similarity >= 0.95:
        return Level.ERROR  # Very high similarity
    elif similarity >= 0.85:
        return Level.WARNING  # High similarity
    else:
        return Level.NOTE  # Moderate similarity
