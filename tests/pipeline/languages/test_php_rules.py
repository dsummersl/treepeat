from pathlib import Path

import pytest

from treepeat.models.similarity import Region
from treepeat.pipeline.languages.php import PHPConfig
from treepeat.pipeline.parse import parse_source_code
from treepeat.pipeline.region_extraction import ExtractedRegion
from treepeat.pipeline.rules.engine import RuleEngine
from treepeat.pipeline.shingle import ASTShingler


def _shingles(source, loose=False):
    source_bytes = ("<?php\n" + source).encode()
    parsed = parse_source_code(source_bytes, "php", Path("test.php"))
    assert not parsed.root_node.has_error
    config = PHPConfig()
    engine = RuleEngine(config.get_loose_rules() if loose else config.get_default_rules())
    region = Region(
        path=parsed.path,
        language="php",
        region_type="test",
        region_name="test",
        start_line=1,
        end_line=source_bytes.count(b"\n") + 1,
    )
    engine.precompute_queries(parsed.root_node, "php", source_bytes)
    shingler = ASTShingler(rule_engine=engine, k=2)
    return shingler.shingle_region(
        ExtractedRegion(region=region, node=parsed.root_node),
        source_bytes,
    ).shingles.get_contents()


def test_php_default_rules_ignore_comments_and_namespace_imports():
    source = r"""
use Foo\Bar;
use Foo\{Bar, Baz};
use function Foo\helper;
use const Foo\VALUE;
// line
# hash
/** documentation */
/* block */
function keep() { require 'bootstrap.php'; return 42; }
trait KeepTrait { use SharedTrait; }
$closure = function () use ($captured) { return $captured; };
"""
    tokens = " ".join(_shingles(source))
    assert "namespace_use_declaration" not in tokens
    assert "comment" not in tokens
    assert "require_expression" in tokens
    assert "use_declaration" in tokens
    assert "anonymous_function_use_clause" in tokens
    assert "captured" in tokens
    assert "42" in tokens


@pytest.mark.parametrize(
    "declaration",
    [
        "function Original() { return 1; }",
        "class Container { public function Original() { return 1; } }",
        "class Original {}",
        "interface Original {}",
        "trait Original {}",
        "enum Original { case Active; }",
    ],
)
@pytest.mark.parametrize("loose", [False, True])
def test_php_declaration_names_are_normalized(declaration, loose):
    assert _shingles(declaration, loose) == _shingles(declaration.replace("Original", "Renamed"), loose)


@pytest.mark.parametrize(
    "original, renamed",
    [
        ("$value + $value", "$amount + $amount"),
        ("$object->method($value)", "$other->call($input)"),
        ("Thing::VALUE", "Other::CONSTANT"),
        ("helper($value)", "calculate($amount)"),
    ],
)
def test_php_identifier_normalization_is_loose_only(original, renamed):
    first, second = f"return {original};", f"return {renamed};"
    assert _shingles(first) != _shingles(second)
    assert _shingles(first, loose=True) == _shingles(second, loose=True)


@pytest.mark.parametrize(
    "first, second",
    [
        ("1", "42"),
        ("1.5", "9.25"),
        ("true", "false"),
        ("null", "NULL"),
        ("'hello'", "'goodbye'"),
        ('"hello $value"', '"goodbye $value"'),
        ('"hello\\n"', '"goodbye\\t"'),
        ("<<<TEXT\nhello $value\nTEXT", "<<<TEXT\ngoodbye $value\nTEXT"),
        ("<<<'TEXT'\nhello\nTEXT", "<<<'TEXT'\ngoodbye\nTEXT"),
        ("<<<TEXT\nhello $value\nTEXT", "<<<OTHER\ngoodbye $value\nOTHER"),
        ("<<<'TEXT'\nhello\nTEXT", "<<<'OTHER'\ngoodbye\nOTHER"),
    ],
)
def test_php_literal_normalization_is_loose_only(first, second):
    original, changed = f"return {first};", f"return {second};"
    assert _shingles(original) != _shingles(changed)
    assert _shingles(original, loose=True) == _shingles(changed, loose=True)


def test_php_loose_rules_preserve_structure_and_identifier_reuse():
    assert _shingles("return $a + $a;", True) != _shingles("return $a + $b;", True)
    assert _shingles("return $a + 1;", True) != _shingles("return $a - 1;", True)
    assert _shingles('return "hello $a";', True) != _shingles('return "hello {$a->name}";', True)
