"""Extract regions (functions, classes, sections, etc) from parsed files."""

import logging
from dataclasses import dataclass

from pydantic import BaseModel, Field
from tree_sitter import Node

from tssim.models.ast import ParsedFile
from tssim.models.similarity import Region

logger = logging.getLogger(__name__)


class ExtractedRegion(BaseModel):
    """A region with its AST node for further processing."""

    model_config = {"arbitrary_types_allowed": True}

    region: Region = Field(description="Region metadata")
    node: Node = Field(description="AST node for this region")


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
    return ExtractedRegion(region=region, node=first_node)


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
) -> list[ExtractedRegion]:
    """Partition nodes into regions, ensuring all code is covered.

    This function groups consecutive nodes into regions based on whether they match
    target types. Nodes that match target types become their own regions, while
    consecutive non-matching nodes are grouped into "section" regions.

    Args:
        nodes: List of top-level nodes to partition
        target_types: Set of node types to extract as named regions
        parsed_file: The parsed file for context

    Returns:
        List of extracted regions covering all nodes
    """
    regions: list[ExtractedRegion] = []
    pending_section_nodes: list[Node] = []

    for node in nodes:
        if node.type in target_types:
            # Flush any pending section first
            if pending_section_nodes:
                regions.append(_create_section_region(pending_section_nodes, parsed_file))
                pending_section_nodes.clear()

            # Create a region for this target node
            regions.append(_create_target_region(node, parsed_file))
        else:
            # Accumulate non-target nodes into pending section
            pending_section_nodes.append(node)

    # Flush any remaining pending section
    if pending_section_nodes:
        regions.append(_create_section_region(pending_section_nodes, parsed_file))

    return regions


def extract_regions(parsed_file: ParsedFile) -> list[ExtractedRegion]:
    """Extract code regions from a parsed file.

    Uses language-specific mappings to partition the file into regions,
    ensuring all code is covered (either as named regions like functions/classes
    or as "section" regions for other code).

    Args:
        parsed_file: Parsed source file

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
        regions = _partition_by_type(top_level_nodes, target_types, parsed_file)

    logger.info("Extracted %d region(s) from %s", len(regions), parsed_file.path)
    return regions


def extract_all_regions(parsed_files: list[ParsedFile]) -> list[ExtractedRegion]:
    all_regions: list[ExtractedRegion] = []

    for parsed_file in parsed_files:
        try:
            regions = extract_regions(parsed_file)
            all_regions.extend(regions)
        except Exception as e:
            logger.error("Failed to extract regions from %s: %s", parsed_file.path, e)

    logger.info(
        "Extracted %d total region(s) from %d file(s)", len(all_regions), len(parsed_files)
    )
    return all_regions
