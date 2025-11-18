"""Treesitter command - visualize AST transformations."""

import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console

from covey.config import LSHSettings, MinHashSettings, PipelineSettings, RulesSettings, ShingleSettings, set_settings

console = Console()


def _parse_patterns(pattern_string: str) -> list[str]:
    """Parse comma-separated pattern string into list."""
    return [p.strip() for p in pattern_string.split(",") if p.strip()]


def _create_rules_settings(ruleset: str) -> RulesSettings:
    """Create RulesSettings."""
    return RulesSettings(ruleset=ruleset)


def _configure_settings(
    ruleset: str,
    threshold: float | None,
    min_lines: int,
    ignore: str,
    ignore_files: str,
) -> None:
    """Configure pipeline settings."""
    # Create LSH settings - if threshold is None, use internal defaults
    if threshold is not None:
        lsh_settings = LSHSettings(similarity_percent=threshold, min_lines=min_lines)
    else:
        lsh_settings = LSHSettings(min_lines=min_lines)

    settings = PipelineSettings(
        rules=_create_rules_settings(ruleset),
        shingle=ShingleSettings(),  # Uses default k=3
        minhash=MinHashSettings(),  # Uses default num_perm=128
        lsh=lsh_settings,
        ignore_patterns=_parse_patterns(ignore),
        ignore_file_patterns=_parse_patterns(ignore_files),
    )
    set_settings(settings)


def _extract_tokens_from_file(parsed_file: Any, shingler: Any) -> dict[int, list[str]]:
    """Extract individual normalized tokens from a file's AST, grouped by line number.

    Returns a dictionary mapping line numbers (1-indexed) to lists of token representations.
    """
    from covey.models.normalization import SkipNode

    tokens_by_line: dict[int, list[str]] = {}
    source = parsed_file.source
    language = parsed_file.language
    root = parsed_file.root_node

    # Reset identifiers for consistent output
    shingler.rule_engine.reset_identifiers()
    shingler.rule_engine.precompute_queries(root, language, source)

    def traverse(node: Any) -> None:
        """Traverse AST and collect normalized token representations by line."""
        try:
            node_repr = shingler._get_node_representation(node, language, source, root)
            # Get the line number for this node (1-indexed)
            line_num = node.start_point[0] + 1
            if line_num not in tokens_by_line:
                tokens_by_line[line_num] = []
            tokens_by_line[line_num].append(str(node_repr))
        except SkipNode:
            # Skip this node but continue with children
            pass

        # Recursively traverse children
        for child in node.children:
            traverse(child)

    traverse(root)
    return tokens_by_line


def _process_leaf_node(
    node: Any, node_repr: Any, line_parts: dict[int, list[tuple[int, str]]],
    include_node_type: bool = False
) -> None:
    """Process a leaf node and add its representation to line_parts."""
    line_num = node.start_point[0] + 1
    col_num = node.start_point[1]

    # Use the normalized representation
    if include_node_type:
        # Include node type prefix (for tokens view)
        if node_repr.value:
            text = f"{node_repr.name}:{node_repr.value}"
        else:
            text = node_repr.name
    else:
        # Just show the value (for transformed view)
        text = node_repr.value if node_repr.value else node_repr.name

    if line_num not in line_parts:
        line_parts[line_num] = []
    line_parts[line_num].append((col_num, text))


def _process_internal_node(
    node: Any, shingler: Any, language: str, source: bytes, root: Any,
    line_parts: dict[int, list[tuple[int, str]]]
) -> None:
    """Process an internal node where all children were skipped."""
    from covey.models.normalization import SkipNode

    line_num = node.start_point[0] + 1
    col_num = node.start_point[1]
    try:
        node_repr = shingler._get_node_representation(node, language, source, root)
        if line_num not in line_parts:
            line_parts[line_num] = []
        line_parts[line_num].append((col_num, f"<{node_repr.name}>"))
    except SkipNode:
        pass


def _reconstruct_lines_from_parts(
    line_parts: dict[int, list[tuple[int, str]]],
    source_lines: list[str]
) -> dict[int, str]:
    """Reconstruct source lines from collected node parts, preserving original indentation."""
    reconstructed_lines: dict[int, str] = {}
    for line_num, parts in sorted(line_parts.items()):
        sorted_parts = sorted(parts, key=lambda x: x[0])
        tokens = " ".join(text for _, text in sorted_parts)

        # Extract indentation from original source line
        if line_num <= len(source_lines):
            original_line = source_lines[line_num - 1]
            indentation = original_line[:len(original_line) - len(original_line.lstrip())]
            reconstructed_lines[line_num] = indentation + tokens
        else:
            reconstructed_lines[line_num] = tokens
    return reconstructed_lines


