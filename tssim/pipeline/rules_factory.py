"""Factory for building rule engines from settings."""

import logging
from pathlib import Path

from tssim.config import PipelineSettings
from tssim.pipeline.rules import (
    Rule,
    RuleEngine,
    RuleParseError,
    build_default_rules,
    parse_yaml_rules_file,
)
from tssim.pipeline.rules.engine import build_loose_rules, build_region_extraction_rules

logger = logging.getLogger(__name__)


def _load_rules_from_file(rules_file_path: str, ruleset_name: str = "default") -> list[Rule]:
    """Load rules from a YAML file with error handling.

    Args:
        rules_file_path: Path to the YAML rules file
        ruleset_name: The ruleset to load (default: "default")

    Returns:
        List of rules

    Raises:
        FileNotFoundError: If file doesn't exist
        RuleParseError: If parsing fails
    """
    path = Path(rules_file_path)
    logger.info("Loading rules from YAML file: %s", path)

    try:
        rules = parse_yaml_rules_file(str(path), ruleset_name)
        logger.info("Loaded %d rule(s) from YAML ruleset '%s' in %s", len(rules), ruleset_name, path)
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
        query_preview = rule.query[:50] + "..." if len(rule.query) > 50 else rule.query
        logger.debug(
            "  %s (languages=%s, action=%s, query=%s)",
            rule.name,
            ",".join(rule.languages),
            rule.action.value if rule.action else "none",
            query_preview,
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
