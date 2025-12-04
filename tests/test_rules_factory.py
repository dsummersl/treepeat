from treepeat.config import PipelineSettings
from treepeat.pipeline.rules_factory import build_rule_engine


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
