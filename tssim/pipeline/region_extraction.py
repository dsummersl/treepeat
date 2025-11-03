"""Extract regions (functions, classes, sections, etc) from parsed files."""

import logging

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


def _extract_python_regions(
    parsed_file: ParsedFile,
    parent_node: Node | None = None,
    parent_name: str | None = None,
) -> list[ExtractedRegion]:
    """Extract regions from Python code.

    Args:
        parsed_file: Parsed Python file
        parent_node: Parent node to search within (None for root)
        parent_name: Name of parent class (for methods)

    Returns:
        List of extracted regions
    """
    regions: list[ExtractedRegion] = []
    node = parent_node or parsed_file.root_node

    def traverse(current: Node, in_class: str | None = None) -> None:
        # Extract functions (top-level or methods)
        if current.type == "function_definition":
            name = _extract_node_name(current, parsed_file.source)
            region_type = "method" if in_class else "function"
            full_name = f"{in_class}.{name}" if in_class else name

            region = Region(
                path=parsed_file.path,
                language=parsed_file.language,
                region_type=region_type,
                region_name=full_name,
                start_line=current.start_point[0] + 1,  # 0-indexed to 1-indexed
                end_line=current.end_point[0] + 1,
            )
            regions.append(ExtractedRegion(region=region, node=current))
            logger.debug(
                "Extracted %s: %s at lines %d-%d",
                region_type,
                full_name,
                region.start_line,
                region.end_line,
            )

        # Extract classes and recursively find methods
        elif current.type == "class_definition":
            name = _extract_node_name(current, parsed_file.source)
            region = Region(
                path=parsed_file.path,
                language=parsed_file.language,
                region_type="class",
                region_name=name,
                start_line=current.start_point[0] + 1,
                end_line=current.end_point[0] + 1,
            )
            regions.append(ExtractedRegion(region=region, node=current))
            logger.debug(
                "Extracted class: %s at lines %d-%d",
                name,
                region.start_line,
                region.end_line,
            )

            # Find methods within this class
            for child in current.children:
                traverse(child, in_class=name)
            return  # Don't traverse children again

        # Continue traversing
        for child in current.children:
            traverse(child, in_class)

    traverse(node, parent_name)
    return regions


def _extract_javascript_regions(parsed_file: ParsedFile) -> list[ExtractedRegion]:
    """Extract regions from JavaScript/TypeScript code.

    Args:
        parsed_file: Parsed JavaScript/TypeScript file

    Returns:
        List of extracted regions
    """
    regions: list[ExtractedRegion] = []
    node = parsed_file.root_node

    def traverse(current: Node) -> None:
        # Function declarations
        if current.type in ("function_declaration", "function", "arrow_function"):
            name = _extract_node_name(current, parsed_file.source)
            region = Region(
                path=parsed_file.path,
                language=parsed_file.language,
                region_type="function",
                region_name=name,
                start_line=current.start_point[0] + 1,
                end_line=current.end_point[0] + 1,
            )
            regions.append(ExtractedRegion(region=region, node=current))

        # Method definitions
        elif current.type in ("method_definition", "method"):
            name = _extract_node_name(current, parsed_file.source)
            region = Region(
                path=parsed_file.path,
                language=parsed_file.language,
                region_type="method",
                region_name=name,
                start_line=current.start_point[0] + 1,
                end_line=current.end_point[0] + 1,
            )
            regions.append(ExtractedRegion(region=region, node=current))

        # Class declarations
        elif current.type == "class_declaration":
            name = _extract_node_name(current, parsed_file.source)
            region = Region(
                path=parsed_file.path,
                language=parsed_file.language,
                region_type="class",
                region_name=name,
                start_line=current.start_point[0] + 1,
                end_line=current.end_point[0] + 1,
            )
            regions.append(ExtractedRegion(region=region, node=current))

        # Continue traversing
        for child in current.children:
            traverse(child)

    traverse(node)
    return regions


def extract_regions(parsed_file: ParsedFile) -> list[ExtractedRegion]:
    """Extract code regions from a parsed file.

    Args:
        parsed_file: Parsed source file

    Returns:
        List of extracted regions with their AST nodes
    """
    logger.info("Extracting regions from %s (%s)", parsed_file.path, parsed_file.language)

    if parsed_file.language == "python":
        regions = _extract_python_regions(parsed_file)
    elif parsed_file.language in ("javascript", "typescript", "tsx", "jsx"):
        regions = _extract_javascript_regions(parsed_file)
    else:
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

    logger.info("Extracted %d region(s) from %s", len(regions), parsed_file.path)
    return regions


def extract_all_regions(parsed_files: list[ParsedFile]) -> list[ExtractedRegion]:
    """Extract regions from multiple parsed files.

    Args:
        parsed_files: List of parsed files

    Returns:
        List of all extracted regions across all files
    """
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
