"""Parser for YAML-based tree-sitter query rules."""

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .models import Rule, RuleAction


class RuleParseError(Exception):
    """Raised when a rule cannot be parsed."""

    pass


def _parse_action(action_str: str) -> RuleAction:
    """Parse action string into RuleAction enum."""
    try:
        return RuleAction(action_str)
    except ValueError:
        valid_actions = [action.value for action in RuleAction]
        raise RuleParseError(
            f"Invalid action '{action_str}'. Valid actions: {', '.join(valid_actions)}"
        )


def _validate_yaml_rule_fields(rule_dict: dict[str, Any]) -> None:
    """Validate required fields in a YAML rule."""
    required_fields = ["name", "languages", "query", "action"]
    for field in required_fields:
        if field not in rule_dict:
            name_info = f" '{rule_dict['name']}'" if "name" in rule_dict else ""
            raise RuleParseError(f"Rule{name_info} missing required '{field}' field")


def _parse_yaml_rule(rule_dict: dict[str, Any], ruleset_name: str) -> Rule:
    """Parse a single rule from YAML dictionary."""
    _validate_yaml_rule_fields(rule_dict)

    name = rule_dict["name"]
    languages = rule_dict["languages"]
    if isinstance(languages, str):
        languages = [languages]

    return Rule(
        name=name,
        languages=languages,
        query=rule_dict["query"],
        action=_parse_action(rule_dict["action"]),
        target=rule_dict.get("target"),
        params=rule_dict.get("params", {}),
    )


def _get_extended_rules(
    rulesets: dict[str, Any],
    ruleset: dict[str, Any],
    resolved: set[str],
) -> list[Rule]:
    """Get rules from extended rulesets."""
    if "extends" not in ruleset:
        return []
    extended_name = ruleset["extends"]
    return _resolve_extends(rulesets, extended_name, resolved)


def _parse_ruleset_rules(ruleset: dict[str, Any], ruleset_name: str) -> list[Rule]:
    """Parse rules from a ruleset."""
    if "rules" not in ruleset:
        return []
    return [_parse_yaml_rule(rule_dict, ruleset_name) for rule_dict in ruleset["rules"]]


def _resolve_extends(
    rulesets: dict[str, Any],
    ruleset_name: str,
    resolved: set[str],
) -> list[Rule]:
    """Recursively resolve ruleset inheritance."""
    if ruleset_name in resolved:
        raise RuleParseError(f"Circular dependency detected in ruleset '{ruleset_name}'")

    if ruleset_name not in rulesets:
        raise RuleParseError(f"Ruleset '{ruleset_name}' not found (referenced by 'extends')")

    resolved.add(ruleset_name)
    ruleset = rulesets[ruleset_name]

    # Combine rules from extended rulesets and this ruleset
    extended_rules = _get_extended_rules(rulesets, ruleset, resolved)
    own_rules = _parse_ruleset_rules(ruleset, ruleset_name)

    return extended_rules + own_rules


def _load_yaml_file(file_path: str) -> Any:
    """Load and validate YAML file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Rules file not found: {file_path}")

    with open(path, "r") as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise RuleParseError(f"Invalid YAML: {e}")


def _validate_rulesets_structure(data: Any, ruleset_name: str) -> dict[str, Any]:
    """Validate and extract rulesets from YAML data."""
    if not isinstance(data, dict):
        raise RuleParseError("YAML file must contain a dictionary")

    if "rulesets" not in data:
        raise RuleParseError("YAML file missing 'rulesets' key")

    rulesets = data["rulesets"]
    if not isinstance(rulesets, dict):
        raise RuleParseError("'rulesets' must be a dictionary")

    if ruleset_name not in rulesets:
        available = ", ".join(rulesets.keys())
        raise RuleParseError(
            f"Ruleset '{ruleset_name}' not found. Available rulesets: {available}"
        )

    return rulesets


def parse_yaml_rules_file(file_path: str, ruleset_name: str = "default") -> list[Rule]:
    """
    Parse rules from a YAML file with ruleset support.

    Args:
        file_path: Path to the YAML rules file
        ruleset_name: Name of the ruleset to load (default: "default")

    Returns:
        List of Rule objects from the specified ruleset

    Raises:
        RuleParseError: If the YAML is invalid or rules are malformed
        FileNotFoundError: If the file doesn't exist
    """
    data = _load_yaml_file(file_path)
    rulesets = _validate_rulesets_structure(data, ruleset_name)

    resolved: set[str] = set()
    return _resolve_extends(rulesets, ruleset_name, resolved)
