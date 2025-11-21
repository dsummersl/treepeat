"""Terminal background color detection utilities."""

import os
import sys
import select
import termios
import tty
from enum import Enum


class BackgroundMode(Enum):
    """Terminal background mode."""
    LIGHT = "light"
    DARK = "dark"
    UNKNOWN = "unknown"


def _calculate_luminance(r: int, g: int, b: int) -> float:
    """Calculate relative luminance using sRGB formula.

    Returns a value between 0 (black) and 1 (white).
    """
    # Normalize to 0-1
    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0

    # Apply sRGB gamma correction
    def correct(c: float) -> float:
        if c <= 0.03928:
            return c / 12.92
        result: float = ((c + 0.055) / 1.055) ** 2.4
        return result

    r_corrected = correct(r_norm)
    g_corrected = correct(g_norm)
    b_corrected = correct(b_norm)

    # Calculate luminance
    return 0.2126 * r_corrected + 0.7152 * g_corrected + 0.0722 * b_corrected


def _extract_rgb_part(response: str) -> str | None:
    """Extract RGB part from OSC 11 response."""
    if 'rgb:' not in response:
        return None
    rgb_part = response.split('rgb:')[1]
    # Remove any escape sequences or terminators
    return rgb_part.split('\033')[0].split('\007')[0]


def _parse_hex_component(hex_str: str) -> int:
    """Parse a hex color component to 0-255 range."""
    # Values are typically 16-bit (0000-FFFF), we need 8-bit (00-FF)
    if len(hex_str) >= 2:
        return int(hex_str[:2], 16)
    return int(hex_str, 16)


def _parse_osc11_response(response: str) -> tuple[int, int, int] | None:
    """Parse OSC 11 response to extract RGB values.

    Expected format: \033]11;rgb:RRRR/GGGG/BBBB\033\\
    or variants with different terminators.
    """
    try:
        rgb_part = _extract_rgb_part(response)
        if not rgb_part:
            return None

        # Parse RGB values (format is typically RRRR/GGGG/BBBB in hex)
        parts = rgb_part.split('/')
        if len(parts) != 3:
            return None

        r = _parse_hex_component(parts[0])
        g = _parse_hex_component(parts[1])
        b = _parse_hex_component(parts[2])

        return (r, g, b)
    except (ValueError, IndexError):
        return None


def _is_response_complete(response: str, max_length: int) -> bool:
    """Check if terminal response is complete."""
    if response.endswith('\033\\') or response.endswith('\007'):
        return True
    if len(response) >= max_length:
        return True
    return False


def _read_terminal_response(timeout: float = 0.1, max_length: int = 100) -> str:
    """Read response from terminal with timeout. """
    response = ""
    while True:
        # Check if data is available
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if not ready:
            break

        char = sys.stdin.read(1)
        response += char

        if _is_response_complete(response, max_length):
            break

    return response


def _rgb_to_background_mode(rgb: tuple[int, int, int]) -> BackgroundMode:
    """Convert RGB values to background mode based on luminance."""
    r, g, b = rgb
    luminance = _calculate_luminance(r, g, b)
    # Threshold: > 0.5 is light, <= 0.5 is dark
    return BackgroundMode.LIGHT if luminance > 0.5 else BackgroundMode.DARK


def _query_terminal_background() -> str:
    """Query terminal for background color using OSC 11."""
    sys.stdout.write('\033]11;?\033\\')
    sys.stdout.flush()
    return _read_terminal_response()


def _detect_via_osc11() -> BackgroundMode:
    """Detect background using OSC 11 escape sequence.

    This queries the terminal for its background color.
    Returns UNKNOWN if detection fails.
    """
    # Only works if stdout is a terminal
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
    """Interpret ANSI color code to determine background mode. """
    # 0: black (dark)
    # 7: white/light gray (light)
    # 15: bright white (light)
    # 8-15: bright colors (light background)
    # 0-7: dark colors (dark background)
    if bg_code == 0:
        return BackgroundMode.DARK
    if bg_code in (7, 15):
        return BackgroundMode.LIGHT
    if bg_code >= 8:
        return BackgroundMode.LIGHT
    return BackgroundMode.DARK


def _detect_via_colorfgbg() -> BackgroundMode:
    """Detect background using COLORFGBG environment variable.

    Format is typically "foreground;background" with color codes 0-15.
    Lower numbers (0-7) are dark, higher (8-15) are light for background.
    """
    colorfgbg = os.environ.get('COLORFGBG', '')
    if not colorfgbg:
        return BackgroundMode.UNKNOWN

    try:
        # Parse format: "foreground;background"
        parts = colorfgbg.split(';')
        if len(parts) < 2:
            return BackgroundMode.UNKNOWN

        bg_code = int(parts[-1])  # Background is the last part
        return _interpret_color_code(bg_code)

    except (ValueError, IndexError):
        return BackgroundMode.UNKNOWN


def detect_background() -> BackgroundMode:
    """Detect terminal background mode (light or dark).

    Tries multiple detection methods in order:
    1. OSC 11 escape sequence query (most accurate)
    2. COLORFGBG environment variable
    3. Defaults to DARK (most common modern terminal default)

    Returns:
        BackgroundMode enum indicating LIGHT, DARK, or UNKNOWN
    """
    # Try OSC 11 first (most accurate)
    mode = _detect_via_osc11()
    if mode != BackgroundMode.UNKNOWN:
        return mode

    # Try COLORFGBG
    mode = _detect_via_colorfgbg()
    if mode != BackgroundMode.UNKNOWN:
        return mode

    # Default to dark (most common nowadays)
    return BackgroundMode.DARK


class DiffColors:
    """Color scheme for diff display."""

    def __init__(
        self,
        left_bg: str,
        right_bg: str,
        left_fg: str,
        right_fg: str,
    ):
        """Initialize diff color scheme. """
        self.left_bg = left_bg
        self.right_bg = right_bg
        self.left_fg = left_fg
        self.right_fg = right_fg


# Color schemes for different background modes
LIGHT_MODE_COLORS = DiffColors(
    left_bg="on rgb(255,235,235)",    # Soft pink background
    right_bg="on rgb(235,255,235)",   # Soft mint background
    left_fg="bold rgb(120,25,25)",      # Muted red text
    right_fg="bold rgb(0,100,0)",     # Muted green text
)

DARK_MODE_COLORS = DiffColors(
    left_bg="on rgb(60,20,20)",       # Dark red background
    right_bg="on rgb(20,60,20)",      # Dark green background
    left_fg="bold rgb(170,40,40)",  # Muted light red text
    right_fg="bold rgb(40,170,40)", # Muted light green text

)


def get_diff_colors() -> DiffColors:
    """Get appropriate diff colors based on terminal background.

    Returns:
        DiffColors instance with colors appropriate for current terminal
    """
    mode = detect_background()

    if mode == BackgroundMode.LIGHT:
        return LIGHT_MODE_COLORS
    else:
        # Use dark mode colors for DARK or UNKNOWN
        return DARK_MODE_COLORS
