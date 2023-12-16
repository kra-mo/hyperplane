# items_page.py
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

from pathlib import Path
from time import time
from typing import Any, Callable, Iterable, Optional

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Xdp, XdpGtk4

from hyperplane import shared
from hyperplane.item import HypItem
from hyperplane.item_filter import HypItemFilter
from hyperplane.item_sorter import HypItemSorter
from hyperplane.utils.files import (
    copy,
    get_copy_path,
    get_gfile_display_name,
    get_gfile_path,
    move,
    restore,
    rm,
    trash_rm,
)
from hyperplane.utils.iterplane import iterplane
from hyperplane.utils.validate_name import validate_name


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/items-page.ui")
class HypItemsPage(Adw.NavigationPage):
    __gtype_name__ = "HypItemsPage"

    scrolled_window: Gtk.ScrolledWindow = Gtk.Template.Child()
    grid_view: Gtk.GridView = Gtk.Template.Child()
    empty_folder: Adw.StatusPage = Gtk.Template.Child()
    empty_trash: Adw.StatusPage = Gtk.Template.Child()
    no_results: Adw.StatusPage = Gtk.Template.Child()

    multi_selection: Gtk.MultiSelection
    item_filter: HypItemFilter
    filter_list: Gtk.FilterListModel
    sorter: HypItemSorter
    sorter: Gtk.CustomSorter
    sort_list: Gtk.SortListModel
    dir_list: Gtk.FlattenListModel | Gtk.DirectoryList
    factory: Gtk.SignalListItemFactory

    action_group: Gio.SimpleActionGroup

    def __init__(
        self,
        gfile: Optional[Gio.File] = None,
        tags: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.gfile = gfile
        self.tags = tags

        if self.gfile:
            if self.gfile.get_path() == str(shared.home):
                self.set_title(_("Home"))
            else:
                self.set_title(get_gfile_display_name(self.gfile))
        elif self.tags:
            self.set_title(" + ".join(self.tags))

        # Right click
        gesture_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        gesture_click.connect("pressed", self.__right_click)
        self.add_controller(gesture_click)

        # Drag and drop
        # TODO: Accept more actions than just copy
        # TODO: Provide DragSource (why is it so hard with rubberbanding TwT)
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self.__drop)
        self.add_controller(drop_target)

        shared.postmaster.connect("toggle-hidden", self.__toggle_hidden)

        self.dir_list = self.__get_list(self.gfile, self.tags)
        self.item_filter = HypItemFilter()
        self.filter_list = Gtk.FilterListModel.new(self.dir_list, self.item_filter)

        self.sorter = HypItemSorter()
        self.sort_list = Gtk.SortListModel.new(self.filter_list, self.sorter)

        self.multi_selection = Gtk.MultiSelection.new(self.sort_list)
        self.factory = Gtk.SignalListItemFactory()
        self.grid_view.set_model(self.multi_selection)
        self.grid_view.set_factory(self.factory)

        self.factory.connect("setup", self.__setup)
        self.factory.connect("bind", self.__bind)
        self.factory.connect("unbind", self.__unbind)
        self.grid_view.connect("activate", self.activate)

        self.filter_list.connect("items-changed", self.__items_changed)
        self.__items_changed(self.dir_list)

        # Set up the "page" action group
        self.shortcut_controller = Gtk.ShortcutController.new()
        self.add_controller(self.shortcut_controller)

        self.action_group = Gio.SimpleActionGroup.new()
        self.insert_action_group("page", self.action_group)

        self.create_action(
            "zoom-in",
            self.__on_zoom_in_action,
            ("<primary>plus", "<Primary>KP_Add", "<primary>equal"),
        )
        self.create_action(
            "zoom-out",
            self.__on_zoom_out_action,
            ("<primary>minus", "<Primary>KP_Subtract", "<Primary>underscore"),
        )
        self.create_action(
            "reset-zoom", self.__reset_zoom, ("<primary>0", "<primary>KP_0")
        )
        self.create_action("reload", self.__reload, ("<primary>r", "F5"))

        self.create_action("undo", self.__undo, ("<primary>z",))
        self.create_action("open", self.__open, ("Return", "<primary>o"))
        self.create_action("open-new-tab", self.__open_new_tab, ("<primary>Return",))
        self.create_action(
            "open-new-window", self.__open_new_window, ("<shift>Return",)
        )
        self.create_action("open-with", self.__open_with)
        self.create_action("new-folder", self.__new_folder, ("<primary><shift>n",))
        self.create_action("copy", self.__copy, ("<primary>c",))
        self.create_action("cut", self.__cut, ("<primary>x",))
        self.create_action("paste", self.__paste, ("<primary>v",))
        self.create_action("select-all", self.__select_all, ("<primary>a",))
        self.create_action("rename", self.__rename, ("F2",))
        self.create_action("trash", self.__trash, ("Delete",))
        self.create_action("trash-delete", self.__trash_delete, ("Delete",))
        self.create_action("trash-restore", self.__trash_restore)

    def __get_list(
        self, gfile: Optional[Gio.File] = None, tags: Optional[list[str]] = None
    ) -> Gtk.FlattenListModel | Gtk.DirectoryList:
        attrs = ",".join(
            (
                Gio.FILE_ATTRIBUTE_STANDARD_SYMBOLIC_ICON,
                Gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE,
                Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH,
                Gio.FILE_ATTRIBUTE_STANDARD_IS_HIDDEN,
                Gio.FILE_ATTRIBUTE_STANDARD_DISPLAY_NAME,
                Gio.FILE_ATTRIBUTE_STANDARD_TARGET_URI, # For Recent
            )
        )
        if gfile:
            return Gtk.DirectoryList.new(attrs, gfile)

        list_store = Gio.ListStore.new(Gtk.DirectoryList)
        for plane_path in iterplane(tags):
            list_store.append(
                Gtk.DirectoryList.new(attrs, Gio.File.new_for_path(str(plane_path)))
            )

        return Gtk.FlattenListModel.new(list_store)

    # TODO: Make this more efficient with removed and added?
    # TODO: Make this less prone to showing up during initial population
    def __items_changed(self, filter_list: Gtk.FilterListModel, *_args: Any) -> None:
        if (
            child := self.scrolled_window.get_child()
        ) != self.grid_view and filter_list.get_n_items():
            self.scrolled_window.set_child(self.grid_view)
        if (
            child not in (self.empty_folder, self.empty_trash)
            and not filter_list.get_n_items()
        ):
            if (
                win := self.get_root()
            ) and win.title_stack.get_visible_child() == win.search_entry_clamp:
                self.scrolled_window.set_child(self.no_results)
                return

            if self.gfile and self.gfile.get_uri() != "trash:///":
                self.scrolled_window.set_child(self.empty_folder)
                return

            self.scrolled_window.set_child(self.empty_trash)

    def __setup(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        item.set_child(HypItem(item))

    def __bind(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        item.get_child().bind()

    def __unbind(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        item.get_child().unbind()

    def __toggle_hidden(self, *_args: Any) -> None:
        if shared.show_hidden:
            self.item_filter.changed(Gtk.FilterChange.LESS_STRICT)
        else:
            self.item_filter.changed(Gtk.FilterChange.MORE_STRICT)

    def activate(self, _grid_view: Gtk.GridView, pos: int) -> None:
        """Activates an item at the given position."""
        file_info = self.multi_selection.get_item(pos)
        if not file_info:
            return

        gfile = file_info.get_attribute_object("standard::file")

        if file_info.get_content_type() == "inode/directory":
            self.get_root().tab_view.get_selected_page().get_child().new_page(gfile)
            return

        Gio.AppInfo.launch_default_for_uri(uri := gfile.get_uri())

        recent_data = Gtk.RecentData()
        recent_data.display_name = file_info.get_display_name()
        recent_data.mime_type = file_info.get_content_type()
        recent_data.app_name = "hyperplane"
        recent_data.app_exec = r"hyperplane %u"

        shared.recent_manager.add_full(uri, recent_data)

    def __right_click(self, _gesture, _n, x, y) -> None:
        self.get_root().right_click_menu.unparent()
        self.get_root().right_click_menu.set_parent(self)
        rectangle = Gdk.Rectangle()
        rectangle.x, rectangle.y, rectangle.width, rectangle.height = x, y, 0, 0
        self.get_root().right_click_menu.set_pointing_to(rectangle)
        self.get_root().right_click_menu.popup()

    def __drop(self, _drop_target: Gtk.DropTarget, file_list: GObject.Value, _x, _y):
        # TODO: This is mostly copy-paste from HypWindow.__paste()
        for gfile in file_list:
            if self.tags:
                dst = Path(
                    shared.home,
                    *(tag for tag in shared.tags if tag in self.tags),
                )
            else:
                try:
                    dst = get_gfile_path(self.gfile)
                except FileNotFoundError:
                    continue
            try:
                src = get_gfile_path(gfile)
            except (
                TypeError,  # If the value being dropped isn't a pathlike
                FileNotFoundError,
            ):
                continue
            if not src.exists():
                continue

            dst = dst / src.name

            try:
                copy(src, dst)
            except FileExistsError:
                dst = get_copy_path(dst)
                copy(src, dst)

    def create_action(
        self, name: str, callback: Callable, shortcuts: Optional[Iterable] = None
    ) -> None:
        """Add a page action.

        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
        """
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.action_group.add_action(action)

        # HACK: Use the proper Gio API (I have no idea what it is though)
        if shortcuts:
            for shortcut in shortcuts:
                self.shortcut_controller.add_shortcut(
                    Gtk.Shortcut.new(
                        Gtk.ShortcutTrigger.parse_string(shortcut),
                        Gtk.ShortcutAction.parse_string(f"action(page.{name})"),
                    )
                )

    def __on_zoom_in_action(self, *_args: Any) -> None:
        win = self.get_root()

        if (zoom_level := shared.state_schema.get_uint("zoom-level")) > 4:
            return

        shared.state_schema.set_uint("zoom-level", zoom_level + 1)
        win.update_zoom()

    def __on_zoom_out_action(self, *_args: Any) -> None:
        win = self.get_root()

        if (zoom_level := shared.state_schema.get_uint("zoom-level")) < 2:
            return

        shared.state_schema.set_uint("zoom-level", zoom_level - 1)
        win.update_zoom()

    def __reset_zoom(self, *_args: Any) -> None:
        win = self.get_root()

        shared.state_schema.reset("zoom-level")
        win.update_zoom()

    def __undo(self, obj: Any, *_args: Any) -> None:
        win = self.get_root()

        if not win.undo_queue:
            return

        if isinstance(obj, Adw.Toast):
            index = obj
        else:
            index = tuple(win.undo_queue.keys())[-1]
        item = win.undo_queue[index]

        # TODO: Look up the pages with the paths and update those
        match item[0]:
            case "copy":
                for trash_item in item[1]:
                    if trash_item.is_dir():
                        rm(trash_item)
                    else:
                        trash_item.unlink(missing_ok=True)
            case "cut":
                for paths in item[1]:
                    if paths[1].exists():
                        move(paths[1], paths[0])
            case "rename":
                try:
                    item[1].set_display_name(item[2])
                except GLib.Error:
                    pass
            case "trash":
                for trash_item in item[1]:
                    restore(*trash_item)

        if isinstance(index, Adw.Toast):
            index.dismiss()
        win.undo_queue.popitem()

    def __open(self, *_args: Any) -> None:
        win = self.get_root()

        if len(positions := win.get_selected_items()) > 1:
            # TODO: Maybe switch to newly opened tab like Nautilus?
            self.__open_new_tab(None, None, positions)
            return

        if not positions:
            return

        self.activate(None, positions[0])

    def __open_new_tab(
        self, _obj: Any, _parameter: Any, positions: Optional[list[int]] = None
    ) -> None:
        win = self.get_root()

        if not positions:
            positions = win.get_selected_items()

        gfiles = win.get_gfiles_from_positions(positions)

        for gfile in gfiles:
            win.new_tab(gfile)

    def __open_new_window(self, *_args: Any) -> None:
        win = self.get_root()

        gfiles = win.get_gfiles_from_positions(win.get_selected_items())

        for gfile in gfiles:
            win.new_window(gfile)

    def __open_with(self, *_args: Any) -> None:
        win = self.get_root()

        portal = Xdp.Portal()
        parent = XdpGtk4.parent_new_gtk(win)
        gfiles = win.get_gfiles_from_positions(win.get_selected_items())
        if not gfiles:
            return

        # TODO: Is there any way to open multiple files?
        portal.open_uri(parent, gfiles[0].get_uri(), Xdp.OpenUriFlags.ASK)

    def __reload(self, *_args: Any) -> None:
        if isinstance(self.dir_list, Gtk.DirectoryList):
            self.dir_list.set_monitored(False)
            self.dir_list.set_monitored(True)
            return

        # TODO: This works, but it would be best if instead of manually refreshing,
        # tags would be monitored for changes too. I don't know how I would do that though.
        if isinstance(self.dir_list, Gtk.FlattenListModel):
            self.dir_list = self.__get_list(tags=self.tags)
            self.filter_list.set_model(self.dir_list)

    def __new_folder(self, *_args: Any) -> None:
        path = None

        if self.tags:
            path = Path(shared.home, *(tag for tag in shared.tags if tag in self.tags))

        if not path:
            try:
                path = get_gfile_path(self.gfile)
            except FileNotFoundError:
                return

        dialog = Adw.MessageDialog.new(self.get_root(), _("New Folder"))

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

            can_create, message = validate_name(Gio.File.new_for_path(str(path)), text)
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
        win = self.get_root()

        win.cut_page = None
        clipboard = Gdk.Display.get_default().get_clipboard()
        if not (items := win.get_gfiles_from_positions(win.get_selected_items())):
            return

        provider = Gdk.ContentProvider.new_for_value(Gdk.FileList.new_from_array(items))

        clipboard.set_content(provider)

    def __cut(self, _obj: Any, *args: Any) -> None:
        win = self.get_root()

        self.__copy(*args)
        win.cut_page = self

    def __paste(self, *_args: Any) -> None:
        win = self.get_root()

        clipboard = Gdk.Display.get_default().get_clipboard()
        paths = []

        if not clipboard.get_formats().contain_gtype(Gdk.FileList):
            return

        def __cb(clipboard, result) -> None:
            nonlocal paths

            try:
                file_list = clipboard.read_value_finish(result)
            except GLib.Error:
                win.cut_page = None
                return

            for gfile in file_list:
                if self.tags:
                    dst = Path(
                        shared.home,
                        *(tag for tag in shared.tags if tag in self.tags),
                    )
                else:
                    try:
                        dst = get_gfile_path(self.gfile)
                    except FileNotFoundError:
                        continue
                try:
                    src = get_gfile_path(gfile)
                except (
                    TypeError,  # If the value being pasted isn't a pathlike
                    FileNotFoundError,
                ):
                    continue
                if not src.exists():
                    continue

                dst = dst / src.name

                if win.cut_page:
                    try:
                        move(src, dst)
                    except FileExistsError:
                        win.send_toast(
                            _("A folder with that name already exists.")
                            if src.is_dir()
                            else _("A file with that name already exists.")
                        )
                        continue
                    else:
                        paths.append((src, dst))

                else:
                    try:
                        copy(src, dst)
                    except FileExistsError:
                        dst = get_copy_path(dst)
                        copy(src, dst)

                    paths.append(dst)

            if win.cut_page:
                win.undo_queue[time()] = ("cut", paths)
            else:
                win.undo_queue[time()] = ("copy", paths)
            win.cut_page = None

        clipboard.read_value_async(Gdk.FileList, GLib.PRIORITY_DEFAULT, None, __cb)

    def __select_all(self, *_args: Any) -> None:
        self.multi_selection.select_all()

    def __rename(self, *_args: Any) -> None:
        win = self.get_root()

        # TODO: Maybe make it stop iteration on first item?
        try:
            position = win.get_selected_items()[0]
        except IndexError:
            return
        # TODO: Get edit name from gfile
        gfile = win.get_gfiles_from_positions([position])[0]

        try:
            path = get_gfile_path(gfile)
        except FileNotFoundError:
            return

        self.multi_selection.select_item(position, True)

        children = self.grid_view.observe_children()

        # TODO: This may be slow
        index = 0
        while item := children.get_item(index):
            if item.get_first_child().gfile == gfile:
                (popover := win.rename_popover).set_parent(item)
                break
            index += 1

        if path.is_dir():
            win.rename_label.set_label(_("Rename Folder"))
        else:
            win.rename_label.set_label(_("Rename File"))

        entry = win.rename_entry
        entry.set_text(path.name)

        button = win.rename_button
        revealer = win.rename_revealer
        revealer_label = win.rename_revealer_label
        can_rename = True

        def rename(obj: Any, *_args: Any) -> None:
            if isinstance(obj, Gio.SimpleAction) and (not self.is_focus()):
                return

            popover.popdown()
            try:
                old_name = path.name
                new_file = gfile.set_display_name(entry.get_text().strip())
            except GLib.Error:
                pass
            else:
                win.undo_queue[time()] = ("rename", new_file, old_name)

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

            can_rename, message = validate_name(
                Gio.File.new_for_path(str(path)), text, True
            )
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

    def __trash(self, *args) -> None:
        win = self.get_root()

        gfiles = win.get_gfiles_from_positions(win.get_selected_items())

        # When the Delete key is pressed but the user is in the trash
        if gfiles and gfiles[0].get_uri().startswith("trash://"):
            self.__trash_delete(*args)

        files = []
        n = 0
        for gfile in gfiles:
            try:
                gfile.trash()
            except GLib.Error:
                pass
            else:
                try:
                    files.append((get_gfile_path(gfile), int(time())))
                except FileNotFoundError:
                    continue
                else:
                    n += 1

        if not n:
            return

        if n > 1:
            message = _("{} files moved to trash").format(n)
        elif n:
            # TODO: Use the GFileInfo's display name maybe
            message = _("{} moved to trash").format(
                f'"{files[0][0].name}"'  # pylint: disable=undefined-loop-variable
            )

        toast = win.send_toast(message, undo=True)
        win.undo_queue[toast] = ("trash", files)
        toast.connect("button-clicked", self.__undo)

    def __trash_delete(self, *args: Any) -> None:
        win = self.get_root()

        gfiles = win.get_gfiles_from_positions(win.get_selected_items())

        # When the Delete key is pressed but the user is not in the trash
        if gfiles and (not gfiles[0].get_uri().startswith("trash://")):
            self.__trash_delete(*args)

        def delete():
            for gfile in gfiles:
                trash_rm(gfile)

        match len(gfiles):
            case 0:
                return
            case 1:
                # TODO: Blocking I/O for this? Really?
                msg = _("Are you sure you want to permanently delete {}?").format(
                    f'"{get_gfile_display_name(gfiles[0])}"'
                )
            case _:
                # The variable is the number of items to be deleted
                msg = _(
                    "Are you sure you want to permanently delete the {} selected items?"
                ).format(len(gfiles))

        dialog = Adw.MessageDialog.new(self.get_root(), msg)
        dialog.set_body(_("If you delete an item, it will be permanently lost."))

        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("delete", _("Delete"))

        dialog.set_default_response("delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def handle_response(_dialog: Adw.MessageDialog, response: str) -> None:
            if response == "delete":
                delete()

        dialog.connect("response", handle_response)
        dialog.present()

    def __trash_restore(self, *_args: Any) -> None:
        win = self.get_root()

        gfiles = win.get_gfiles_from_positions(win.get_selected_items())

        for gfile in gfiles:
            restore(gfile=gfile)
