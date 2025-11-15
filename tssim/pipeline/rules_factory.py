"""Factory for building rule engines from settings."""

import logging
from pathlib import Path

from tssim.config import PipelineSettings
from tssim.pipeline.rules import (
    Rule,
    RuleEngine,
    RuleParseError,
    build_default_rules,
    parse_rules,
    parse_rules_file,
    parse_yaml_rules_file,
)
from tssim.pipeline.rules.engine import build_loose_rules, build_region_extraction_rules

logger = logging.getLogger(__name__)


def _is_yaml_file(file_path: str) -> bool:
    """Check if a file is a YAML file based on extension."""
    path = Path(file_path)
    return path.suffix.lower() in [".yaml", ".yml"]


def _load_rules_from_file(rules_file_path: str, ruleset_name: str = "default") -> list[Rule]:
    """Load rules from a file with error handling.

    Args:
        rules_file_path: Path to the rules file
        ruleset_name: For YAML files, the ruleset to load (default: "default")

    Returns:
        List of rules

    Raises:
        FileNotFoundError: If file doesn't exist
        RuleParseError: If parsing fails
    """
    path = Path(rules_file_path)
    logger.info("Loading rules from file: %s", path)

    try:
        if _is_yaml_file(rules_file_path):
            rules = parse_yaml_rules_file(str(path), ruleset_name)
            logger.info("Loaded %d rule(s) from YAML ruleset '%s' in %s", len(rules), ruleset_name, path)
        else:
            rules = parse_rules_file(str(path))
            logger.info("Loaded %d rule(s) from legacy rules file %s", len(rules), path)
        return rules
    except (FileNotFoundError, RuleParseError) as e:
        logger.error("Failed to load rules file: %s", e)
        raise


def _log_active_rules(rules: list[Rule]) -> None:
    """Log the active rules for debugging."""
    if not rules:
        logger.warning("No rules configured - no normalization will be applied")
        return

    logger.debug("Active rules:")
    for rule in rules:
        if rule.is_query_based():
            # Query-based rule
            logger.debug(
                "  %s (languages=%s, action=%s, query=%s)",
                rule.name,
                ",".join(rule.languages),
                rule.action.value if rule.action else "none",
                rule.query[:50] + "..." if rule.query and len(rule.query) > 50 else rule.query,
            )
        else:
            # Legacy rule
            params_str = (
                f",{','.join(f'{k}={v}' for k,v in rule.params.items())}"
                if rule.params
                else ""
            )
            logger.debug(
                "  %s (languages=%s, operation=%s, nodes=%s%s)",
                rule.name,
                ",".join(rule.languages),
                rule.operation.value if rule.operation else "none",
                "|".join(rule.node_patterns) if rule.node_patterns else "",
                params_str,
            )


def get_ruleset_with_descriptions(ruleset: str) -> list[tuple[Rule, str]]:
    """Get a ruleset with rule descriptions for display purposes.

    Args:
        ruleset: Name of the ruleset (default, loose, none)

    Returns:
        List of tuples containing (Rule, description)
    """
    ruleset = ruleset.lower()
    if ruleset == "default":
        return build_default_rules()
    elif ruleset == "loose":
        return build_loose_rules()
    else:  # none - only region extraction rules, no normalization
        return build_region_extraction_rules()


def _load_ruleset_rules(ruleset: str) -> list[Rule]:
    """Load rules from a predefined ruleset.

    Args:
        ruleset: Name of the ruleset (default, loose, none)

    Returns:
        List of rules (without descriptions)
    """
    rules_with_descriptions = get_ruleset_with_descriptions(ruleset)
    if rules_with_descriptions:
        logger.info("Using '%s' ruleset", ruleset)
    return [rule for rule, _ in rules_with_descriptions]


def build_rule_engine(settings: PipelineSettings) -> RuleEngine:
    """Build a rule engine from settings.

    Args:
        settings: Pipeline settings containing rule configuration

    Returns:
        Configured RuleEngine instance
    """
    # Load rules based on priority: rules-file > built-in ruleset
    if settings.rules.rules_file:
        rules = _load_rules_from_file(
            settings.rules.rules_file,
            settings.rules.rules_file_ruleset,
        )
    else:
        rules = _load_ruleset_rules(settings.rules.ruleset.lower())

    _log_active_rules(rules)
    return RuleEngine(rules)
