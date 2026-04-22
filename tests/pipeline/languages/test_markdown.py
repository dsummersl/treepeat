"""Tests for Markdown language configuration, code block injection, and cross-file similarity."""

from pathlib import Path

import pytest

from tests.conftest import parse_fixture
from treepeat.pipeline.languages.markdown import MarkdownConfig
from treepeat.pipeline.parse import parse_file
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules
from treepeat.pipeline.shingle import ASTShingler

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures"
MARKDOWN_DIR = FIXTURE_DIR / "markdown"

fixture_plain = MARKDOWN_DIR / "one.md"
fixture_headings = MARKDOWN_DIR / "two.md"
fixture_guide = MARKDOWN_DIR / "guide.md"

fixture_py_stats = FIXTURE_DIR / "python" / "stats.py"
fixture_js_date = FIXTURE_DIR / "javascript" / "date_utils.js"
fixture_bash_req = FIXTURE_DIR / "bash" / "requirements.sh"


# ---------------------------------------------------------------------------
# MarkdownConfig interface
# ---------------------------------------------------------------------------


def test_region_extraction_rules_exist():
    rules = MarkdownConfig().get_region_extraction_rules()
    labels = [r.label for r in rules]
    assert "heading" in labels
    assert "code_block" in labels


def test_fenced_code_block_rule_has_injection():
    """The code_block rule must declare a dynamic target_language and content_query."""
    rules = MarkdownConfig().get_region_extraction_rules()
    code_block_rule = next(r for r in rules if r.label == "code_block")
    assert callable(code_block_rule.target_language)
    assert code_block_rule.content_query is not None


# ---------------------------------------------------------------------------
# guide.md parsing
# ---------------------------------------------------------------------------


def test_parse_guide_md_no_errors():
    parsed = parse_file(fixture_guide)
    assert parsed.language == "markdown"
    assert not parsed.root_node.has_error


def test_guide_md_source_contains_all_embedded_functions():
    parsed = parse_file(fixture_guide)
    assert b"calculate_stats" in parsed.source
    assert b"formatDate" in parsed.source
    assert b"check_requirements" in parsed.source


# ---------------------------------------------------------------------------
# Code block region extraction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("embedded_lang", ["python", "javascript", "bash"])
def test_code_block_extracted_for_language(embedded_lang):
    """Each fenced block with a known language tag is extracted with an injected tree."""
    parsed = parse_file(fixture_guide)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    injected = [r for r in regions if r.injected_language == embedded_lang]
    assert injected, f"No injected region found for language {embedded_lang!r}"


@pytest.mark.parametrize("embedded_lang", ["python", "javascript", "bash"])
def test_injected_tree_and_source_set(embedded_lang):
    """Each embedded code block has injected_tree and injected_source populated."""
    parsed = parse_file(fixture_guide)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    region = next(r for r in regions if r.injected_language == embedded_lang)
    assert region.injected_tree is not None
    assert region.injected_source is not None


@pytest.mark.parametrize("embedded_lang", ["python", "javascript", "bash"])
def test_region_language_is_markdown(embedded_lang):
    """Region metadata preserves the file language (markdown), not the injection language."""
    parsed = parse_file(fixture_guide)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    region = next(r for r in regions if r.injected_language == embedded_lang)
    assert region.region.language == "markdown"


def test_unlabelled_code_block_not_injected():
    """A fenced block with no language tag is extracted as a plain code_block (no injection)."""
    parsed = parse_file(fixture_guide)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    uninjected = [
        r for r in regions
        if r.region.region_type == "code_block" and r.injected_tree is None
    ]
    assert uninjected, "Expected at least one uninjected code_block region for the plain block"


# ---------------------------------------------------------------------------
# Cross-file shingle similarity — the core correctness invariant
# ---------------------------------------------------------------------------


def _shingle_injected_region(region, engine: RuleEngine, shingler: ASTShingler) -> set[str]:
    """Shingle a markdown-injected code block; return the set of shingle content strings."""
    engine.reset_identifiers()
    engine.precompute_queries(
        region.injected_tree.root_node,
        region.injected_language,
        region.injected_source,
    )
    shingled = shingler.shingle_region(region, region.injected_source)
    return {s.content for s in shingled.shingles.shingles}


def _shingle_standalone_file(path: Path, language: str, rules: list) -> set[str]:
    """Parse a standalone source file, shingle all its extracted regions, and return combined shingles."""
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


@pytest.mark.parametrize("embedded_lang,standalone_path,standalone_lang", [
    ("python", fixture_py_stats, "python"),
    ("javascript", fixture_js_date, "javascript"),
    ("bash", fixture_bash_req, "bash"),
])
def test_embedded_shingles_overlap_with_standalone(embedded_lang, standalone_path, standalone_lang):
    """A function embedded in a markdown code block produces shingles that overlap
    with the same function in a standalone source file.

    This is the key property that allows treepeat to detect that documentation
    examples are similar to their implementation files.
    """
    rules = [r for r, _ in build_loose_rules()]

    # --- Markdown (injection) path ---
    md_engine = RuleEngine(rules)
    md_shingler = ASTShingler(rule_engine=md_engine, k=3)
    md_parsed = parse_file(fixture_guide)
    md_regions = extract_all_regions([md_parsed], md_engine)
    embedded_region = next(r for r in md_regions if r.injected_language == embedded_lang)
    md_shingles = _shingle_injected_region(embedded_region, md_engine, md_shingler)

    # --- Standalone file path ---
    standalone_shingles = _shingle_standalone_file(standalone_path, standalone_lang, rules)

    assert md_shingles, f"No shingles produced from markdown {embedded_lang!r} block"
    assert standalone_shingles, f"No shingles produced from standalone {standalone_lang!r} file"
    assert md_shingles & standalone_shingles, (
        f"Markdown {embedded_lang!r} block and standalone {standalone_lang!r} file "
        f"share no common shingles — similarity detection would miss this pair"
    )


# ---------------------------------------------------------------------------
# Unknown language guard
# ---------------------------------------------------------------------------


def test_unknown_language_skips_injection_and_warns(caplog):
    """A fenced code block with an unsupported language tag produces no injection
    and emits a warning naming the unknown language.
    """
    import logging

    from tree_sitter_language_pack import get_parser

    from treepeat.pipeline.languages.markdown import _resolve_code_block_language

    source = b"```ruby\nputs 'hello'\n```\n"
    parser = get_parser("markdown")
    tree = parser.parse(source)

    fenced_node = next(
        (n for n in tree.root_node.children if n.type == "fenced_code_block"),
        None,
    )
    # tree-sitter-markdown may nest the block inside a section; walk one level deeper if needed
    if fenced_node is None:
        for child in tree.root_node.children:
            fenced_node = next(
                (n for n in child.children if n.type == "fenced_code_block"), None
            )
            if fenced_node is not None:
                break

    assert fenced_node is not None, "Could not find fenced_code_block node in parsed tree"

    with caplog.at_level(logging.WARNING, logger="treepeat.pipeline.languages.markdown"):
        result = _resolve_code_block_language(fenced_node, source)

    assert result == "", f"Expected '' for unsupported language 'ruby', got {result!r}"
    assert any("ruby" in msg for msg in caplog.messages), (
        "Expected a warning mentioning 'ruby' for the unsupported language"
    )
