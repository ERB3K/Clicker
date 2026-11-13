# config.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass, field
from typing import List, Optional, Union
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gdk, Gio


AVAILABLE_KEYS = [
    'Enter (Return)', 'Space', 'Meta (Super Key/ Start Key)', 'Escape',
    'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
    'Up', 'Down', 'Left', 'Right',
    'Backspace', 'Delete', 'Insert', 'Home', 'End', 'PageUp', 'PageDown', 'Tab',
    'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
    'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
    '-', '=', '[', ']', '\\', ';', "'", '`', ',', '.', '/'
]

SPECIAL_KEY_MAP = {
    'Enter (Return)': Gdk.KEY_Return,
    'Space': Gdk.KEY_space,
    'Meta (Super Key/ Start Key)': Gdk.KEY_Super_L,
    'Backspace': Gdk.KEY_BackSpace,
    'PageUp': Gdk.KEY_Page_Up,
    'PageDown': Gdk.KEY_Page_Down,
    '-': Gdk.KEY_minus,
    '=': Gdk.KEY_equal,
    '[': Gdk.KEY_bracketleft,
    ']': Gdk.KEY_bracketright,
    '\\': Gdk.KEY_backslash,
    ';': Gdk.KEY_semicolon,
    "'": Gdk.KEY_apostrophe,
    '`': Gdk.KEY_grave,
    ',': Gdk.KEY_comma,
    '.': Gdk.KEY_period,
    '/': Gdk.KEY_slash,
}


def resolve_key(key_name: str) -> int:
    """Resolve a human-readable key name into a Gdk keysym integer."""
    key_name = key_name.strip()
    if key_name in SPECIAL_KEY_MAP:
        return SPECIAL_KEY_MAP[key_name]
    attr = f'KEY_{key_name}'
    if hasattr(Gdk, attr):
        return getattr(Gdk, attr)
    raise ValueError(f"Unknown key name: {key_name!r}")


def parse_pattern(pattern_text: str) -> List[Union[int, float]]:
    """Parse a pattern string into a sequence of Gdk keysyms (int) and delays (float seconds)."""
    steps: List[Union[int, float]] = []
    for raw_line in pattern_text.strip().splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith('delay '):
            delay_val = float(line[6:].strip())
            steps.append(max(0.0, delay_val))
        else:
            steps.append(resolve_key(line))
    return steps


@dataclass
class AutomationConfig:
    """Snapshot of all configuration options for a single automation run."""
    mode: str = 'mouse'  # 'mouse', 'keyboard', 'pattern'
    delay_seconds: float = 5.0

    # Speed settings
    speed_mode: str = 'interval'  # 'interval' or 'cps'
    interval_ms: float = 100.0
    clicks_per_second: float = 10.0

    # Duration settings
    duration_mode: str = 'timed'  # 'timed', 'count', 'infinite'
    duration_minutes: float = 1.0
    duration_seconds: float = 0.0
    repeat_count: int = 100

    # Mouse settings
    mouse_button: str = 'left'  # 'left', 'middle', 'right'
    position_mode: str = 'current'  # 'current' or 'fixed'
    target_x: float = 500.0
    target_y: float = 500.0

    # Keyboard settings
    key_name: str = 'Enter (Return)'
    shift: bool = False
    ctrl: bool = False
    alt: bool = False

    # Pattern settings
    pattern_text: str = ''

    # Shortcut triggers
    start_shortcut: str = 'F6'
    stop_shortcut: str = 'F5'
    toggle_shortcut: str = 'F8'

    @property
    def effective_interval_seconds(self) -> float:
        """Compute the interval in seconds between actions based on speed_mode."""
        if self.speed_mode == 'cps':
            cps = max(0.1, float(self.clicks_per_second))
            return 1.0 / cps
        return max(0.001, float(self.interval_ms) * 0.001)

    @property
    def total_duration_seconds(self) -> Optional[float]:
        """Return total duration in seconds for 'timed' mode, or None for count/infinite."""
        if self.duration_mode == 'timed':
            return max(0.0, float(self.duration_minutes) * 60.0 + float(self.duration_seconds))
        return None

    @property
    def max_repeats(self) -> Optional[int]:
        """Return max repeats for 'count' mode, or None for timed/infinite."""
        if self.duration_mode == 'count':
            return max(1, int(self.repeat_count))
        return None


class SettingsManager:
    """Wrapper around Gio.Settings for reading and binding Clicker settings."""

    SCHEMA_ID = 'net.codelogistics.clicker'

    def __init__(self):
        self.settings = Gio.Settings.new(self.SCHEMA_ID)

    def bind(self, key: str, widget, prop: str, flags=Gio.SettingsBindFlags.DEFAULT):
        self.settings.bind(key, widget, prop, flags)

    def snapshot(self) -> AutomationConfig:
        """Create an AutomationConfig snapshot from current GSettings values."""
        return AutomationConfig(
            mode=self.settings.get_string('mode'),
            delay_seconds=self.settings.get_double('delay-seconds'),
            speed_mode=self.settings.get_string('speed-mode'),
            interval_ms=self.settings.get_double('interval'),
            clicks_per_second=self.settings.get_double('clicks-per-second'),
            duration_mode=self.settings.get_string('duration-mode'),
            duration_minutes=self.settings.get_double('duration-minutes'),
            duration_seconds=self.settings.get_double('duration-seconds'),
            repeat_count=self.settings.get_int('repeat-count'),
            mouse_button=self.settings.get_string('mouse-button'),
            position_mode=self.settings.get_string('position-mode'),
            target_x=self.settings.get_double('target-x'),
            target_y=self.settings.get_double('target-y'),
            key_name=self.settings.get_string('key'),
            shift=self.settings.get_boolean('shift'),
            ctrl=self.settings.get_boolean('ctrl'),
            alt=self.settings.get_boolean('alt'),
            pattern_text=self.settings.get_string('pattern'),
            start_shortcut=self.settings.get_string('start-shortcut'),
            stop_shortcut=self.settings.get_string('stop-shortcut'),
            toggle_shortcut=self.settings.get_string('toggle-shortcut'),
        )
