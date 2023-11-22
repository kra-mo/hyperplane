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
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GnomeDesktop", "4.0")

# pylint: disable=wrong-import-position

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from hyperplane import shared
from hyperplane.item import HypItem
from hyperplane.tag import HypTag
from hyperplane.window import HypWindow


class HypApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(
            application_id=shared.APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.create_action("quit", lambda *_: self.quit(), ("<primary>q",))
        self.create_action("about", self.__on_about_action)
        self.create_action("preferences", self.__on_preferences_action)

        self.create_action(
            "new-folder", self.__on_new_folder_action, ("<primary><shift>n",)
        )
        self.create_action("copy", self.__on_copy_action, ("<primary>c",))
        self.create_action("select-all", self.__on_select_all_action)
        self.create_action("trash", self.__on_trash_action, ("Delete",))

    def do_activate(self):
        """Called when the application is activated.

        We raise the application's main window, creating it if
        necessary.
        """
        shared.app = self
        win = self.props.active_window
        if not win:
            win = HypWindow(application=self)

        # Save window geometry
        shared.state_schema.bind(
            "width", win, "default-width", Gio.SettingsBindFlags.DEFAULT
        )
        shared.state_schema.bind(
            "height", win, "default-height", Gio.SettingsBindFlags.DEFAULT
        )
        shared.state_schema.bind(
            "is-maximized", win, "maximized", Gio.SettingsBindFlags.DEFAULT
        )

        win.present()

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

    def __on_about_action(self, _widget, _):
        """Callback for the app.about action."""
        about = Adw.AboutWindow(
            transient_for=self.props.active_window,
            application_name="Hyperplane",
            application_icon=shared.APP_ID,
            developer_name="kramo",
            version="0.1.0",
            developers=["kramo"],
            copyright="© 2023 kramo",
        )
        about.present()

    def __on_preferences_action(self, _widget, _):
        """Callback for the app.preferences action."""
        print("app.preferences action activated")

    def __on_new_folder_action(self, *_args: Any) -> None:
        if not shared.get_win().items_page.path:
            return

        dialog = Adw.MessageDialog.new(shared.get_win(), _("New Folder"))

        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("create", _("Create"))

        dialog.set_default_response("create")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)

        preferences_group = Adw.PreferencesGroup()
        exists_label = Gtk.Label(
            label=_("A folder with that name already exists."),
            margin_start=6,
            margin_end=6,
            margin_top=12,
        )
        preferences_group.add(revealer := Gtk.Revealer(child=exists_label))
        preferences_group.add(entry := Adw.EntryRow(title=_("Folder name")))
        dialog.set_extra_child(preferences_group)

        dialog.set_response_enabled("create", False)
        can_create = False

        def set_incative(*_args: Any):
            nonlocal can_create

            if not (text := entry.get_text()):
                can_create = False
                dialog.set_response_enabled("create", False)
                revealer.set_reveal_child(False)
                return

            if Path(shared.get_win().items_page.path, text.strip()).is_dir():
                can_create = False
                dialog.set_response_enabled("create", False)
                revealer.set_reveal_child(True)
            else:
                can_create = True
                dialog.set_response_enabled("create", True)
                revealer.set_reveal_child(False)

        def create_folder(*_args: Any):
            nonlocal can_create

            if not can_create:
                return

            path = Path(shared.get_win().items_page.path, entry.get_text().strip())
            path.mkdir(parents=True, exist_ok=True)
            shared.get_win().items_page.flow_box.append(HypItem(path))
            dialog.close()

        def handle_response(_dialog, response):
            if response == "create":
                create_folder()

        dialog.connect("response", handle_response)
        entry.connect("entry-activated", create_folder)
        entry.connect("changed", set_incative)

        dialog.present()

    def __on_copy_action(self, *_args: Any) -> None:
        clipboard = Gdk.Display.get_default().get_clipboard()

        uris = ""

        for child in shared.get_win().items_page.flow_box.get_selected_children():
            child = child.get_child()

            if isinstance(child, HypItem):
                uris += str(child.path) + "\n"
            elif isinstance(child, HypTag):
                uris += child.name + "\n"

        if uris:
            clipboard.set(uris.strip())

    def __on_select_all_action(self, *_args: Any) -> None:
        shared.get_win().items_page.flow_box.select_all()

    def __on_trash_action(self, *_args: Any) -> None:
        n = 0
        for child in (
            items_page := shared.get_win().items_page
        ).flow_box.get_selected_children():
            child = child.get_child()

            if not isinstance(child, HypItem):
                continue

            try:
                child.gfile.trash()
            except GLib.GError:
                pass
            else:
                items_page.flow_box.remove(child.get_parent())
                n += 1

        if not n:
            return

        if n > 1:
            message = _("{} files moved to trash").format(n)
        elif n:
            message = _("{} moved to trash").format(
                '"' + child.path.name + '"'  # pylint: disable=undefined-loop-variable
            )

        shared.get_win().send_toast(message)


def main(_version):
    """The application's entry point."""
    app = HypApplication()
    return app.run(sys.argv)
