"""List-ruleset command - display rules in a ruleset."""

from typing import Any

import click
from rich.console import Console

console = Console()


def _print_rule_spec(rule: Any) -> None:
    """Print rule specification."""
    query_preview = rule.query[:60] + "..." if len(rule.query) > 60 else rule.query
    rule_spec = f"languages={','.join(rule.languages)}, action={rule.action.value if rule.action else 'none'}"
    console.print(f"    [dim]{rule_spec}[/dim]")
    console.print(f"    [dim]query: {query_preview}[/dim]\n")


def _build_ruleset_header(ruleset_name: str, language_filter: str | None) -> str:
    """Build the ruleset header with optional language filter."""
    header = f"Ruleset: {ruleset_name}"
    if language_filter:
        header += f" (language: {language_filter})"
    return header


def _print_empty_ruleset_message(language_filter: str | None) -> None:
    """Print message when no rules are found."""
    if language_filter:
        console.print(f"  [dim]No rules found for language '{language_filter}'[/dim]\n")
    else:
        console.print("  [dim]No normalization rules - raw AST comparison[/dim]\n")


def _filter_rules_by_language(
    rules: list[tuple[Any, str]], language_filter: str | None
) -> list[tuple[Any, str]]:
    """Filter rules by language if specified."""
    if not language_filter:
        return rules
    return [(rule, desc) for rule, desc in rules if language_filter in rule.languages]


def _print_rulesets(ruleset_name: str, language_filter: str | None = None) -> None:
    """Print rules in the specified ruleset, optionally filtered by language."""
    from covey.pipeline.rules_factory import get_ruleset_with_descriptions

    rules_with_descriptions = get_ruleset_with_descriptions(ruleset_name)
    rules_with_descriptions = _filter_rules_by_language(rules_with_descriptions, language_filter)

    header = _build_ruleset_header(ruleset_name, language_filter)
    console.print(f"\n[bold blue]{header}[/bold blue]\n")

    if not rules_with_descriptions:
        _print_empty_ruleset_message(language_filter)
        return

    console.print(f"[dim]{len(rules_with_descriptions)} rule(s):[/dim]\n")
    for rule, description in rules_with_descriptions:
        console.print(f"  [cyan]•[/cyan] {description}")
        _print_rule_spec(rule)


@click.command(name="list-ruleset")
@click.argument(
    "ruleset",
    type=click.Choice(["none", "default", "loose"], case_sensitive=False),
)
@click.option(
    "--language",
    "-l",
    type=str,
    default=None,
    help="Filter rules by language (e.g., python, java, javascript)",
)
def list_ruleset(ruleset: str, language: str | None) -> None:
    """List rules in the specified ruleset.

    Display all rules in a given ruleset (none/default/loose), optionally
    filtered by a specific programming language.
    """
    _print_rulesets(ruleset, language)
