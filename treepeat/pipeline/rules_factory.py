"""Factory for building rule engines from settings."""

import logging

from treepeat.config import PipelineSettings
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules
from treepeat.pipeline.rules.models import Rule
from treepeat.pipeline.rules.engine import build_loose_rules, build_region_extraction_rules

logger = logging.getLogger(__name__)


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
    """Get a ruleset with rule descriptions for display purposes. """
    ruleset = ruleset.lower()
    if ruleset == "default":
        return build_default_rules()
    elif ruleset == "loose":
        return build_loose_rules()
    else:  # none - only region extraction rules, no normalization
        return build_region_extraction_rules()


def _load_ruleset_rules(ruleset: str) -> list[Rule]:
    """Load rules from a predefined ruleset. """
    rules_with_descriptions = get_ruleset_with_descriptions(ruleset)
    if rules_with_descriptions:
        logger.info("Using '%s' ruleset", ruleset)
    return [rule for rule, _ in rules_with_descriptions]


def build_rule_engine(settings: PipelineSettings) -> RuleEngine:
    """Build a rule engine from settings. """
    rules = _load_ruleset_rules(settings.rules.ruleset.lower())
    _log_active_rules(rules)
    return RuleEngine(rules)
