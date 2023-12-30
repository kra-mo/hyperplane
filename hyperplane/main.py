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

"""The main application singleton class."""
import logging
import sys
from typing import Any, Callable, Iterable, Optional, Sequence

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GnomeDesktop", "4.0")
gi.require_version("Xdp", "1.0")
gi.require_version("XdpGtk4", "1.0")

# pylint: disable=wrong-import-position

from gi.repository import Adw, Gio, GLib, Gtk

from hyperplane import shared
from hyperplane.file_manager_dbus import FileManagerDBusServer
from hyperplane.guide import HypGuide
from hyperplane.logging.logging_config import logging_config
from hyperplane.preferences import HypPreferencesWindow
from hyperplane.window import HypWindow


class HypApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self) -> None:
        super().__init__(
            application_id=shared.APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )
        logging_config()
        FileManagerDBusServer()

        # Create home
        shared.home_path.mkdir(parents=True, exist_ok=True)
        (shared.home_path / ".hyperplane").touch(exist_ok=True)

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
        self.set_option_context_parameter_string("[DIRECTORIES]")

        self.create_action("quit", lambda *_: self.quit(), ("<primary>q",))
        self.create_action("show-guide", self.__guide, ("F1",))
        self.create_action("about", self.__about)
        self.create_action("preferences", self.__preferences, ("<primary>comma",))

        # Show hidden
        show_hidden_action = Gio.SimpleAction.new_stateful(
            "show-hidden", None, shared.state_schema.get_value("show-hidden")
        )
        show_hidden_action.connect("activate", self.__show_hidden)
        show_hidden_action.connect("change-state", self.__show_hidden)
        self.add_action(show_hidden_action)
        self.set_accels_for_action("app.show-hidden", ("<primary>h",))

        # Sort by
        sort_action = Gio.SimpleAction.new_stateful(
            "sort", GLib.VariantType.new("s"), shared.state_schema.get_value("sort-by")
        )
        sort_action.connect("activate", self.__sort)
        self.add_action(sort_action)

        # Reverse sort
        reverse_sort_action = Gio.SimpleAction.new_stateful(
            "reverse-sort", None, shared.state_schema.get_value("sort-reversed")
        )
        reverse_sort_action.connect("activate", self.__reverse_sort)
        reverse_sort_action.connect("change-state", self.__reverse_sort)
        self.add_action(reverse_sort_action)

        # List/grid view
        change_view_action = Gio.SimpleAction.new_stateful(
            "change-view",
            GLib.VariantType.new("s"),
            GLib.Variant.new_string("grid" if shared.grid_view else "list"),
        )
        change_view_action.connect("activate", self.__change_view)
        change_view_action.connect("change-state", self.__change_view)
        self.add_action(change_view_action)

        self.create_action(
            "list-view",
            lambda *_: self.__change_view(
                change_view_action, GLib.Variant.new_string("list")
            ),
            ("<primary>1",),
        )
        self.create_action(
            "grid-view",
            lambda *_: self.__change_view(
                change_view_action, GLib.Variant.new_string("grid")
            ),
            ("<primary>2",),
        )

    def do_open(self, gfiles: Sequence[Gio.File], _n_files: int, _hint: str) -> None:
        """Opens the given files."""
        for gfile in gfiles:
            if (
                gfile.query_file_type(Gio.FileQueryInfoFlags.NONE)
                != Gio.FileType.DIRECTORY
            ):
                logging.error("%s is not a directory.", gfile.get_uri())
                return

            self.do_activate(gfile)

    def do_activate(
        self,
        gfile: Optional[Gio.File] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> HypWindow:
        """Called when the application is activated."""

        if not (gfile or tags):
            gfile = shared.home

        win = HypWindow(application=self, initial_gfile=gfile, initial_tags=tags)

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

        if shared.state_schema.get_boolean("first-run"):
            shared.state_schema.set_boolean("first-run", False)
            guide = HypGuide()
            guide.present()
            guide.connect("close-request", lambda *_: win.present())
        else:
            win.present()

        return win

    def do_handle_local_options(self, options: GLib.VariantDict) -> int:
        """Handles local command line arguments."""
        self.register()  # This is so get_is_remote works
        if self.get_is_remote():
            if options.contains("new-window"):
                return -1

            logging.warning(
                "Hyperplane is already running. "
                "To open a new window, run the app with --new-window."
            )
            return 0

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

    def __guide(self, *_args: Any) -> None:
        guide = HypGuide()

        guide.set_modal(True)
        guide.set_transient_for(self.get_active_window())
        guide.add_controller(shortcut_controller := Gtk.ShortcutController())
        shortcut_controller.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("Escape"),
                Gtk.NamedAction.new("window.close"),
            ),
        )

        guide.present()

    def __about(self, *_args: Any) -> None:
        about = Adw.AboutWindow.new_from_appdata(
            shared.PREFIX + "/" + shared.APP_ID + ".metainfo.xml", shared.VERSION
        )
        about.set_transient_for(self.get_active_window())
        about.set_developers(
            (
                "kramo https://kramo.hu",
                "Benedek Dévényi https://github.com/rdbende",
            )
        )
        about.set_designers(("kramo https://kramo.hu",))
        about.set_copyright("© 2023 kramo")
        # Translators: Replace this with your name for it to show up in the about window
        about.set_translator_credits = (_("translator_credits"),)
        about.present()

    def __preferences(self, *_args: Any) -> None:
        prefs = HypPreferencesWindow()
        prefs.set_transient_for(self.get_active_window())
        prefs.present()

    def __show_hidden(self, action: Gio.SimpleAction, _state: GLib.Variant) -> None:
        value = not action.props.state.get_boolean()
        action.set_state(GLib.Variant.new_boolean(value))

        shared.state_schema.set_boolean("show-hidden", value)
        shared.show_hidden = value

        shared.postmaster.emit("toggle-hidden")

    def __sort(self, action: Gio.SimpleAction, state: GLib.Variant) -> None:
        action.set_state(state)

        shared.sort_by = state.get_string()
        shared.postmaster.emit("sort-changed")

        shared.state_schema.set_string("sort-by", shared.sort_by)

    def __reverse_sort(self, action: Gio.SimpleAction, _state: GLib.Variant) -> None:
        value = not action.props.state.get_boolean()
        action.set_state(GLib.Variant.new_boolean(value))

        shared.state_schema.set_boolean("sort-reversed", value)
        shared.sort_reversed = value

        shared.postmaster.emit("sort-changed")

    def __change_view(self, action: Gio.SimpleAction, state: GLib.Variant) -> None:
        action.set_state(state)

        shared.grid_view = state.get_string() == "grid"
        shared.state_schema.set_boolean("grid-view", shared.grid_view)

        shared.postmaster.emit("view-changed")


def main(_version):
    """The application's entry point."""
    app = HypApplication()
    return app.run(sys.argv)
