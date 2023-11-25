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

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from hyperplane import shared
from hyperplane.item import HypItem
from hyperplane.tag import HypTag
from hyperplane.utils.iterplane import iterplane


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/items-page.ui")
class HypItemsPage(Adw.NavigationPage):
    __gtype_name__ = "HypItemsPage"

    grid_view = Gtk.GdriView = Gtk.Template.Child()
    empty_folder: Adw.StatusPage = Gtk.Template.Child()
    empty_filter: Adw.StatusPage = Gtk.Template.Child()
    scrolled_window: Gtk.ScrolledWindow = Gtk.Template.Child()
    right_click_menu: Gtk.PopoverMenu = Gtk.Template.Child()

    multi_selection: Gtk.MultiSelection

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

        self.update()

        self.right_click_menu.set_parent(self)
        gesture_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        gesture_click.connect("pressed", self.__right_click)
        self.add_controller(gesture_click)
        self.right_click_menu.connect("closed", self.__set_actions)
        self.__set_actions()

        shared.postmaster.connect("toggle-hidden", self.__toggle_hidden)

        if self.path:  # TODO: remove condition
            self.directory_list = Gtk.DirectoryList.new(
                ",".join(
                    (
                        Gio.FILE_ATTRIBUTE_STANDARD_SYMBOLIC_ICON,
                        Gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE,
                        Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH,
                    )
                ),
                Gio.File.new_for_path(str(self.path)),
            )
            self.multi_selection = Gtk.MultiSelection.new(self.directory_list)
            self.factory = Gtk.SignalListItemFactory()
            self.grid_view.set_model(self.multi_selection)
            self.grid_view.set_factory(self.factory)

            self.factory.connect("setup", self.__setup)
            self.factory.connect("bind", self.__bind)
            self.factory.connect("unbind", self.__unbind)
            self.factory.connect("teardown", self.__teardown)
            self.grid_view.connect("activate", self.__activate)

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

    def update(self) -> None:
        """Updates the visible items in the view."""

        if self.get_child() != self.scrolled_window:
            self.set_child(self.scrolled_window)

        # TODO: post-flowbox
        # self.flow_box.remove_all()
        if self.path:
            if self.path == shared.home:
                for item in self.path.iterdir():
                    if item.name not in shared.tags:
                        # TODO: post-flowbox
                        # self.flow_box.append(HypItem(item))
                        pass
                for tag in shared.tags:
                    # TODO: post-flowbox
                    # self.flow_box.append(HypTag(tag))
                    pass
                return

            for item in self.path.iterdir():
                # TODO: post-flowbox
                # self.flow_box.append(HypItem(item))
                pass

            if "item" not in vars():
                self.set_child(self.empty_folder)

        elif self.tags:
            for item in iterplane(self.tags):
                if isinstance(item, Path):
                    # TODO: post-flowbox
                    # self.flow_box.append(HypItem(item))
                    pass
                elif isinstance(item, str):
                    # TODO: post-flowbox
                    # self.flow_box.append(HypTag(item))
                    pass

            if "item" not in vars():
                self.set_child(self.empty_filter)

    def __toggle_hidden(self, *_args: Any) -> None:
        # TODO: post-flowbox
        # self.flow_box.invalidate_filter()
        pass

    def __sort_func(self, child1: Gtk.FlowBoxChild, child2: Gtk.FlowBoxChild) -> int:
        child1 = child1.get_child()
        child2 = child2.get_child()

        if isinstance(child1, HypItem):
            if isinstance(child2, HypItem):
                return strcoll(child1.path.name, child2.path.name)
            return 1
        if isinstance(child2, HypItem):
            return -1
        return strcoll(child1.name, child2.name)

    def __search_filter(self, initial_child: Gtk.FlowBoxChild) -> bool:
        if not shared.search:
            return True

        child = initial_child.get_child()
        search = shared.search.lower()

        if isinstance(child, HypTag):
            if search in child.name.lower():
                # TODO: post-flowbox
                # self.flow_box.unselect_all()
                # self.flow_box.select_child(initial_child)
                return True
            return False

        if search in child.path.name.lower():
            # TODO: post-flowbox
            # self.flow_box.unselect_all()
            # self.flow_box.select_child(initial_child)
            return True

        return False

    def __hidden_filter(self, initial_child: Gtk.FlowBoxChild) -> bool:
        if shared.show_hidden:
            return True

        child = initial_child.get_child()

        if isinstance(child, HypTag):
            return True

        try:
            if child.gfile.query_info(
                Gio.FILE_ATTRIBUTE_STANDARD_IS_HIDDEN, Gio.FileQueryInfoFlags.NONE
            ).get_is_hidden():
                # TODO: post-flowbox
                # self.flow_box.unselect_child(initial_child)
                return False
        except GLib.Error:
            pass
        return True

    def __filter_func(self, child: Gtk.FlowBoxChild) -> bool:
        return all((self.__search_filter(child), self.__hidden_filter(child)))

    def __activate(self, _grid_view: Gtk.GridView, pos: int) -> None:
        path = Path(
            (
                gfile := self.multi_selection.get_item(pos).get_attribute_object(
                    "standard::file"
                )
            ).get_path()
        )

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
