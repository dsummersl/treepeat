import logging

from treepeat.config import PipelineSettings
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules
from treepeat.pipeline.rules.models import Rule, RuleAction
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


def get_ruleset_with_descriptions(
    ruleset: str, filters: dict[str, set[str]] | None = None
) -> list[tuple[Rule, str]]:
    """Get a ruleset with rule descriptions for display purposes."""
    ruleset = ruleset.lower()
    if ruleset == "default":
        rules = build_default_rules()
    elif ruleset == "loose":
        rules = build_loose_rules()
    else:  # none - only region extraction rules, no normalization
        rules = build_region_extraction_rules()

    if not filters:
        return rules
    return _filter_rules_by_region_filters(rules, filters)


def _filter_rules_by_region_filters(
    rules: list[tuple[Rule, str]], filters: dict[str, set[str]]
) -> list[tuple[Rule, str]]:
    """Filter rules to languages and region types specified in `filters`."""
    allowed_langs = set(filters.keys())

    def keep(rule: Rule) -> bool:
        # Language must intersect
        if not any(lang in allowed_langs for lang in rule.languages):
            return False
        # For extraction rules, region_type must be allowed for some language
        if rule.action == RuleAction.EXTRACT_REGION:
            region_type = rule.params.get("region_type") if hasattr(rule, "params") else None
            if not region_type:
                return False
            return any(
                region_type in filters.get(lang, set())
                for lang in rule.languages
                if lang in allowed_langs
            )
        # For normalization rules, just language match is enough
        return True

    return [(r, d) for (r, d) in rules if keep(r)]


def _build_additional_region_rules(additional_regions: dict[str, set[str]]) -> list[Rule]:
    """Create rule definitions for user-specified region types."""
    rules: list[Rule] = []
    for language, node_types in additional_regions.items():
        for node_type in sorted(node_types):
            rule = Rule(
                name=f"Extract {node_type} regions for {language} (custom)",
                languages=[language],
                query=f"({node_type}) @region",
                action=RuleAction.EXTRACT_REGION,
                params={"region_type": node_type},
            )
            rules.append(rule)
    return rules


def _load_ruleset_rules(ruleset: str, filters: dict[str, set[str]] | None = None) -> list[Rule]:
    """Load rules from a predefined ruleset, honoring optional filters."""
    rules_with_descriptions = get_ruleset_with_descriptions(ruleset, filters)
    if rules_with_descriptions:
        logger.info("Using '%s' ruleset", ruleset)
    return [rule for rule, _ in rules_with_descriptions]


def _is_excluded_region_type(rule: Rule, excluded_regions: dict[str, set[str]]) -> bool:
    region_type = rule.params.get("region_type", None)
    if not region_type:
        return False

    return any(region_type in excluded_regions.get(lang, set()) for lang in rule.languages)

def _filter_extract_region_rules(rules: list[Rule]) -> list[Rule]:
    return [rule for rule in rules if rule.action == RuleAction.EXTRACT_REGION]


def _filter_excluded_regions(
    rules: list[Rule], excluded_regions: dict[str, set[str]]
) -> list[Rule]:
    if not excluded_regions:
        return rules

    return [
        rule for rule in _filter_extract_region_rules(rules) if not _is_excluded_region_type(rule, excluded_regions)
    ]


def build_rule_engine(settings: PipelineSettings) -> RuleEngine:
    """Build a rule engine from settings."""
    filters = getattr(settings.rules, "region_filters", {}) or {}
    additional_regions = getattr(settings.rules, "additional_regions", {}) or {}
    excluded_regions = getattr(settings.rules, "excluded_regions", {}) or {}

    rules = _load_ruleset_rules(settings.rules.ruleset.lower(), filters)
    if additional_regions:
        rules.extend(_build_additional_region_rules(additional_regions))

    # Apply exclusions after all rules are loaded
    rules = _filter_excluded_regions(rules, excluded_regions)

    _log_active_rules(rules)
    return RuleEngine(rules)
