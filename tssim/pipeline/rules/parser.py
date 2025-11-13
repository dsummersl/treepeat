"""Parser for rule DSL."""

from typing import Optional

from .models import Rule, RuleOperation


class RuleParseError(Exception):
    """Raised when a rule cannot be parsed."""

    pass


def parse_rule(rule_string: str) -> Rule:
    """
    Parse a rule string into a Rule object.

    Format: <lang|*> : <op> : nodes=<node1|node2|glob*> [,k=v ...]

    Examples:
        python:skip:nodes=import_statement|import_from_statement
        python:replace_value:nodes=string|integer|float,value=<LIT>
        *:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR

    Args:
        rule_string: The rule string to parse

    Returns:
        A Rule object

    Raises:
        RuleParseError: If the rule string is invalid
    """
    rule_string = rule_string.strip()
    if not rule_string:
        raise RuleParseError("Empty rule string")

    # Split by colon
    parts = rule_string.split(":")
    if len(parts) < 3:
        raise RuleParseError(
            f"Invalid rule format: expected 'lang:op:params' but got '{rule_string}'"
        )

    language = parts[0].strip()
    operation_str = parts[1].strip()
    params_str = ":".join(parts[2:]).strip()  # Rejoin in case there are colons in params

    # Parse operation
    try:
        operation = RuleOperation(operation_str)
    except ValueError:
        valid_ops = [op.value for op in RuleOperation]
        raise RuleParseError(
            f"Invalid operation '{operation_str}'. Valid operations: {', '.join(valid_ops)}"
        )

    # Parse parameters
    params = {}
    node_patterns = []

    if params_str:
        # Split by comma, but be careful of commas in values
        param_parts = params_str.split(",")
        for part in param_parts:
            part = part.strip()
            if not part:
                continue

            if "=" not in part:
                raise RuleParseError(
                    f"Invalid parameter format '{part}': expected 'key=value'"
                )

            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip()

            if key == "nodes":
                # Split node patterns by pipe
                node_patterns = [n.strip() for n in value.split("|") if n.strip()]
            else:
                params[key] = value

    # Validate nodes parameter
    if not node_patterns:
        raise RuleParseError("Missing required 'nodes' parameter")

    # Validate language
    if not language:
        raise RuleParseError("Missing language specifier")

    return Rule(
        language=language,
        operation=operation,
        node_patterns=node_patterns,
        params=params,
    )


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

    rules = []
    # For comma-separated rules, we need to be careful about commas in the params
    # Split by looking for pattern boundaries (lang:op:)
    current_rule = []
    parts = rules_string.split(",")

    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue

        # Check if this part starts a new rule (has format lang:op:...)
        if ":" in part:
            # Count colons to determine if this is a new rule
            colon_count = part.count(":")
            if colon_count >= 2 and current_rule:
                # This is a new rule, parse the previous one
                rule_str = ",".join(current_rule)
                try:
                    rules.append(parse_rule(rule_str))
                except RuleParseError as e:
                    raise RuleParseError(f"Error parsing rule '{rule_str}': {e}")
                current_rule = [part]
            else:
                current_rule.append(part)
        else:
            current_rule.append(part)

    # Parse the last rule
    if current_rule:
        rule_str = ",".join(current_rule)
        try:
            rules.append(parse_rule(rule_str))
        except RuleParseError as e:
            raise RuleParseError(f"Error parsing rule '{rule_str}': {e}")

    return rules


def parse_rules_file(file_path: str) -> list[Rule]:
    """
    Parse rules from a file (one rule per line).

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
