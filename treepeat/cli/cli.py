"""CLI interface for treepeat."""

import logging

import click
from rich.console import Console
from rich.logging import RichHandler

from treepeat.cli.commands import detect, list_ruleset, treesitter

console = Console()


def setup_logging(log_level: str) -> None:
    """Configure logging with rich handler."""
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@click.group()
@click.pass_context
@click.option(
    "--log-level",
    "-l",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    default="WARNING",
    help="Set the logging level",
)
@click.option(
    "--ruleset",
    "-r",
    type=click.Choice(["none", "default", "loose"], case_sensitive=False),
    default="default",
    help="Built-in ruleset profile to use (default: default)",
)
def main(
    ctx: click.Context,
    log_level: str,
    ruleset: str,
) -> None:
    """Tree-sitter based similarity detector."""
    setup_logging(log_level.upper())

    # Store common options in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level
    ctx.obj["ruleset"] = ruleset


# Register subcommands
main.add_command(detect)
main.add_command(treesitter)
main.add_command(list_ruleset)


if __name__ == "__main__":
    main()
