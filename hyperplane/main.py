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
from typing import Any, Callable, Iterable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GnomeDesktop", "4.0")

# pylint: disable=wrong-import-position

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from hyperplane import shared
from hyperplane.item import HypItem
from hyperplane.tag import HypTag
from hyperplane.utils.validate_name import validate_name
from hyperplane.window import HypWindow


class HypApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(
            application_id=shared.APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
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
        self.create_action("preferences", self.__on_preferences_action)
        self.create_action(
            "refresh",
            self.__on_refresh_action,
            (
                "<primary>r",
                "F5",
            ),
        )

        self.create_action(
            "new-folder", self.__on_new_folder_action, ("<primary><shift>n",)
        )
        self.create_action("copy", self.__on_copy_action, ("<primary>c",))
        self.create_action("select-all", self.__on_select_all_action)
        self.create_action("rename", self.__on_rename_action, ("F2",))
        self.create_action("trash", self.__on_trash_action, ("Delete",))

        show_hidden_action = Gio.SimpleAction.new_stateful(
            "show-hidden", None, shared.state_schema.get_value("show-hidden")
        )
        show_hidden_action.connect("activate", self.__show_hidden)
        show_hidden_action.connect("change-state", self.__show_hidden)
        self.add_action(show_hidden_action)
        self.set_accels_for_action("app.show-hidden", ("<primary>h",))

    def __show_hidden(self, action: Gio.SimpleAction, _state: GLib.Variant) -> None:
        value = not action.get_property("state").get_boolean()
        action.set_state(GLib.Variant.new_boolean(value))

        shared.state_schema.set_boolean("show-hidden", value)
        shared.show_hidden = value

        shared.postmaster.emit("toggle-hidden")

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
            application_name="Hyperplane",
            application_icon=shared.APP_ID,
            developer_name="kramo",
            version="0.1.0",
            developers=["kramo"],
            copyright="© 2023 kramo",
        )
        about.present()

    def __on_preferences_action(self, *_args: Any) -> None:
        """Callback for the app.preferences action."""
        print("app.preferences action activated")

    def __on_refresh_action(self, *_args: Any) -> None:
        self.get_active_window().get_visible_page().update()

    def __on_new_folder_action(self, *_args: Any) -> None:
        if not (path := (page := self.get_active_window().get_visible_page()).path):
            if page.tags:
                path = Path(
                    shared.home, *(tag for tag in shared.tags if tag in page.tags)
                )
        if not path:
            return

        dialog = Adw.MessageDialog.new(self.get_active_window(), _("New Folder"))

        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("create", _("Create"))

        dialog.set_default_response("create")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)

        preferences_group = Adw.PreferencesGroup(width_request=360)
        revealer_label = Gtk.Label(
            margin_start=6,
            margin_end=6,
            margin_top=12,
        )
        preferences_group.add(revealer := Gtk.Revealer(child=revealer_label))
        preferences_group.add(entry := Adw.EntryRow(title=_("Folder name")))
        dialog.set_extra_child(preferences_group)

        dialog.set_response_enabled("create", False)
        can_create = False

        def set_incative(*_args: Any) -> None:
            nonlocal can_create
            nonlocal path

            if not (text := entry.get_text().strip()):
                can_create = False
                dialog.set_response_enabled("create", False)
                revealer.set_reveal_child(False)
                return

            can_create, message = validate_name(path, text)
            dialog.set_response_enabled("create", can_create)
            revealer.set_reveal_child(bool(message))
            if message:
                revealer_label.set_label(message)

        def create_folder(*_args: Any):
            nonlocal can_create
            nonlocal path

            if not can_create:
                return

            Path(path, entry.get_text().strip()).mkdir(parents=True, exist_ok=True)
            self.get_active_window().get_visible_page().update()
            dialog.close()

        def handle_response(_dialog: Adw.MessageDialog, response: str) -> None:
            if response == "create":
                create_folder()

        dialog.connect("response", handle_response)
        entry.connect("entry-activated", create_folder)
        entry.connect("changed", set_incative)

        dialog.present()

    def __on_copy_action(self, *_args: Any) -> None:
        clipboard = Gdk.Display.get_default().get_clipboard()

        uris = ""

        for child in (
            self.get_active_window().get_visible_page().flow_box.get_selected_children()
        ):
            child = child.get_child()

            if isinstance(child, HypItem):
                uris += str(child.path) + "\n"
            elif isinstance(child, HypTag):
                uris += child.name + "\n"

        if uris:
            clipboard.set(uris.strip())

    def __on_select_all_action(self, *_args: Any) -> None:
        self.get_active_window().get_visible_page().flow_box.select_all()

    def __on_rename_action(self, *_args: Any) -> None:
        if not isinstance(
            child := (
                (flow_box := self.get_active_window().get_visible_page().flow_box)
                .get_selected_children()[0]
                .get_child()
            ),
            HypItem,
        ):
            return

        flow_box.unselect_all()
        flow_box.select_child(child.get_parent())

        (popover := self.get_active_window().rename_popover).unparent()
        popover.set_parent(child)
        if child.path.is_dir():
            self.get_active_window().rename_label.set_label(_("Rename Folder"))
        else:
            self.get_active_window().rename_label.set_label(_("Rename File"))

        path = child.path
        entry = self.get_active_window().rename_row
        entry.set_text(path.name)
        entry.select_region(0, len(path.name) - len("".join(path.suffixes)))

        button = self.get_active_window().rename_button
        revealer = self.get_active_window().rename_revealer
        revealer_label = self.get_active_window().rename_revealer_label
        can_rename = True

        def rename(*_args: Any) -> None:
            try:
                child.gfile.set_display_name(entry.get_text().strip())
            except GLib.GError:
                pass
            self.get_active_window().get_visible_page().update()
            popover.popdown()

        def set_incative(*_args: Any) -> None:
            nonlocal can_rename
            nonlocal path

            if not popover.is_visible():
                return

            text = entry.get_text().strip()

            if not text:
                can_rename = False
                button.set_sensitive(False)
                revealer.set_reveal_child(False)
                return

            can_rename, message = validate_name(path, text, True)
            button.set_sensitive(can_rename)
            revealer.set_reveal_child(bool(message))
            if message:
                revealer_label.set_label(message)

        popover.connect("notify::visible", set_incative)
        entry.connect("changed", set_incative)
        entry.connect("entry-activated", rename)
        button.connect("clicked", rename)

        popover.popup()

    def __on_trash_action(self, *_args: Any) -> None:
        n = 0
        for child in (
            items_page := self.get_active_window().get_visible_page()
        ).flow_box.get_selected_children():
            child = child.get_child()

            if not isinstance(child, HypItem):
                continue

            try:
                child.gfile.trash()
            except GLib.GError:
                pass
            else:
                items_page.update()
                n += 1

        if not n:
            return

        if n > 1:
            message = _("{} files moved to trash").format(n)
        elif n:
            message = _("{} moved to trash").format(
                '"' + child.path.name + '"'  # pylint: disable=undefined-loop-variable
            )

        self.get_active_window().send_toast(message)


def main(_version):
    """The application's entry point."""
    app = HypApplication()
    return app.run(sys.argv)
