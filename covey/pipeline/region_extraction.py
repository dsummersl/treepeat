"""Extract regions (functions, classes, sections, etc) from parsed files."""

import logging
from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel, Field
from tree_sitter import Node

from covey.models.ast import ParsedFile
from covey.models.similarity import Region
from covey.config import get_settings

from covey.pipeline.rules.engine import RuleEngine

logger = logging.getLogger(__name__)


class ExtractedRegion(BaseModel):
    """A region with its AST node(s) for further processing."""

    model_config = {"arbitrary_types_allowed": True}

    region: Region = Field(description="Region metadata")
    node: Node = Field(description="Primary AST node for this region")
    nodes: list[Node] | None = Field(default=None, description="Multiple nodes for section regions")


@dataclass
class RegionTypeMapping:
    """Mapping of queries to region types for a language."""

    query: str  # TreeSitter query to match nodes
    region_type: str  # Region type label (e.g., "function")


def _get_region_mappings_from_engine(engine: "RuleEngine", language: str) -> list[RegionTypeMapping]:
    """Get region extraction rules from the rule engine for a language."""
    rules = engine.get_region_extraction_rules(language)
    mappings = []
    for query, region_type in rules:
        mappings.append(RegionTypeMapping(query=query, region_type=region_type))
    return mappings


def _extract_node_name(node: Node, source: bytes) -> str:
    """Extract the name of a function/class/method from its node."""
    # Look for 'name', 'identifier', or 'property_identifier' child node
    # property_identifier is used for JavaScript method names
    for child in node.children:
        if child.type in ("identifier", "name", "property_identifier"):
            return source[child.start_byte : child.end_byte].decode("utf-8", errors="ignore")
    return "anonymous"


def _collect_all_matching_nodes(
    root_node: Node, mappings: list[RegionTypeMapping], language: str, engine: "RuleEngine"
) -> list[tuple[Node, str]]:
    """Execute queries to collect all matching nodes and their region types."""
    matching_nodes: list[tuple[Node, str]] = []

    for mapping in mappings:
        nodes = engine.get_nodes_matching_query(root_node, mapping.query, language)
        for node in nodes:
            matching_nodes.append((node, mapping.region_type))

    # Sort by start position to maintain document order
    matching_nodes.sort(key=lambda x: (x[0].start_byte, x[0].end_byte))
    return matching_nodes


def _create_target_region(
    node: Node,
    region_type: str,
    parsed_file: ParsedFile,
) -> ExtractedRegion:
    """Create a region for a target node such as a function or class."""
    name = _extract_node_name(node, parsed_file.source)

    region = Region(
        path=parsed_file.path,
        language=parsed_file.language,
        region_type=region_type,
        region_name=name,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
    )

    logger.debug(
        "Extracted %s: %s at lines %d-%d",
        region_type,
        name,
        region.start_line,
        region.end_line,
    )

    return ExtractedRegion(region=region, node=node)


def extract_regions(
    parsed_file: ParsedFile,
    rule_engine: "RuleEngine",
) -> list[ExtractedRegion]:
    """Extract code regions from a parsed file using rules from the engine."""
    logger.info("Extracting regions from %s (%s)", parsed_file.path, parsed_file.language)

    # Get region mappings from the rule engine
    mappings = _get_region_mappings_from_engine(rule_engine, parsed_file.language)

    if not mappings:
        # For unsupported languages, treat the entire file as one region
        logger.warning(
            "Language '%s' not supported for region extraction, treating entire file as one region",
            parsed_file.language,
        )
        region = Region(
            path=parsed_file.path,
            language=parsed_file.language,
            region_type="file",
            region_name=parsed_file.path.name,
            start_line=1,
            end_line=parsed_file.root_node.end_point[0] + 1,
        )
        regions = [ExtractedRegion(region=region, node=parsed_file.root_node)]
    else:
        # Recursive extraction: find ALL matching nodes (methods, nested functions, etc.)
        matching_nodes_list = _collect_all_matching_nodes(
            parsed_file.root_node, mappings, parsed_file.language, rule_engine
        )
        regions = [_create_target_region(node, region_type, parsed_file) for node, region_type in matching_nodes_list]

    logger.info("Extracted %d region(s) from %s", len(regions), parsed_file.path)
    return regions


def _is_explicit_type(region_type: str) -> bool:
    """Check if region type is from explicit rules (vs statistical chunks)."""
    explicit_types = {"function", "class", "method", "heading", "section", "head", "body"}
    return region_type in explicit_types


