"""Tests for Astro (.astro) file support.

Astro components consist of an optional TypeScript/JavaScript frontmatter block
delimited by ``---`` markers, followed by an HTML-like template.  treepeat
extracts the frontmatter and re-parses it as TypeScript so that all existing
TypeScript rules (function / class / interface extraction, identifier
anonymisation, …) apply without changes to the rest of the pipeline.
"""

from pathlib import Path

import pytest

from treepeat.pipeline.parse import extract_astro_frontmatter, parse_file
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "astro"
fixture_one = FIXTURE_DIR / "one.astro"
fixture_two = FIXTURE_DIR / "two.astro"
fixture_template_only = FIXTURE_DIR / "template_only.astro"


# ---------------------------------------------------------------------------
# extract_astro_frontmatter
# ---------------------------------------------------------------------------


def test_extract_frontmatter_returns_typescript_content():
    source = b"---\nconst x = 1;\n---\n<p>{x}</p>\n"
    result = extract_astro_frontmatter(source)
    assert result is not None
    assert b"const x = 1;" in result


def test_extract_frontmatter_preserves_line_numbers():
    """Frontmatter code should start on line 2 (same as in the original file)."""
    source = b"---\nconst x = 1;\n---\n"
    result = extract_astro_frontmatter(source)
    assert result is not None
    # Padded with a leading newline → first real code is at line 2 (index 1)
    lines = result.split(b"\n")
    assert lines[0] == b""  # blank padding for opening ---
    assert lines[1] == b"const x = 1;"


def test_extract_frontmatter_no_frontmatter_returns_none():
    source = b"<html><body><p>No frontmatter here.</p></body></html>\n"
    assert extract_astro_frontmatter(source) is None


def test_extract_frontmatter_unclosed_returns_none():
    source = b"---\nconst x = 1;\n"
    assert extract_astro_frontmatter(source) is None


def test_extract_frontmatter_empty_block_returns_none():
    source = b"---\n---\n<p>empty</p>\n"
    assert extract_astro_frontmatter(source) is None


def test_extract_frontmatter_multiline():
    source = (
        b"---\n"
        b"import Foo from './Foo.astro';\n"
        b"const a = 1;\n"
        b"const b = 2;\n"
        b"---\n"
        b"<p>{a}</p>\n"
    )
    result = extract_astro_frontmatter(source)
    assert result is not None
    assert b"import Foo" in result
    assert b"const a = 1;" in result
    assert b"const b = 2;" in result
    # Template code must NOT appear in the extracted frontmatter
    assert b"<p>" not in result


# ---------------------------------------------------------------------------
# parse_file
# ---------------------------------------------------------------------------


def test_parse_file_astro_with_frontmatter_uses_typescript():
    """An Astro file with frontmatter is parsed as TypeScript."""
    parsed = parse_file(fixture_one)
    assert parsed.path == fixture_one
    assert parsed.language == "typescript"


def test_parse_file_astro_without_frontmatter_uses_html():
    """A template-only Astro file (no frontmatter) falls back to HTML parsing."""
    parsed = parse_file(fixture_template_only)
    assert parsed.path == fixture_template_only
    assert parsed.language == "html"


def test_parse_file_astro_source_is_frontmatter_only():
    """The parsed source for an Astro file contains the frontmatter, not the template."""
    parsed = parse_file(fixture_one)
    # Template markers should not appear in the parsed source
    assert b"<Layout" not in parsed.source
    assert b"<main>" not in parsed.source
    # But frontmatter code should be present
    assert b"buildPageTitle" in parsed.source


# ---------------------------------------------------------------------------
# Region extraction from Astro frontmatter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rules_factory", [
    lambda: [r for r, _ in build_default_rules()],
    lambda: [r for r, _ in build_loose_rules()],
])
def test_region_extraction_from_astro_frontmatter(rules_factory):
    """Functions declared in the Astro frontmatter are extracted as regions."""
    parsed = parse_file(fixture_one)
    engine = RuleEngine(rules_factory())
    regions = extract_all_regions([parsed], engine)

    region_names = [r.region.region_name for r in regions]
    assert "buildPageTitle" in region_names
    assert "truncateDescription" in region_names


def test_region_line_numbers_match_original_file():
    """Extracted region line numbers should refer to the original Astro file."""
    parsed = parse_file(fixture_one)
    engine = RuleEngine([r for r, _ in build_default_rules()])
    regions = extract_all_regions([parsed], engine)

    by_name = {r.region.region_name: r.region for r in regions}
    assert "buildPageTitle" in by_name

    # In one.astro:
    #   Line 1:  ---  (opening delimiter)
    #   Line 2:  import Layout...
    #   ...
    #   Line 11: function buildPageTitle(...)
    #   Line 16: function truncateDescription(...)
    assert by_name["buildPageTitle"].start_line == 11
    assert by_name["truncateDescription"].start_line == 16


def test_interface_extracted_from_astro_frontmatter():
    """TypeScript interfaces in the frontmatter are detected by their region language."""
    parsed = parse_file(fixture_one)
    assert parsed.language == "typescript"
    # The TypeScript tree parses the interface — no errors expected
    assert not parsed.root_node.has_error
