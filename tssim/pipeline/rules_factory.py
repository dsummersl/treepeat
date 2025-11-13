"""Factory for building rule engines from settings."""

import logging
from pathlib import Path

from tssim.config import PipelineSettings
from tssim.pipeline.rules import (
    RuleEngine,
    RuleParseError,
    build_default_rules,
    parse_rules,
    parse_rules_file,
)

logger = logging.getLogger(__name__)


def build_rule_engine(settings: PipelineSettings) -> RuleEngine:
    """
    Build a rule engine from pipeline settings.

    If rules or rules_file are specified, they override defaults.
    Last one wins (rules_file takes precedence over rules).

    Args:
        settings: Pipeline settings with rules configuration

    Returns:
        RuleEngine configured with the specified rules

    Raises:
        RuleParseError: If rules cannot be parsed
        FileNotFoundError: If rules_file doesn't exist
    """
    rules = build_default_rules()

    # If custom rules specified via CLI, use them instead
    if settings.rules.rules:
        logger.info("Loading rules from --rules parameter")
        try:
            rules = parse_rules(settings.rules.rules)
            logger.info("Loaded %d rule(s) from --rules", len(rules))
        except RuleParseError as e:
            logger.error("Failed to parse rules: %s", e)
            raise

    # If rules file specified, it overrides everything (last wins)
    if settings.rules.rules_file:
        rules_file_path = Path(settings.rules.rules_file)
        logger.info("Loading rules from file: %s", rules_file_path)
        try:
            rules = parse_rules_file(str(rules_file_path))
            logger.info("Loaded %d rule(s) from %s", len(rules), rules_file_path)
        except FileNotFoundError:
            logger.error("Rules file not found: %s", rules_file_path)
            raise
        except RuleParseError as e:
            logger.error("Failed to parse rules file: %s", e)
            raise

    # Log the active rules
    if not rules:
        logger.warning("No rules configured - no normalization will be applied")
    else:
        logger.debug("Active rules:")
        for rule in rules:
            logger.debug(
                "  %s:%s:nodes=%s%s",
                rule.language,
                rule.operation.value,
                "|".join(rule.node_patterns),
                f",{','.join(f'{k}={v}' for k,v in rule.params.items())}"
                if rule.params
                else "",
            )

    return RuleEngine(rules)
