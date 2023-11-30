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

from locale import strcoll
from pathlib import Path
from typing import Any, Optional

from gi.repository import Adw, Gdk, Gio, Gtk

from hyperplane import shared
from hyperplane.item import HypItem
from hyperplane.item_filter import HypItemFilter
from hyperplane.utils.iterplane import iterplane


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/items-page.ui")
class HypItemsPage(Adw.NavigationPage):
    __gtype_name__ = "HypItemsPage"

    scrolled_window: Gtk.ScrolledWindow = Gtk.Template.Child()
    grid_view: Gtk.GridView = Gtk.Template.Child()
    empty_folder: Adw.StatusPage = Gtk.Template.Child()

    multi_selection: Gtk.MultiSelection
    item_filter: HypItemFilter
    filter_list: Gtk.FilterListModel
    sorter: Gtk.CustomSorter
    sort_list: Gtk.SortListModel
    dir_list: Gtk.FlattenListModel | Gtk.DirectoryList
    factory: Gtk.SignalListItemFactory

    def __init__(
        self,
        path: Optional[Path] = None,
        tags: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.path = path
        self.tags = tags

        if self.path and not self.path.is_dir():
            return

        if self.path == shared.home:
            self.set_title(_("Home"))
        elif self.path:
            self.set_title(self.path.name)
        elif self.tags:
            self.set_title(" + ".join(self.tags))

        gesture_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        gesture_click.connect("pressed", self.__right_click)
        self.add_controller(gesture_click)

        shared.postmaster.connect("toggle-hidden", self.__toggle_hidden)

        self.dir_list = self.__get_list(self.path, self.tags)
        self.item_filter = HypItemFilter()
        self.filter_list = Gtk.FilterListModel.new(self.dir_list, self.item_filter)

        self.sorter = Gtk.CustomSorter.new(self.__sort_func)
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
        self, path: Optional[Path] = None, tags: Optional[list[str]] = None
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
        if path:
            return Gtk.DirectoryList.new(attrs, Gio.File.new_for_path(str(path)))

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
        if self.get_child() != self.empty_folder and not filter_list.get_n_items():
            self.set_child(self.empty_folder)

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

    def __sort_func(
        self,
        file_info1: Optional[Gio.FileInfo] = None,
        file_info2: Optional[Gio.FileInfo] = None,
        _user_data: Optional[Any] = None,
    ) -> int:
        if (not file_info1) or (not file_info2):
            return 0

        name1 = file_info1.get_display_name()
        name2 = file_info2.get_display_name()

        if name1.startswith("."):
            if not name2.startswith("."):
                return 1

        if name2.startswith("."):
            return -1

        return strcoll(name1, name2)

    def activate(self, _grid_view: Gtk.GridView, pos: int) -> None:
        """Activates an item at the given position."""
        try:
            path = Path(
                (
                    gfile := self.multi_selection.get_item(pos).get_attribute_object(
                        "standard::file"
                    )
                ).get_path()
            )
        except AttributeError:
            return

        if path.is_file():
            Gio.AppInfo.launch_default_for_uri(gfile.get_uri())
        elif path.is_dir():
            self.get_root().tab_view.get_selected_page().get_child().new_page(path)

    def __right_click(self, _gesture, _n, x, y) -> None:
        self.get_root().right_click_menu.unparent()
        self.get_root().right_click_menu.set_parent(self)
        rectangle = Gdk.Rectangle()
        rectangle.x, rectangle.y, rectangle.width, rectangle.height = x, y, 0, 0
        self.get_root().right_click_menu.set_pointing_to(rectangle)
        self.get_root().right_click_menu.popup()
