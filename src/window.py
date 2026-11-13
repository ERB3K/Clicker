# window.py
#
# Copyright 2026 Erick Bueno (ERB3K)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('GtkSource', '5')
from gi.repository import Adw, Gio, GLib, Gtk, GtkSource

from .config import AVAILABLE_KEYS, SettingsManager
from .engine import AutomationEngine
from .location_picker import LocationPickerOverlay
from .shortcuts import ShortcutRecorderDialog, ShortcutsManager


class vsep(Gtk.Separator):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class('spacer')


class hsep(Gtk.Separator):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.add_css_class('spacer')


class ClickerWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'ClickerWindow'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(760, 420)
        self.set_title(_('Clicker'))

        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.settings

        self.engine = AutomationEngine(
            on_state_changed=self._on_engine_state_changed,
            on_error=self._on_engine_error,
        )

        toolbarview = Adw.ToolbarView()
        headerbar = self._build_headerbar()
        toolbarview.add_top_bar(headerbar)

        self.view_stack = Adw.ViewStack()
        view_stack_bar = Adw.ViewSwitcherBar()
        view_stack_bar.set_reveal(True)
        view_stack_bar.set_stack(self.view_stack)
        toolbarview.add_top_bar(view_stack_bar)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.append(vsep())

        self.view_stack.add_titled_with_icon(
            self._build_mouse_page(), 'mouse', _('Mouse'), 'input-mouse-symbolic'
        )
        self.view_stack.add_titled_with_icon(
            self._build_keyboard_page(), 'keyboard', _('Keyboard'), 'input-keyboard-symbolic'
        )
        self.view_stack.add_titled_with_icon(
            self._build_pattern_page(), 'pattern', _('Pattern'), 'code-symbolic'
        )

        main_box.append(self.view_stack)
        main_box.append(vsep())

        self.status_label = Gtk.Label()
        self.status_label.add_css_class('dim-label')
        self.status_label.set_wrap(True)
        self.status_label.set_justify(Gtk.Justification.CENTER)
        main_box.append(self.status_label)

        toolbarview.set_content(main_box)
        toolbarview.add_bottom_bar(self._build_bottom_bar())

        self.set_content(toolbarview)

        self._bind_settings()
        self._update_status_hint()

        self.shortcuts_manager = ShortcutsManager(
            window=self,
            settings_manager=self.settings_manager,
            on_start=self.on_start_requested,
            on_stop=self.on_stop_requested,
            on_toggle=self.on_toggle_requested,
        )

        self.show_warning_dialog()

    def _build_headerbar(self) -> Adw.HeaderBar:
        headerbar = Adw.HeaderBar()

        toolbar = Gtk.Box(spacing=6)
        toolbar.append(hsep())

        # Start Delay (in seconds)
        delay_img = Gtk.Image.new_from_icon_name('delay-long-symbolic')
        delay_img.set_tooltip_text(_('Start Delay (seconds)'))
        toolbar.append(delay_img)

        self.delay_spin = Gtk.SpinButton.new_with_range(0, 3600, 1)
        self.delay_spin.set_digits(1)
        self.delay_spin.set_value(5.0)
        self.delay_spin.set_tooltip_text(_('Delay in seconds before automation starts'))
        toolbar.append(self.delay_spin)

        delay_unit = Gtk.Label()
        delay_unit.set_markup('<b>{}</b>'.format(_('s delay')))
        toolbar.append(delay_unit)

        toolbar.append(hsep())

        # Speed Mode selector: Interval (ms) vs Speed (CPS)
        speed_img = Gtk.Image.new_from_icon_name('hourglass-symbolic')
        speed_img.set_tooltip_text(_('Repeat speed / interval'))
        toolbar.append(speed_img)

        self.speed_mode_dropdown = Gtk.DropDown.new_from_strings([
            _('Interval (ms)'),
            _('Speed (CPS)'),
        ])
        toolbar.append(self.speed_mode_dropdown)

        self.interval_spinbox = Gtk.SpinButton.new_with_range(1, 3600000, 10)
        self.interval_spinbox.set_value(100)
        self.interval_spinbox.set_tooltip_text(_('Milliseconds between repeats'))
        toolbar.append(self.interval_spinbox)

        self.cps_spinbox = Gtk.SpinButton.new_with_range(0.1, 500.0, 1.0)
        self.cps_spinbox.set_digits(1)
        self.cps_spinbox.set_value(10.0)
        self.cps_spinbox.set_tooltip_text(_('Clicks / repeats per second'))
        toolbar.append(self.cps_spinbox)

        headerbar.pack_start(toolbar)

        # Start / Stop button
        self.start_button = Gtk.Button()
        self.start_button.set_icon_name('media-playback-start-symbolic')
        self.start_button.set_tooltip_text(_('Start'))
        self.start_button.add_css_class('suggested-action')
        self.start_button.connect('clicked', lambda *_: self.on_toggle_requested())
        headerbar.pack_end(self.start_button)

        # Configure Shortcuts button
        shortcuts_button = Gtk.Button()
        shortcuts_button.set_icon_name('preferences-desktop-keyboard-shortcuts-symbolic')
        shortcuts_button.set_tooltip_text(_('Configure Start / Stop Shortcuts'))
        shortcuts_button.connect('clicked', self._on_configure_shortcuts)
        headerbar.pack_end(shortcuts_button)

        # About button
        about_button = Gtk.Button()
        about_button.set_icon_name('help-about-symbolic')
        about_button.set_tooltip_text(_('About'))
        about_button.connect('clicked', self.get_application().on_about_action, None)
        headerbar.pack_end(about_button)

        return headerbar

    def _build_mouse_page(self) -> Gtk.Widget:
        mouse_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        mouse_box.set_margin_top(8)
        mouse_box.set_margin_bottom(8)
        mouse_box.set_margin_start(16)
        mouse_box.set_margin_end(16)

        # Mouse Button selection (Left / Middle / Right)
        buttons_box = Gtk.Box()
        buttons_box.add_css_class('linked')
        buttons_box.set_halign(Gtk.Align.CENTER)
        buttons_box.set_vexpand(True)

        self.left_button = Gtk.ToggleButton()
        self.left_button.add_css_class('flat')
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        left_img = Gtk.Image.new_from_icon_name('mouse-primary-click-symbolic')
        left_img.set_pixel_size(96)
        left_box.append(left_img)
        left_box.append(Gtk.Label(label=_('Left')))
        self.left_button.set_child(left_box)
        self.left_button.set_active(True)
        buttons_box.append(self.left_button)

        self.middle_button = Gtk.ToggleButton()
        self.middle_button.add_css_class('flat')
        mid_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        mid_img = Gtk.Image.new_from_icon_name('input-mouse-symbolic')
        mid_img.set_pixel_size(96)
        mid_box.append(mid_img)
        mid_box.append(Gtk.Label(label=_('Middle')))
        self.middle_button.set_child(mid_box)
        self.middle_button.set_group(self.left_button)
        buttons_box.append(self.middle_button)

        self.right_button = Gtk.ToggleButton()
        self.right_button.add_css_class('flat')
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        right_img = Gtk.Image.new_from_icon_name('mouse-secondary-click-symbolic')
        right_img.set_pixel_size(96)
        right_box.append(right_img)
        right_box.append(Gtk.Label(label=_('Right')))
        self.right_button.set_child(right_box)
        self.right_button.set_group(self.left_button)
        buttons_box.append(self.right_button)

        mouse_box.append(buttons_box)

        # Click Position Mode: Current Cursor vs Picked Position
        pos_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        pos_frame.set_halign(Gtk.Align.CENTER)

        pos_mode_box = Gtk.Box(spacing=8)
        pos_mode_box.set_halign(Gtk.Align.CENTER)

        pos_label = Gtk.Label()
        pos_label.set_markup('<b>{}</b>'.format(_('Click Position:')))
        pos_mode_box.append(pos_label)

        pos_toggle_box = Gtk.Box()
        pos_toggle_box.add_css_class('linked')

        self.pos_current_btn = Gtk.ToggleButton(label=_('Current Cursor Location'))
        self.pos_current_btn.set_active(True)
        pos_toggle_box.append(self.pos_current_btn)

        self.pos_fixed_btn = Gtk.ToggleButton(label=_('Fixed Position (X, Y)'))
        self.pos_fixed_btn.set_group(self.pos_current_btn)
        pos_toggle_box.append(self.pos_fixed_btn)

        pos_mode_box.append(pos_toggle_box)
        pos_frame.append(pos_mode_box)

        # Coordinates & Location Picker row
        self.coords_row = Gtk.Box(spacing=8)
        self.coords_row.set_halign(Gtk.Align.CENTER)

        x_lbl = Gtk.Label()
        x_lbl.set_markup('<b>X:</b>')
        self.coords_row.append(x_lbl)

        self.target_x_spin = Gtk.SpinButton.new_with_range(0, 16384, 1)
        self.target_x_spin.set_digits(1)
        self.target_x_spin.set_value(500.0)
        self.coords_row.append(self.target_x_spin)

        y_lbl = Gtk.Label()
        y_lbl.set_markup('<b>Y:</b>')
        self.coords_row.append(y_lbl)

        self.target_y_spin = Gtk.SpinButton.new_with_range(0, 16384, 1)
        self.target_y_spin.set_digits(1)
        self.target_y_spin.set_value(500.0)
        self.coords_row.append(self.target_y_spin)

        self.pick_location_btn = Gtk.Button(label=_('Pick Location'))
        self.pick_location_btn.set_icon_name('find-location-symbolic')
        self.pick_location_btn.set_tooltip_text(
            _('Open fullscreen crosshair picker to choose click coordinates')
        )
        self.pick_location_btn.connect('clicked', self._on_pick_location_clicked)
        self.coords_row.append(self.pick_location_btn)

        pos_frame.append(self.coords_row)
        mouse_box.append(pos_frame)

        return mouse_box

    def _build_keyboard_page(self) -> Gtk.Widget:
        keyboard_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        keyboard_box.set_valign(Gtk.Align.CENTER)

        select_key_label = Gtk.Label()
        select_key_label.set_markup('<b>{}</b>'.format(_('Key:')))
        keyboard_box.append(select_key_label)

        self.key_dropdown = Gtk.DropDown.new_from_strings(AVAILABLE_KEYS)
        self.key_dropdown.set_hexpand(False)
        self.key_dropdown.set_halign(Gtk.Align.CENTER)
        keyboard_box.append(self.key_dropdown)

        modifiers_box = Gtk.Box()
        modifiers_box.add_css_class('linked')
        modifiers_box.set_halign(Gtk.Align.CENTER)

        self.shift_button = Gtk.ToggleButton(label='Shift')
        self.shift_button.add_css_class('flat')
        self.shift_button.set_tooltip_text('Shift')
        modifiers_box.append(self.shift_button)

        self.ctrl_button = Gtk.ToggleButton(label='Ctrl')
        self.ctrl_button.add_css_class('flat')
        self.ctrl_button.set_tooltip_text('Control')
        modifiers_box.append(self.ctrl_button)

        self.alt_button = Gtk.ToggleButton(label='Alt')
        self.alt_button.add_css_class('flat')
        self.alt_button.set_tooltip_text('Alt')
        modifiers_box.append(self.alt_button)

        keyboard_box.append(modifiers_box)
        return keyboard_box

    def _build_pattern_page(self) -> Gtk.Widget:
        pattern_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        warnclamp = Adw.Clamp()
        warningbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        warningbox.add_css_class('card')
        pattern_warning = Gtk.Label()
        pattern_warning.set_markup(
            '<b>{}</b>'.format(_("Only use this if you know what you're doing!"))
        )
        pattern_warning.add_css_class('warning')
        warningbox.append(pattern_warning)

        warning_text_label = Gtk.Label()
        warning_text_label.set_wrap(True)
        warning_text_label.add_css_class('dim-label')
        t1 = _('Enter each key press on a new line using the exact key name from the Keyboard section.')
        warning_text_label.set_text(
            '{}\n{}'.format(t1, _("Add a time delay with 'delay <time>' (time in seconds)."))
        )
        warning_text_label.set_justify(Gtk.Justification.CENTER)
        warningbox.append(warning_text_label)
        warnclamp.set_child(warningbox)
        pattern_box.append(warnclamp)

        entryclamp = Adw.Clamp()
        self.pattern_buffer = GtkSource.Buffer()
        self.pattern_buffer.set_text(
            'Meta (Super Key/ Start Key)\nc\nl\ni\nc\nk\ne\nr\ndelay 1'
        )

        pattern_textview = GtkSource.View()
        pattern_textview.set_monospace(True)
        pattern_textview.set_show_line_numbers(True)
        pattern_textview.set_buffer(self.pattern_buffer)

        frame = Gtk.Frame()
        scrolled = Gtk.ScrolledWindow()
        frame.set_valign(Gtk.Align.FILL)
        frame.set_vexpand(True)
        scrolled.set_hexpand(False)
        scrolled.set_child(pattern_textview)
        frame.set_child(scrolled)

        entryclamp.set_child(frame)
        pattern_box.append(entryclamp)
        return pattern_box

    def _build_bottom_bar(self) -> Gtk.Widget:
        duration_box = Gtk.Box(spacing=8)
        duration_box.add_css_class('toolbar')
        duration_box.set_halign(Gtk.Align.CENTER)
        duration_box.set_vexpand(True)

        duration_label = Gtk.Label()
        duration_label.set_markup('<b>{}</b>'.format(_('Duration:')))
        duration_box.append(duration_label)

        self.duration_mode_dropdown = Gtk.DropDown.new_from_strings([
            _('Fixed Time'),
            _('Repeat Count'),
            _('Until Stopped'),
        ])
        duration_box.append(self.duration_mode_dropdown)

        # Timed mode controls
        self.timed_box = Gtk.Box(spacing=6)
        self.min_duration_spin = Gtk.SpinButton.new_with_range(0, 100000, 1)
        self.min_duration_spin.set_digits(2)
        self.min_duration_spin.set_value(1)
        self.min_duration_spin.connect('value-changed', self._update_start_sensitivity)
        self.timed_box.append(self.min_duration_spin)

        min_label = Gtk.Label()
        min_label.set_markup('<b>{}</b>'.format(_('min')))
        self.timed_box.append(min_label)

        self.s_duration_spin = Gtk.SpinButton.new_with_range(0, 100000, 1)
        self.s_duration_spin.set_digits(2)
        self.s_duration_spin.set_value(1)
        self.s_duration_spin.connect('value-changed', self._update_start_sensitivity)
        self.timed_box.append(self.s_duration_spin)

        s_label = Gtk.Label()
        s_label.set_markup('<b>{}</b>'.format(_('sec')))
        self.timed_box.append(s_label)
        duration_box.append(self.timed_box)

        # Repeat count mode controls
        self.count_box = Gtk.Box(spacing=6)
        self.repeat_count_spin = Gtk.SpinButton.new_with_range(1, 10000000, 10)
        self.repeat_count_spin.set_value(100)
        self.count_box.append(self.repeat_count_spin)
        repeats_label = Gtk.Label()
        repeats_label.set_markup('<b>{}</b>'.format(_('repeats')))
        self.count_box.append(repeats_label)
        duration_box.append(self.count_box)

        return duration_box

    def _bind_settings(self):
        flags = Gio.SettingsBindFlags.DEFAULT
        self.settings.bind('mode', self.view_stack, 'visible-child-name', flags)
        self.settings.bind('delay-seconds', self.delay_spin, 'value', flags)
        self.settings.bind('interval', self.interval_spinbox, 'value', flags)
        self.settings.bind('clicks-per-second', self.cps_spinbox, 'value', flags)
        self.settings.bind('duration-minutes', self.min_duration_spin, 'value', flags)
        self.settings.bind('duration-seconds', self.s_duration_spin, 'value', flags)
        self.settings.bind('repeat-count', self.repeat_count_spin, 'value', flags)
        self.settings.bind('target-x', self.target_x_spin, 'value', flags)
        self.settings.bind('target-y', self.target_y_spin, 'value', flags)
        self.settings.bind('shift', self.shift_button, 'active', flags)
        self.settings.bind('ctrl', self.ctrl_button, 'active', flags)
        self.settings.bind('alt', self.alt_button, 'active', flags)
        self.settings.bind('pattern', self.pattern_buffer, 'text', flags)

        # Speed mode ('interval' vs 'cps')
        speed_modes = ['interval', 'cps']
        saved_speed_mode = self.settings.get_string('speed-mode')
        if saved_speed_mode in speed_modes:
            self.speed_mode_dropdown.set_selected(speed_modes.index(saved_speed_mode))
        self._sync_speed_mode_ui()
        self.speed_mode_dropdown.connect('notify::selected', self._on_speed_mode_changed)

        # Duration mode ('timed', 'count', 'infinite')
        duration_modes = ['timed', 'count', 'infinite']
        saved_dur_mode = self.settings.get_string('duration-mode')
        if saved_dur_mode in duration_modes:
            self.duration_mode_dropdown.set_selected(duration_modes.index(saved_dur_mode))
        self._sync_duration_mode_ui()
        self.duration_mode_dropdown.connect('notify::selected', self._on_duration_mode_changed)

        # Mouse button ('left', 'middle', 'right')
        saved_btn = self.settings.get_string('mouse-button')
        if saved_btn == 'middle':
            self.middle_button.set_active(True)
        elif saved_btn == 'right' or self.settings.get_boolean('right-click'):
            self.right_button.set_active(True)
        else:
            self.left_button.set_active(True)

        self.left_button.connect('toggled', self._on_mouse_button_toggled)
        self.middle_button.connect('toggled', self._on_mouse_button_toggled)
        self.right_button.connect('toggled', self._on_mouse_button_toggled)

        # Position mode ('current' vs 'fixed')
        saved_pos_mode = self.settings.get_string('position-mode')
        if saved_pos_mode == 'fixed':
            self.pos_fixed_btn.set_active(True)
        else:
            self.pos_current_btn.set_active(True)
        self._sync_position_mode_ui()
        self.pos_current_btn.connect('toggled', self._on_position_mode_toggled)
        self.pos_fixed_btn.connect('toggled', self._on_position_mode_toggled)

        # Key dropdown
        keys = self.key_dropdown.get_model()
        saved_key = self.settings.get_string('key')
        for i in range(keys.get_n_items()):
            if keys.get_string(i) == saved_key:
                self.key_dropdown.set_selected(i)
                break
        self.key_dropdown.connect(
            'notify::selected',
            lambda dropdown, _: self.settings.set_string(
                'key', dropdown.get_selected_item().get_string()
            ),
        )

        # Update status hint whenever shortcut settings change
        self.settings.connect('changed::start-shortcut', lambda *_: self._update_status_hint())
        self.settings.connect('changed::stop-shortcut', lambda *_: self._update_status_hint())
        self.settings.connect('changed::toggle-shortcut', lambda *_: self._update_status_hint())

    def _on_speed_mode_changed(self, dropdown, _):
        mode = ['interval', 'cps'][dropdown.get_selected()]
        self.settings.set_string('speed-mode', mode)
        self._sync_speed_mode_ui()

    def _sync_speed_mode_ui(self):
        is_cps = self.speed_mode_dropdown.get_selected() == 1
        self.interval_spinbox.set_visible(not is_cps)
        self.cps_spinbox.set_visible(is_cps)

    def _on_duration_mode_changed(self, dropdown, _):
        mode = ['timed', 'count', 'infinite'][dropdown.get_selected()]
        self.settings.set_string('duration-mode', mode)
        self._sync_duration_mode_ui()
        self._update_start_sensitivity()

    def _sync_duration_mode_ui(self):
        idx = self.duration_mode_dropdown.get_selected()
        self.timed_box.set_visible(idx == 0)
        self.count_box.set_visible(idx == 1)

    def _on_mouse_button_toggled(self, _button):
        if self.middle_button.get_active():
            self.settings.set_string('mouse-button', 'middle')
            self.settings.set_boolean('right-click', False)
        elif self.right_button.get_active():
            self.settings.set_string('mouse-button', 'right')
            self.settings.set_boolean('right-click', True)
        else:
            self.settings.set_string('mouse-button', 'left')
            self.settings.set_boolean('right-click', False)

    def _on_position_mode_toggled(self, _button):
        is_fixed = self.pos_fixed_btn.get_active()
        self.settings.set_string('position-mode', 'fixed' if is_fixed else 'current')
        self._sync_position_mode_ui()

    def _sync_position_mode_ui(self):
        is_fixed = self.pos_fixed_btn.get_active()
        self.target_x_spin.set_sensitive(is_fixed)
        self.target_y_spin.set_sensitive(is_fixed)

    def _on_pick_location_clicked(self, _button):
        def on_picked(x: float, y: float):
            self.target_x_spin.set_value(x)
            self.target_y_spin.set_value(y)
            self.pos_fixed_btn.set_active(True)

        picker = LocationPickerOverlay(parent=self, on_picked=on_picked)
        picker.present()

    def _on_configure_shortcuts(self, _button):
        dialog = ShortcutRecorderDialog(
            parent=self,
            settings_manager=self.settings_manager,
            shortcuts_manager=self.shortcuts_manager,
        )
        dialog.present()

    def _update_start_sensitivity(self, *_):
        if self.engine.is_running:
            self.start_button.set_sensitive(True)
            return
        dur_mode = self.settings.get_string('duration-mode')
        if dur_mode == 'timed':
            if self.min_duration_spin.get_value() == 0 and self.s_duration_spin.get_value() == 0:
                self.start_button.set_sensitive(False)
                return
        self.start_button.set_sensitive(True)

    def _update_status_hint(self, state_msg: str = ''):
        start_sc = self.settings.get_string('start-shortcut')
        stop_sc = self.settings.get_string('stop-shortcut')
        toggle_sc = self.settings.get_string('toggle-shortcut')
        shortcuts_line = _('Shortcuts — Start: {} | Stop: {} | Toggle: {}').format(
            start_sc, stop_sc, toggle_sc
        )
        if state_msg:
            self.status_label.set_text(f"{state_msg}\n{shortcuts_line}")
        else:
            portal_line = _('When you press Start, allow remote interaction in the portal prompt.')
            self.status_label.set_text(f"{portal_line}\n{shortcuts_line}")

    def on_start_requested(self):
        if not self.engine.is_running:
            config = self.settings_manager.snapshot()
            self.engine.start(config)

    def on_stop_requested(self):
        if self.engine.is_running:
            self.engine.stop()

    def on_toggle_requested(self):
        self.engine.toggle(self.settings_manager.snapshot)

    def _on_engine_state_changed(self, running: bool, status_text: str):
        if running:
            self.start_button.set_icon_name('media-playback-stop-symbolic')
            self.start_button.set_tooltip_text(_('Stop'))
            self.start_button.remove_css_class('suggested-action')
            self.start_button.add_css_class('destructive-action')
        else:
            self.start_button.set_icon_name('media-playback-start-symbolic')
            self.start_button.set_tooltip_text(_('Start'))
            self.start_button.remove_css_class('destructive-action')
            self.start_button.add_css_class('suggested-action')
        self._update_start_sensitivity()
        self._update_status_hint(status_text if running else '')

    def _on_engine_error(self, message: str):
        dialog = Adw.MessageDialog.new(self, _('Automation Error'), message)
        dialog.add_response('ok', _('OK'))
        dialog.present()

    def show_warning_dialog(self):
        seen_path = os.path.expanduser('~/.var/app/io.github.erb3k.clicker/seen_dialog')
        if os.path.exists(seen_path):
            return

        def set_dont_show(dialog, response):
            if dont_show_cb.get_active():
                os.makedirs(os.path.dirname(seen_path), exist_ok=True)
                with open(seen_path, 'w') as f:
                    f.write('1')

        # Translators: Do not translate the word Portal
        message = Adw.MessageDialog.new(
            self,
            _('Portal access'),
            _(
                'Clicker needs permission to simulate input by simulating a connection to this computer. '
                'It does not connect to any remote host.'
            ),
        )
        message.add_response('ok', _('OK'))
        dont_show_cb = Gtk.CheckButton()
        dont_show_cb.set_label(_("Don't show this message again"))
        message.set_extra_child(dont_show_cb)
        message.connect('response', set_dont_show)
        message.present()
