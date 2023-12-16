# main.py
#
# Copyright 2023 kramo
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
from typing import Any, Callable, Iterable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GnomeDesktop", "4.0")
gi.require_version("Xdp", "1.0")
gi.require_version("XdpGtk4", "1.0")

# pylint: disable=wrong-import-position

from gi.repository import Adw, Gio, GLib

from hyperplane import shared
from hyperplane.preferences import HypPreferencesWindow
from hyperplane.window import HypWindow


class HypApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self) -> None:
        super().__init__(
            application_id=shared.APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

        # Create home
        shared.home.mkdir(parents=True, exist_ok=True)
        (shared.home / ".hyperplane").touch(exist_ok=True)

        shared.app = self

        new_window = GLib.OptionEntry()
        new_window.long_name = "new-window"
        new_window.short_name = ord("n")
        new_window.flags = int(GLib.OptionFlags.NONE)
        new_window.arg = int(GLib.OptionArg.NONE)
        new_window.arg_data = None
        new_window.description = "Open the app with a new window"
        new_window.arg_description = None

        self.add_main_option_entries((new_window,))

        self.create_action("quit", lambda *_: self.quit(), ("<primary>q",))
        self.create_action("about", self.__on_about_action)
        self.create_action(
            "preferences", self.__on_preferences_action, ("<primary>comma",)
        )

        show_hidden_action = Gio.SimpleAction.new_stateful(
            "show-hidden", None, shared.state_schema.get_value("show-hidden")
        )
        show_hidden_action.connect("activate", self.__show_hidden)
        show_hidden_action.connect("change-state", self.__show_hidden)
        self.add_action(show_hidden_action)
        self.set_accels_for_action("app.show-hidden", ("<primary>h",))

    def do_activate(self) -> HypWindow:
        """Called when the application is activated."""
        win = HypWindow(application=self)

        win.set_default_size(
            shared.state_schema.get_int("width"),
            shared.state_schema.get_int("height"),
        )
        if shared.state_schema.get_boolean("is-maximized"):
            win.maximize()

        # Save window geometry
        shared.state_schema.bind(
            "width", win, "default-width", Gio.SettingsBindFlags.SET
        )
        shared.state_schema.bind(
            "height", win, "default-height", Gio.SettingsBindFlags.SET
        )
        shared.state_schema.bind(
            "is-maximized", win, "maximized", Gio.SettingsBindFlags.SET
        )

        win.present()
        return win

    def do_handle_local_options(self, options: GLib.VariantDict) -> int:
        if options.contains("new-window") and self.get_is_registered():
            self.do_activate()
        return -1

    def create_action(
        self, name: str, callback: Callable, shortcuts: Optional[Iterable] = None
    ) -> None:
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

    def __on_about_action(self, *_args: Any) -> None:
        """Callback for the app.about action."""
        about = Adw.AboutWindow(
            transient_for=self.get_active_window(),
            application_name=_("Hyperplane"),
            application_icon=shared.APP_ID,
            developer_name="kramo",
            version="0.1.0",
            developers=["kramo"],
            copyright="© 2023 kramo",
        )
        about.present()

    def __on_preferences_action(self, *_args: Any) -> None:
        prefs = HypPreferencesWindow()
        prefs.present()

    def __show_hidden(self, action: Gio.SimpleAction, _state: GLib.Variant) -> None:
        value = not action.get_property("state").get_boolean()
        action.set_state(GLib.Variant.new_boolean(value))

        shared.state_schema.set_boolean("show-hidden", value)
        shared.show_hidden = value

        shared.postmaster.emit("toggle-hidden")


def main(_version):
    """The application's entry point."""
    app = HypApplication()
    return app.run(sys.argv)
