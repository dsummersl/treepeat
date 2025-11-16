"""Extract regions (functions, classes, sections, etc) from parsed files."""

import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field
from tree_sitter import Node

from tssim.models.ast import ParsedFile
from tssim.models.similarity import Region

from tssim.pipeline.rules.engine import RuleEngine

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
    # Look for 'name' or 'identifier' child node
    for child in node.children:
        if child.type in ("identifier", "name"):
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


def extract_all_regions(
    parsed_files: list[ParsedFile],
    rule_engine: "RuleEngine",
) -> list[ExtractedRegion]:
    """Extract regions from all parsed files."""
    all_regions: list[ExtractedRegion] = []

    for parsed_file in parsed_files:
        try:
            regions = extract_regions(parsed_file, rule_engine)
            all_regions.extend(regions)
        except Exception as e:
            logger.error("Failed to extract regions from %s: %s", parsed_file.path, e)

    logger.info("Extracted %d total region(s) from %d file(s)", len(all_regions), len(parsed_files))
    return all_regions


def get_matched_line_ranges(matched_regions: list[Region]) -> dict[Path, set[int]]:
    """Get the line ranges that were matched, organized by file path."""
    matched_lines_by_file: dict[Path, set[int]] = {}

    for region in matched_regions:
        if region.path not in matched_lines_by_file:
            matched_lines_by_file[region.path] = set()

        # Add all lines in this region to the matched set
        for line in range(region.start_line, region.end_line + 1):
            matched_lines_by_file[region.path].add(line)

    return matched_lines_by_file


def _finish_range(
    range_start: int | None, end_line: int, ranges: list[tuple[int, int]]
) -> None:
    """Finish a range and add it to the list."""
    if range_start is not None:
        ranges.append((range_start, end_line))


def _find_unmatched_ranges(
    matched_lines: set[int], file_end_line: int
) -> list[tuple[int, int]]:
    """Find contiguous ranges of unmatched lines in a file."""
    unmatched_ranges: list[tuple[int, int]] = []
    range_start = None

    for line in range(1, file_end_line + 1):
        if line in matched_lines:
            _finish_range(range_start, line - 1, unmatched_ranges)
            range_start = None
        elif range_start is None:
            range_start = line

    _finish_range(range_start, file_end_line, unmatched_ranges)
    return unmatched_ranges


def _create_line_region(
    parsed_file: ParsedFile, start_line: int, end_line: int
) -> ExtractedRegion:
    """Create a line-based region for a range of lines."""
    region = Region(
        path=parsed_file.path,
        language=parsed_file.language,
        region_type="lines",
        region_name=f"lines_{start_line}_{end_line}",
        start_line=start_line,
        end_line=end_line,
    )

    # Find all nodes that fall within this line range
    # We use the root node and filter its children during shingling
    # by checking line ranges, rather than trying to create a sub-tree
    return ExtractedRegion(region=region, node=parsed_file.root_node)


def create_line_based_regions(
    parsed_files: list[ParsedFile],
    matched_lines_by_file: dict[Path, set[int]],
    min_lines: int,
) -> list[ExtractedRegion]:
    """Create line-based regions for unmatched sections of files."""
    line_regions: list[ExtractedRegion] = []

    for parsed_file in parsed_files:
        matched_lines = matched_lines_by_file.get(parsed_file.path, set())
        file_end_line = parsed_file.root_node.end_point[0] + 1

        unmatched_ranges = _find_unmatched_ranges(matched_lines, file_end_line)

        for start_line, end_line in unmatched_ranges:
            line_count = end_line - start_line + 1
            if line_count >= min_lines:
                extracted_region = _create_line_region(parsed_file, start_line, end_line)
                line_regions.append(extracted_region)

                logger.debug(
                    "Created line-based region for %s: lines %d-%d (%d lines)",
                    parsed_file.path,
                    start_line,
                    end_line,
                    line_count,
                )

    logger.info("Created %d line-based region(s) for unmatched sections", len(line_regions))
    return line_regions
