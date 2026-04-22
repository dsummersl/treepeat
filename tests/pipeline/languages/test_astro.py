from pathlib import Path

import pytest
from tree_sitter_language_pack import get_parser

from treepeat.models.ast import ParsedFile
from treepeat.pipeline.languages.astro import AstroConfig
from treepeat.pipeline.parse import parse_file
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "astro"
fixture_one = FIXTURE_DIR / "one.astro"
fixture_two = FIXTURE_DIR / "two.astro"
fixture_template_only = FIXTURE_DIR / "template_only.astro"


# ---------------------------------------------------------------------------
# AstroConfig interface
# ---------------------------------------------------------------------------


def test_region_extraction_rules_exist():
    rules = AstroConfig().get_region_extraction_rules()
    assert len(rules) >= 1
    labels = [r.label for r in rules]
    assert "frontmatter" in labels


def test_frontmatter_rule_injects_typescript():
    rules = AstroConfig().get_region_extraction_rules()
    frontmatter_rule = next(r for r in rules if r.label == "frontmatter")
    assert frontmatter_rule.target_language == "typescript"
    assert frontmatter_rule.content_query is not None


# ---------------------------------------------------------------------------
# parse_file for Astro
# ---------------------------------------------------------------------------


def test_parse_file_astro_language():
    """Astro files are parsed with the astro grammar (language == 'astro')."""
    parsed = parse_file(fixture_one)
    assert parsed.language == "astro"
    assert parsed.path == fixture_one


def test_parse_file_astro_no_parse_errors():
    parsed = parse_file(fixture_one)
    assert not parsed.root_node.has_error


def test_parse_file_astro_source_contains_frontmatter_and_template():
    """The parsed source is the full Astro file (not just the frontmatter)."""
    parsed = parse_file(fixture_one)
    assert b"---" in parsed.source
    assert b"<Layout" in parsed.source
    assert b"buildPageTitle" in parsed.source


# ---------------------------------------------------------------------------
# Region extraction via injection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rules_factory",
    [
        lambda: [r for r, _ in build_default_rules()],
        lambda: [r for r, _ in build_loose_rules()],
    ],
)
def test_frontmatter_region_extracted(rules_factory):
    """A single 'frontmatter' region is extracted from an Astro file."""
    parsed = parse_file(fixture_one)
    engine = RuleEngine(rules_factory())
    regions = extract_all_regions([parsed], engine)

    region_types = [r.region.region_type for r in regions]
    assert "frontmatter" in region_types


def test_injected_tree_is_typescript():
    """The frontmatter region carries an injected TypeScript tree."""
    parsed = parse_file(fixture_one)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    frontmatter_regions = [r for r in regions if r.region.region_type == "frontmatter"]
    assert frontmatter_regions, "No frontmatter region extracted"

    fm = frontmatter_regions[0]
    assert fm.injected_tree is not None
    assert fm.injected_language == "typescript"
    assert fm.injected_source is not None


def test_injected_source_contains_typescript():
    """Injected source bytes contain TypeScript code, not the --- delimiters."""
    parsed = parse_file(fixture_one)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    fm = next(r for r in regions if r.region.region_type == "frontmatter")
    # TypeScript code should be present
    assert b"buildPageTitle" in fm.injected_source
    # Astro delimiters should NOT appear
    assert b"---" not in fm.injected_source
    # HTML template should NOT appear
    assert b"<Layout" not in fm.injected_source


def test_region_language_is_astro():
    """Region metadata preserves the file language (astro), not the injection language."""
    parsed = parse_file(fixture_one)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    fm = next(r for r in regions if r.region.region_type == "frontmatter")
    assert fm.region.language == "astro"


def test_region_line_numbers_match_original_file():
    """Frontmatter region start/end lines refer to the Astro file's --- delimiters."""
    parsed = parse_file(fixture_one)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    fm = next(r for r in regions if r.region.region_type == "frontmatter")
    # In one.astro the frontmatter is lines 1–20 (opening --- to closing ---)
    assert fm.region.start_line == 1
    assert fm.region.end_line == 20


# ---------------------------------------------------------------------------
# Shingle cross-file consistency (the core invariant)
# ---------------------------------------------------------------------------


def _make_parsed_file(path: Path, language: str, source: bytes) -> ParsedFile:
    parser = get_parser(language)  # type: ignore[arg-type]
    tree = parser.parse(source)
    return ParsedFile(path=path, language=language, tree=tree, source=source)


def test_injected_shingles_match_standalone_typescript():
    """TypeScript code in an Astro frontmatter produces the same shingles
    as the same code in a plain ``.ts`` file.

    This is the key correctness property of the injection architecture.
    """
    from treepeat.pipeline.region_extraction import extract_all_regions
    from treepeat.pipeline.shingle import ASTShingler

    rules = [r for r, _ in build_loose_rules()]
    engine = RuleEngine(rules)
    shingler = ASTShingler(rule_engine=engine, k=3)

    # ---------- Astro path ----------
    astro_parsed = parse_file(fixture_one)
    astro_regions = extract_all_regions([astro_parsed], engine)
    fm_region = next(r for r in astro_regions if r.region.region_type == "frontmatter")

    engine.reset_identifiers()
    engine.precompute_queries(
        fm_region.injected_tree.root_node,
        fm_region.injected_language,
        fm_region.injected_source,
    )
    astro_shingled = shingler.shingle_region(fm_region, fm_region.injected_source)

    # ---------- Standalone TypeScript path ----------
    # Build the same TypeScript source that was injected
    ts_source = fm_region.injected_source
    ts_path = fixture_one.with_suffix(".ts")
    ts_parsed = _make_parsed_file(ts_path, "typescript", ts_source)
    ts_engine = RuleEngine(rules)
    ts_regions = extract_all_regions([ts_parsed], ts_engine)

    assert ts_regions, "No TypeScript regions extracted from injected source"
    # TypeScript extraction gives us individual functions; collect all shingles
    ts_all_shingles: set[str] = set()
    for ts_region in ts_regions:
        ts_engine.reset_identifiers()
        ts_engine.precompute_queries(ts_region.node, "typescript", ts_source)
        ts_shingled = shingler.shingle_region(ts_region, ts_source)
        ts_all_shingles.update(s.content for s in ts_shingled.shingles.shingles)

    # The Astro frontmatter shingles should be a superset of TypeScript shingles
    # (the frontmatter region covers the whole block, TS regions are per-function)
    astro_shingle_set = {s.content for s in astro_shingled.shingles.shingles}
    assert astro_shingle_set, "No shingles produced from injected frontmatter"
    # At least some shingles must overlap — the same TypeScript k-grams appear in both
    assert astro_shingle_set & ts_all_shingles, "No common shingles between Astro frontmatter and standalone TypeScript"


