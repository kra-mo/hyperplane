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

import shutil
import sys
from pathlib import Path
from time import time
from typing import Any, Callable, Iterable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GnomeDesktop", "4.0")

# pylint: disable=wrong-import-position

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from hyperplane import shared
from hyperplane.items_page import HypItemsPage
from hyperplane.navigation_bin import HypNavigationBin
from hyperplane.utils.restore_file import restore_file
from hyperplane.utils.tags import remove_tags
from hyperplane.utils.validate_name import validate_name
from hyperplane.window import HypWindow


class HypApplication(Adw.Application):
    """The main application singleton class."""

    cut_page: Optional[HypItemsPage] = None
    undo_queue: dict = {}
    right_clicked_tag: str

    def __init__(self) -> None:
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
        self.create_action("reload", self.__reload, ("<primary>r", "F5"))

        self.create_action("undo", self.__undo, ("<primary>z",))
        # TODO: Keyboard shortcuts for these that don't disrupt other operations
        self.create_action("open", self.__open)
        self.create_action("open-new-tab", self.__open_new_tab)
        self.create_action("open-new-window", self.__open_new_window)
        self.create_action("new-folder", self.__new_folder, ("<primary><shift>n",))
        self.create_action("copy", self.__copy, ("<primary>c",))
        self.create_action("cut", self.__cut, ("<primary>x",))
        self.create_action("paste", self.__paste, ("<primary>v",))
        self.create_action("select-all", self.__select_all)
        self.create_action("rename", self.__rename, ("F2",))
        self.create_action("trash", self.__trash, ("Delete",))

        # TODO: This is tedious, maybe use GTK Expressions?
        self.create_action("open-tag", self.__open_tag)
        self.create_action("open-new-tab-tag", self.__open_new_tab_tag)
        self.create_action("open-new-window-tag", self.__open_new_window_tag)
        self.create_action("remove-tag", self.__remove_tag)

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

    def __undo(self, toast: Any, *_args: Any) -> None:
        if not self.undo_queue:
            return

        if isinstance(toast, Adw.Toast):
            index = toast
        else:
            index = tuple(self.undo_queue.keys())[-1]
        item = self.undo_queue[index]

        # TODO: Lookup the pages with the paths and update those
        match item[0]:
            case "copy":
                for trash_item in item[1]:
                    if trash_item.is_dir():
                        shutil.rmtree(trash_item, ignore_errors=True)
                    else:
                        trash_item.unlink(missing_ok=True)
            case "cut":
                for paths in item[1]:
                    if paths[1].exists():
                        shutil.move(paths[1], paths[0])
            case "rename":
                try:
                    item[1].set_display_name(item[2])
                except GLib.Error:
                    pass
            case "trash":
                for trash_item in item[1]:
                    restore_file(*trash_item)

        if isinstance(index, Adw.Toast):
            index.dismiss()
        self.undo_queue.popitem()

    def get_gfiles_from_positions(self, positions: list[int]) -> list[Gio.File]:
        """Get a list of GFiles corresponding to positions in the ListModel."""
        paths = []
        multi_selection = self.get_active_window().get_visible_page().multi_selection

        for position in positions:
            paths.append(
                multi_selection.get_item(position).get_attribute_object(
                    "standard::file"
                )
            )

        return paths

    def get_paths_from_positions(self, positions: list[int]) -> list[Path]:
        """Get a list of file paths corresponding to positions in the ListModel."""
        paths = []
        multi_selection = self.get_active_window().get_visible_page().multi_selection

        for position in positions:
            paths.append(
                Path(
                    (
                        multi_selection.get_item(position).get_attribute_object(
                            "standard::file"
                        )
                    ).get_path()
                )
            )

        return paths

    def get_selected_items(self) -> list[int]:
        """Gets the list of positions for selected items in the currently active window."""
        bitset = (
            self.get_active_window().get_visible_page().multi_selection.get_selection()
        )
        not_empty, bitset_iter, position = Gtk.BitsetIter.init_first(bitset)

        if not not_empty:
            return []

        positions = [position]

        while True:
            next_val, pos = bitset_iter.next()
            if not next_val:
                break
            positions.append(pos)

        return positions

    def __open(self, *_args: Any) -> None:
        if len(positions := self.get_selected_items()) > 1:
            # TODO: Maybe switch to newly opened tab like Nautilus?
            self.__open_new_tab(None, None, positions)
            return

        self.get_active_window().get_visible_page().activate(None, positions[0])

    def __open_new_tab(
        self, _obj: Any, _parameter: Any, positions: Optional[list[int]] = None
    ) -> None:
        if not positions:
            positions = self.get_selected_items()

        paths = self.get_paths_from_positions(positions)

        for path in paths:
            if not path.is_dir():
                continue
            self.get_active_window().new_tab(path)

    def __open_new_window(self, *_args: Any) -> None:
        paths = self.get_paths_from_positions(self.get_selected_items())

        for path in paths:
            if not path.is_dir():
                continue
            new_bin = HypNavigationBin(path)

            win = self.do_activate()
            win.tab_view.close_page(win.tab_view.get_selected_page())
            win.tab_view.append(new_bin)

    def __open_tag(self, *_args: Any) -> None:
        # TODO: This is ugly
        self.get_active_window().tab_view.get_selected_page().get_child().new_page(
            tag=self.right_clicked_tag
        )

    def __open_new_tab_tag(self, *_args: Any) -> None:
        self.get_active_window().new_tab(tag=self.right_clicked_tag)

    def __open_new_window_tag(self, *_args: Any) -> None:
        new_bin = HypNavigationBin(initial_tags=[self.right_clicked_tag])
        win = self.do_activate()
        win.tab_view.close_page(win.tab_view.get_selected_page())
        win.tab_view.append(new_bin)

    def __remove_tag(self, *_args: Any) -> None:
        remove_tags(self.right_clicked_tag)

    # TODO: Do I really need this? Nautilus has refresh, but I don't know how they monitor.
    def __reload(self, *_args: Any) -> None:
        dir_list = self.get_active_window().get_visible_page().dir_list
        if isinstance(dir_list, Gtk.DirectoryList):
            dir_list.set_monitored(False)
            dir_list.set_monitored(True)
            return

        if isinstance(dir_list, Gtk.FlattenListModel):
            model = dir_list.get_model()
            index = 0
            while item := model.get_item(index):
                item.set_monitored(False)
                item.set_monitored(True)
                index += 1

    def __new_folder(self, *_args: Any) -> None:
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

        def set_incative(popover: Gtk.Popover, *_args: Any) -> None:
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
            dialog.close()

        def handle_response(_dialog: Adw.MessageDialog, response: str) -> None:
            if response == "create":
                create_folder()

        dialog.connect("response", handle_response)
        entry.connect("entry-activated", create_folder)
        entry.connect("changed", set_incative)

        dialog.choose()

    def __copy(self, *_args: Any) -> None:
        self.cut_page = None
        clipboard = Gdk.Display.get_default().get_clipboard()
        if not (items := self.get_gfiles_from_positions(self.get_selected_items())):
            return

        provider = Gdk.ContentProvider.new_for_value(Gdk.FileList.new_from_array(items))

        clipboard.set_content(provider)

    def __cut(self, *args: Any) -> None:
        self.__copy(*args)
        self.cut_page = self.get_active_window().get_visible_page()

    def __paste(self, *_args: Any) -> None:
        clipboard = Gdk.Display.get_default().get_clipboard()
        paths = []

        if not clipboard.get_formats().contain_gtype(Gdk.FileList):
            return

        def __callback(clipboard, result) -> None:
            nonlocal paths

            try:
                file_list = clipboard.read_value_finish(result)
            except GLib.Error:
                self.cut_page = None
                return

            page = self.get_active_window().get_visible_page()
            for gfile in file_list:
                if page.tags:
                    dst = Path(
                        shared.home,
                        *(tag for tag in shared.tags if tag in page.tags),
                    )
                else:
                    dst = page.path
                try:
                    src = Path(gfile.get_path())
                except TypeError:  # If the value being pasted isn't a pathlike
                    continue
                if not src.exists():
                    continue

                dst = dst / src.name

                if self.cut_page:
                    try:
                        shutil.move(src, dst.parent)
                    except (
                        OSError,
                        IsADirectoryError,
                        NotADirectoryError,
                        FileExistsError,
                    ):
                        continue
                    else:
                        paths.append((src, dst))

                else:
                    if src.is_dir():
                        try:
                            shutil.copytree(src, dst)
                        except FileExistsError:
                            self.get_active_window().send_toast(
                                _("A folder with that name already exists.")
                            )
                            continue
                        else:
                            paths.append(dst)
                    elif src.is_file():
                        # TODO: Ask before replacing
                        try:
                            shutil.copyfile(src, dst)
                        except (OSError, shutil.Error, shutil.SameFileError):
                            continue
                        else:
                            paths.append(dst)

            if self.cut_page:
                self.undo_queue[time()] = ("cut", paths)
            else:
                self.undo_queue[time()] = ("copy", paths)
            self.cut_page = None

        clipboard.read_value_async(
            Gdk.FileList, GLib.PRIORITY_DEFAULT, None, __callback
        )

    def __select_all(self, *_args: Any) -> None:
        self.get_active_window().get_visible_page().multi_selection.select_all()

    def __rename(self, *_args: Any) -> None:
        # TODO: Maybe make it stop iteration on first item?
        try:
            position = self.get_selected_items()[0]
        except IndexError:
            return
        # TODO: Get edit name from gfile
        gfile = self.get_gfiles_from_positions([position])[0]
        path = Path(gfile.get_path())

        multi_selection = self.get_active_window().get_visible_page().multi_selection
        multi_selection.select_item(position, True)

        children = (
            self.get_active_window().get_visible_page().grid_view.observe_children()
        )

        # TODO: This may be slow
        index = 0
        while item := children.get_item(index):
            if item.get_first_child().gfile == gfile:
                (popover := self.get_active_window().rename_popover).set_parent(item)
                break
            index += 1

        if path.is_dir():
            self.get_active_window().rename_label.set_label(_("Rename Folder"))
        else:
            self.get_active_window().rename_label.set_label(_("Rename File"))

        entry = self.get_active_window().rename_entry
        entry.set_text(path.name)

        button = self.get_active_window().rename_button
        revealer = self.get_active_window().rename_revealer
        revealer_label = self.get_active_window().rename_revealer_label
        can_rename = True

        def rename(*_args: Any) -> None:
            popover.popdown()
            try:
                old_name = path.name
                new_file = gfile.set_display_name(entry.get_text().strip())
            except GLib.Error:
                pass
            else:
                self.undo_queue[time()] = ("rename", new_file, old_name)

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

        def unparent(popover):
            popover.unparent()

        popover.connect("notify::visible", set_incative)
        popover.connect("closed", unparent)
        entry.connect("changed", set_incative)
        entry.connect("entry-activated", rename)
        button.connect("clicked", rename)

        popover.popup()
        entry.select_region(0, len(path.name) - len("".join(path.suffixes)))

    def __trash(self, *_args: Any) -> None:
        gfiles = self.get_gfiles_from_positions(self.get_selected_items())

        files = []
        n = 0
        for gfile in gfiles:
            try:
                gfile.trash()
            except GLib.Error:
                pass
            else:
                files.append((gfile.get_path(), int(time())))
                n += 1

        if not n:
            return

        if n > 1:
            message = _("{} files moved to trash").format(n)
        elif n:
            message = _("{} moved to trash").format(
                # TODO: Use the GFileInfo's display name maybe?
                '"'
                + Path(gfile.get_path()).name  # pylint: disable=undefined-loop-variable
                + '"'
            )

        toast = self.get_active_window().send_toast(message, undo=True)
        self.undo_queue[toast] = ("trash", files)
        toast.connect("button-clicked", self.__undo)

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
