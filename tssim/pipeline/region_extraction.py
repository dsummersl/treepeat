"""Extract regions (functions, classes, sections, etc) from parsed files."""

import logging
from dataclasses import dataclass

from pydantic import BaseModel, Field
from tree_sitter import Node

from tssim.models.ast import ParsedFile
from tssim.models.similarity import Region

logger = logging.getLogger(__name__)


class ExtractedRegion(BaseModel):
    """A region with its AST node(s) for further processing."""

    model_config = {"arbitrary_types_allowed": True}

    region: Region = Field(description="Region metadata")
    node: Node = Field(description="Primary AST node for this region")
    nodes: list[Node] | None = Field(default=None, description="Multiple nodes for section regions")


@dataclass
class RegionTypeMapping:
    """Mapping of node types to region types for a language."""

    types: list[str]  # Node types to extract (e.g., "function_definition")
    region_type: str  # Region type label (e.g., "function")


# Language-specific mappings of node types to region types
LANGUAGE_REGION_MAPPINGS: dict[str, list[RegionTypeMapping]] = {
    "python": [
        RegionTypeMapping(types=["function_definition"], region_type="function"),
        RegionTypeMapping(types=["class_definition"], region_type="class"),
    ],
    "javascript": [
        RegionTypeMapping(
            types=["function_declaration", "function", "arrow_function"],
            region_type="function",
        ),
        RegionTypeMapping(types=["method_definition"], region_type="method"),
        RegionTypeMapping(types=["class_declaration"], region_type="class"),
    ],
    "typescript": [
        RegionTypeMapping(
            types=["function_declaration", "function", "arrow_function"],
            region_type="function",
        ),
        RegionTypeMapping(types=["method_definition"], region_type="method"),
        RegionTypeMapping(types=["class_declaration"], region_type="class"),
    ],
    "markdown": [
        RegionTypeMapping(
            types=["atx_heading", "setext_heading", "section"], region_type="heading"
        ),
        RegionTypeMapping(
            types=["fenced_code_block", "indented_code_block"], region_type="code_block"
        ),
    ],
}

# Copy typescript mappings for tsx and jsx
LANGUAGE_REGION_MAPPINGS["tsx"] = LANGUAGE_REGION_MAPPINGS["typescript"]
LANGUAGE_REGION_MAPPINGS["jsx"] = LANGUAGE_REGION_MAPPINGS["javascript"]


def _extract_node_name(node: Node, source: bytes) -> str:
    """Extract the name of a function/class/method from its node.

    Args:
        node: The function_definition or class_definition node
        source: Source code bytes

    Returns:
        The extracted name or 'anonymous' if not found
    """
    # Look for 'name' or 'identifier' child node
    for child in node.children:
        if child.type in ("identifier", "name"):
            return source[child.start_byte : child.end_byte].decode("utf-8", errors="ignore")
    return "anonymous"


def _collect_top_level_nodes(root_node: Node) -> list[Node]:
    """Collect all top-level nodes that are direct children of the root.

    Args:
        root_node: The root node of the AST

    Returns:
        List of top-level nodes (direct children)
    """
    # For most languages, the root is a "program" or "module" node
    # We want its direct children as top-level nodes
    if root_node.type in ("module", "program", "source_file"):
        return list(root_node.children)
    return [root_node]


def _create_section_region(
    pending_nodes: list[Node],
    parsed_file: ParsedFile,
) -> ExtractedRegion:
    """Create a section region from a list of pending nodes.

    Args:
        pending_nodes: List of nodes to group into a section
        parsed_file: The parsed file for context

    Returns:
        ExtractedRegion for the section
    """
    first_node = pending_nodes[0]
    last_node = pending_nodes[-1]
    start_line = first_node.start_point[0] + 1
    end_line = last_node.end_point[0] + 1

    region = Region(
        path=parsed_file.path,
        language=parsed_file.language,
        region_type="lines",
        region_name=f"lines_{start_line}_{end_line}",
        start_line=start_line,
        end_line=end_line,
    )
    # Store all nodes for sections so shingling can process them all
    return ExtractedRegion(
        region=region, node=first_node, nodes=pending_nodes if len(pending_nodes) > 1 else None
    )


def _get_region_type_for_node(node_type: str, language: str) -> str:
    """Get the region type label for a node type.

    Args:
        node_type: The AST node type
        language: Programming language

    Returns:
        Region type label (e.g., "function", "class")
    """
    mappings = LANGUAGE_REGION_MAPPINGS.get(language, [])
    for mapping in mappings:
        if node_type in mapping.types:
            return mapping.region_type
    return "unknown"


def _create_target_region(
    node: Node,
    parsed_file: ParsedFile,
) -> ExtractedRegion:
    """Create a region for a target node (function, class, etc).

    Args:
        node: The AST node
        parsed_file: The parsed file for context

    Returns:
        ExtractedRegion for the target node
    """
    name = _extract_node_name(node, parsed_file.source)
    region_type = _get_region_type_for_node(node.type, parsed_file.language)

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


