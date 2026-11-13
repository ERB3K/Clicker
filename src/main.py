# main.py
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

import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Gio, Adw
from .window import ClickerWindow


class ClickerApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(application_id='io.github.erb3k.clicker',
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.create_action('quit', lambda *_: self.quit(), ['<primary>q'])
        self.create_action('close', self.close_, ['<primary>w'])

    def close_(self, *_):
        print(self.get_active_window())
        if self.get_active_window().get_visible_dialog():
            self.get_active_window().get_visible_dialog().close()
        else:
            self.get_active_window().close()

    def do_activate(self):
        """Called when the application is activated.

        We raise the application's main window, creating it if
        necessary.
        """
        win = self.props.active_window
        if not win:
            win = ClickerWindow(application=self)
        win.present()

    def on_about_action(self, widget, data):
        """Callback for the app.about action."""
        about = Adw.AboutDialog()
        about.set_presentation_mode(Adw.DialogPresentationMode.FLOATING)
        about.set_application_name(_("Clicker"))
        about.set_comments(_("Simulate user input repeatedly"))
        about.set_developer_name("Erick Bueno (ERB3K)")
        about.set_application_icon('io.github.erb3k.clicker')
        about.set_version('0.2.0')
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_developers(['Erick Bueno (ERB3K)'])
        about.set_copyright('© 2026 Erick Bueno (ERB3K)')
        about.set_website("https://github.com/ERB3K/Clicker")
        about.set_issue_url("https://github.com/ERB3K/Clicker/issues")

        about.present(self.get_active_window())

    def create_action(self, name, callback, shortcuts=None):
        """Add an application action.

        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
        """
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)


def main(version):
    """The application's entry point."""
    app = ClickerApplication()
    return app.run(sys.argv)
