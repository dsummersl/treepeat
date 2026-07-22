"""Tests for YAML language configuration and Markdown ```yaml code block injection."""

from pathlib import Path

import pytest

from tests.conftest import parse_fixture
from treepeat.pipeline.languages import LANGUAGE_CONFIGS
from treepeat.pipeline.languages.markdown import _resolve_code_block_language
from treepeat.pipeline.languages.yaml import YAMLConfig
from treepeat.pipeline.parse import detect_language, parse_file
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules
from treepeat.pipeline.shingle import ASTShingler

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures"
fixture_config = FIXTURE_DIR / "yaml" / "config.yaml"
fixture_guide = FIXTURE_DIR / "markdown" / "guide.md"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_yaml_registered_in_configs():
    assert "yaml" in LANGUAGE_CONFIGS
    assert isinstance(LANGUAGE_CONFIGS["yaml"], YAMLConfig)


@pytest.mark.parametrize("ext", [".yaml", ".yml"])
def test_yaml_extensions_detected(ext):
    assert detect_language(Path(f"foo{ext}")) == "yaml"


def test_yaml_region_extraction_rules_exist():
    labels = [r.label for r in YAMLConfig().get_region_extraction_rules()]
    assert "block_mapping_pair" in labels


# ---------------------------------------------------------------------------
# Standalone YAML parsing / extraction
# ---------------------------------------------------------------------------


def test_parse_yaml_no_errors():
    parsed = parse_file(fixture_config)
    assert parsed.language == "yaml"
    assert not parsed.root_node.has_error


@pytest.mark.parametrize("rules", [
    [rule for rule, _ in build_default_rules()],
    [rule for rule, _ in build_loose_rules()],
])
def test_yaml_regions_extracted(rules):
    parsed = parse_fixture(fixture_config, "yaml")
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine)
    assert regions, "Expected at least one extracted region from the YAML fixture"


# ---------------------------------------------------------------------------
# Markdown ```yaml injection
# ---------------------------------------------------------------------------


def test_markdown_yaml_block_injected():
    parsed = parse_file(fixture_guide)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    injected = [r for r in regions if r.injected_language == "yaml"]
    assert injected, "Expected the ```yaml block in guide.md to be injected as yaml"
    region = injected[0]
    assert region.injected_tree is not None
    assert region.injected_source is not None
    # Region metadata preserves the file language, not the injection language.
    assert region.region.language == "markdown"


def test_yml_alias_resolves_to_yaml():
    """A ```yml fence resolves to the yaml language via the info-string alias."""
    from tree_sitter_language_pack import get_parser

    source = b"```yml\nname: test\n```\n"
    tree = get_parser("markdown").parse(source)

    fenced_node = None
    for child in [tree.root_node, *tree.root_node.children]:
        fenced_node = next(
            (n for n in child.children if n.type == "fenced_code_block"), None
        )
        if fenced_node is not None:
            break

    assert fenced_node is not None, "Could not find fenced_code_block node"
    assert _resolve_code_block_language(fenced_node, source) == "yaml"


# ---------------------------------------------------------------------------
# Cross-file shingle similarity: embedded YAML mirrors a standalone YAML file
# ---------------------------------------------------------------------------


def _shingle_injected_region(region, engine, shingler):
    engine.reset_identifiers()
    engine.precompute_queries(
        region.injected_tree.root_node,
        region.injected_language,
        region.injected_source,
    )
    shingled = shingler.shingle_region(region, region.injected_source)
    return {s.content for s in shingled.shingles.shingles}


def _shingle_standalone_file(path, language, rules):
    parsed = parse_fixture(path, language)
    engine = RuleEngine(rules)
    shingler = ASTShingler(rule_engine=engine, k=3)
    regions = extract_all_regions([parsed], engine)

    all_shingles: set[str] = set()
    for region in regions:
        engine.reset_identifiers()
        engine.precompute_queries(region.node, language, parsed.source)
        shingled = shingler.shingle_region(region, parsed.source)
        all_shingles.update(s.content for s in shingled.shingles.shingles)
    return all_shingles


def test_embedded_yaml_shingles_overlap_with_standalone():
    """A YAML block embedded in markdown shares shingles with the same
    content in a standalone .yaml file, so similarity detection links them."""
    rules = [r for r, _ in build_loose_rules()]

    md_engine = RuleEngine(rules)
    md_shingler = ASTShingler(rule_engine=md_engine, k=3)
    md_parsed = parse_file(fixture_guide)
    md_regions = extract_all_regions([md_parsed], md_engine)
    embedded = next(r for r in md_regions if r.injected_language == "yaml")
    md_shingles = _shingle_injected_region(embedded, md_engine, md_shingler)

    standalone_shingles = _shingle_standalone_file(fixture_config, "yaml", rules)

    assert md_shingles, "No shingles produced from markdown yaml block"
    assert standalone_shingles, "No shingles produced from standalone yaml file"
    assert md_shingles & standalone_shingles, (
        "Markdown yaml block and standalone yaml file share no shingles"
    )