def _should_replace_region(new: ExtractedRegion, existing: ExtractedRegion) -> bool:
    """Determine if new region should replace existing one (prefer explicit types)."""
    return _is_explicit_type(new.region.region_type) and not _is_explicit_type(
        existing.region.region_type
    )


def _deduplicate_regions(regions: list[ExtractedRegion]) -> list[ExtractedRegion]:
    """Deduplicate regions based on file path and line range.

    In hybrid mode, explicit and statistical extraction may find the same region.
    Keep explicit regions when there's overlap (they have better semantic labels).
    """
    if not regions:
        return regions

    # Group by (path, start_line, end_line), keeping explicit types when duplicates occur
    seen_locations: dict[tuple[str, int, int], ExtractedRegion] = {}

    for region in regions:
        key = (str(region.region.path), region.region.start_line, region.region.end_line)
        existing = seen_locations.get(key)

        # Keep new region if no existing or if new is explicit and existing isn't
        should_keep = existing is None or _should_replace_region(region, existing)
        if should_keep:
            seen_locations[key] = region

    deduped = list(seen_locations.values())
    duplicate_count = len(regions) - len(deduped)
    if duplicate_count > 0:
        logger.debug("Deduplicated %d overlapping regions", duplicate_count)

    return deduped


def _log_region_type_statistics(regions: list[ExtractedRegion], method: str) -> None:
    """Log statistics about region types extracted."""
    if not regions:
        return

    type_counts: Counter[str] = Counter(r.region.region_type for r in regions)
    logger.info(
        "%s extraction found %d region(s) across %d type(s)",
        method,
        len(regions),
        len(type_counts),
    )

    # Log top 10 most common types
    for region_type, count in type_counts.most_common(10):
        logger.info("  %s: %d region(s)", region_type, count)

    if len(type_counts) > 10:
        logger.info("  ... and %d more type(s)", len(type_counts) - 10)


def _extract_hybrid(
    parsed_file: ParsedFile, rule_engine: "RuleEngine", min_lines: int
) -> list[ExtractedRegion]:
    """Extract regions using hybrid method (explicit + statistical)."""
    from covey.pipeline.statistical_chunk_extraction import extract_chunks_statistical

    # Get both types of regions
    explicit_regions = extract_regions(parsed_file, rule_engine)
    statistical_regions = extract_chunks_statistical(parsed_file, min_lines=min_lines)

    # Combine and deduplicate
    combined = explicit_regions + statistical_regions
    regions = _deduplicate_regions(combined)

    logger.debug(
        "%s: %d explicit + %d statistical -> %d after dedup",
        parsed_file.path.name,
        len(explicit_regions),
        len(statistical_regions),
        len(regions),
    )

    return regions


def _extract_regions_by_method(
    parsed_file: ParsedFile,
    rule_engine: "RuleEngine",
    method: str,
    min_lines: int,
) -> list[ExtractedRegion]:
    """Extract regions using the specified method."""
    if method == "hybrid":
        return _extract_hybrid(parsed_file, rule_engine, min_lines)
    elif method == "statistical":
        from covey.pipeline.statistical_chunk_extraction import extract_chunks_statistical

        return extract_chunks_statistical(parsed_file, min_lines=min_lines)
    elif method == "naive":
        from covey.pipeline.auto_chunk_extraction import extract_chunks

        return extract_chunks(parsed_file, min_lines=min_lines)
    else:  # "explicit"
        return extract_regions(parsed_file, rule_engine)


def extract_all_regions(
    parsed_files: list[ParsedFile],
    rule_engine: "RuleEngine",
) -> list[ExtractedRegion]:
    """Extract regions from all parsed files using configured extraction method."""
    settings = get_settings()
    extraction_method = settings.region.extraction_method.lower()

    logger.info("Using %s region extraction method", extraction_method)

    all_regions: list[ExtractedRegion] = []

    for parsed_file in parsed_files:
        try:
            regions = _extract_regions_by_method(
                parsed_file, rule_engine, extraction_method, settings.lsh.min_lines
            )
            all_regions.extend(regions)
        except Exception as e:
            logger.error("Failed to extract regions from %s: %s", parsed_file.path, e)

    # Log overall statistics
    logger.info("Extracted %d total region(s) from %d file(s)", len(all_regions), len(parsed_files))
    _log_region_type_statistics(all_regions, extraction_method)

    return all_regions