def _partition_by_type(
    nodes: list[Node],
    target_types: set[str],
    parsed_file: ParsedFile,
    include_sections: bool = True,
) -> list[ExtractedRegion]:
    """Partition nodes into regions.

    When include_sections is False, only extract target regions.
    When include_sections is True, also group non-target nodes into sections.

    Args:
        nodes: List of top-level nodes to partition
        target_types: Set of node types to extract as named regions
        parsed_file: The parsed file for context
        include_sections: If True, create section regions for non-target nodes

    Returns:
        List of extracted regions
    """
    if not include_sections:
        # Simple case: only extract target regions
        return [_create_target_region(node, parsed_file) for node in nodes if node.type in target_types]

    # Complex case: extract targets and group remaining into sections
    regions: list[ExtractedRegion] = []
    pending_section_nodes: list[Node] = []

    for node in nodes:
        if node.type in target_types:
            if pending_section_nodes:
                regions.append(_create_section_region(pending_section_nodes, parsed_file))
                pending_section_nodes.clear()
            regions.append(_create_target_region(node, parsed_file))
        else:
            pending_section_nodes.append(node)

    if pending_section_nodes:
        regions.append(_create_section_region(pending_section_nodes, parsed_file))

    return regions


def extract_regions(parsed_file: ParsedFile, include_sections: bool = True) -> list[ExtractedRegion]:
    """Extract code regions from a parsed file.

    Uses language-specific mappings to partition the file into regions.
    When include_sections is True, ensures all code is covered (either as named
    regions like functions/classes or as "section" regions for other code).
    When False, only extracts named regions.

    Args:
        parsed_file: Parsed source file
        include_sections: If True, create section regions for non-target code

    Returns:
        List of extracted regions with their AST nodes
    """
    logger.info("Extracting regions from %s (%s)", parsed_file.path, parsed_file.language)

    # Check if language has region mappings
    mappings = LANGUAGE_REGION_MAPPINGS.get(parsed_file.language)
    if mappings is None:
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
        # Collect all target types from mappings
        target_types: set[str] = set()
        for mapping in mappings:
            target_types.update(mapping.types)

        # Collect top-level nodes
        top_level_nodes = _collect_top_level_nodes(parsed_file.root_node)

        # Partition nodes into regions
        regions = _partition_by_type(top_level_nodes, target_types, parsed_file, include_sections)

    logger.info("Extracted %d region(s) from %s", len(regions), parsed_file.path)
    return regions


def extract_all_regions(
    parsed_files: list[ParsedFile], include_sections: bool = True
) -> list[ExtractedRegion]:
    """Extract regions from all parsed files.

    Args:
        parsed_files: List of parsed source files
        include_sections: If True, create section regions for non-target code

    Returns:
        List of all extracted regions
    """
    all_regions: list[ExtractedRegion] = []

    for parsed_file in parsed_files:
        try:
            regions = extract_regions(parsed_file, include_sections)
            all_regions.extend(regions)
        except Exception as e:
            logger.error("Failed to extract regions from %s: %s", parsed_file.path, e)

    logger.info("Extracted %d total region(s) from %d file(s)", len(all_regions), len(parsed_files))
    return all_regions


def get_matched_line_ranges(matched_regions: list[Region]) -> dict:
    """Get the line ranges that were matched, organized by file path.

    Args:
        matched_regions: List of regions that were matched

    Returns:
        Dictionary mapping file paths to sets of matched line numbers
    """
    matched_lines_by_file: dict = {}

    for region in matched_regions:
        if region.path not in matched_lines_by_file:
            matched_lines_by_file[region.path] = set()

        # Add all lines in this region to the matched set
        for line in range(region.start_line, region.end_line + 1):
            matched_lines_by_file[region.path].add(line)

    return matched_lines_by_file


def create_line_based_regions(
    parsed_files: list[ParsedFile],
    matched_lines_by_file: dict,
    min_lines: int,
) -> list[ExtractedRegion]:
    """Create line-based regions for unmatched sections of files.

    Args:
        parsed_files: List of parsed source files
        matched_lines_by_file: Dictionary mapping file paths to sets of matched line numbers
        min_lines: Minimum number of lines for a region to be created

    Returns:
        List of line-based regions for unmatched sections
    """
    line_regions: list[ExtractedRegion] = []

    for parsed_file in parsed_files:
        matched_lines = matched_lines_by_file.get(parsed_file.path, set())
        file_end_line = parsed_file.root_node.end_point[0] + 1

        # Find contiguous unmatched line ranges
        unmatched_ranges: list[tuple[int, int]] = []
        range_start = None

        for line in range(1, file_end_line + 1):
            if line not in matched_lines:
                if range_start is None:
                    range_start = line
            else:
                if range_start is not None:
                    # End of unmatched range
                    unmatched_ranges.append((range_start, line - 1))
                    range_start = None

        # Handle case where file ends with unmatched lines
        if range_start is not None:
            unmatched_ranges.append((range_start, file_end_line))

        # Create regions for unmatched ranges that meet min_lines threshold
        for start_line, end_line in unmatched_ranges:
            line_count = end_line - start_line + 1
            if line_count >= min_lines:
                region = Region(
                    path=parsed_file.path,
                    language=parsed_file.language,
                    region_type="lines",
                    region_name=f"lines_{start_line}_{end_line}",
                    start_line=start_line,
                    end_line=end_line,
                )

                # Create a dummy node that spans the line range
                # We'll use the root node as a placeholder
                extracted_region = ExtractedRegion(
                    region=region,
                    node=parsed_file.root_node,
                )
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
