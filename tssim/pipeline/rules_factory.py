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


def build_rule_engine(settings: PipelineSettings) -> RuleEngine:
    """
    Build a rule engine from pipeline settings.

    Rule precedence (last wins):
    1. ruleset (none or default)
    2. --rules parameter (overrides ruleset)
    3. --rules-file parameter (overrides both)

    Args:
        settings: Pipeline settings with rules configuration

    Returns:
        RuleEngine configured with the specified rules

    Raises:
        RuleParseError: If rules cannot be parsed
        FileNotFoundError: If rules_file doesn't exist
    """
    # Start with ruleset-based defaults
    ruleset = settings.rules.ruleset.lower()
    if ruleset == "none":
        logger.info("Using 'none' ruleset - no rules will be applied")
        rules = []
    elif ruleset == "default":
        logger.info("Using 'default' ruleset")
        rules = build_default_rules()
    else:
        logger.warning("Unknown ruleset '%s', falling back to 'default'", ruleset)
        rules = build_default_rules()

    # Override with --rules parameter if provided
    if settings.rules.rules:
        rules = _load_rules_from_string(settings.rules.rules)

    # Override with --rules-file parameter if provided (takes precedence)
    if settings.rules.rules_file:
        rules = _load_rules_from_file(settings.rules.rules_file)

    _log_active_rules(rules)
    return RuleEngine(rules)
