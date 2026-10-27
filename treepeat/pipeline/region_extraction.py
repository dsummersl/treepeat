import logging
import sys
from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel, Field
from tqdm import tqdm
from tree_sitter import Node, Tree
from tree_sitter_language_pack import get_parser

from treepeat.models.ast import ParsedFile
from treepeat.models.similarity import Region
from treepeat.pipeline.rules.engine import RuleEngine
from treepeat.pipeline.rules.models import Rule
from treepeat.pipeline.verbose_metrics import record_used_node_type

logger = logging.getLogger(__name__)

__all__ = ["ExtractedRegion", "extract_all_regions", "extract_regions"]


class ExtractedRegion(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    region: Region = Field(description="Region metadata")
    node: Node = Field(description="Primary AST node for this region")
    nodes: list[Node] | None = Field(default=None, description="Multiple nodes for section regions")

    injected_tree: Tree | None = Field(default=None, description="Re-parsed tree for injected language")
    injected_language: str | None = Field(default=None, description="Language of the injected tree")
    injected_source: bytes | None = Field(default=None, description="Source bytes of the injected content")


@dataclass
class RegionTypeMapping:
    query: str
    region_type: str
    rule: Rule | None = None


def _get_region_mappings_from_engine(engine: "RuleEngine", language: str) -> list[RegionTypeMapping]:

    rules = engine.get_region_extraction_rule_objects(language)
    return [
        RegionTypeMapping(
            query=rule.query,
            region_type=rule.params.get("region_type", "unknown"),
            rule=rule,
        )
        for rule in rules
    ]


def _extract_node_name(node: Node, source: bytes) -> str:

    for child in node.children:
        if child.type in (
            "identifier",
            "name",
            "property_identifier",
            "dot_index_expression",
            "method_index_expression",
        ):
            return source[child.start_byte : child.end_byte].decode("utf-8", errors="ignore")
    return "anonymous"


def _collect_all_matching_nodes(
    root_node: Node, mappings: list[RegionTypeMapping], language: str, engine: "RuleEngine"
) -> list[tuple[Node, str, Rule | None]]:

    matching_nodes: list[tuple[Node, str, Rule | None]] = []

    for mapping in mappings:
        nodes = engine.get_nodes_matching_query(root_node, mapping.query, language)
        for node in nodes:
            matching_nodes.append((node, mapping.region_type, mapping.rule))

    matching_nodes.sort(key=lambda x: (x[0].start_byte, x[0].end_byte))
    return matching_nodes


def _extract_injection_bytes(
    node: Node,
    rule: Rule,
    parsed_file: ParsedFile,
    rule_engine: RuleEngine,
) -> tuple[bytes, int] | None:

    if rule.injection_content_query:
        content_nodes = rule_engine.get_nodes_matching_query(node, rule.injection_content_query, parsed_file.language)
        if not content_nodes:
            return None
        content_node = content_nodes[0]
        return parsed_file.source[content_node.start_byte : content_node.end_byte], content_node.start_point[0]
    return parsed_file.source[node.start_byte : node.end_byte], node.start_point[0]


def _do_language_injection(
    node: Node,
    rule: Rule,
    parsed_file: ParsedFile,
    rule_engine: RuleEngine,
) -> ExtractedRegion | None:

    target_lang = rule.resolve_injection_language(node, parsed_file.source)
    if not target_lang:
        return None

    result = _extract_injection_bytes(node, rule, parsed_file, rule_engine)
    if result is None:
        return None
    content_bytes, line_offset = result

    if not content_bytes.strip():
        return None

    padded = b"\n" * line_offset + content_bytes

    try:
        parser = get_parser(target_lang)  # type: ignore[arg-type]
        injected_tree = parser.parse(padded)
    except Exception as e:
        logger.debug("Injection: failed to parse content as %s: %s", target_lang, e)
        return None

    region_type = rule.params.get("region_type", rule.query)
    name = _extract_node_name(node, parsed_file.source)

    region = Region(
        path=parsed_file.path,
        language=parsed_file.language,
        region_type=region_type,
        region_name=name,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
    )

    return ExtractedRegion(
        region=region,
        node=node,
        injected_tree=injected_tree,
        injected_language=target_lang,
        injected_source=padded,
    )


def _create_target_region(
    node: Node,
    region_type: str,
    parsed_file: ParsedFile,
) -> ExtractedRegion:

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


def _create_region_for_node(
    node: Node,
    region_type: str,
    rule: Rule | None,
    parsed_file: ParsedFile,
    rule_engine: "RuleEngine",
) -> ExtractedRegion:

    if rule is not None and rule.injection_language is not None:
        injected = _do_language_injection(node, rule, parsed_file, rule_engine)
        if injected is not None:
            return injected
    return _create_target_region(node, region_type, parsed_file)


def extract_regions(
    parsed_file: ParsedFile,
    rule_engine: "RuleEngine",
) -> list[ExtractedRegion]:

    logger.debug("Extracting explicit regions from %s (%s)", parsed_file.path, parsed_file.language)

    mappings = _get_region_mappings_from_engine(rule_engine, parsed_file.language)

    if not mappings:
        logger.warning(
            "No region extraction rules for language %s. Skipping file %s.",
            parsed_file.language,
            parsed_file.path,
        )
        return []

    matching_nodes_list = _collect_all_matching_nodes(
        parsed_file.root_node, mappings, parsed_file.language, rule_engine
    )
    regions = []
    for node, region_type, rule in matching_nodes_list:
        regions.append(_create_region_for_node(node, region_type, rule, parsed_file, rule_engine))

    for region in regions:
        record_used_node_type(parsed_file.language, region.region.region_type)

    logger.debug("Extracted %d explicit region(s) from %s", len(regions), parsed_file.path)
    return regions


def _is_explicit_type(region_type: str) -> bool:

    explicit_types = {"function", "class", "method", "heading", "section", "head", "body"}
    return region_type in explicit_types


def _should_replace_region(new: ExtractedRegion, existing: ExtractedRegion) -> bool:

    return _is_explicit_type(new.region.region_type) and not _is_explicit_type(existing.region.region_type)


def _make_region_key(region: ExtractedRegion) -> tuple[str, int, int]:

    return (str(region.region.path), region.region.start_line, region.region.end_line)


def _should_keep_region(region: ExtractedRegion, existing: ExtractedRegion | None) -> bool:

    return existing is None or _should_replace_region(region, existing)


def _build_deduplicated_map(regions: list[ExtractedRegion]) -> dict[tuple[str, int, int], ExtractedRegion]:

    seen_locations: dict[tuple[str, int, int], ExtractedRegion] = {}
    for region in regions:
        key = _make_region_key(region)
        existing = seen_locations.get(key)
        if _should_keep_region(region, existing):
            seen_locations[key] = region
    return seen_locations


def _deduplicate_regions(regions: list[ExtractedRegion]) -> list[ExtractedRegion]:

    if not regions:
        return regions

    seen_locations = _build_deduplicated_map(regions)
    deduped = list(seen_locations.values())
    duplicate_count = len(regions) - len(deduped)
    if duplicate_count > 0:
        logger.debug("Deduplicated %d overlapping regions", duplicate_count)

    return deduped


def _log_region_type_statistics(regions: list[ExtractedRegion], method: str) -> None:

    if not regions:
        return

    type_counts: Counter[str] = Counter(r.region.region_type for r in regions)
    logger.info(
        "%s extraction found %d region(s) across %d type(s)",
        method,
        len(regions),
        len(type_counts),
    )

    for region_type, count in type_counts.most_common(10):
        logger.info("  %s: %d region(s)", region_type, count)

    if len(type_counts) > 10:
        logger.info("  ... and %d more type(s)", len(type_counts) - 10)


def extract_all_regions(
    parsed_files: list[ParsedFile],
    rule_engine: "RuleEngine",
    progress: bool = False,
) -> list[ExtractedRegion]:

    logger.info("Using explicit region extraction (no statistical chunking)")

    all_regions: list[ExtractedRegion] = []

    iterable = tqdm(parsed_files, desc="Extracting", unit="file", file=sys.stderr) if progress else parsed_files

    for parsed_file in iterable:
        try:
            regions = extract_regions(parsed_file, rule_engine)
            deduped = _deduplicate_regions(regions)
            all_regions.extend(deduped)
        except Exception as e:
            logger.error("Failed to extract regions from %s: %s", parsed_file.path, e)

    logger.info("Extracted %d total region(s) from %d file(s)", len(all_regions), len(parsed_files))
    _log_region_type_statistics(all_regions, "explicit")

    return all_regions
