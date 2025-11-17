import logging
from collections import deque
from pathlib import Path
from typing import Sequence

from tree_sitter import Node

from covey.models.ast import ParsedFile, ParseResult
from covey.models.normalization import NodeRepresentation, SkipNode
from covey.models.shingle import Shingle, ShingledRegion, ShingleResult, ShingleList, ShingledFile
from covey.pipeline.region_extraction import ExtractedRegion
from covey.pipeline.rules.engine import RuleEngine
from covey.pipeline.rules.models import SkipNodeException

logger = logging.getLogger(__name__)

# Maximum length for node values in shingles (longer values are truncated)
MAX_NODE_VALUE_LENGTH = 50


class ASTShingler:
    def __init__(
        self,
        rule_engine: RuleEngine,
        k: int = 3,
    ):
        if k < 1:
            raise ValueError("k must be at least 1")
        self.rule_engine = rule_engine
        self.k = k

    def shingle_file(self, parsed_file: ParsedFile) -> ShingledFile:
        shingles = self._extract_shingles(
            parsed_file.root_node,
            parsed_file.language,
            parsed_file.source,
        )

        logger.debug(
            "Extracted %d shingle(s) from %s (k=%d)",
            len(shingles),
            parsed_file.path,
            self.k,
        )

        return ShingledFile(
            path=parsed_file.path,
            language=parsed_file.language,
            shingles=ShingleList(shingles=shingles),
        )

    def shingle_region(self, extracted_region: ExtractedRegion, source: bytes) -> ShingledRegion:
        region = extracted_region.region

        # If region has multiple nodes (section regions), extract shingles from all
        if extracted_region.nodes is not None:
            all_shingles: list[Shingle] = []
            for node in extracted_region.nodes:
                node_shingles = self._extract_shingles(node, region.language, source)
                all_shingles.extend(node_shingles)
            shingles = all_shingles
        else:
            # Single node region (target regions like functions/classes or line-based regions)
            # For line-based regions, we need to filter nodes by line range
            start_line = region.start_line if region.region_type == "lines" else None
            end_line = region.end_line if region.region_type == "lines" else None
            shingles = self._extract_shingles(
                extracted_region.node,
                region.language,
                source,
                start_line=start_line,
                end_line=end_line,
            )

        logger.debug(
            "Extracted %d shingle(s) from %s (k=%d)",
            len(shingles),
            region.region_name,
            self.k,
        )

        return ShingledRegion(
            region=region,
            shingles=ShingleList(shingles=shingles),
        )

    def _extract_node_value(self, node: Node, source: bytes) -> str | None:
        if len(node.children) != 0:
            return None

        text = source[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")
        text = text.replace("→", "->").replace("\n", "\\n").replace("\t", "\\t")

        # Truncate long values instead of dropping them
        if len(text) > MAX_NODE_VALUE_LENGTH:
            text = text[:MAX_NODE_VALUE_LENGTH]

        return text

    def _apply_rules(
        self,
        node: Node,
        name: str,
        value: str | None,
        language: str,
        source: bytes,
        root: Node,
    ) -> tuple[str, str | None]:
        """Apply rules to a node and return the modified name and value."""
        rule_name, rule_value = self.rule_engine.apply_rules(node, language, name, root)
        if rule_name is not None:
            name = rule_name
        if rule_value is not None:
            value = rule_value
        return name, value

    def _get_node_representation(
        self,
        node: Node,
        language: str,
        source: bytes,
        root: Node,
    ) -> NodeRepresentation:
        """Get the representation of a node with rules applied."""
        name = node.type
        value = self._extract_node_value(node, source)
        try:
            name, value = self._apply_rules(node, name, value, language, source, root)
        except SkipNodeException:
            # Convert to SkipNode for compatibility with existing code
            raise SkipNode(f"Node type '{name}' skipped by rule")
        return NodeRepresentation(name=name, value=value)

    def _extract_shingles(
        self,
        root: Node,
        language: str,
        source: bytes,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> list[Shingle]:
        """Extract shingles from AST with line range metadata.

        Note: start_line and end_line parameters are deprecated and ignored.
        Line ranges are now tracked automatically from AST nodes.

        Args:
            root: Root AST node to extract shingles from
            language: Programming language
            source: Source code bytes
            start_line: Deprecated, will be removed
            end_line: Deprecated, will be removed

        Returns:
            List of Shingle objects with content and line ranges
        """
        shingles: list[Shingle] = []

        # Pre-order traversal to extract all paths
        def traverse(node: Node, path: deque[tuple[NodeRepresentation, Node]]) -> None:
            # Get normalized representation (may raise SkipNode)
            try:
                node_repr = self._get_node_representation(node, language, source, root)
            except SkipNode:
                # Skip this node and its entire subtree
                return

            path.append((node_repr, node))

            # If path is long enough, create a shingle with line range metadata
            if len(path) >= self.k:
                shingle_path = list(path)[-self.k :]
                shingle_reprs = [repr for repr, _ in shingle_path]
                shingle_nodes = [n for _, n in shingle_path]

                # Create shingle content
                shingle_content = "→".join(str(repr) for repr in shingle_reprs)

                # Calculate line range from the nodes in this shingle
                # Use the LAST node in the k-gram (most specific) for line positioning
                # rather than min/max which often includes the root node spanning the entire file
                last_node = shingle_nodes[-1]
                start_line = last_node.start_point[0] + 1
                end_line = last_node.end_point[0] + 1

                shingle = Shingle(
                    content=shingle_content, start_line=start_line, end_line=end_line
                )
                shingles.append(shingle)

            # Recursively traverse children
            for child in node.children:
                traverse(child, path)

            # Backtrack
            _ = path.pop()

        traverse(root, deque())
        return shingles


def shingle_files(
    parse_result: ParseResult,
    rule_engine: RuleEngine,
    k: int = 3,
) -> ShingleResult:
    logger.info("Shingling %d file(s) with k=%d", len(parse_result.parsed_files), k)

    shingler = ASTShingler(rule_engine=rule_engine, k=k)
    shingled_files = []
    failed_files = dict(parse_result.failed_files)  # Start with parse failures

    for parsed_file in parse_result.parsed_files:
        try:
            shingled_file = shingler.shingle_file(parsed_file)
            shingled_files.append(shingled_file)
        except Exception as e:
            logger.error("Failed to shingle %s: %s", parsed_file.path, e)
            failed_files[parsed_file.path] = str(e)

    logger.info(
        "Shingling complete: %d succeeded, %d failed",
        len(shingled_files),
        len(failed_files) - len(parse_result.failed_files),
    )

    return ShingleResult(
        shingled_files=shingled_files,
        failed_files=failed_files,
    )


def _shingle_single_region(
    extracted_region: ExtractedRegion,
    path_to_source: dict[Path, bytes],
    shingler: ASTShingler,
) -> ShingledRegion | None:
    source = path_to_source.get(extracted_region.region.path)
    if source is None:
        logger.error(
            "Source not found for region %s in %s",
            extracted_region.region.region_name,
            extracted_region.region.path,
        )
        return None

    # Reset identifier counter for each region to ensure consistent anonymization
    # This allows identical functions to get the same anonymized variable names
    shingler.rule_engine.reset_identifiers()

    # Pre-execute all queries for this region to populate the cache upfront
    # This is a performance optimization to avoid lazy query execution during traversal
    shingler.rule_engine.precompute_queries(
        extracted_region.node, extracted_region.region.language, source
    )

    return shingler.shingle_region(extracted_region, source)


def shingle_regions(
    extracted_regions: list[ExtractedRegion],
    parsed_files: list[ParsedFile],
    rule_engine: RuleEngine,
    k: int = 3,
) -> list[ShingledRegion]:
    logger.info(
        "Shingling %d region(s) across %d file(s) with k=%d",
        len(extracted_regions),
        len(parsed_files),
        k,
    )

    path_to_source = {pf.path: pf.source for pf in parsed_files}
    shingler = ASTShingler(rule_engine=rule_engine, k=k)
    shingled_regions = []
    filtered_count = 0

    for extracted_region in extracted_regions:
        try:
            shingled_region = _shingle_single_region(
                extracted_region, path_to_source, shingler
            )
            if shingled_region is not None:
                shingled_regions.append(shingled_region)
            else:
                filtered_count += 1
        except Exception as e:
            logger.error(
                "Failed to shingle region %s in %s: %s",
                extracted_region.region.region_name,
                extracted_region.region.path,
                e,
            )

    logger.info(
        "Shingling complete: %d region(s) shingled, %d filtered",
        len(shingled_regions),
        filtered_count
    )
    return shingled_regions


def _get_window_line_range(shingle_objs: list[Shingle], parent_start: int, parent_end: int) -> tuple[int, int]:
    """Calculate line range from shingles or use parent range."""
    if shingle_objs:
        return (min(s.start_line for s in shingle_objs), max(s.end_line for s in shingle_objs))
    return (parent_start, parent_end)


def _create_window_region(
    shingled_region: ShingledRegion, window_idx: int, window_shingles: Sequence[Shingle | str]
) -> ShingledRegion:
    """Create a window region from a parent shingled region with calculated line ranges."""
    from covey.models.similarity import Region
    from covey.models.shingle import Shingle

    shingle_objs = [s for s in window_shingles if isinstance(s, Shingle)]
    start_line, end_line = _get_window_line_range(
        shingle_objs, shingled_region.region.start_line, shingled_region.region.end_line
    )

    return ShingledRegion(
        region=Region(
            path=shingled_region.region.path,
            language=shingled_region.region.language,
            region_type="shingle_window",
            region_name=f"{shingled_region.region.region_name}_window_{window_idx}",
            start_line=start_line,
            end_line=end_line,
        ),
        shingles=ShingleList(shingles=window_shingles),
    )


def _create_windows_from_region(
    shingled_region: ShingledRegion,
    window_size: int,
    stride: int,
    min_shingles: int,
) -> list[ShingledRegion]:
    """Create sliding windows from a single shingled region."""
    shingles = shingled_region.shingles.shingles
    total_shingles = len(shingles)

    # If the region has fewer shingles than window_size, use it as one window
    if total_shingles <= window_size:
        return [shingled_region] if total_shingles >= min_shingles else []

    # Create sliding windows of shingles
    windows = []
    window_idx = 0
    start_idx = 0

    while start_idx < total_shingles:
        end_idx = min(start_idx + window_size, total_shingles)
        window_shingles = shingles[start_idx:end_idx]

        if len(window_shingles) >= min_shingles:
            window = _create_window_region(shingled_region, window_idx, window_shingles)
            windows.append(window)
            logger.debug(
                "Created shingle window %d for %s: shingles [%d:%d] (%d shingles)",
                window_idx,
                shingled_region.region.region_name,
                start_idx,
                end_idx,
                len(window_shingles),
            )
            window_idx += 1

        start_idx += stride

    return windows


def create_shingle_windows(
    shingled_regions: list[ShingledRegion],
    window_size: int,
    stride: int,
    min_shingles: int,
) -> list[ShingledRegion]:
    """Create sliding windows from shingled regions.

    This creates overlapping windows of shingles from each shingled region,
    allowing for similarity detection at a finer granularity than full regions.

    Args:
        shingled_regions: Regions that have been shingled
        window_size: Number of shingles per window
        stride: Step size for sliding window (in number of shingles)
        min_shingles: Minimum number of shingles for a window to be valid

    Returns:
        List of shingled regions representing windows
    """
    windowed_regions: list[ShingledRegion] = []

    for shingled_region in shingled_regions:
        windows = _create_windows_from_region(
            shingled_region, window_size, stride, min_shingles
        )
        windowed_regions.extend(windows)

    logger.info(
        "Created %d shingle window(s) from %d shingled region(s)",
        len(windowed_regions),
        len(shingled_regions),
    )
    return windowed_regions
