# window.py
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
from typing import Any

from gi.repository import Adw, Gio, Gtk

from hyperplane import shared
from hyperplane.items_page import HypItemsPage

# This is to avoid a circular import in item.py
from hyperplane.thumbnail import HypThumb  # pylint: disable=unused-import


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/window.ui")
class HypWindow(Adw.ApplicationWindow):
    __gtype_name__ = "HypWindow"

    navigation_view: Adw.NavigationView = Gtk.Template.Child()

    items_page: HypItemsPage

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        if shared.PROFILE == "development":
            self.add_css_class("devel")

        self.items_page = HypItemsPage(shared.home)
        self.navigation_view.push(self.items_page)

        self.create_action("close", lambda *_: self.close(), ("<primary>w",))
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

        self.navigation_view.connect("popped", self.__update_items_page)
        self.navigation_view.connect("pushed", self.__update_items_page)

    def new_page(self, path: Path) -> None:
        """Push a new page with the given path to the navigation stack."""
        if path == self.items_page.path:
            return

        self.navigation_view.push(HypItemsPage(path))

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
            self.get_application().set_accels_for_action(f"win.{name}", shortcuts)

    def update_zoom(self) -> None:
        """Update the zoom level of all items in the navigation stack"""
        stack = self.navigation_view.get_navigation_stack()
        page_index = 0
        while page := stack.get_item(page_index):
            child_index = 0
            while child := page.flow_box.get_child_at_index(child_index):
                child.get_child().zoom(shared.state_schema.get_uint("zoom-level"))

                child_index += 1
            page_index += 1

    def __on_zoom_in_action(self, *_args) -> None:
        if (zoom_level := shared.state_schema.get_uint("zoom-level")) > 4:
            return

        shared.state_schema.set_uint("zoom-level", zoom_level + 1)
        self.update_zoom()

    def __on_zoom_out_action(self, *_args) -> None:
        if (zoom_level := shared.state_schema.get_uint("zoom-level")) < 2:
            return

        shared.state_schema.set_uint("zoom-level", zoom_level - 1)
        self.update_zoom()

    def __update_items_page(
        self, navigation_view: Adw.NavigationView, *_args: Any
    ) -> None:
        self.items_page = navigation_view.get_visible_page()
