import os
import select
import sys
import termios
import tty
from enum import Enum


class BackgroundMode(Enum):
    LIGHT = "light"
    DARK = "dark"
    UNKNOWN = "unknown"


def _calculate_luminance(r: int, g: int, b: int) -> float:

    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0

    def correct(c: float) -> float:
        if c <= 0.03928:
            return c / 12.92
        result: float = ((c + 0.055) / 1.055) ** 2.4
        return result

    r_corrected = correct(r_norm)
    g_corrected = correct(g_norm)
    b_corrected = correct(b_norm)

    return 0.2126 * r_corrected + 0.7152 * g_corrected + 0.0722 * b_corrected


def _extract_rgb_part(response: str) -> str | None:

    if "rgb:" not in response:
        return None
    rgb_part = response.split("rgb:")[1]

    return rgb_part.split("\033")[0].split("\007")[0]


def _parse_hex_component(hex_str: str) -> int:

    if len(hex_str) >= 2:
        return int(hex_str[:2], 16)
    return int(hex_str, 16)


def _parse_osc11_response(response: str) -> tuple[int, int, int] | None:

    try:
        rgb_part = _extract_rgb_part(response)
        if not rgb_part:
            return None

        parts = rgb_part.split("/")
        if len(parts) != 3:
            return None

        r = _parse_hex_component(parts[0])
        g = _parse_hex_component(parts[1])
        b = _parse_hex_component(parts[2])

        return (r, g, b)
    except (ValueError, IndexError):
        return None


def _is_response_complete(response: str, max_length: int) -> bool:

    if response.endswith("\033\\") or response.endswith("\007"):
        return True
    if len(response) >= max_length:
        return True
    return False


def _read_terminal_response(timeout: float = 0.1, max_length: int = 100) -> str:

    response = ""
    while True:
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if not ready:
            break

        char = sys.stdin.read(1)
        response += char

        if _is_response_complete(response, max_length):
            break

    return response


def _rgb_to_background_mode(rgb: tuple[int, int, int]) -> BackgroundMode:

    r, g, b = rgb
    luminance = _calculate_luminance(r, g, b)

    return BackgroundMode.LIGHT if luminance > 0.5 else BackgroundMode.DARK


def _query_terminal_background() -> str:

    sys.stdout.write("\033]11;?\033\\")
    sys.stdout.flush()
    return _read_terminal_response()


def _detect_via_osc11() -> BackgroundMode:

    if not sys.stdout.isatty() or not sys.stdin.isatty():
        return BackgroundMode.UNKNOWN

    try:
        old_settings = termios.tcgetattr(sys.stdin.fileno())
    except (OSError, termios.error):
        return BackgroundMode.UNKNOWN

    try:
        tty.setraw(sys.stdin.fileno())
        response = _query_terminal_background()
        rgb = _parse_osc11_response(response)

        return _rgb_to_background_mode(rgb) if rgb else BackgroundMode.UNKNOWN
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)


def _interpret_color_code(bg_code: int) -> BackgroundMode:

    if bg_code == 0:
        return BackgroundMode.DARK
    if bg_code in (7, 15):
        return BackgroundMode.LIGHT
    if bg_code >= 8:
        return BackgroundMode.LIGHT
    return BackgroundMode.DARK


def _detect_via_colorfgbg() -> BackgroundMode:

    colorfgbg = os.environ.get("COLORFGBG", "")
    if not colorfgbg:
        return BackgroundMode.UNKNOWN

    try:
        parts = colorfgbg.split(";")
        if len(parts) < 2:
            return BackgroundMode.UNKNOWN

        bg_code = int(parts[-1])
        return _interpret_color_code(bg_code)

    except (ValueError, IndexError):
        return BackgroundMode.UNKNOWN


def detect_background() -> BackgroundMode:

    mode = _detect_via_osc11()
    if mode != BackgroundMode.UNKNOWN:
        return mode

    mode = _detect_via_colorfgbg()
    if mode != BackgroundMode.UNKNOWN:
        return mode

    return BackgroundMode.DARK


class DiffColors:
    def __init__(
        self,
        left_bg: str,
        right_bg: str,
        left_fg: str,
        right_fg: str,
    ):

        self.left_bg = left_bg
        self.right_bg = right_bg
        self.left_fg = left_fg
        self.right_fg = right_fg


LIGHT_MODE_COLORS = DiffColors(
    left_bg="on rgb(255,235,235)",
    right_bg="on rgb(235,255,235)",
    left_fg="bold rgb(120,25,25)",
    right_fg="bold rgb(0,100,0)",
)

DARK_MODE_COLORS = DiffColors(
    left_bg="on rgb(60,20,20)",
    right_bg="on rgb(20,60,20)",
    left_fg="bold rgb(170,40,40)",
    right_fg="bold rgb(40,170,40)",
)


def get_diff_colors() -> DiffColors:

    mode = detect_background()

    if mode == BackgroundMode.LIGHT:
        return LIGHT_MODE_COLORS
    else:
        return DARK_MODE_COLORS
