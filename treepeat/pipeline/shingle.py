import logging
import sys
from collections import deque
from pathlib import Path
from typing import Iterable, cast

from tqdm import tqdm  # type: ignore[import-untyped]
from tree_sitter import Node

from treepeat.models.ast import ParsedFile, ParseResult
from treepeat.models.normalization import NodeRepresentation, SkipNode
from treepeat.models.shingle import (
    Shingle,
    ShingledFile,
    ShingledRegion,
    ShingleList,
    ShingleResult,
)
from treepeat.pipeline.region_extraction import ExtractedRegion
from treepeat.pipeline.rules.engine import RuleEngine
from treepeat.pipeline.rules.models import SkipNodeException

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

    def _shingle_injected_region(self, extracted_region: ExtractedRegion) -> list[Shingle]:
        injected_tree = extracted_region.injected_tree
        injected_language = extracted_region.injected_language
        injected_source = extracted_region.injected_source

        assert injected_tree is not None, "injected_tree must be set for injected regions"
        assert (
            injected_language is not None and injected_source is not None
        ), "injected_language and injected_source must be set when injected_tree is set"

        return self._extract_shingles(
            injected_tree.root_node,
            injected_language,
            injected_source,
        )

    def _shingle_section_region(
        self, nodes: list[Node], language: str, source: bytes
    ) -> list[Shingle]:
        all_shingles: list[Shingle] = []
        for node in nodes:
            all_shingles.extend(self._extract_shingles(node, language, source))
        return all_shingles

    def shingle_region(self, extracted_region: ExtractedRegion, source: bytes) -> ShingledRegion:
        region = extracted_region.region

        if extracted_region.injected_tree is not None:
            shingles = self._shingle_injected_region(extracted_region)
        elif extracted_region.nodes is not None:
            shingles = self._shingle_section_region(extracted_region.nodes, region.language, source)
        else:
            start_line, end_line = (
                (region.start_line, region.end_line) if region.region_type == "lines" else (None, None)
            )
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
        except SkipNodeException as sne:
            # Convert to SkipNode for compatibility with existing code
            raise SkipNode(f"Node type '{name}' skipped by rule") from sne
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

                shingle = Shingle(content=shingle_content, start_line=start_line, end_line=end_line)
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

    for parsed_file in parse_result.parsed_files:
        try:
            shingled_file = shingler.shingle_file(parsed_file)
            shingled_files.append(shingled_file)
        except Exception as e:
            logger.warning("Failed to shingle %s: %s", parsed_file.path, e)

    logger.info(
        "Shingling complete: %d succeeded",
        len(shingled_files),
    )

    return ShingleResult(
        shingled_files=shingled_files,
    )


def _shingle_single_region(
    extracted_region: ExtractedRegion,
    path_to_source: dict[Path, bytes],
    shingler: ASTShingler,
) -> ShingledRegion | None:
    # Injected regions carry their own source bytes; other regions look up by path.
    source: bytes | None
    if extracted_region.injected_source is not None:
        source = extracted_region.injected_source
    else:
        source = path_to_source.get(extracted_region.region.path)

    if source is None:
        logger.error(
            "Source not found for region %s in %s",
            extracted_region.region.region_name,
            extracted_region.region.path,
        )
        return None

    # Reset identifier counter for each region to ensure consistent anonymization
    shingler.rule_engine.reset_identifiers()

    # Pre-execute all queries upfront to populate the cache.
    # For injected regions use the injected tree + language so that the target
    # language's normalization rules are applied during traversal.
    if extracted_region.injected_tree is not None:
        assert extracted_region.injected_language is not None
        shingler.rule_engine.precompute_queries(
            extracted_region.injected_tree.root_node,
            extracted_region.injected_language,
            source,
        )
    else:
        shingler.rule_engine.precompute_queries(
            extracted_region.node, extracted_region.region.language, source
        )

    return shingler.shingle_region(extracted_region, source)


def _get_region_shingling_iterable(
    extracted_regions: list[ExtractedRegion],
    progress: bool,
) -> Iterable[ExtractedRegion]:
    if progress:
        return cast(
            Iterable[ExtractedRegion],
            tqdm(extracted_regions, desc="Shingling", unit="region", file=sys.stderr),
        )
    return extracted_regions


def _append_shingled_region(
    extracted_region: ExtractedRegion,
    path_to_source: dict[Path, bytes],
    shingler: ASTShingler,
    shingled_regions: list[ShingledRegion],
) -> int:
    shingled_region = _shingle_single_region(extracted_region, path_to_source, shingler)
    if shingled_region is None:
        return 1
    shingled_regions.append(shingled_region)
    return 0


def _log_region_shingling_error(extracted_region: ExtractedRegion, error: Exception) -> None:
    logger.error(
        "Failed to shingle region %s in %s: %s",
        extracted_region.region.region_name,
        extracted_region.region.path,
        error,
    )


def shingle_regions(
    extracted_regions: list[ExtractedRegion],
    parsed_files: list[ParsedFile],
    rule_engine: RuleEngine,
    k: int = 3,
    progress: bool = False,
) -> list[ShingledRegion]:
    logger.info(
        "Shingling %d region(s) across %d file(s) with k=%d",
        len(extracted_regions),
        len(parsed_files),
        k,
    )

    path_to_source = {pf.path: pf.source for pf in parsed_files}
    shingler = ASTShingler(rule_engine=rule_engine, k=k)
    shingled_regions: list[ShingledRegion] = []
    filtered_count = 0
    iterable = _get_region_shingling_iterable(extracted_regions, progress)

    for extracted_region in iterable:
        try:
            filtered_count += _append_shingled_region(
                extracted_region,
                path_to_source,
                shingler,
                shingled_regions,
            )
        except Exception as e:
            _log_region_shingling_error(extracted_region, e)

    logger.info(
        "Shingling complete: %d region(s) shingled, %d filtered",
        len(shingled_regions),
        filtered_count,
    )
    return shingled_regions
