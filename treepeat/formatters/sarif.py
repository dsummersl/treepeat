"""SARIF (Static Analysis Results Interchange Format) formatter for whorl.

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

from treepeat.models.similarity import SimilarRegionGroup, SimilarityResult


def format_as_sarif(result: SimilarityResult, *, pretty: bool = True) -> str:
    """Format similarity detection results as SARIF JSON. """
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
            name="whorl",
            informationUri="https://github.com/dsummersl/whorl",
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


def _create_result_from_group(group: SimilarRegionGroup) -> Result:
    """Create a SARIF result from a similarity group. """
    similarity_percent = group.similarity * 100
    level = _get_level(group.similarity)

    # Create message describing the group
    region_descriptions = [
        f"{region.path}:{region.start_line}-{region.end_line} ({region.end_line - region.start_line + 1} lines)"
        for region in group.regions
    ]
    message_text = (
        f"Code similarity detected ({similarity_percent:.1f}% similar, {group.size} regions). "
        + ". ".join(region_descriptions)
    )

    # Use first region as primary location
    primary_region = group.regions[0]

    # All other regions are related locations
    related_locations = [
        {
            "id": i,
            "physicalLocation": {
                "artifactLocation": {
                    "uri": str(region.path),
                    "uriBaseId": "%SRCROOT%",
                },
                "region": {
                    "startLine": region.start_line,
                    "endLine": region.end_line,
                    "startColumn": 1,
                },
            },
            "message": {"text": f"Similar code block ({similarity_percent:.1f}% match)"},
        }
        for i, region in enumerate(group.regions[1:], start=1)
    ]

    return Result(
        ruleId="similar-code",
        level=level,
        message=Message(text=message_text),
        locations=[
            Location(
                physicalLocation=PhysicalLocation(
                    artifactLocation=ArtifactLocation(
                        uri=str(primary_region.path),
                        uriBaseId="%SRCROOT%",
                    ),
                    region=Region(
                        startLine=primary_region.start_line,
                        endLine=primary_region.end_line,
                        startColumn=1,
                    ),
                )
            )
        ],
        relatedLocations=related_locations if related_locations else None,
        properties={
            "similarity": group.similarity,
            "similarityPercent": similarity_percent,
            "groupSize": group.size,
            "regions": [
                {
                    "path": str(region.path),
                    "startLine": region.start_line,
                    "endLine": region.end_line,
                    "lines": region.end_line - region.start_line + 1,
                    "type": region.region_type,
                    "name": region.region_name,
                }
                for region in group.regions
            ],
        },
    )


def _create_results(similarity_result: SimilarityResult) -> list[Result]:
    """Create SARIF result objects from similar region groups."""
    return [_create_result_from_group(group) for group in similarity_result.similar_groups]


def _get_level(similarity: float) -> Level:
    """Determine SARIF severity level based on similarity score."""
    if similarity >= 0.95:
        return Level.ERROR  # Very high similarity
    elif similarity >= 0.85:
        return Level.WARNING  # High similarity
    else:
        return Level.NOTE  # Moderate similarity
