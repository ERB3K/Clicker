# engine.py
#
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
import time
from typing import Callable, Optional

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Xdp', '1.0')
from gi.repository import Gdk, GLib, Xdp

import libevdev

from .config import AutomationConfig, parse_pattern, resolve_key


BUTTON_MAP = {
    'left': getattr(libevdev.EV_KEY.BTN_LEFT, 'value', 0x110),
    'right': getattr(libevdev.EV_KEY.BTN_RIGHT, 'value', 0x111),
    'middle': getattr(libevdev.EV_KEY.BTN_MIDDLE, 'value', 0x112),
}


class AutomationEngine:
    """Modular automation engine managing XDG RemoteDesktop sessions and input loops."""

    def __init__(
        self,
        on_state_changed: Optional[Callable[[bool, str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        self.portal = Xdp.Portal()
        self.stop_event = threading.Event()
        self._lock = threading.Lock()
        self._running = False
        self._session: Optional[Xdp.Session] = None
        self.on_state_changed = on_state_changed
        self.on_error = on_error

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def _set_running(self, running: bool, status_text: str = ''):
        with self._lock:
            self._running = running
        if self.on_state_changed:
            GLib.idle_add(self.on_state_changed, running, status_text)

    def _report_error(self, message: str):
        print(f"[CLICKER ENGINE] {message}")
        if self.on_error:
            GLib.idle_add(self.on_error, message)

    def start(self, config: AutomationConfig):
        """Request a Wayland/X11 RemoteDesktop session and start the automation loop."""
        if self.is_running:
            return

        # Validate keyboard/pattern keys upfront before opening a portal prompt
        try:
            if config.mode == 'keyboard':
                resolve_key(config.key_name)
            elif config.mode == 'pattern':
                parse_pattern(config.pattern_text)
        except Exception as exc:
            self._report_error(str(exc))
            return

        if config.mode == 'mouse':
            device = Xdp.DeviceType.POINTER
        else:
            device = Xdp.DeviceType.KEYBOARD

        self._set_running(True, _("Waiting for portal permission..."))

        def on_create_session_finish(portal, result, data):
            try:
                session = portal.create_remote_desktop_session_finish(result)
            except GLib.Error as err:
                self._set_running(False, _("Stopped"))
                self._report_error(err.message)
                return

            self._session = session
            session.start(
                None,
                None,
                lambda sess, res, _data: self._on_session_started(sess, res, config),
                None,
            )

        try:
            self.portal.create_remote_desktop_session(
                device,
                Xdp.OutputType.MONITOR,
                Xdp.RemoteDesktopFlags.MULTIPLE,
                Xdp.CursorMode.EMBEDDED,
                None,
                on_create_session_finish,
                None,
            )
        except Exception as exc:
            self._set_running(False, _("Stopped"))
            self._report_error(str(exc))

    def _on_session_started(self, session: Xdp.Session, result, config: AutomationConfig):
        try:
            if hasattr(session, 'start_finish'):
                started = session.start_finish(result)
                if not started:
                    self._set_running(False, _("Cancelled"))
                    return
        except GLib.Error as err:
            self._set_running(False, _("Cancelled"))
            self._report_error(err.message)
            return

        streams = session.get_streams()
        if not streams:
            self._set_running(False, _("Cancelled"))
            return

        stream_id = None
        try:
            stream_id = int(streams[0][0])
        except Exception:
            stream_id = None

        if stream_id is None and config.mode == 'mouse' and config.position_mode == 'fixed':
            self._set_running(False, _("No monitor stream selected"))
            try:
                session.close()
            except Exception:
                pass
            return

        self.stop_event.clear()
        worker = threading.Thread(
            target=self._run_worker,
            args=(session, stream_id, config),
            daemon=True,
        )
        worker.start()

    def stop(self):
        """Signal the ongoing automation loop to stop immediately."""
        self.stop_event.set()

    def toggle(self, config_provider: Callable[[], AutomationConfig]):
        """Toggle automation on or off."""
        if self.is_running:
            self.stop()
        else:
            self.start(config_provider())

    def _run_worker(self, session: Xdp.Session, stream_id: Optional[int], config: AutomationConfig):
        try:
            # Initial countdown delay
            if config.delay_seconds > 0:
                self._set_running(
                    True,
                    _("Starting in {:.1f}s...").format(config.delay_seconds),
                )
                self.stop_event.wait(config.delay_seconds)

            if self.stop_event.is_set():
                return

            self._set_running(True, _("Running automation..."))

            if config.mode == 'mouse':
                self._loop_mouse(session, stream_id, config)
            elif config.mode == 'keyboard':
                self._loop_keyboard(session, config)
            elif config.mode == 'pattern':
                self._loop_pattern(session, config)
        finally:
            try:
                session.close()
            except Exception:
                pass
            self._session = None
            self._set_running(False, _("Idle"))

    def _should_continue(
        self,
        config: AutomationConfig,
        start_time: float,
        completed_repeats: int,
    ) -> bool:
        if self.stop_event.is_set():
            return False
        if config.duration_mode == 'timed':
            total = config.total_duration_seconds or 0.0
            return (time.monotonic() - start_time) < total
        if config.duration_mode == 'count':
            max_rep = config.max_repeats or 1
            return completed_repeats < max_rep
        # 'infinite' mode runs until stop_event is set
        return True

    def _loop_mouse(self, session: Xdp.Session, stream_id: Optional[int], config: AutomationConfig):
        btn_code = BUTTON_MAP.get(config.mouse_button, BUTTON_MAP['left'])
        interval = config.effective_interval_seconds
        start_time = time.monotonic()
        repeats = 0

        while self._should_continue(config, start_time, repeats):
            if config.position_mode == 'fixed' and stream_id is not None:
                session.pointer_position(stream_id, float(config.target_x), float(config.target_y))
                time.sleep(0.005)

            session.pointer_button(btn_code, Xdp.ButtonState.PRESSED)
            time.sleep(0.01)
            session.pointer_button(btn_code, Xdp.ButtonState.RELEASED)

            repeats += 1
            if not self._should_continue(config, start_time, repeats):
                break
            self.stop_event.wait(interval)

    def _loop_keyboard(self, session: Xdp.Session, config: AutomationConfig):
        key_code = resolve_key(config.key_name)
        interval = config.effective_interval_seconds
        start_time = time.monotonic()
        repeats = 0

        while self._should_continue(config, start_time, repeats):
            self._press_key(session, key_code, config.shift, config.ctrl, config.alt)
            repeats += 1
            if not self._should_continue(config, start_time, repeats):
                break
            self.stop_event.wait(interval)

    def _loop_pattern(self, session: Xdp.Session, config: AutomationConfig):
        steps = parse_pattern(config.pattern_text)
        interval = config.effective_interval_seconds
        start_time = time.monotonic()
        repeats = 0

        while self._should_continue(config, start_time, repeats):
            for step in steps:
                if self.stop_event.is_set():
                    return
                if isinstance(step, float):
                    self.stop_event.wait(step)
                else:
                    self._press_key(session, step, False, False, False)
            repeats += 1
            if not self._should_continue(config, start_time, repeats):
                break
            self.stop_event.wait(interval)

    @staticmethod
    def _press_key(session: Xdp.Session, key: int, shift: bool, ctrl: bool, alt: bool):
        if shift:
            session.keyboard_key(True, Gdk.KEY_Shift_L, Xdp.KeyState.PRESSED)
        if ctrl:
            session.keyboard_key(True, Gdk.KEY_Control_L, Xdp.KeyState.PRESSED)
        if alt:
            session.keyboard_key(True, Gdk.KEY_Alt_L, Xdp.KeyState.PRESSED)

        session.keyboard_key(True, key, Xdp.KeyState.PRESSED)
        time.sleep(0.01)

        if shift:
            session.keyboard_key(True, Gdk.KEY_Shift_L, Xdp.KeyState.RELEASED)
        if ctrl:
            session.keyboard_key(True, Gdk.KEY_Control_L, Xdp.KeyState.RELEASED)
        if alt:
            session.keyboard_key(True, Gdk.KEY_Alt_L, Xdp.KeyState.RELEASED)

        session.keyboard_key(True, key, Xdp.KeyState.RELEASED)
