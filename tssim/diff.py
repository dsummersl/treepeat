"""Side-by-side diff display functionality."""

import difflib
from collections.abc import Sequence

from rich.console import Console

from tssim.models.similarity import Region

console = Console()


def _truncate_line(line: str, max_width: int) -> str:
    """Truncate a line to fit within max_width."""
    return line[:max_width] if len(line) > max_width else line


def _read_region_lines(region: Region) -> list[str]:
    """Read lines from a file for a specific region."""
    try:
        with open(region.path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # Extract lines for this region (1-indexed to 0-indexed)
            return lines[region.start_line - 1 : region.end_line]
    except Exception:
        return []


def _prepare_diff_lines(region1: Region, region2: Region) -> tuple[list[str], list[str]] | None:
    """Read and prepare lines from both regions for diff."""
    lines1 = _read_region_lines(region1)
    lines2 = _read_region_lines(region2)

    if not lines1 or not lines2:
        return None

    # Strip newlines from lines
    lines1 = [line.rstrip('\n\r') for line in lines1]
    lines2 = [line.rstrip('\n\r') for line in lines2]

    return (lines1, lines2)


def _regions_are_identical(opcodes: Sequence[tuple[str, int, int, int, int]]) -> bool:
    """Check if opcodes indicate identical regions."""
    if len(opcodes) != 1:
        return False
    return opcodes[0][0] == 'equal'


def _print_equal_lines(lines1: list[str], lines2: list[str], i1: int, i2: int, j1: int, j2: int, col_width: int) -> None:
    """Print equal (matching) lines side-by-side."""
    for i, j in zip(range(i1, i2), range(j1, j2)):
        left = _truncate_line(lines1[i], col_width)
        right = _truncate_line(lines2[j], col_width)
        console.print(f"  {left:<{col_width}} │ {right:<{col_width}}")


def _apply_char_style(text: str, style: str) -> str:
    """Apply a style to text."""
    return f"[{style}]{text}[/{style}]"


def _process_diff_opcode(tag: str, left_part: str, right_part: str, bright_left: str, bright_right: str) -> tuple[str, str]:
    """Process a single diff opcode and return styled parts."""
    if tag == 'equal':
        return left_part, right_part
    if tag == 'replace':
        return _apply_char_style(left_part, bright_left), _apply_char_style(right_part, bright_right)
    if tag == 'delete':
        return _apply_char_style(left_part, bright_left), ""
    if tag == 'insert':
        return "", _apply_char_style(right_part, bright_right)
    return "", ""


def _highlight_char_diff(text1: str, text2: str, col_width: int) -> tuple[str, str]:
    """Highlight character-level differences within two strings.

    Returns (left_highlighted, right_highlighted) with full-width backgrounds.
    """
    soft_left_bg = "on rgb(255,235,235)"
    soft_right_bg = "on rgb(235,255,235)"
    bright_left_style = "bold rgb(220,0,0)"
    bright_right_style = "bold rgb(0,180,0)"

    matcher = difflib.SequenceMatcher(None, text1, text2)
    result_left = []
    result_right = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        left_styled, right_styled = _process_diff_opcode(
            tag, text1[i1:i2], text2[j1:j2], bright_left_style, bright_right_style
        )
        if left_styled:
            result_left.append(left_styled)
        if right_styled:
            result_right.append(right_styled)

    left_text = ''.join(result_left)
    right_text = ''.join(result_right)
    left_padding = col_width - len(text1)
    right_padding = col_width - len(text2)

    return (
        f"[{soft_left_bg}]{left_text}{' ' * left_padding}[/{soft_left_bg}]",
        f"[{soft_right_bg}]{right_text}{' ' * right_padding}[/{soft_right_bg}]"
    )


def _print_replaced_lines(lines1: list[str], lines2: list[str], i1: int, i2: int, j1: int, j2: int, col_width: int) -> None:
    """Print replaced (changed) lines side-by-side with character-level diff highlighting."""
    max_len = max(i2 - i1, j2 - j1)
    for idx in range(max_len):
        if idx < (i2 - i1):
            left_line = _truncate_line(lines1[i1 + idx], col_width)

            # If we have a corresponding right line, do character-level diff
            if idx < (j2 - j1):
                right_line = _truncate_line(lines2[j1 + idx], col_width)
                left, right = _highlight_char_diff(left_line, right_line, col_width)
            else:
                # No corresponding right line - just soft background full width
                padding = col_width - len(left_line)
                left = f"[on rgb(255,235,235)]{left_line}{' ' * padding}[/on rgb(255,235,235)]"
                right = f"[on rgb(235,255,235)]{' ' * col_width}[/on rgb(235,255,235)]"
        else:
            # No left line, only right
            right_line = _truncate_line(lines2[j1 + idx], col_width)
            padding = col_width - len(right_line)
            left = f"[on rgb(255,235,235)]{' ' * col_width}[/on rgb(255,235,235)]"
            right = f"[on rgb(235,255,235)]{right_line}{' ' * padding}[/on rgb(235,255,235)]"

        console.print(f"  {left} │ {right}")


def _print_deleted_lines(lines1: list[str], i1: int, i2: int, col_width: int) -> None:
    """Print deleted lines (only on left side)."""
    for i in range(i1, i2):
        left_line = _truncate_line(lines1[i], col_width)
        # Use soft red background for full width
        padding = col_width - len(left_line)
        left = f"[on rgb(255,235,235)]{left_line}{' ' * padding}[/on rgb(255,235,235)]"
        console.print(f"  {left} │ {' ' * col_width}")


def _print_inserted_lines(lines2: list[str], j1: int, j2: int, col_width: int) -> None:
    """Print inserted lines (only on right side)."""
    for j in range(j1, j2):
        right_line = _truncate_line(lines2[j], col_width)
        # Use soft green background for full width
        padding = col_width - len(right_line)
        right = f"[on rgb(235,255,235)]{right_line}{' ' * padding}[/on rgb(235,255,235)]"
        console.print(f"  {' ' * col_width} │ {right}")


def _print_diff_header(region1: Region, region2: Region, col_width: int) -> None:
    """Print diff header with file information."""
    console.print("  [bold]Side-by-side diff:[/bold]")
    header1 = f"{region1.path}:{region1.start_line}-{region1.end_line}"
    header2 = f"{region2.path}:{region2.start_line}-{region2.end_line}"
    console.print(f"  [dim]{header1:<{col_width}}[/dim] │ [dim]{header2:<{col_width}}[/dim]")
    console.print(f"  {'-' * col_width} │ {'-' * col_width}")


def _process_diff_opcodes(
    lines1: list[str], lines2: list[str], opcodes: Sequence[tuple[str, int, int, int, int]], col_width: int
) -> None:
    """Process diff opcodes and display changes."""
    handlers = {
        'equal': lambda i1, i2, j1, j2: _print_equal_lines(lines1, lines2, i1, i2, j1, j2, col_width),
        'replace': lambda i1, i2, j1, j2: _print_replaced_lines(lines1, lines2, i1, i2, j1, j2, col_width),
        'delete': lambda i1, i2, j1, j2: _print_deleted_lines(lines1, i1, i2, col_width),
        'insert': lambda i1, i2, j1, j2: _print_inserted_lines(lines2, j1, j2, col_width),
    }

    for tag, i1, i2, j1, j2 in opcodes:
        handler = handlers.get(tag)
        if handler:
            handler(i1, i2, j1, j2)


def display_diff(region1: Region, region2: Region) -> None:
    """Display a side-by-side diff between two regions."""
    # Prepare lines from both regions
    prepared = _prepare_diff_lines(region1, region2)
    if prepared is None:
        console.print("  [yellow]Unable to generate diff (failed to read file content)[/yellow]\n")
        return

    lines1, lines2 = prepared

    # Use SequenceMatcher to get diff opcodes
    matcher = difflib.SequenceMatcher(None, lines1, lines2)
    opcodes = matcher.get_opcodes()

    # Check if regions are identical
    if _regions_are_identical(opcodes):
        console.print("  [green]No differences found (regions are identical)[/green]\n")
        return

    # Calculate column width
    terminal_width = console.width
    available_width = terminal_width - 4
    col_width = available_width // 2

    # Display diff
    _print_diff_header(region1, region2, col_width)
    _process_diff_opcodes(lines1, lines2, opcodes, col_width)
    console.print()
