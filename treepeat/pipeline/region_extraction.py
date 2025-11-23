"""Extract regions (functions, classes, sections, etc) from parsed files."""

import logging
from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel, Field
from tree_sitter import Node

from treepeat.models.ast import ParsedFile
from treepeat.models.similarity import Region
from treepeat.config import get_settings

from treepeat.pipeline.rules.engine import RuleEngine
from treepeat.pipeline.verbose_metrics import record_used_node_type

logger = logging.getLogger(__name__)


def _extract_node_types_from_query(query: str) -> set[str]:
    """Extract tree-sitter node type names from a query string.

    Parses queries like "(function_definition) @region" to extract "function_definition".
    Also handles alternatives like "[(func_a) (func_b)] @region".
    """
    import re
    # Match node types in parentheses: (node_type) or (node_type ...)
    # This handles both simple matches and matches with predicates/children
    pattern = r'\((\w+)(?:\s|[)\]])'
    matches = re.findall(pattern, query)
    return set(matches)


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


def _get_explicit_node_types(engine: "RuleEngine", language: str) -> set[str]:
    """Get the tree-sitter node types that explicit rules target for a language.

    This is used to exclude these types from statistical extraction to avoid duplicates.
    """
    rules = engine.get_region_extraction_rules(language)
    node_types: set[str] = set()
    for query, _ in rules:
        node_types.update(_extract_node_types_from_query(query))
    return node_types


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
    """Extract code regions from a parsed file using explicit rules from the engine.

    Returns empty list if no explicit rules exist for this language (statistical chunking will handle it).
    """
    logger.debug("Extracting explicit regions from %s (%s)", parsed_file.path, parsed_file.language)

    # Get region mappings from the rule engine
    mappings = _get_region_mappings_from_engine(rule_engine, parsed_file.language)

    if not mappings:
        # No explicit rules for this language - return empty, statistical chunking will handle it
        logger.debug("No explicit rules for %s, relying on statistical chunking", parsed_file.language)
        return []

    # Recursive extraction: find ALL matching nodes (methods, nested functions, etc.)
    matching_nodes_list = _collect_all_matching_nodes(
        parsed_file.root_node, mappings, parsed_file.language, rule_engine
    )
    regions = [_create_target_region(node, region_type, parsed_file) for node, region_type in matching_nodes_list]

    # Record used node types for verbose output
    for region in regions:
        record_used_node_type(parsed_file.language, region.region.region_type)

    logger.debug("Extracted %d explicit region(s) from %s", len(regions), parsed_file.path)
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


def _make_region_key(region: ExtractedRegion) -> tuple[str, int, int]:
    """Create deduplication key from region location."""
    return (str(region.region.path), region.region.start_line, region.region.end_line)


def _should_keep_region(region: ExtractedRegion, existing: ExtractedRegion | None) -> bool:
    """Determine if region should be kept (prefer explicit types)."""
    return existing is None or _should_replace_region(region, existing)


def _build_deduplicated_map(regions: list[ExtractedRegion]) -> dict[tuple[str, int, int], ExtractedRegion]:
    """Build map of unique regions, preferring explicit types for duplicates."""
    seen_locations: dict[tuple[str, int, int], ExtractedRegion] = {}
    for region in regions:
        key = _make_region_key(region)
        existing = seen_locations.get(key)
        if _should_keep_region(region, existing):
            seen_locations[key] = region
    return seen_locations


def _deduplicate_regions(regions: list[ExtractedRegion]) -> list[ExtractedRegion]:
    """Deduplicate regions based on file path and line range.

    In hybrid mode, explicit and statistical extraction may find the same region.
    Keep explicit regions when there's overlap (they have better semantic labels).
    """
    if not regions:
        return regions

    seen_locations = _build_deduplicated_map(regions)
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


def _group_files_by_language(parsed_files: list[ParsedFile]) -> dict[str, list[ParsedFile]]:
    """Group parsed files by language."""
    by_language: dict[str, list[ParsedFile]] = {}
    for pf in parsed_files:
        if pf.language not in by_language:
            by_language[pf.language] = []
        by_language[pf.language].append(pf)
    return by_language


def _get_file_line_count(parsed_file: ParsedFile) -> int:
    """Get line count for a file."""
    return parsed_file.root_node.end_point[0] + 1


def _select_sample_files(files: list[ParsedFile], max_files: int = 5) -> list[ParsedFile]:
    """Select the largest files as a sample."""
    sorted_files = sorted(files, key=_get_file_line_count, reverse=True)
    return sorted_files[:max_files]


