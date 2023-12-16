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
from typing import Any, Optional

from gi.repository import Adw, Gdk, Gio, GObject, Gtk

from hyperplane import shared
from hyperplane.item import HypItem
from hyperplane.item_filter import HypItemFilter
from hyperplane.item_sorter import HypItemSorter
from hyperplane.utils.files import (
    copy,
    get_copy_path,
    get_gfile_display_name,
    get_gfile_path,
)
from hyperplane.utils.iterplane import iterplane


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
        if self.get_child() != self.scrolled_window and filter_list.get_n_items():
            self.set_child(self.scrolled_window)
        if (
            self.get_child() not in (self.empty_folder, self.empty_trash)
            and not filter_list.get_n_items()
        ):
            if (
                win := self.get_root()
            ) and win.title_stack.get_visible_child() == win.search_entry_clamp:
                self.set_child(self.no_results)
                return

            if self.gfile and self.gfile.get_uri() != "trash:///":
                self.set_child(self.empty_folder)
                return

            self.set_child(self.empty_trash)

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
        gfile = file_info.get_attribute_object("standard::file")

        if file_info.get_content_type() == "inode/directory":
            self.get_root().tab_view.get_selected_page().get_child().new_page(gfile)
            return

        Gio.AppInfo.launch_default_for_uri(gfile.get_uri())

    def __right_click(self, _gesture, _n, x, y) -> None:
        self.get_root().right_click_menu.unparent()
        self.get_root().right_click_menu.set_parent(self)
        rectangle = Gdk.Rectangle()
        rectangle.x, rectangle.y, rectangle.width, rectangle.height = x, y, 0, 0
        self.get_root().right_click_menu.set_pointing_to(rectangle)
        self.get_root().right_click_menu.popup()

    def __drop(self, _drop_target: Gtk.DropTarget, file_list: GObject.Value, _x, _y):
        # TODO: this is mostly copy-paste from HypWindow.__paste()
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
