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
    r, g, b = r / 255.0, g / 255.0, b / 255.0

    # Apply sRGB gamma correction
    def correct(c: float) -> float:
        if c <= 0.03928:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4

    r, g, b = correct(r), correct(g), correct(b)

    # Calculate luminance
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _parse_osc11_response(response: str) -> tuple[int, int, int] | None:
    """Parse OSC 11 response to extract RGB values.

    Expected format: \033]11;rgb:RRRR/GGGG/BBBB\033\\
    or variants with different terminators.
    """
    try:
        # Look for rgb: pattern
        if 'rgb:' not in response:
            return None

        # Extract the RGB part
        rgb_part = response.split('rgb:')[1]
        # Remove any escape sequences or terminators
        rgb_part = rgb_part.split('\033')[0].split('\007')[0]

        # Parse RGB values (format is typically RRRR/GGGG/BBBB in hex)
        parts = rgb_part.split('/')
        if len(parts) != 3:
            return None

        # Convert from hex to 0-255 range
        # Values are typically 16-bit (0000-FFFF), we need 8-bit (00-FF)
        r = int(parts[0][:2], 16) if len(parts[0]) >= 2 else int(parts[0], 16)
        g = int(parts[1][:2], 16) if len(parts[1]) >= 2 else int(parts[1], 16)
        b = int(parts[2][:2], 16) if len(parts[2]) >= 2 else int(parts[2], 16)

        return (r, g, b)
    except (ValueError, IndexError):
        return None


def _detect_via_osc11() -> BackgroundMode:
    """Detect background using OSC 11 escape sequence.

    This queries the terminal for its background color.
    Returns UNKNOWN if detection fails.
    """
    # Only works if stdout is a terminal
    if not sys.stdout.isatty() or not sys.stdin.isatty():
        return BackgroundMode.UNKNOWN

    try:
        # Save current terminal settings
        old_settings = termios.tcgetattr(sys.stdin.fileno())

        try:
            # Set terminal to raw mode to read response
            tty.setraw(sys.stdin.fileno())

            # Send OSC 11 query
            sys.stdout.write('\033]11;?\033\\')
            sys.stdout.flush()

            # Wait for response with timeout (100ms)
            response = ""
            timeout = 0.1

            while True:
                # Check if data is available
                ready, _, _ = select.select([sys.stdin], [], [], timeout)
                if not ready:
                    break

                char = sys.stdin.read(1)
                response += char

                # Check for end of response (either \033\\ or \007)
                if response.endswith('\033\\') or response.endswith('\007'):
                    break

                # Safety: don't read forever
                if len(response) > 100:
                    break

            # Parse the response
            rgb = _parse_osc11_response(response)
            if rgb:
                r, g, b = rgb
                luminance = _calculate_luminance(r, g, b)

                # Threshold: > 0.5 is light, <= 0.5 is dark
                return BackgroundMode.LIGHT if luminance > 0.5 else BackgroundMode.DARK

            return BackgroundMode.UNKNOWN

        finally:
            # Restore terminal settings
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)

    except (OSError, termios.error):
        # Terminal control not available (e.g., in tests, pipes, etc.)
        return BackgroundMode.UNKNOWN


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

        # Typically:
        # 0-7: dark colors (black, red, green, yellow, blue, magenta, cyan, white)
        # 8-15: bright versions (light background)
        # 15 is often white, 0 is black

        if bg_code == 0:  # Black
            return BackgroundMode.DARK
        elif bg_code == 15 or bg_code == 7:  # White or light gray
            return BackgroundMode.LIGHT
        elif bg_code >= 8:  # Bright colors
            return BackgroundMode.LIGHT
        else:  # Dark colors
            return BackgroundMode.DARK

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
        """Initialize diff color scheme.

        Args:
            left_bg: Background color for left side (deletions/changes)
            right_bg: Background color for right side (additions/changes)
            left_fg: Foreground color for character-level diffs on left
            right_fg: Foreground color for character-level diffs on right
        """
        self.left_bg = left_bg
        self.right_bg = right_bg
        self.left_fg = left_fg
        self.right_fg = right_fg


# Color schemes for different background modes
LIGHT_MODE_COLORS = DiffColors(
    left_bg="on rgb(255,235,235)",    # Soft pink background
    right_bg="on rgb(235,255,235)",   # Soft mint background
    left_fg="bold rgb(220,0,0)",      # Bright red text
    right_fg="bold rgb(0,180,0)",     # Bright green text
)

DARK_MODE_COLORS = DiffColors(
    left_bg="on rgb(60,20,20)",       # Dark red background
    right_bg="on rgb(20,60,20)",      # Dark green background
    left_fg="bold rgb(255,120,120)",  # Light red text
    right_fg="bold rgb(120,255,120)", # Light green text
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