def _count_chunks_in_sample(
    sample_files: list[ParsedFile],
    min_lines: int,
    max_lines_per_file: int,
) -> tuple[Counter[str], int]:
    """Count chunk types in sample files, limiting to first max_lines_per_file lines."""
    from treepeat.pipeline.statistical_chunk_extraction import _collect_all_chunks

    all_chunks_by_type: Counter[str] = Counter()
    total_chunks = 0

    for pf in sample_files:
        chunks = _collect_all_chunks(pf.root_node, min_lines)
        for chunk in chunks:
            if chunk.start_point[0] < max_lines_per_file:
                all_chunks_by_type[chunk.type] += 1
                total_chunks += 1

    return all_chunks_by_type, total_chunks


def _identify_frequent_types(
    chunks_by_type: Counter[str],
    total_chunks: int,
    threshold: float = 0.5,
) -> set[str]:
    """Identify node types that appear more frequently than threshold."""
    frequent_types = set()
    for node_type, count in chunks_by_type.items():
        ratio = count / total_chunks
        if ratio > threshold:
            frequent_types.add(node_type)
            logger.debug(
                "Sample analysis: '%s' too frequent (%.1f%%), will filter",
                node_type,
                ratio * 100,
            )
    return frequent_types


def _analyze_sample_for_frequent_types(
    sample_files: list[ParsedFile],
    min_lines: int,
    max_lines_per_file: int = 500,
) -> set[str]:
    """Analyze sample files to find frequently occurring node types.

    Returns set of node types that appear too frequently (>50% of all chunks).
    """
    chunks_by_type, total_chunks = _count_chunks_in_sample(
        sample_files, min_lines, max_lines_per_file
    )

    if total_chunks == 0:
        return set()

    return _identify_frequent_types(chunks_by_type, total_chunks)


def _run_sample_analysis(
    parsed_files: list[ParsedFile],
    min_lines: int,
) -> dict[str, set[str]]:
    """Run sample analysis to find frequent node types per language."""
    by_language = _group_files_by_language(parsed_files)
    frequent_types_by_lang: dict[str, set[str]] = {}

    for language, files in by_language.items():
        if len(files) < 3:
            # Not enough files to sample, skip optimization
            continue

        sample = _select_sample_files(files, max_files=5)
        logger.debug(
            "Analyzing %d sample files for %s (of %d total)",
            len(sample),
            language,
            len(files),
        )

        frequent = _analyze_sample_for_frequent_types(sample, min_lines)
        if frequent:
            frequent_types_by_lang[language] = frequent
            logger.info(
                "Sample analysis for %s: will filter %d frequent types",
                language,
                len(frequent),
            )

    return frequent_types_by_lang


def extract_all_regions(
    parsed_files: list[ParsedFile],
    rule_engine: "RuleEngine",
) -> list[ExtractedRegion]:
    """Extract regions from all parsed files using hybrid extraction (explicit + statistical).

    Hybrid extraction combines:
    - Explicit rules (semantic labels like "function", "class")
    - Statistical auto-chunking (discovers patterns rules miss)

    Optimization: Runs sample analysis on 5 largest files per language first
    to detect overly frequent node types before processing all files.
    """
    from treepeat.pipeline.statistical_chunk_extraction import extract_chunks_statistical

    settings = get_settings()
    logger.info("Using hybrid region extraction (explicit + statistical)")

    # Run sample analysis to find frequent node types per language
    frequent_types_by_lang = _run_sample_analysis(parsed_files, settings.lsh.min_lines)

    all_regions: list[ExtractedRegion] = []

    for parsed_file in parsed_files:
        try:
            # Get explicit regions from rules
            explicit_regions = extract_regions(parsed_file, rule_engine)

            # Get node types covered by explicit rules to exclude from statistical extraction
            explicit_node_types = _get_explicit_node_types(rule_engine, parsed_file.language)

            # Get statistical chunks with optimized max_frequency_ratio
            # if we found frequent types in sample analysis
            max_freq = 0.4  # default
            if parsed_file.language in frequent_types_by_lang:
                # Lower threshold since we already know some types are too frequent
                max_freq = 0.3

            statistical_regions = extract_chunks_statistical(
                parsed_file,
                min_lines=settings.lsh.min_lines,
                max_frequency_ratio=max_freq,
                exclude_node_types=explicit_node_types,
            )

            # Combine and deduplicate (prefer explicit when overlapping)
            combined = explicit_regions + statistical_regions
            regions = _deduplicate_regions(combined)

            logger.debug(
                "%s: %d explicit + %d statistical -> %d after dedup",
                parsed_file.path.name,
                len(explicit_regions),
                len(statistical_regions),
                len(regions),
            )

            all_regions.extend(regions)
        except Exception as e:
            logger.error("Failed to extract regions from %s: %s", parsed_file.path, e)

    # Log overall statistics
    logger.info("Extracted %d total region(s) from %d file(s)", len(all_regions), len(parsed_files))
    _log_region_type_statistics(all_regions, "hybrid")

    return all_regions
