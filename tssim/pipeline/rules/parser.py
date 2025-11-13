"""Parser for rule DSL."""


from .models import Rule, RuleOperation


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

    return Rule(
        language=language,
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
