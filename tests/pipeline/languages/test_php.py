import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from treepeat.cli.cli import main
from treepeat.config import LSHSettings, PipelineSettings, RulesSettings, get_settings, set_settings
from treepeat.pipeline.languages.base import rules_anonymize_region_name
from treepeat.pipeline.parse import detect_language, parse_file, parse_path
from treepeat.pipeline.pipeline import run_pipeline
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules_factory import build_rule_engine

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "php" / "comprehensive.php"


@pytest.fixture(autouse=True)
def restore_settings():
    previous = get_settings()
    yield
    set_settings(previous)


@pytest.mark.parametrize("extension", ["php", "phtml", "PHP"])
def test_php_extension_detection(extension):
    assert detect_language(Path(f"example.{extension}")) == "php"


@pytest.mark.parametrize("ruleset", ["none", "default", "loose"])
def test_php_regions(ruleset):
    parsed = parse_file(FIXTURE)
    assert not parsed.root_node.has_error
    engine = build_rule_engine(PipelineSettings(rules=RulesSettings(ruleset=ruleset)))
    regions = extract_all_regions([parsed], engine)
    assert {(r.region.region_type, r.region.region_name) for r in regions} == {
        ("function", "total"),
        ("interface_declaration", "Formatter"),
        ("method", "format"),
        ("trait_declaration", "HasLabel"),
        ("method", "label"),
        ("enum_declaration", "Status"),
        ("class", "Report"),
        ("method", "__construct"),
        ("anonymous_function", "anonymous"),
        ("arrow_function", "anonymous"),
        ("anonymous_class", "anonymous"),
        ("method", "run"),
    }
    total = next(r.region for r in regions if r.region.region_name == "total")
    assert total.start_line == 12
    assert total.end_line == 21


def test_php_directory_discovery_and_mixed_html(tmp_path):
    set_settings(PipelineSettings())
    source = "<h1>Example</h1>\n<?php\nfunction render() { return 1; }\n?>\n<p>End</p>"
    for filename in ["index.php", "view.phtml", "notes.txt"]:
        (tmp_path / filename).write_text(source)
    parsed = parse_path(tmp_path).parsed_files
    assert {p.path.name for p in parsed} == {"index.php", "view.phtml"}
    engine = build_rule_engine(PipelineSettings())
    for file in parsed:
        assert file.language == "php"
        assert not file.root_node.has_error
        regions = extract_all_regions([file], engine)
        assert len(regions) == 1
        assert regions[0].region.region_name == "render"
        assert regions[0].region.start_line == 3


@pytest.mark.parametrize("region_type", ["function", "method", "class"])
@pytest.mark.parametrize("ruleset", ["none", "default", "loose"])
def test_php_name_normalization_is_recognized(region_type, ruleset):
    engine = build_rule_engine(PipelineSettings(rules=RulesSettings(ruleset=ruleset)))
    assert rules_anonymize_region_name(engine.rules, "php", region_type) == (ruleset != "none")


def _function(name="total", variable="value", number="2", text="hello"):
    return f"""<?php
function {name}(int ${variable}): string {{
    $result = ${variable} * {number};
    if ($result > 0) {{
        return '{text}' . $result;
    }}
    return '';
}}
"""


@pytest.mark.parametrize(
    "ruleset, renamed, changed_values, expected_match",
    [
        ("none", False, False, True),
        ("none", True, False, False),
        ("default", True, False, True),
        ("default", False, True, False),
        ("loose", True, True, True),
    ],
)
def test_php_duplicate_detection(tmp_path, ruleset, renamed, changed_values, expected_match):
    (tmp_path / "one.php").write_text(_function())
    (tmp_path / "two.phtml").write_text(
        _function(
            name="calculate" if renamed else "total",
            variable="amount" if changed_values else "value",
            number="9" if changed_values else "2",
            text="goodbye" if changed_values else "hello",
        )
    )
    set_settings(
        PipelineSettings(
            rules=RulesSettings(ruleset=ruleset),
            lsh=LSHSettings(similarity_percent=1.0),
        )
    )
    result = run_pipeline(tmp_path)
    assert result.total_files == 2
    assert bool(result.similar_groups) == expected_match
    if expected_match:
        assert result.similar_groups[0].similarity == 1.0
        assert {r.path.name for r in result.similar_groups[0].regions} == {"one.php", "two.phtml"}


@pytest.mark.parametrize(
    "region_type, names",
    [
        ("class", {"First", "Second"}),
        ("method", {"first", "second"}),
    ],
)
def test_php_renamed_methods_and_classes_survive_verification(tmp_path, region_type, names):
    source = """<?php
class First {
    public function first(int $value): int {
        $result = $value * 2;
        if ($result > 0) {
            return $result;
        }
        return 0;
    }
}
"""
    (tmp_path / "one.php").write_text(source)
    (tmp_path / "two.php").write_text(source.replace("First", "Second").replace("first", "second"))
    # Isolate each kind: the existing LSH stage can group nested class/method
    # candidates together and average their score below the exact-match threshold.
    set_settings(
        PipelineSettings(
            rules=RulesSettings(region_filters={"php": {region_type}}),
            lsh=LSHSettings(similarity_percent=1.0),
        )
    )
    result = run_pipeline(tmp_path)
    groups = [{r.region_name for r in group.regions} for group in result.similar_groups]
    assert names in groups


def test_php_cli_sarif(tmp_path):
    (tmp_path / "one.php").write_text(_function())
    (tmp_path / "two.php").write_text(_function(name="calculate"))
    result = CliRunner().invoke(main, ["detect", str(tmp_path), "--format", "sarif"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["version"] == "2.1.0"
    assert len(report["runs"][0]["results"]) == 1


def test_php_cli_list_ruleset():
    result = CliRunner().invoke(main, ["list-ruleset", "loose", "--language", "php"])
    assert result.exit_code == 0
    assert "Anonymize identifiers" in result.output
    assert "Extract function regions for php" in result.output