def _reconstruct_transformed_source(parsed_file: Any, shingler: Any) -> dict[int, str]:
    """Reconstruct source code from normalized AST nodes, grouped by line number.

    Returns a dictionary mapping line numbers (1-indexed) to reconstructed source lines.
    """
    from covey.models.normalization import SkipNode

    source = parsed_file.source
    language = parsed_file.language
    root = parsed_file.root_node

    # Get source lines for indentation extraction
    try:
        source_lines = source.decode("utf-8", errors="ignore").splitlines()
    except Exception:
        source_lines = []

    # Reset identifiers for consistent output
    shingler.rule_engine.reset_identifiers()
    shingler.rule_engine.precompute_queries(root, language, source)

    # Track which source bytes have been covered by nodes
    line_parts: dict[int, list[tuple[int, str]]] = {}

    def traverse(node: Any, parent_skipped: bool = False) -> bool:
        """Traverse AST and reconstruct source from normalized nodes."""
        node_skipped = False
        try:
            node_repr = shingler._get_node_representation(node, language, source, root)
            if len(node.children) == 0:
                _process_leaf_node(node, node_repr, line_parts, include_node_type=False)
        except SkipNode:
            # Skip this node and its entire subtree
            return True

        # Process children
        any_child_processed = False
        for child in node.children:
            child_skipped = traverse(child, node_skipped)
            if not child_skipped:
                any_child_processed = True

        # For nodes with children that weren't skipped, add structural info if needed
        if not node_skipped and not any_child_processed and len(node.children) > 0:
            _process_internal_node(node, shingler, language, source, root, line_parts)

        return node_skipped

    traverse(root)
    return _reconstruct_lines_from_parts(line_parts, source_lines)


def _truncate_if_needed(text: str, max_width: int) -> str:
    """Truncate text if it exceeds max_width."""
    if len(text) > max_width - 1:
        return text[:max_width - 4] + "..."
    return text


def _print_side_by_side_header(file_path: Any, language: str, col_width: int, show_transformed: bool = False) -> None:
    """Print the header for side-by-side display."""
    console.print("\n[bold]TreeSitter Side-by-Side View:[/bold]")
    console.print(f"[bold cyan]File:[/bold cyan] {file_path}")
    console.print(f"[dim]Language: {language}[/dim]")
    header_left = "Original Source"
    header_right = "Transformed Source" if show_transformed else "TreeSitter Tokens"
    console.print(f"\n[bold]{header_left:<{col_width}}[/bold]│[bold]{header_right:<{col_width}}[/bold]")
    console.print(f"{'-' * col_width}│{'-' * col_width}")


def _display_transformed_view(
    source_lines: list[str], parsed_file: Any, shingler: Any, col_width: int
) -> None:
    """Display transformed source view."""
    transformed_lines = _reconstruct_transformed_source(parsed_file, shingler)

    for line_num in range(1, len(source_lines) + 1):
        source_line = source_lines[line_num - 1] if line_num <= len(source_lines) else ""
        left_line = _truncate_if_needed(source_line, col_width)
        transformed_line = transformed_lines.get(line_num, "")
        right_line = _truncate_if_needed(transformed_line, col_width)
        console.print(f"{left_line:<{col_width}}│{right_line:<{col_width}}")

    console.print(f"\n[dim]Total source lines: {len(source_lines)}[/dim]")
    console.print(f"[dim]Transformed lines: {len(transformed_lines)}[/dim]")


def _display_tokens_view(
    source_lines: list[str], parsed_file: Any, shingler: Any, col_width: int
) -> None:
    """Display tree-sitter tokens view."""
    tokens_by_line = _extract_tokens_from_file(parsed_file, shingler)
    total_tokens = 0

    for line_num in range(1, len(source_lines) + 1):
        source_line = source_lines[line_num - 1] if line_num <= len(source_lines) else ""
        left_line = _truncate_if_needed(source_line, col_width)
        line_tokens = tokens_by_line.get(line_num, [])
        total_tokens += len(line_tokens)
        tokens_str = " ".join(line_tokens)
        right_line = _truncate_if_needed(tokens_str, col_width)
        console.print(f"{left_line:<{col_width}}│{right_line:<{col_width}}")

    console.print(f"\n[dim]Total source lines: {len(source_lines)}[/dim]")
    console.print(f"[dim]Total tokens: {total_tokens}[/dim]")


def _display_file_side_by_side(parsed_file: Any, shingler: Any, show_transformed: bool = False) -> None:
    """Display original file content side-by-side with treesitter tokens or transformed source."""
    try:
        source_lines = parsed_file.source.decode("utf-8", errors="ignore").splitlines()
    except Exception:
        console.print("[bold red]Error:[/bold red] Failed to decode file content")
        return

    col_width = console.width // 2
    _print_side_by_side_header(parsed_file.path, parsed_file.language, col_width, show_transformed)

    if show_transformed:
        _display_transformed_view(source_lines, parsed_file, shingler, col_width)
    else:
        _display_tokens_view(source_lines, parsed_file, shingler, col_width)

    console.print()


@click.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--transformed",
    "-t",
    is_flag=True,
    default=False,
    help="Show transformed source instead of tree-sitter tokens on the right side",
)
@click.pass_context
def treesitter(
    ctx: click.Context,
    file: Path,
    transformed: bool,
) -> None:
    """Show a file's tree-sitter view after ruleset is applied.

    This command displays the original source code on the left and the
    tree-sitter token representations on the right,
    showing how the code is transformed during similarity detection.
    """
    from covey.config import get_settings
    from covey.pipeline.parse import parse_file
    from covey.pipeline.shingle import ASTShingler
    from covey.pipeline.rules_factory import build_rule_engine

    ruleset = ctx.obj["ruleset"]
    _configure_settings(ruleset, 1.0, 5, "", "**/.*ignore")

    # Parse the file
    try:
        parsed_file = parse_file(file)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to parse file: {e}")
        sys.exit(1)

    # Build rule engine and shingler
    rule_engine = build_rule_engine(get_settings())
    shingler = ASTShingler(rule_engine=rule_engine, k=3)

    # Display side-by-side view
    _display_file_side_by_side(parsed_file, shingler, show_transformed=transformed)
