# items_page.py
#
# Copyright 2023-2024 kramo
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

"""A view of `HypItem`s to be added to an `AdwNavigationView`."""
import logging
from collections import namedtuple
from itertools import chain
from pathlib import Path
from shutil import get_unpack_formats, unpack_archive
from time import time
from typing import Any, Callable, Generator, Iterable, Optional

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Pango, Xdp, XdpGtk4

from hyperplane import shared
from hyperplane.item import HypItem
from hyperplane.item_filter import HypItemFilter
from hyperplane.item_sorter import HypItemSorter
from hyperplane.new_file_dialog import HypNewFileDialog
from hyperplane.utils.create_message_dialog import create_message_dialog
from hyperplane.utils.dates import relative_date
from hyperplane.utils.files import (
    YouAreStupid,
    copy,
    get_copy_gfile,
    get_gfile_display_name,
    get_gfile_path,
    move,
    restore,
    rm,
    trash,
    validate_name,
)
from hyperplane.utils.iterplane import iterplane


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/items-page.ui")
class HypItemsPage(Adw.NavigationPage):
    """A view of `HypItem`s to be added to an `AdwNavigationView`."""

    __gtype_name__ = "HypItemsPage"

    scrolled_window: Gtk.ScrolledWindow = Gtk.Template.Child()
    grid_view: Gtk.GridView = Gtk.Template.Child()
    column_view: Gtk.ColumnView = Gtk.Template.Child()
    empty_folder: Adw.StatusPage = Gtk.Template.Child()
    no_matching_items: Adw.StatusPage = Gtk.Template.Child()
    empty_trash: Adw.StatusPage = Gtk.Template.Child()
    no_recents: Adw.StatusPage = Gtk.Template.Child()
    no_results: Adw.StatusPage = Gtk.Template.Child()
    loading: Gtk.Viewport = Gtk.Template.Child()

    def __init__(
        self,
        gfile: Optional[Gio.File] = None,
        tags: Optional[list[str]] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.gfile = gfile
        self.tags = tags
        self.items = {}
        self.list_items = {}

        if self.gfile:
            if self.gfile.get_path() == str(shared.home_path):
                self.set_title(_("Home"))
            else:
                self.set_title(get_gfile_display_name(self.gfile))
        elif self.tags:
            self.set_title(" + ".join(self.tags))

        # Right-click
        right_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right_click.connect("pressed", self.__right_click)
        self.add_controller(right_click)
        self.menu_items = None
        self.view_right_clicked = False

        shared.postmaster.connect("tags-changed", self.__tags_changed)
        shared.postmaster.connect("toggle-hidden", self.__toggle_hidden)

        self.file_attrs = ",".join(
            (
                Gio.FILE_ATTRIBUTE_STANDARD_SYMBOLIC_ICON,
                Gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE,
                Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH,
                Gio.FILE_ATTRIBUTE_STANDARD_IS_HIDDEN,
                Gio.FILE_ATTRIBUTE_STANDARD_DISPLAY_NAME,
                Gio.FILE_ATTRIBUTE_STANDARD_EDIT_NAME,
                Gio.FILE_ATTRIBUTE_STANDARD_TARGET_URI,  # For Recent
                Gio.FILE_ATTRIBUTE_TRASH_DELETION_DATE,  # For Trash
                Gio.FILE_ATTRIBUTE_FILESYSTEM_USE_PREVIEW,
                # For list view
                Gio.FILE_ATTRIBUTE_STANDARD_SIZE,
                Gio.FILE_ATTRIBUTE_TIME_MODIFIED,
                Gio.FILE_ATTRIBUTE_TIME_CREATED,
            )
        )

        self.dir_list = self.__get_list(self.gfile, self.tags)

        # Filtering
        self.item_filter = HypItemFilter()
        self.filter_list = Gtk.FilterListModel.new(self.dir_list, self.item_filter)
        self.filter_list.connect("items-changed", self.__items_changed)

        # Sorting
        self.sorter = HypItemSorter()
        self.sort_list = Gtk.SortListModel.new(self.filter_list, self.sorter)

        # Selection
        self.multi_selection = Gtk.MultiSelection.new(self.sort_list)

        # Item factory
        self.item_factory = Gtk.SignalListItemFactory()
        self.item_factory.connect("setup", self.__item_setup)
        self.item_factory.connect("bind", self.__item_bind)
        self.item_factory.connect("unbind", self.__item_unbind)

        self.view = (
            self.__get_grid_view()
            if shared.state_schema.get_boolean("grid-view")
            else self.__get_column_view()
        )

        shared.postmaster.connect("view-changed", self.__view_changed)

        self.__items_changed()
        shared.postmaster.connect("tag-location-created", self.__tag_location_created)

        # Set up the `page` action group
        self.shortcut_controller = Gtk.ShortcutController.new()
        self.add_controller(self.shortcut_controller)

        self.action_group = Gio.SimpleActionGroup.new()
        self.insert_action_group("page", self.action_group)

        self.create_action("undo", self.__undo, ("<primary>z",))
        self.create_action("open", self.__open, ("Return", "<primary>o"))
        self.create_action("open-new-tab", self.__open_new_tab, ("<primary>Return",))
        self.create_action(
            "open-new-window", self.__open_new_window, ("<shift>Return",)
        )
        self.create_action("open-with", self.__open_with)
        self.create_action("new-folder", self.__new_folder, ("<primary><shift>n",))
        self.create_action("new-file", self.__new_file, ("<primary><alt>n",))
        self.create_action("copy", self.__copy, ("<primary>c",))
        self.create_action("cut", self.__cut, ("<primary>x",))
        self.create_action("paste", self.__paste, ("<primary>v",))
        self.create_action("select-all", self.__select_all, ("<primary>a",))
        self.create_action("trash", self.__trash, ("Delete",))
        self.create_action("trash-delete", self.__trash_delete, ("Delete",))
        self.create_action("trash-restore", self.__trash_restore)

        # Set up zoom scrolling
        self.scroll = Gtk.EventControllerScroll.new(
            (
                Gtk.EventControllerScrollFlags.VERTICAL
                | Gtk.EventControllerScrollFlags.DISCRETE
            ),
        )
        self.scroll.connect("scroll", self.__scroll)
        self.scrolled_window.add_controller(self.scroll)

    def reload(self) -> None:
        """Refresh the view."""
        if isinstance(self.dir_list, Gtk.DirectoryList):
            self.dir_list.set_monitored(False)
            self.dir_list.set_monitored(True)
            return

        if isinstance(self.dir_list, Gtk.FlattenListModel):
            self.dir_list = self.__get_list(tags=self.tags)
            self.filter_list.set_model(self.dir_list)

    def get_selected_positions(self) -> list[int]:
        """Gets the list of positions for selected items in the view."""
        not_empty, bitset_iter, position = Gtk.BitsetIter.init_first(
            self.multi_selection.get_selection()
        )

        if not not_empty:
            return []

        positions = [position]

        while True:
            next_val, pos = bitset_iter.next()
            if not next_val:
                break
            positions.append(pos)

        return positions

    def get_gfiles_from_positions(self, positions: list[int]) -> list[Gio.File]:
        """Get a list of `GFile`s corresponding to positions in the list model."""
        files = []

        for position in positions:
            files.append(
                self.multi_selection.get_item(position).get_attribute_object(
                    "standard::file"
                )
            )

        return files

    def get_infos_from_positions(self, positions: list[int]) -> list[Gio.FileInfo]:
        """Get a list of `GFileInfo`s corresponding to positions in the list model."""
        infos = []

        for position in positions:
            infos.append(self.multi_selection.get_item(position))

        return infos

    def get_selected_gfiles(self) -> list[Gio.File]:
        """
        Gets a list of `GFiles` representing
        the currently selected items in the view.
        """
        return self.get_gfiles_from_positions(self.get_selected_positions())

    def get_selected_infos(self) -> list[Gio.FileInfo]:
        """
        Gets a list of `GFilesInfos` representing
        the currently selected items in the view.
        """
        return self.get_infos_from_positions(self.get_selected_positions())

    def activate(self, _list: Gtk.ListBase, pos: int) -> None:
        """Activates an item at the given position."""
        file_info = self.multi_selection.get_item(pos)
        if not file_info:
            return

        gfile = file_info.get_attribute_object("standard::file")

        content_type = file_info.get_content_type()

        # Open in the app if it is a directory
        if content_type == "inode/directory":
            self.get_root().new_page(gfile)
            return

        # Unpack if is it an archive
        # TODO: Rename the right-click menu item here
        try:
            assert (path := gfile.get_path())
            assert (dst := self.get_dst().get_path())
        except AssertionError:
            pass
        else:
            if path.endswith(
                tuple(
                    chain(*(unpack_format[1] for unpack_format in get_unpack_formats()))
                )
            ):
                # Removing the `.tar` suffix is a hack,
                # but it works and I can't think of a better solution
                if (
                    extract_dir := Path(dst) / Path(path).stem.removesuffix(".tar")
                ).is_dir():
                    self.get_root().send_toast(
                        _("A folder with that name already exists")
                    )
                    return

                GLib.Thread.new(None, unpack_archive, path, extract_dir)
                return

        # Open externally otherwise
        if not (
            uri := file_info.get_attribute_string(
                Gio.FILE_ATTRIBUTE_STANDARD_TARGET_URI
            )
        ):
            uri = gfile.get_uri()

        Gio.AppInfo.launch_default_for_uri(uri)

        # Don't add trashed items to Recent
        if gfile.get_uri_scheme() == "trash":
            return

        recent_data = Gtk.RecentData()
        recent_data.display_name = file_info.get_display_name()
        recent_data.mime_type = file_info.get_content_type()
        recent_data.app_name = "hyperplane"
        recent_data.app_exec = r"hyperplane %u"

        shared.recent_manager.add_full(uri, recent_data)

    def get_dst(self) -> Gio.File:
        """Gets the destination `GFile` for paste operations to the page."""
        if self.tags:
            tags = tuple(tag for tag in shared.tags if tag in self.tags)
            return Gio.File.new_for_path(
                str(
                    Path(
                        shared.home_path,
                        *tags,
                    )
                )
            )

        return self.gfile

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
                        Gtk.NamedAction.new(f"page.{name}"),
                    )
                )

    def __get_list(
        self, gfile: Optional[Gio.File] = None, tags: Optional[list[str]] = None
    ) -> Gtk.DirectoryList | Gtk.FlattenListModel:
        if gfile:
            dir_list = Gtk.DirectoryList.new(self.file_attrs, gfile)
            dir_list.connect("notify::loading", lambda *_: self.__items_changed())

            return dir_list

        list_store = Gio.ListStore.new(Gtk.DirectoryList)
        for plane_path in iterplane(tags):
            list_store.append(
                dir_list := Gtk.DirectoryList.new(
                    self.file_attrs, Gio.File.new_for_path(str(plane_path))
                )
            )
            dir_list.connect("notify::loading", lambda *_: self.__items_changed())

        return Gtk.FlattenListModel.new(list_store)

    def __tag_location_created(
        self, _obj: Any, string_list: Gtk.StringList, new_location: Gio.File
    ):
        if not self.tags:
            return

        tags = set()
        index = 0
        while string := string_list.get_item(index):
            tags.add(string.get_string())
            index += 1

        if all(tag in self.tags for tag in tags):
            self.dir_list.get_model().append(
                Gtk.DirectoryList.new(self.file_attrs, new_location)
            )

    def __items_changed(
        self,
        _filter_list: Optional[Gtk.FilterListModel] = None,
        _pos: Optional[int] = 0,
        removed: Optional[int] = 1,
        added: Optional[int] = 1,
    ) -> None:
        page = self.scrolled_window.get_child()
        n_items = self.filter_list.get_n_items()

        if added and n_items and (page != self.view):
            if page == self.loading:
                self.loading.get_child().stop()

            self.scrolled_window.set_child(self.view)
            return

        if removed and (not n_items):
            if (
                win := self.get_root()
            ) and win.title_stack.get_visible_child() == win.search_entry_clamp:
                self.scrolled_window.set_child(self.no_results)
                return

            if self.gfile:
                if self.dir_list.is_loading():
                    self.loading.get_child().start()
                    self.scrolled_window.set_child(self.loading)
                    return

                if self.gfile.get_uri() == "trash:///":
                    self.scrolled_window.set_child(self.empty_trash)
                    return

                elif self.gfile.get_uri() == "recent:///":
                    self.scrolled_window.set_child(self.no_recents)
                    return

                self.scrolled_window.set_child(self.empty_folder)

            if self.tags:
                model = self.dir_list.get_model()
                index = 0
                while dir_list := model.get_item(index):
                    if dir_list.is_loading():
                        self.loading.get_child().start()
                        self.scrolled_window.set_child(self.loading)
                        return
                    index += 1

                self.scrolled_window.set_child(self.no_matching_items)
                return

    def __item_setup(
        self, _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        list_item.set_child(HypItem(list_item, self))

    def __item_bind(
        self, _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        list_item.get_child().bind()
        pos = list_item.get_position()

        self.items[pos] = list_item.get_child()

        # For the org.freedesktop.FileManager1 DBus service's ShowItems
        if (
            list_item.get_item().get_attribute_object("standard::file").get_uri()
            != self.get_root().select_uri
        ):
            return

        self.get_root().select_uri = None

        # Not scrolling there because Grid/ColumnView really don't like that during population
        self.multi_selection.select_item(pos, True)

    def __item_unbind(
        self, _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        list_item.get_child().unbind()

    def __tags_changed(self, _obj: GObject.Object, change: Gtk.FilterChange) -> None:
        self.item_filter.changed(change)

    def __toggle_hidden(self, *_args: Any) -> None:
        if shared.show_hidden:
            self.item_filter.changed(Gtk.FilterChange.LESS_STRICT)
        else:
            self.item_filter.changed(Gtk.FilterChange.MORE_STRICT)

    def __get_grid_view(self) -> Gtk.GridView:
        # Only set up the view once
        if not self.grid_view.get_model():
            shared.schema.bind(
                "single-click-open",
                self.grid_view,
                "single-click-activate",
                Gio.SettingsBindFlags.DEFAULT,
            )

            self.grid_view.set_factory(self.item_factory)
            self.grid_view.set_model(self.multi_selection)
            self.grid_view.connect("activate", self.activate)

        return self.grid_view

    def __get_column_view(self) -> Gtk.ColumnView:
        # Only set up the view once
        if not self.column_view.get_model():
            shared.schema.bind(
                "single-click-open",
                self.column_view,
                "single-click-activate",
                Gio.SettingsBindFlags.DEFAULT,
            )

            self.column_view.append_column(
                Gtk.ColumnViewColumn(
                    title=_("Item"),
                    factory=self.item_factory,
                    resizable=True,
                    expand=True,
                )
            )
            for column in self.__get_property_columns():
                self.column_view.append_column(column)

            self.column_view.set_model(self.multi_selection)
            self.column_view.connect("activate", self.activate)

        return self.column_view

    def __get_property_columns(self) -> Generator:
        Prop = namedtuple("Prop", ("title", "bind_func"))
        properties = (
            Prop(
                _("Size"),
                lambda _factory, item: item.get_child().set_label(
                    _("Folder")
                    if item.get_item().get_content_type() == "inode/directory"
                    else GLib.format_size(item.get_item().get_size())
                    if item.get_item().get_size()
                    else "-"
                ),
            ),
            Prop(
                _("Modified"),
                lambda _factory, item: item.get_child().set_label(
                    relative_date(item.get_item().get_modification_date_time())
                    if item.get_item().get_modification_date_time()
                    else "-"
                ),
            ),
            Prop(
                _("Created"),
                lambda _factory, item: item.get_child().set_label(
                    relative_date(item.get_item().get_creation_date_time())
                    if item.get_item().get_creation_date_time()
                    else "-"
                ),
            ),
        )

        for prop in properties:
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", self.__property_setup)
            factory.connect("bind", prop.bind_func)

            yield Gtk.ColumnViewColumn(
                title=prop.title,
                factory=factory,
                resizable=True,
            )

    def __property_setup(
        self, _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        label = Gtk.Label(halign=Gtk.Align.START, ellipsize=Pango.EllipsizeMode.END)
        label.add_css_class("dim-label")
        list_item.set_child(label)

    def __view_changed(self, *_args: Any) -> None:
        change = self.scrolled_window.get_child() == self.view

        self.view = (
            self.__get_grid_view()
            if shared.state_schema.get_boolean("grid-view")
            else self.__get_column_view()
        )

        if not change:
            return

        self.scrolled_window.set_child(self.view)

    def __popup_menu(self) -> None:
        if self.menu_items:
            self.get_root().set_menu_items(self.menu_items)
            self.menu_items = None
        else:
            self.view_right_clicked = True
            items = {
                "paste",
                "new-folder",
                "new-file",
                "select-all",
                "open-with",
            }

            if self.gfile:
                items.add("properties")

                # Read-only special directories
                if self.gfile.get_uri_scheme() in {
                    "trash",
                    "recent",
                    "burn",
                    "network",
                }:
                    items.remove("paste")
                    items.remove("new-folder")
                    items.remove("new-file")

                    if self.gfile.get_uri() == "trash:///":
                        if shared.trash_list.get_n_items():
                            items.add("empty-trash")

                    if self.gfile.get_uri() == "recent:///":
                        if bool(shared.recent_manager.get_items()):
                            items.add("clear-recents")

            self.get_root().set_menu_items(items)

        self.get_root().right_click_menu.popup()

    def __right_click(self, _gesture, _n, x, y) -> None:
        self.get_root().right_click_menu.unparent()
        self.get_root().right_click_menu.set_parent(self)
        rectangle = Gdk.Rectangle()
        rectangle.x, rectangle.y, rectangle.width, rectangle.height = x, y, 0, 0
        self.get_root().right_click_menu.set_pointing_to(rectangle)
        # HACK: Timeout hack because of the right-click callback race condition
        # between the items page and the item
        GLib.timeout_add(10, self.__popup_menu)

    def __undo(self, obj: Any, *_args: Any) -> None:
        if not shared.undo_queue:
            return

        if isinstance(obj, Adw.Toast):
            index = obj
        else:
            index = tuple(shared.undo_queue.keys())[-1]
        item = shared.undo_queue[index]

        match item[0]:
            case "copy":
                for copy_item in item[1]:
                    try:
                        rm(copy_item)
                    except FileNotFoundError:
                        logging.debug("Cannot undo copy: File doesn't exist anymore.")
            case "move":
                for gfiles in item[1]:
                    try:
                        move(gfiles[1], gfiles[0])
                    except FileExistsError:
                        logging.debug("Cannot undo move: File exists.")
                    except YouAreStupid:
                        logging.debug("Cannot undo move: Someone is being stupid.")
            case "rename":
                try:
                    item[1].set_display_name(item[2])
                except GLib.Error as error:
                    logging.debug("Cannot undo rename: %s", error)
            case "trash":
                for trash_item in item[1]:
                    restore(*trash_item)

        if isinstance(index, Adw.Toast):
            index.dismiss()
        shared.undo_queue.popitem()

    def __open(self, *_args: Any) -> None:
        if len(positions := self.get_selected_positions()) > 1:
            # TODO: Maybe switch to newly opened tab like Nautilus?
            self.__open_new_tab(None, None, positions)
            return

        if not positions:
            return

        self.activate(None, positions[0])

    def __open_new_tab(
        self, _obj: Any, _parameter: Any, positions: Optional[list[int]] = None
    ) -> None:
        if not positions:
            positions = self.get_selected_positions()

        gfiles = self.get_gfiles_from_positions(positions)

        for gfile in gfiles:
            self.get_root().new_tab(gfile)

    def __open_new_window(self, *_args: Any) -> None:
        gfiles = self.get_selected_gfiles()

        for gfile in gfiles:
            self.get_root().new_window(gfile)

    def __open_with(self, *_args: Any) -> None:
        portal = Xdp.Portal()
        parent = XdpGtk4.parent_new_gtk(self.get_root())
        gfiles = [self.gfile] if self.view_right_clicked else self.get_selected_gfiles()
        self.view_right_clicked = False
        if not gfiles:
            return

        # TODO: Is there any way to open multiple files?
        portal.open_uri(parent, gfiles[0].get_uri(), Xdp.OpenUriFlags.ASK)

    def __new_file(self, *_args: Any) -> None:
        dst = self.get_dst()

        dialog = HypNewFileDialog(dst)
        dialog.set_transient_for(self.get_root())
        dialog.present()

    def __new_folder(self, *_args: Any) -> None:
        dst = self.get_dst()

        preferences_group = Adw.PreferencesGroup(width_request=360)
        revealer_label = Gtk.Label(
            margin_start=6,
            margin_end=6,
            margin_top=12,
        )
        preferences_group.add(revealer := Gtk.Revealer(child=revealer_label))
        preferences_group.add(entry := Adw.EntryRow(title=_("Folder name")))

        def dialog_cb() -> None:
            create_folder()

        dialog = create_message_dialog(
            self.get_root(),
            _("New Folder"),
            (
                _("Cancel"),
                None,
                None,
                None,
                False,
            ),
            (
                _("Create"),
                "create",
                Adw.ResponseAppearance.SUGGESTED,
                dialog_cb,
                True,
            ),
            extra_child=preferences_group,
        )

        dialog.set_response_enabled("create", False)
        can_create = False

        def set_inactive(*_args: Any) -> None:
            nonlocal can_create

            if not (text := entry.get_text().strip()):
                can_create = False
                dialog.set_response_enabled("create", False)
                revealer.set_reveal_child(False)
                return

            can_create, message = validate_name(dst, text, directory=True)
            dialog.set_response_enabled("create", can_create)
            revealer.set_reveal_child(bool(message))
            if message:
                revealer_label.set_label(message)

        def create_folder(*_args: Any):
            nonlocal can_create

            if not can_create:
                return

            new_gfile = dst.get_child_for_display_name(entry.get_text())
            emit = self.tags and (not new_gfile.get_parent().query_exists())

            new_gfile.make_directory_with_parents()
            dialog.close()

            if not emit:
                return

            shared.postmaster.emit(
                "tag-location-created",
                Gtk.StringList.new(self.tags),
                dst,
            )

        entry.connect("entry-activated", create_folder)
        entry.connect("changed", set_inactive)

        dialog.choose()

    def __copy(self, *_args: Any) -> None:
        shared.set_cut_uris(set())
        clipboard = Gdk.Display.get_default().get_clipboard()
        if not (items := self.get_selected_gfiles()):
            return

        provider = Gdk.ContentProvider.new_for_value(Gdk.FileList.new_from_array(items))

        clipboard.set_content(provider)

    def __cut(self, _obj: Any, *args: Any) -> None:
        self.__copy(*args)
        shared.set_cut_uris(
            set(gfile.get_uri() for gfile in self.get_selected_gfiles())
        )

    def __paste(self, *_args: Any) -> None:
        clipboard = Gdk.Display.get_default().get_clipboard()
        files = []

        dst = self.get_dst()

        def paste_file_cb(clipboard: Gdk.Clipboard, result: Gio.AsyncResult) -> None:
            nonlocal files
            nonlocal dst

            try:
                file_list = clipboard.read_value_finish(result)
            except GLib.Error:
                shared.set_cut_uris(set())
                return

            for src in file_list:
                try:
                    final_dst = Gio.File.new_for_path(
                        str(get_gfile_path(dst) / get_gfile_display_name(src))
                    )
                except (FileNotFoundError, TypeError) as error:
                    logging.debug('Cannot paste file "%s": %s', src.get_uri(), error)
                    continue

                if shared.cut_uris:
                    try:
                        move(src, final_dst)
                    except FileExistsError:
                        self.get_root().send_toast(
                            _("A folder with that name already exists")
                            if src.query_file_type(Gio.FileQueryInfoFlags.NONE)
                            == Gio.FileType.DIRECTORY
                            else _("A file with that name already exists")
                        )
                        continue
                    except YouAreStupid:
                        self.get_root().send_toast(
                            _("You cannot move a folder into itself")
                        )
                        continue
                    else:
                        files.append((src, final_dst))

                else:
                    try:
                        copy(src, final_dst)
                    except FileExistsError:
                        try:
                            final_dst = get_copy_gfile(final_dst)
                            copy(src, final_dst)
                        except (FileExistsError, FileNotFoundError) as error:
                            logging.debug(
                                'Cannot paste file "%s": %s', src.get_uri(), error
                            )
                            continue

                    files.append(final_dst)

            if shared.cut_uris:
                shared.undo_queue[time()] = ("move", files)
            else:
                shared.undo_queue[time()] = ("copy", files)
            shared.set_cut_uris(set())

        def paste_texture_cb(clipboard: Gdk.Clipboard, result: Gio.AsyncResult) -> None:
            nonlocal dst

            try:
                texture = clipboard.read_value_finish(result)
            except GLib.Error as error:
                logging.debug("Cannot create texture: %s", error)
                return

            texture_bytes = texture.save_to_png_bytes()

            dst = dst.get_child_for_display_name(_("Pasted Image") + ".png")

            if dst.query_exists():
                dst = get_copy_gfile(dst)
                try:
                    stream = dst.create_readwrite(Gio.FileCreateFlags.NONE)
                except GLib.Error as error:
                    logging.error("Cannot open stream for pasting texture: %s", error)
                    return
            else:
                try:
                    stream = dst.create_readwrite(Gio.FileCreateFlags.NONE)
                except GLib.Error as error:
                    logging.error("Cannot open stream for pasting texture: %s", error)
                    return

            output = stream.get_output_stream()
            output.write_bytes(texture_bytes)

        formats = clipboard.get_formats()

        if formats.contain_gtype(Gdk.FileList):
            clipboard.read_value_async(
                Gdk.FileList,
                GLib.PRIORITY_DEFAULT,
                None,
                paste_file_cb,
            )
        elif formats.contain_gtype(Gdk.Texture):
            # Run this threaded because the operation can take a long time
            clipboard.read_value_async(
                Gdk.Texture,
                GLib.PRIORITY_DEFAULT,
                None,
                lambda *args: GLib.Thread.new(None, paste_texture_cb, *args),
            )

    def __select_all(self, *_args: Any) -> None:
        self.multi_selection.select_all()

    def __trash(self, *args) -> None:
        gfiles = self.get_selected_gfiles()

        # When the Delete key is pressed but the user is in the trash
        if gfiles and gfiles[0].get_uri_scheme() == "trash":
            self.__trash_delete(*args)
            return

        files = []
        n = 0
        for gfile in gfiles.copy():
            try:
                files.append((get_gfile_path(gfile), int(time())))
            except FileNotFoundError:
                logging.debug(
                    'Should not trash "%s": File has no path.', gfile.get_uri()
                )
                gfiles.remove(gfile)
                continue

        if not gfiles:
            return

        trash(*gfiles)

        n = len(gfiles)
        if n > 1:
            message = _("{} files moved to trash").format(n)
        else:
            message = _("{} moved to trash").format(
                f"“{get_gfile_display_name(gfiles[0])}”"
            )

        toast = self.get_root().send_toast(message, undo=True)
        shared.undo_queue[toast] = ("trash", files)
        toast.connect("button-clicked", self.__undo)

        self.get_root().trash_animation.play()

    def __trash_delete(self, *args: Any) -> None:
        gfiles = self.get_selected_gfiles()

        # When the Delete key is pressed but the user is not in the trash
        if gfiles and (not gfiles[0].get_uri_scheme() == "trash"):
            self.__trash_delete(*args)

        def delete():
            for gfile in gfiles:
                rm(gfile)

        match len(gfiles):
            case 0:
                return
            case 1:
                msg = _("Are you sure you want to permanently delete {}?").format(
                    f"“{get_gfile_display_name(gfiles[0])}”"
                )
            case _:
                # The variable is the number of items to be deleted
                msg = _(
                    "Are you sure you want to permanently delete the {} selected items?"
                ).format(len(gfiles))

        create_message_dialog(
            self.get_root(),
            msg,
            (_("Cancel"), None, None, None, False),
            (_("Delete"), None, Adw.ResponseAppearance.DESTRUCTIVE, delete, True),
            body=_("If you delete an item, it will be permanently lost."),
        ).present()

    def __trash_restore(self, *_args: Any) -> None:
        gfiles = self.get_selected_gfiles()

        for gfile in gfiles:
            restore(gfile=gfile)

    def __scroll(
        self, _scroll: Gtk.EventControllerScroll, _dx: float, dy: float
    ) -> None:
        if self.scroll.get_current_event_state() != Gdk.ModifierType.CONTROL_MASK:
            return

        # TODO: Temporairily disallow scrolling in the ScrolledWindow here

        if dy < 0:
            self.get_root().zoom_in()
            return

        self.get_root().zoom_out()
