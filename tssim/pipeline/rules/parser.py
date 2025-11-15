"""Parser for rule DSL."""

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .models import Rule, RuleAction, RuleOperation


class RuleParseError(Exception):
    """Raised when a rule cannot be parsed."""

    pass


def _parse_operation(operation_str: str) -> RuleOperation:
    """Parse operation string into RuleOperation enum."""
    try:
        return RuleOperation(operation_str)
    except ValueError:
        valid_ops = [op.value for op in RuleOperation]
        raise RuleParseError(
            f"Invalid operation '{operation_str}'. Valid operations: {', '.join(valid_ops)}"
        )


def _parse_single_parameter(
    part: str, node_patterns: list[str], params: dict[str, str]
) -> None:
    """Parse a single parameter and update node_patterns or params."""
    if "=" not in part:
        raise RuleParseError(
            f"Invalid parameter format '{part}': expected 'key=value'"
        )

    key, value = part.split("=", 1)
    key = key.strip()
    value = value.strip()

    if key == "nodes":
        node_patterns.extend([n.strip() for n in value.split("|") if n.strip()])
    else:
        params[key] = value


def _parse_parameters(params_str: str) -> tuple[list[str], dict[str, str]]:
    """Parse parameters string into node patterns and params dict."""
    params: dict[str, str] = {}
    node_patterns: list[str] = []

    if not params_str:
        return node_patterns, params

    for part in params_str.split(","):
        part = part.strip()
        if part:
            _parse_single_parameter(part, node_patterns, params)

    return node_patterns, params


def _validate_rule_components(language: str, node_patterns: list[str]) -> None:
    """Validate required rule components."""
    if not node_patterns:
        raise RuleParseError("Missing required 'nodes' parameter")
    if not language:
        raise RuleParseError("Missing language specifier")


def parse_rule(rule_string: str) -> Rule:
    """
    Parse a rule string into a Rule object (legacy format).

    Format: <lang|*> : <op> : nodes=<node1|node2|glob*> [,k=v ...]

    Examples:
        python:skip:nodes=import_statement|import_from_statement
        python:replace_value:nodes=string|integer|float,value=<LIT>
        *:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR

    Args:
        rule_string: The rule string to parse

    Returns:
        A Rule object with legacy fields populated

    Raises:
        RuleParseError: If the rule string is invalid
    """
    rule_string = rule_string.strip()
    if not rule_string:
        raise RuleParseError("Empty rule string")

    parts = rule_string.split(":")
    if len(parts) < 3:
        raise RuleParseError(
            f"Invalid rule format: expected 'lang:op:params' but got '{rule_string}'"
        )

    language = parts[0].strip()
    operation_str = parts[1].strip()
    params_str = ":".join(parts[2:]).strip()

    operation = _parse_operation(operation_str)
    node_patterns, params = _parse_parameters(params_str)
    _validate_rule_components(language, node_patterns)

    # Create rule with legacy fields
    return Rule(
        name=f"Legacy {operation_str} rule",
        languages=["*"] if language == "*" else [language],
        operation=operation,
        node_patterns=node_patterns,
        params=params,
    )


def _is_new_rule_start(part: str, has_current_rule: bool) -> bool:
    """Check if a part starts a new rule (has lang:op: format)."""
    return ":" in part and part.count(":") >= 2 and has_current_rule


def _parse_accumulated_rule(current_rule: list[str], rules: list[Rule]) -> None:
    """Parse accumulated rule parts and add to rules list."""
    if not current_rule:
        return

    rule_str = ",".join(current_rule)
    try:
        rules.append(parse_rule(rule_str))
    except RuleParseError as e:
        raise RuleParseError(f"Error parsing rule '{rule_str}': {e}") from e


def parse_rules(rules_string: str) -> list[Rule]:
    """
    Parse multiple rules from a comma-separated string.

    Args:
        rules_string: Comma-separated rule strings

    Returns:
        List of Rule objects

    Raises:
        RuleParseError: If any rule string is invalid
    """
    if not rules_string.strip():
        return []

    rules: list[Rule] = []
    current_rule: list[str] = []
    parts = rules_string.split(",")

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if _is_new_rule_start(part, bool(current_rule)):
            _parse_accumulated_rule(current_rule, rules)
            current_rule = [part]
        else:
            current_rule.append(part)

    _parse_accumulated_rule(current_rule, rules)
    return rules


def parse_rules_file(file_path: str) -> list[Rule]:
    """
    Parse rules from a file (one rule per line, legacy format).

    Args:
        file_path: Path to the rules file

    Returns:
        List of Rule objects

    Raises:
        RuleParseError: If any rule string is invalid
        FileNotFoundError: If the file doesn't exist
    """
    rules = []
    with open(file_path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            try:
                rule = parse_rule(line)
                rules.append(rule)
            except RuleParseError as e:
                raise RuleParseError(f"Error on line {line_num}: {e}")

    return rules


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
