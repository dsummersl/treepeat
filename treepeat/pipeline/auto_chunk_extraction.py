import logging
from tree_sitter import Node

from treepeat.models.ast import ParsedFile
from treepeat.models.similarity import Region
from treepeat.pipeline.region_extraction import ExtractedRegion

logger = logging.getLogger(__name__)


def _get_node_name(node: Node, source: bytes) -> str:
    """Extract a name from a node, using multiple strategies.

    Strategies (in order):
    1. Look for child nodes named 'identifier', 'name', 'property_identifier'
    2. Use the node type + first few characters of text
    3. Fall back to just the node type
    """
    # Strategy 1: Look for identifier-like children
    for child in node.children:
        if child.type in ("identifier", "name", "property_identifier", "tag_name"):
            name = source[child.start_byte : child.end_byte].decode("utf-8", errors="ignore")
            if name.strip():
                return name.strip()

    # Strategy 2: Use node type + snippet of text
    node_text = source[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")
    # Get first line or first 50 chars, whichever is shorter
    first_line = node_text.split('\n')[0][:50].strip()
    if first_line:
        return f"{node.type}:{first_line}"

    # Strategy 3: Just use node type
    return node.type


def _calculate_node_lines(node: Node) -> int:
    """Calculate the number of lines a node spans (inclusive)."""
    return node.end_point[0] - node.start_point[0] + 1


def _find_leaf_chunks(root: Node, min_lines: int) -> list[Node]:
    """Find all leaf chunks: minimal nodes that meet min_lines with no qualifying children.

    A node is a leaf chunk if:
    1. It meets the min_lines threshold
    2. None of its children meet the min_lines threshold

    This creates a set of disjoint chunks that cover the parts of the tree
    that are large enough to be interesting.

    Args:
        root: Root node to start traversal
        min_lines: Minimum number of lines for a chunk to be considered

    Returns:
        List of nodes that are leaf chunks
    """
    chunks = []

    def traverse(node: Node) -> bool:
        """Returns True if this node (or its subtree) has qualifying chunks."""
        node_lines = _calculate_node_lines(node)

        # If this node is too small, it and its subtree can't be chunks
        if node_lines < min_lines:
            return False

        # Check if any children are large enough to be chunks
        has_chunk_children = False
        for child in node.children:
            if traverse(child):
                has_chunk_children = True

        # If no children are chunks, this node is a leaf chunk
        if not has_chunk_children:
            chunks.append(node)
            logger.debug(
                "Found leaf chunk: %s (%d lines)",
                node.type,
                node_lines,
            )
            return True

        # Otherwise, we've already processed children, this node is not a chunk
        return True

    traverse(root)
    return chunks


def _create_chunk_region(
    node: Node,
    parsed_file: ParsedFile,
) -> ExtractedRegion:
    """Create a region from an auto-discovered chunk.

    The region_type is set to the node's AST type (e.g., 'function_definition').
    The region_name is extracted using multiple strategies.
    """
    name = _get_node_name(node, parsed_file.source)

    region = Region(
        path=parsed_file.path,
        language=parsed_file.language,
        region_type=node.type,  # Use AST node type as region type
        region_name=name,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
    )

    logger.debug(
        "Created chunk region: %s (%s) at lines %d-%d",
        name,
        node.type,
        region.start_line,
        region.end_line,
    )

    return ExtractedRegion(region=region, node=node)


def extract_chunks(
    parsed_file: ParsedFile,
    min_lines: int = 5,
) -> list[ExtractedRegion]:
    """Extract chunks from a parsed file using bottom-up auto-discovery.

    This is an alternative to extract_regions() that doesn't require
    language-specific RegionExtractionRules. Instead, it:

    1. Traverses the entire AST depth-first
    2. Finds the SMALLEST nodes that meet min_lines (leaf chunks)
    3. Creates regions from these chunks

    The resulting chunks are disjoint (non-overlapping) and cover all
    parts of the file that are large enough to be interesting.

    Args:
        parsed_file: Parsed source file with AST
        min_lines: Minimum lines for a chunk (default: 5)

    Returns:
        List of extracted regions representing auto-discovered chunks
    """
    logger.info(
        "Auto-chunking file: %s (%s) with min_lines=%d",
        parsed_file.path,
        parsed_file.language,
        min_lines,
    )

    # Find all leaf chunks
    chunk_nodes = _find_leaf_chunks(parsed_file.root_node, min_lines)

    # Convert to ExtractedRegion objects
    regions = [_create_chunk_region(node, parsed_file) for node in chunk_nodes]

    logger.info(
        "Auto-chunked %d region(s) from %s",
        len(regions),
        parsed_file.path,
    )

    return regions


def extract_chunks_with_hierarchy(
    parsed_file: ParsedFile,
    min_lines: int = 5,
) -> tuple[list[ExtractedRegion], dict[Node, list[Node]]]:
    """Extract chunks and return their hierarchical relationships.

    This is an extended version of extract_chunks() that also returns
    parent-child relationships between chunks. This enables compositional
    comparison: if chunks A and B both match something, we can check if
    their parent also matches.

    Args:
        parsed_file: Parsed source file with AST
        min_lines: Minimum lines for a chunk (default: 5)

    Returns:
        Tuple of:
        - List of extracted regions
        - Dict mapping parent nodes to their chunk children
    """
    logger.info(
        "Auto-chunking with hierarchy: %s (%s) with min_lines=%d",
        parsed_file.path,
        parsed_file.language,
        min_lines,
    )

    chunks = []
    hierarchy: dict[Node, list[Node]] = {}

    def traverse(node: Node, parent: Node | None) -> list[Node]:
        """Returns list of chunk nodes found in this subtree."""
        node_lines = _calculate_node_lines(node)

        if node_lines < min_lines:
            return []

        # Recursively process children
        child_chunks: list[Node] = []
        for child in node.children:
            child_chunks.extend(traverse(child, node))

        # If no children are chunks, this node is a leaf chunk
        if not child_chunks:
            chunks.append(node)
            logger.debug(
                "Found leaf chunk: %s (%d lines)",
                node.type,
                node_lines,
            )
            return [node]

        # Record parent-child relationships
        if child_chunks:
            hierarchy[node] = child_chunks
            logger.debug(
                "Parent node %s has %d chunk children",
                node.type,
                len(child_chunks),
            )

        return child_chunks

    traverse(parsed_file.root_node, None)

    # Convert to ExtractedRegion objects
    regions = [_create_chunk_region(node, parsed_file) for node in chunks]

    logger.info(
        "Auto-chunked %d region(s) with %d parent relationships from %s",
        len(regions),
        len(hierarchy),
        parsed_file.path,
    )

    return regions, hierarchy
