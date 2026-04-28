from treepeat.config import PipelineSettings
from treepeat.pipeline.rules_factory import build_rule_engine, get_ruleset_with_descriptions


def _javascript_rule_names(ruleset: str) -> list[str]:
    return [
        rule.name
        for rule, _ in get_ruleset_with_descriptions(ruleset)
        if rule.matches_language("javascript")
    ]


def test_additional_regions_extend_default_rules() -> None:
    settings = PipelineSettings()
    settings.rules.additional_regions = {"python": {"decorated_definition"}}

    engine = build_rule_engine(settings)
    region_rules = engine.get_region_extraction_rules("python")

    region_types = {region_type for _, region_type in region_rules}

    assert {"function_definition", "class_definition"}.issubset(region_types)
    assert "decorated_definition" in region_types


def test_excluded_regions_remove_default_rules() -> None:
    settings = PipelineSettings()
    settings.rules.excluded_regions = {"python": {"function_definition"}}

    engine = build_rule_engine(settings)
    region_rules = engine.get_region_extraction_rules("python")

    region_types = {region_type for _, region_type in region_rules}

    assert "function_definition" not in region_types
    assert "class_definition" in region_types


def test_excluded_regions_with_additional_regions() -> None:
    settings = PipelineSettings()
    settings.rules.additional_regions = {"python": {"decorated_definition"}}
    settings.rules.excluded_regions = {"python": {"function_definition"}}

    engine = build_rule_engine(settings)
    region_rules = engine.get_region_extraction_rules("python")

    region_types = {region_type for _, region_type in region_rules}

    assert "function_definition" not in region_types
    assert "class_definition" in region_types
    assert "decorated_definition" in region_types


def test_javascript_identifier_anonymization_is_only_in_loose_ruleset() -> None:
    default_rule_names = _javascript_rule_names("default")
    loose_rule_names = _javascript_rule_names("loose")

    assert "Anonymize identifiers" not in default_rule_names
    assert "Anonymize identifiers" in loose_rule_names
