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
)
from tssim.pipeline.rules.engine import build_loose_rules

logger = logging.getLogger(__name__)


def _load_rules_from_string(rules_string: str) -> list[Rule]:
    """Load rules from a string with error handling."""
    logger.info("Loading rules from --rules parameter")
    try:
        rules = parse_rules(rules_string)
        logger.info("Loaded %d rule(s) from --rules", len(rules))
        return rules
    except RuleParseError as e:
        logger.error("Failed to parse rules: %s", e)
        raise


def _load_rules_from_file(rules_file_path: str) -> list[Rule]:
    """Load rules from a file with error handling."""
    path = Path(rules_file_path)
    logger.info("Loading rules from file: %s", path)
    try:
        rules = parse_rules_file(str(path))
        logger.info("Loaded %d rule(s) from %s", len(rules), path)
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
        params_str = (
            f",{','.join(f'{k}={v}' for k,v in rule.params.items())}"
            if rule.params
            else ""
        )
        logger.debug(
            "  %s:%s:nodes=%s%s",
            rule.language,
            rule.operation.value,
            "|".join(rule.node_patterns),
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
    else:  # none
        return []


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
    # Load rules based on priority: rules-file > rules > ruleset
    if settings.rules.rules_file:
        rules = _load_rules_from_file(settings.rules.rules_file)
    elif settings.rules.rules:
        rules = _load_rules_from_string(settings.rules.rules)
    else:
        rules = _load_ruleset_rules(settings.rules.ruleset.lower())

    _log_active_rules(rules)
    return RuleEngine(rules)
