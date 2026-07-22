"""Tests for name-anonymization detection used by signature verification."""

from treepeat.pipeline.languages import LANGUAGE_CONFIGS
from treepeat.pipeline.languages.base import rules_anonymize_region_name
from treepeat.pipeline.rules.models import Rule, RuleAction


def _default_rules(language: str):
    return LANGUAGE_CONFIGS[language].get_default_rules()


def test_javascript_default_rules_anonymize_function_and_class_names():
    rules = _default_rules("javascript")
    assert rules_anonymize_region_name(rules, "javascript", "function")
    assert rules_anonymize_region_name(rules, "javascript", "class")


def test_python_default_rules_anonymize_names_despite_different_capture_target():
    # Python captures the name as @func / @class rather than @name; detection
    # must not depend on the capture name.
    rules = _default_rules("python")
    assert rules_anonymize_region_name(rules, "python", "function")
    assert rules_anonymize_region_name(rules, "python", "function_definition")
    assert rules_anonymize_region_name(rules, "python", "class")


def test_empty_ruleset_anonymizes_nothing():
    # The 'none' ruleset strips anonymization rules, so name differences must
    # remain meaningful (and therefore penalized) during verification.
    assert not rules_anonymize_region_name([], "javascript", "function")
    assert not rules_anonymize_region_name([], "python", "class")


def test_rules_only_apply_to_their_language():
    js_rules = _default_rules("javascript")
    # JS rules declare languages=[javascript, typescript, tsx, jsx]; an
    # unrelated language must not match them.
    assert not rules_anonymize_region_name(js_rules, "python", "function")


def test_non_code_region_type_is_never_anonymized():
    rules = _default_rules("javascript")
    assert not rules_anonymize_region_name(rules, "heading", "heading")


def test_rule_targeting_non_name_child_of_declaration_does_not_count():
    # A rule scoped to a function_declaration but replacing a string literal
    # (not the name identifier) must not be mistaken for name anonymization.
    rule = Rule(
        name="Anonymize string literals inside functions",
        languages=["javascript"],
        query="(function_declaration body: (statement_block (string) @lit))",
        target="lit",
        action=RuleAction.REPLACE_VALUE,
        params={"value": "<LIT>"},
    )
    assert not rules_anonymize_region_name([rule], "javascript", "function")


def test_identifier_mentioned_only_in_predicate_string_does_not_count():
    # "identifier" appearing inside a #match? predicate literal is not a real
    # identifier node capture, so this rule must not count as anonymizing.
    rule = Rule(
        name="Replace calls named like identifier",
        languages=["javascript"],
        query='(function_declaration (call_expression) @c (#match? @c "identifier"))',
        target="c",
        action=RuleAction.REPLACE_VALUE,
        params={"value": "<CALL>"},
    )
    assert not rules_anonymize_region_name([rule], "javascript", "function")


def test_property_identifier_name_capture_counts():
    # Method names are captured as property_identifier, not identifier.
    rule = Rule(
        name="Anonymize method names",
        languages=["javascript"],
        query="(method_definition (property_identifier) @name)",
        target="name",
        action=RuleAction.REPLACE_VALUE,
        params={"value": "FUNC"},
    )
    assert rules_anonymize_region_name([rule], "javascript", "method")


def test_non_replace_value_action_does_not_count():
    rule = Rule(
        name="Remove function declarations",
        languages=["javascript"],
        query="(function_declaration (identifier) @name)",
        target="name",
        action=RuleAction.REMOVE,
    )
    assert not rules_anonymize_region_name([rule], "javascript", "function")