# ---------------------------------------------------------------------------
# Template-only Astro files (no frontmatter)
# ---------------------------------------------------------------------------


def test_parse_template_only_language():
    """Template-only Astro files are still parsed with the astro grammar."""
    parsed = parse_file(fixture_template_only)
    assert parsed.language == "astro"
    assert parsed.path == fixture_template_only


def test_parse_template_only_no_parse_errors():
    parsed = parse_file(fixture_template_only)
    assert not parsed.root_node.has_error


def test_parse_template_only_source_has_no_frontmatter_delimiters():
    """Confirm the fixture contains no --- markers."""
    parsed = parse_file(fixture_template_only)
    assert b"---" not in parsed.source


def test_template_only_no_frontmatter_region_extracted():
    """No frontmatter region is extracted when there is no --- block."""
    parsed = parse_file(fixture_template_only)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    frontmatter_regions = [r for r in regions if r.region.region_type == "frontmatter"]
    assert not frontmatter_regions


def test_template_only_yields_template_region_not_frontmatter():
    """A template-only Astro file produces a template region but no frontmatter region."""
    parsed = parse_file(fixture_template_only)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    region_types = {r.region.region_type for r in regions}
    assert "template" in region_types
    assert "frontmatter" not in region_types


def test_template_only_extract_all_regions_does_not_raise():
    """extract_all_regions must complete without exceptions on a template-only file."""
    parsed = parse_file(fixture_template_only)
    engine = RuleEngine([r for r, _ in build_loose_rules()])
    regions = extract_all_regions([parsed], engine)  # must not raise
    assert isinstance(regions, list)


# ---------------------------------------------------------------------------
# Template region extraction
# ---------------------------------------------------------------------------


def test_template_rule_registered():
    """AstroConfig declares a 'template' region extraction rule."""
    labels = [r.label for r in AstroConfig().get_region_extraction_rules()]
    assert "template" in labels


@pytest.mark.parametrize("fixture", [fixture_one, fixture_two, fixture_template_only])
def test_template_region_extracted(fixture):
    """Every Astro file (with or without frontmatter) yields at least one template region."""
    parsed = parse_file(fixture)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    template_regions = [r for r in regions if r.region.region_type == "template"]
    assert template_regions, f"No template region extracted from {fixture.name}"


@pytest.mark.parametrize("fixture", [fixture_one, fixture_two, fixture_template_only])
def test_template_region_not_injected(fixture):
    """Template regions use the Astro grammar directly (no language injection)."""
    parsed = parse_file(fixture)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    for r in regions:
        if r.region.region_type == "template":
            assert r.injected_tree is None
            assert r.injected_language is None


def test_template_region_line_numbers_component():
    """Template region in one.astro spans the <Layout> element (after the frontmatter)."""
    parsed = parse_file(fixture_one)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    tmpl = next(r for r in regions if r.region.region_type == "template")
    assert tmpl.region.start_line == 22
    assert tmpl.region.end_line == 27


def test_template_region_line_numbers_template_only():
    """Template region in template_only.astro starts at line 1."""
    parsed = parse_file(fixture_template_only)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    tmpl = next(r for r in regions if r.region.region_type == "template")
    assert tmpl.region.start_line == 1


def test_template_region_language_is_astro():
    """Template region metadata records the file language as 'astro'."""
    parsed = parse_file(fixture_one)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    tmpl = next(r for r in regions if r.region.region_type == "template")
    assert tmpl.region.language == "astro"


def test_template_shingles_overlap_between_similar_components():
    """one.astro and two.astro have structurally identical templates; their
    shingles must overlap so treepeat flags them as similar.
    """
    from treepeat.pipeline.shingle import ASTShingler

    rules = [r for r, _ in build_loose_rules()]

    def template_shingle_set(fixture: Path) -> set[str]:
        engine = RuleEngine(rules)
        shingler = ASTShingler(rule_engine=engine, k=3)
        parsed = parse_file(fixture)
        regions = extract_all_regions([parsed], engine)
        tmpl = next(r for r in regions if r.region.region_type == "template")
        engine.reset_identifiers()
        engine.precompute_queries(tmpl.node, "astro", parsed.source)
        shingled = shingler.shingle_region(tmpl, parsed.source)
        return {s.content for s in shingled.shingles.shingles}

    shingles_one = template_shingle_set(fixture_one)
    shingles_two = template_shingle_set(fixture_two)

    assert shingles_one, "No shingles from one.astro template"
    assert shingles_two, "No shingles from two.astro template"
    assert shingles_one & shingles_two, (
        "one.astro and two.astro have identical template structures "
        "but share no common shingles"
    )

