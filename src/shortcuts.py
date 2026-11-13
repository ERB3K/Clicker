# shortcuts.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Callable, Optional

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Xdp', '1.0')
from gi.repository import Adw, Gdk, GLib, Gtk, Xdp

from .config import SettingsManager


def format_Trigger(keyval: int, state: Gdk.ModifierType) -> Optional[str]:
    """Convert a GTK keyval and modifier state into an XDG/GTK accelerator string."""
    # Ignore standalone modifier key presses
    if keyval in (
        Gdk.KEY_Shift_L, Gdk.KEY_Shift_R,
        Gdk.KEY_Control_L, Gdk.KEY_Control_R,
        Gdk.KEY_Alt_L, Gdk.KEY_Alt_R,
        Gdk.KEY_Super_L, Gdk.KEY_Super_R,
        Gdk.KEY_Meta_L, Gdk.KEY_Meta_R,
    ):
        return None

    mods = state & Gtk.accelerator_get_default_mod_mask()
    accel = Gtk.accelerator_name(keyval, mods)
    return accel if accel else None


class ShortcutsManager:
    """Manages both Wayland XDG Global Shortcuts and window-level shortcut triggers."""

    def __init__(
        self,
        window: Gtk.Window,
        settings_manager: SettingsManager,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_toggle: Callable[[], None],
    ):
        self.window = window
        self.settings = settings_manager.settings
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_toggle = on_toggle

        self.shortcuts_portal = Xdp.Portal()
        self.shortcuts_session = None

        self._setup_window_key_controller()
        self._init_portal_session()

    def _setup_window_key_controller(self):
        """Attach an in-window key controller so shortcuts also work without portal support."""
        controller = Gtk.EventControllerKey()
        controller.connect('key-pressed', self._on_window_key_pressed)
        self.window.add_controller(controller)

    def _on_window_key_pressed(self, controller, keyval, keycode, state) -> bool:
        # Avoid triggering start/stop while typing in an editable widget (e.g. SpinButton or Pattern view)
        focus = self.window.get_focus()
        if isinstance(focus, (Gtk.Text, Gtk.TextView)) and keyval not in (
            Gdk.KEY_F1, Gdk.KEY_F2, Gdk.KEY_F3, Gdk.KEY_F4,
            Gdk.KEY_F5, Gdk.KEY_F6, Gdk.KEY_F7, Gdk.KEY_F8,
            Gdk.KEY_F9, Gdk.KEY_F10, Gdk.KEY_F11, Gdk.KEY_F12,
            Gdk.KEY_Escape,
        ):
            return False

        trigger = format_Trigger(keyval, state)
        if not trigger:
            return False

        start_sc = self.settings.get_string('start-shortcut')
        stop_sc = self.settings.get_string('stop-shortcut')
        toggle_sc = self.settings.get_string('toggle-shortcut')

        if self._triggers_match(trigger, stop_sc):
            self.on_stop()
            return True
        if self._triggers_match(trigger, start_sc):
            self.on_start()
            return True
        if self._triggers_match(trigger, toggle_sc):
            self.on_toggle()
            return True
        return False

    @staticmethod
    def _triggers_match(a: str, b: str) -> bool:
        if not a or not b:
            return False
        ok_a, key_a, mod_a = Gtk.accelerator_parse(a)
        ok_b, key_b, mod_b = Gtk.accelerator_parse(b)
        if ok_a and ok_b and key_a != 0 and key_b != 0:
            return key_a == key_b and mod_a == mod_b
        return a.lower() == b.lower()

    def _init_portal_session(self):
        def on_session_created(portal, result, data):
            try:
                self.shortcuts_session = portal.create_global_shortcuts_session_finish(result)
            except GLib.Error as err:
                print(f"[CLICKER SHORTCUTS] {err.message}")
                return
            self.shortcuts_session.connect('activated', self._on_portal_shortcut_activated)
            self.rebind_portal_shortcuts()

        try:
            self.shortcuts_portal.create_global_shortcuts_session(
                None,
                on_session_created,
                None,
            )
        except Exception as exc:
            print(
                exc,
                "[CLICKER] Global shortcuts portal could not be initialised; using window shortcuts fallback.",
            )

    def rebind_portal_shortcuts(self):
        """Bind or update the global shortcuts with the XDG GlobalShortcuts portal."""
        if not self.shortcuts_session:
            return

        start_trigger = self.settings.get_string('start-shortcut') or 'F6'
        stop_trigger = self.settings.get_string('stop-shortcut') or 'F5'
        toggle_trigger = self.settings.get_string('toggle-shortcut') or 'F8'

        shortcuts = [
            Xdp.GlobalShortcut.new(
                'start-automation',
                _('Start automation'),
                start_trigger,
            ),
            Xdp.GlobalShortcut.new(
                'stop-automation',
                _('Stop the ongoing automation'),
                stop_trigger,
            ),
            Xdp.GlobalShortcut.new(
                'toggle-automation',
                _('Toggle (Start / Stop) automation'),
                toggle_trigger,
            ),
        ]
        try:
            self.shortcuts_session.bind_shortcuts(shortcuts, None, None, None, None)
        except Exception as exc:
            print(f"[CLICKER SHORTCUTS] Failed to bind shortcuts: {exc}")

    def _on_portal_shortcut_activated(self, session, shortcut_id: str, timestamp, options):
        if shortcut_id == 'start-automation':
            GLib.idle_add(self.on_start)
        elif shortcut_id == 'stop-automation':
            self.on_stop()
        elif shortcut_id == 'toggle-automation':
            GLib.idle_add(self.on_toggle)


