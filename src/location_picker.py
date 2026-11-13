# location_picker.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Callable

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gdk, Gtk


class LocationPickerOverlay(Gtk.Window):
    """Fullscreen crosshair overlay for picking screen coordinates on Wayland/X11."""

    def __init__(self, parent: Gtk.Window, on_picked: Callable[[float, float], None]):
        super().__init__(
            transient_for=parent,
            modal=True,
            title=_('Pick Click Location'),
            decorated=False,
        )
        self.on_picked = on_picked
        self._cursor_x = 0.0
        self._cursor_y = 0.0

        # Set crosshair cursor
        crosshair = Gdk.Cursor.new_from_name('crosshair', None)
        if crosshair:
            self.set_cursor(crosshair)

        overlay = Gtk.Overlay()

        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_hexpand(True)
        self.drawing_area.set_vexpand(True)
        self.drawing_area.set_draw_func(self._on_draw)
        overlay.set_child(self.drawing_area)

        banner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        banner_box.set_halign(Gtk.Align.CENTER)
        banner_box.set_valign(Gtk.Align.START)
        banner_box.set_margin_top(32)
        banner_box.add_css_class('card')
        banner_box.set_margin_start(16)
        banner_box.set_margin_end(16)

        inner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        inner_box.set_margin_top(12)
        inner_box.set_margin_bottom(12)
        inner_box.set_margin_start(20)
        inner_box.set_margin_end(20)

        title_lbl = Gtk.Label()
        title_lbl.set_markup(
            '<b>{}</b>'.format(_('Click anywhere on the screen to select the target position'))
        )
        inner_box.append(title_lbl)

        self.coords_label = Gtk.Label(label='X: 0, Y: 0')
        self.coords_label.add_css_class('monospace')
        inner_box.append(self.coords_label)

        hint_lbl = Gtk.Label(label=_('Press Escape or right-click to cancel'))
        hint_lbl.add_css_class('dim-label')
        inner_box.append(hint_lbl)

        banner_box.append(inner_box)
        overlay.add_overlay(banner_box)

        self.set_child(overlay)

        # Motion tracking for live crosshair and coordinates
        motion = Gtk.EventControllerMotion()
        motion.connect('motion', self._on_motion)
        self.drawing_area.add_controller(motion)

        # Left-click to pick coordinate
        click = Gtk.GestureClick()
        click.set_button(0)  # Listen to any mouse button
        click.connect('pressed', self._on_clicked)
        self.drawing_area.add_controller(click)

        # Escape key to cancel
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect('key-pressed', self._on_key_pressed)
        self.add_controller(key_ctrl)

        self.fullscreen()

    def _on_motion(self, _controller, x: float, y: float):
        self._cursor_x = x
        self._cursor_y = y
        self.coords_label.set_text(f"X: {int(round(x))}, Y: {int(round(y))}")
        self.drawing_area.queue_draw()

    def _on_clicked(self, gesture: Gtk.GestureClick, _n_press: int, x: float, y: float):
        btn = gesture.get_current_button()
        if btn == Gdk.BUTTON_SECONDARY:
            self.close()
            return
        if btn == Gdk.BUTTON_PRIMARY:
            picked_x = round(x, 1)
            picked_y = round(y, 1)
            self.close()
            self.on_picked(picked_x, picked_y)

    def _on_key_pressed(self, _controller, keyval, _keycode, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _on_draw(self, _area: Gtk.DrawingArea, cr, width: int, height: int):
        # Subtle translucent dark backdrop
        cr.set_source_rgba(0.08, 0.08, 0.10, 0.35)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        # Crosshair lines at current cursor position
        cr.set_source_rgba(0.20, 0.65, 1.0, 0.85)
        cr.set_line_width(1.5)

        # Horizontal line
        cr.move_to(0, self._cursor_y)
        cr.line_to(width, self._cursor_y)
        cr.stroke()

        # Vertical line
        cr.move_to(self._cursor_x, 0)
        cr.line_to(self._cursor_x, height)
        cr.stroke()

        # Target circle around cursor
        cr.arc(self._cursor_x, self._cursor_y, 8.0, 0, 6.283185307179586)
        cr.stroke()
