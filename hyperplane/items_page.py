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
from typing import Any, Iterable, Optional

from gi.repository import Adw, Gdk, Gio, Gtk

from hyperplane import shared
from hyperplane.item import HypItem
from hyperplane.item_filter import HypItemFilter


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/items-page.ui")
class HypItemsPage(Adw.NavigationPage):
    __gtype_name__ = "HypItemsPage"

    grid_view = Gtk.GdriView = Gtk.Template.Child()
    empty_folder: Adw.StatusPage = Gtk.Template.Child()
    empty_filter: Adw.StatusPage = Gtk.Template.Child()
    scrolled_window: Gtk.ScrolledWindow = Gtk.Template.Child()
    right_click_menu: Gtk.PopoverMenu = Gtk.Template.Child()

    multi_selection: Gtk.MultiSelection
    item_filter = HypItemFilter
    filter_list: Gtk.FilterListModel
    sorter: Gtk.CustomSorter
    sort_list: Gtk.SortListModel
    directory_list: Gtk.DirectoryList
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

        self.right_click_menu.set_parent(self)
        gesture_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        gesture_click.connect("pressed", self.__right_click)
        self.add_controller(gesture_click)
        self.right_click_menu.connect("closed", self.__set_actions)
        self.__set_actions()

        shared.postmaster.connect("toggle-hidden", self.__toggle_hidden)

        if self.path:  # TODO: Remove condition
            self.directory_list = Gtk.DirectoryList.new(
                ",".join(
                    (
                        Gio.FILE_ATTRIBUTE_STANDARD_SYMBOLIC_ICON,
                        Gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE,
                        Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH,
                        Gio.FILE_ATTRIBUTE_STANDARD_IS_HIDDEN,
                        Gio.FILE_ATTRIBUTE_STANDARD_DISPLAY_NAME,
                    )
                ),
                Gio.File.new_for_path(str(self.path)),
            )
            self.item_filter = HypItemFilter()
            self.filter_list = Gtk.FilterListModel.new(
                self.directory_list, self.item_filter
            )

            self.sorter = Gtk.CustomSorter.new(self.__sort_func)
            self.sort_list = Gtk.SortListModel.new(self.filter_list, self.sorter)

            self.multi_selection = Gtk.MultiSelection.new(self.sort_list)
            self.factory = Gtk.SignalListItemFactory()
            self.grid_view.set_model(self.multi_selection)
            self.grid_view.set_factory(self.factory)

            self.factory.connect("setup", self.__setup)
            self.factory.connect("bind", self.__bind)
            self.factory.connect("unbind", self.__unbind)
            self.factory.connect("teardown", self.__teardown)
            self.grid_view.connect("activate", self.activate)

            self.directory_list.connect("items-changed", self.__items_changed)
            self.__items_changed(self.directory_list)

    # TODO: Make this more efficient with removed and added?
    # TODO: Make this less prone to showing up during initial population
    def __items_changed(self, dir_list: Gtk.DirectoryList, *_args: Any) -> None:
        if self.get_child() != self.scrolled_window and dir_list.get_n_items():
            self.set_child(self.scrolled_window)
        if self.get_child() != self.empty_folder and not dir_list.get_n_items():
            self.set_child(self.empty_folder)

    def __setup(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        item.set_child(HypItem(item))

    def __bind(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        item.get_child().bind(
            item.get_item().get_attribute_object("standard::file"),
            item.get_item().get_symbolic_icon(),
            item.get_item().get_content_type(),
            item.get_item().get_attribute_byte_string(
                Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH
            ),
        )

    def __unbind(self, *args) -> None:
        return

    def __teardown(self, *args) -> None:
        return

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

    def set_menu_items(self, menu_items: Iterable[str]) -> None:
        """Disables all right-clickc menu items not in `menu_items`."""
        actions = {
            "rename",
            "copy",
            "cut",
            "paste",
            "trash",
            "new-folder",
            "select-all",
            "open",
            "open-new-tab",
            "open-new-window",
        }

        for action in actions.difference(menu_items):
            try:
                shared.app.lookup_action(action).set_enabled(False)
            except AttributeError:
                pass
        for action in menu_items:
            try:
                shared.app.lookup_action(action).set_enabled(True)
            except AttributeError:
                pass

    def __set_actions(self, *_args: Any) -> None:
        self.set_menu_items(
            {
                "rename",
                "copy",
                "cut",
                "paste",
                "trash",
                "new-folder",
                "select-all",
                "open",
                "open-new-tab",
                "open-new-window",
            }
        )

    def __right_click(self, _gesture, _n, x, y) -> None:
        rectangle = Gdk.Rectangle()
        rectangle.x, rectangle.y, rectangle.width, rectangle.height = x, y, 0, 0
        self.right_click_menu.set_pointing_to(rectangle)
        self.right_click_menu.popup()