class ShortcutRecorderDialog(Adw.Window):
    """Dialog allowing the user to configure Start, Stop, and Toggle shortcuts."""

    def __init__(
        self,
        parent: Gtk.Window,
        settings_manager: SettingsManager,
        shortcuts_manager: ShortcutsManager,
    ):
        super().__init__(
            transient_for=parent,
            modal=True,
            title=_('Configure Shortcuts'),
            default_width=440,
            default_height=340,
        )
        self.settings = settings_manager.settings
        self.shortcuts_manager = shortcuts_manager
        self._recording_key: Optional[str] = None
        self._recording_button: Optional[Gtk.Button] = None

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)

        group = Adw.PreferencesGroup(
            title=_('Automation Shortcuts'),
            description=_(
                'Click a shortcut button and press any key combination to change it. '
                'Press Escape while recording to cancel.'
            ),
        )

        self.buttons = {}
        for setting_key, title, subtitle in [
            ('start-shortcut', _('Start Automation'), _('Begins clicking or pressing keys')),
            ('stop-shortcut', _('Stop Automation'), _('Immediately stops ongoing automation')),
            ('toggle-shortcut', _('Toggle Start / Stop'), _('Starts when idle, stops when running')),
        ]:
            row = Adw.ActionRow(title=title, subtitle=subtitle)
            btn = Gtk.Button(label=self._display_label(self.settings.get_string(setting_key)))
            btn.set_valign(Gtk.Align.CENTER)
            btn.add_css_class('flat')
            btn.connect('clicked', self._on_record_clicked, setting_key)
            row.add_suffix(btn)
            group.add(row)
            self.buttons[setting_key] = btn

        content.append(group)

        rebind_btn = Gtk.Button(label=_('Apply & Re-register Global Shortcuts'))
        rebind_btn.add_css_class('suggested-action')
        rebind_btn.set_halign(Gtk.Align.CENTER)
        rebind_btn.connect('clicked', self._on_apply_clicked)
        content.append(rebind_btn)

        toolbar_view.set_content(content)
        self.set_content(toolbar_view)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect('key-pressed', self._on_key_pressed)
        self.add_controller(key_ctrl)

    @staticmethod
    def _display_label(accel: str) -> str:
        ok, keyval, mods = Gtk.accelerator_parse(accel)
        if ok and keyval != 0:
            return Gtk.accelerator_get_label(keyval, mods)
        return accel or _('Unset')

    def _on_record_clicked(self, button: Gtk.Button, setting_key: str):
        if self._recording_button and self._recording_key:
            prev_val = self.settings.get_string(self._recording_key)
            self._recording_button.set_label(self._display_label(prev_val))
            self._recording_button.remove_css_class('suggested-action')

        self._recording_key = setting_key
        self._recording_button = button
        button.set_label(_('Press a key...'))
        button.add_css_class('suggested-action')

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        if not self._recording_key or not self._recording_button:
            return False

        if keyval == Gdk.KEY_Escape:
            prev_val = self.settings.get_string(self._recording_key)
            self._recording_button.set_label(self._display_label(prev_val))
            self._recording_button.remove_css_class('suggested-action')
            self._recording_key = None
            self._recording_button = None
            return True

        trigger = format_Trigger(keyval, state)
        if not trigger:
            return False

        self.settings.set_string(self._recording_key, trigger)
        self._recording_button.set_label(self._display_label(trigger))
        self._recording_button.remove_css_class('suggested-action')
        self._recording_key = None
        self._recording_button = None
        return True

    def _on_apply_clicked(self, _button):
        self.shortcuts_manager.rebind_portal_shortcuts()
        self.close()
