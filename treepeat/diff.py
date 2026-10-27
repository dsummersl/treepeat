import difflib
from collections.abc import Sequence

from rich.console import Console
from rich.markup import escape

from treepeat.models.similarity import Region
from treepeat.terminal_detect import get_diff_colors

console = Console()


_colors = get_diff_colors()


def _truncate_line(line: str, max_width: int) -> str:

    return line[:max_width] if len(line) > max_width else line


def _read_region_lines(region: Region) -> list[str]:

    try:
        with open(region.path, "r", encoding="utf-8") as f:
            lines = f.readlines()

            return lines[region.start_line - 1 : region.end_line]
    except Exception:
        return []


def _prepare_diff_lines(region1: Region, region2: Region) -> tuple[list[str], list[str]] | None:

    lines1 = _read_region_lines(region1)
    lines2 = _read_region_lines(region2)

    if not lines1 or not lines2:
        return None

    lines1 = [line.rstrip("\n\r") for line in lines1]
    lines2 = [line.rstrip("\n\r") for line in lines2]

    return (lines1, lines2)


def _regions_are_identical(opcodes: Sequence[tuple[str, int, int, int, int]]) -> bool:

    if len(opcodes) != 1:
        return False
    return opcodes[0][0] == "equal"


def _print_equal_lines(
    lines1: list[str], lines2: list[str], i1: int, i2: int, j1: int, j2: int, col_width: int
) -> None:

    for i, j in zip(range(i1, i2), range(j1, j2), strict=False):
        left = _truncate_line(lines1[i], col_width)
        right = _truncate_line(lines2[j], col_width)
        console.print(f"{left:<{col_width}}│{right:<{col_width}}")


def _apply_char_style(text: str, style: str) -> str:

    return f"[{style}]{text}[/{style}]"


def _process_diff_opcode(
    tag: str, left_part: str, right_part: str, bright_left: str, bright_right: str
) -> tuple[str, str]:

    if tag == "equal":
        return left_part, right_part
    if tag == "replace":
        return _apply_char_style(left_part, bright_left), _apply_char_style(right_part, bright_right)
    if tag == "delete":
        return _apply_char_style(left_part, bright_left), ""
    if tag == "insert":
        return "", _apply_char_style(right_part, bright_right)
    return "", ""


def _highlight_char_diff(text1: str, text2: str, col_width: int) -> tuple[str, str]:

    matcher = difflib.SequenceMatcher(None, text1, text2)
    result_left = []
    result_right = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        left_styled, right_styled = _process_diff_opcode(
            tag, text1[i1:i2], text2[j1:j2], _colors.left_fg, _colors.right_fg
        )
        if left_styled:
            result_left.append(left_styled)
        if right_styled:
            result_right.append(right_styled)

    left_text = "".join(result_left)
    right_text = "".join(result_right)
    left_padding = col_width - len(text1)
    right_padding = col_width - len(text2)

    return (
        f"[{_colors.left_bg}]{left_text}{' ' * left_padding}[/{_colors.left_bg}]",
        f"[{_colors.right_bg}]{right_text}{' ' * right_padding}[/{_colors.right_bg}]",
    )


def _print_replaced_lines(
    lines1: list[str], lines2: list[str], i1: int, i2: int, j1: int, j2: int, col_width: int
) -> None:

    max_len = max(i2 - i1, j2 - j1)
    for idx in range(max_len):
        has_left = idx < (i2 - i1)
        has_right = idx < (j2 - j1)

        if has_left and has_right:
            left_line = _truncate_line(lines1[i1 + idx], col_width)
            right_line = _truncate_line(lines2[j1 + idx], col_width)
            left, right = _highlight_char_diff(left_line, right_line, col_width)
            console.print(f"{left}│{right}")
            continue

        if has_left:
            left_line = _truncate_line(lines1[i1 + idx], col_width)
            padding = col_width - len(left_line)
            left = f"[{_colors.left_bg}]{left_line}{' ' * padding}[/{_colors.left_bg}]"
            right = f"[{_colors.right_bg}]{' ' * col_width}[/{_colors.right_bg}]"
            console.print(f"{left}│{right}")
            continue

        right_line = _truncate_line(lines2[j1 + idx], col_width)
        padding = col_width - len(right_line)
        left = f"[{_colors.left_bg}]{' ' * col_width}[/{_colors.left_bg}]"
        right = f"[{_colors.right_bg}]{right_line}{' ' * padding}[/{_colors.right_bg}]"
        console.print(f"{left}│{right}")


def _print_deleted_lines(lines1: list[str], i1: int, i2: int, col_width: int) -> None:

    for i in range(i1, i2):
        left_line = _truncate_line(lines1[i], col_width)

        padding = col_width - len(left_line)
        left = f"[{_colors.left_bg}]{left_line}{' ' * padding}[/{_colors.left_bg}]"
        console.print(f"{left}│{' ' * col_width}")


def _print_inserted_lines(lines2: list[str], j1: int, j2: int, col_width: int) -> None:

    for j in range(j1, j2):
        right_line = _truncate_line(lines2[j], col_width)

        padding = col_width - len(right_line)
        right = f"[{_colors.right_bg}]{right_line}{' ' * padding}[/{_colors.right_bg}]"
        console.print(f"{' ' * col_width}│{right}")


def _print_diff_header(region1: Region, region2: Region, col_width: int) -> None:

    console.print("[bold]Diff:[/bold]")
    header1 = f"{escape(str(region1.path))}:{region1.start_line}-{region1.end_line}"
    header2 = f"{escape(str(region2.path))}:{region2.start_line}-{region2.end_line}"
    console.print(f"[dim]{header1:<{col_width}}[/dim]│[dim]{header2:<{col_width}}[/dim]")
    console.print(f"{'-' * col_width}│{'-' * col_width}")


def _process_diff_opcodes(
    lines1: list[str], lines2: list[str], opcodes: Sequence[tuple[str, int, int, int, int]], col_width: int
) -> None:

    handlers = {
        "equal": lambda i1, i2, j1, j2: _print_equal_lines(lines1, lines2, i1, i2, j1, j2, col_width),
        "replace": lambda i1, i2, j1, j2: _print_replaced_lines(lines1, lines2, i1, i2, j1, j2, col_width),
        "delete": lambda i1, i2, j1, j2: _print_deleted_lines(lines1, i1, i2, col_width),
        "insert": lambda i1, i2, j1, j2: _print_inserted_lines(lines2, j1, j2, col_width),
    }

    for tag, i1, i2, j1, j2 in opcodes:
        handler = handlers.get(tag)
        if handler:
            handler(i1, i2, j1, j2)


def display_diff(region1: Region, region2: Region) -> None:

    prepared = _prepare_diff_lines(region1, region2)
    if prepared is None:
        console.print("[yellow]Unable to generate diff (failed to read file content)[/yellow]\n")
        return

    lines1, lines2 = prepared

    matcher = difflib.SequenceMatcher(None, lines1, lines2)
    opcodes = matcher.get_opcodes()

    if _regions_are_identical(opcodes):
        console.print("[green]No differences found (regions are identical)[/green]\n")
        return

    terminal_width = console.width
    col_width = terminal_width // 2

    _print_diff_header(region1, region2, col_width)
    _process_diff_opcodes(lines1, lines2, opcodes, col_width)
    console.print()
