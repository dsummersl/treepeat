from pathlib import Path

import pytest
from tree_sitter_language_pack import get_parser

from tests.conftest import parse_fixture
from treepeat.pipeline.languages import LANGUAGE_CONFIGS
from treepeat.pipeline.languages.markdown import _resolve_code_block_language
from treepeat.pipeline.languages.mermaid import MermaidConfig
from treepeat.pipeline.parse import detect_language, parse_file
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules
from treepeat.pipeline.shingle import ASTShingler

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures"
fixture_flow = FIXTURE_DIR / "mermaid" / "flow.mmd"
fixture_guide = FIXTURE_DIR / "markdown" / "guide.md"


def test_mermaid_registered_in_configs():
    assert "mermaid" in LANGUAGE_CONFIGS
    assert isinstance(LANGUAGE_CONFIGS["mermaid"], MermaidConfig)


@pytest.mark.parametrize("ext", [".mmd", ".mermaid"])
def test_mermaid_extensions_detected(ext):
    assert detect_language(Path(f"foo{ext}")) == "mermaid"


def test_parse_mermaid_no_errors():
    parsed = parse_file(fixture_flow)
    assert parsed.language == "mermaid"
    assert not parsed.root_node.has_error


@pytest.mark.parametrize(
    "rules",
    [
        [rule for rule, _ in build_default_rules()],
        [rule for rule, _ in build_loose_rules()],
    ],
)
def test_mermaid_regions_extracted(rules):
    parsed = parse_fixture(fixture_flow, "mermaid")
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine)
    region_types = {r.region.region_type for r in regions}
    assert "diagram" in region_types
    assert "flow_stmt_subgraph" in region_types


@pytest.mark.parametrize(
    "diagram",
    [
        b"sequenceDiagram\n    Alice->>John: Hello John\n    John-->>Alice: Hi\n",
        b"classDiagram\n    Animal <|-- Duck\n",
        b"stateDiagram-v2\n  [*] --> Still\n",
        b"erDiagram\n  CUSTOMER ||--o{ ORDER : places\n",
        b'pie\n  "Dogs" : 386\n',
    ],
)
def test_other_diagram_types_extracted(tmp_path, diagram):
    path = tmp_path / "d.mmd"
    path.write_bytes(diagram)
    parsed = parse_file(path)
    assert not parsed.root_node.has_error
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)
    assert any(r.region.region_type == "diagram" for r in regions)


def test_markdown_mermaid_block_injected():
    parsed = parse_file(fixture_guide)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    injected = [r for r in regions if r.injected_language == "mermaid"]
    assert injected, "Expected the ```mermaid block in guide.md to be injected as mermaid"
    region = injected[0]
    assert region.injected_tree is not None
    assert not region.injected_tree.root_node.has_error
    assert region.region.language == "markdown"


def test_mmd_alias_resolves_to_mermaid():
    source = b"```mmd\nflowchart LR\n  A --> B\n```\n"
    tree = get_parser("markdown").parse(source)

    fenced_node = None
    for child in [tree.root_node, *tree.root_node.children]:
        fenced_node = next((n for n in child.children if n.type == "fenced_code_block"), None)
        if fenced_node is not None:
            break
    assert fenced_node is not None, "Could not find fenced_code_block node"
    assert _resolve_code_block_language(fenced_node, source) == "mermaid"


def _shingle_injected_region(region, engine, shingler):
    engine.reset_identifiers()
    engine.precompute_queries(region.injected_tree.root_node, region.injected_language, region.injected_source)
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


def test_loose_rules_anonymize_labels():
    rules = [r for r, _ in build_loose_rules()]
    shingles = _shingle_standalone_file(fixture_flow, "mermaid", rules)
    joined = " ".join(shingles)
    assert "Receive request" not in joined
    assert "Authenticated" not in joined


def test_embedded_mermaid_shingles_overlap_with_standalone():
    rules = [r for r, _ in build_loose_rules()]

    md_engine = RuleEngine(rules)
    md_shingler = ASTShingler(rule_engine=md_engine, k=3)
    md_parsed = parse_file(fixture_guide)
    md_regions = extract_all_regions([md_parsed], md_engine)
    embedded = next(r for r in md_regions if r.injected_language == "mermaid")
    md_shingles = _shingle_injected_region(embedded, md_engine, md_shingler)

    standalone_shingles = _shingle_standalone_file(fixture_flow, "mermaid", rules)

    assert md_shingles and standalone_shingles
    assert md_shingles & standalone_shingles, "Markdown mermaid block and standalone file share no shingles"
