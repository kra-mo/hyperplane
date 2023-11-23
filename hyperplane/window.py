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
from typing import Any, Callable, Iterable, Optional

from gi.repository import Adw, Gio, Gtk

from hyperplane import shared
from hyperplane.navigation_bin import HypNavigationBin

# This is to avoid a circular import in item.py
from hyperplane.thumbnail import HypThumb  # pylint: disable=unused-import


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/window.ui")
class HypWindow(Adw.ApplicationWindow):
    __gtype_name__ = "HypWindow"

    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    tab_view: Adw.TabView = Gtk.Template.Child()
    toolbar_view: Adw.ToolbarView = Gtk.Template.Child()

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        if shared.PROFILE == "development":
            self.add_css_class("devel")

        self.tab_view.connect("page-attached", self.__page_attached)

        navigation_view = HypNavigationBin(initial_path=shared.home)
        self.tab_view.append(navigation_view).set_title(
            title := navigation_view.view.get_visible_page().get_title()
        )
        self.set_title(title)

        self.create_action("close", self.__on_close_action, ("<primary>w",))
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

        self.tab_view.connect("notify::selected-page", self.__update_window_title)

    def __update_window_title(self, *_args: Any) -> None:
        self.set_title(
            self.tab_view.get_selected_page()
            .get_child()
            .view.get_visible_page()
            .get_title()
        )

    def __update_tab_title(self, view: Adw.NavigationView, *_args: Any) -> None:
        title = view.get_visible_page().get_title()
        (page := self.tab_view.get_page(view.get_parent())).set_title(title)

        if self.tab_view.get_selected_page() == page:
            self.set_title(title)

    def __page_attached(self, _view: Adw.TabView, page: Adw.TabPage, _pos: int) -> None:
        page.get_child().view.connect("popped", self.__update_tab_title)
        page.get_child().view.connect("pushed", self.__update_tab_title)

    def send_toast(self, message: str) -> None:
        toast = Adw.Toast.new(message)
        toast.set_priority(Adw.ToastPriority.HIGH)
        toast.set_use_markup(False)

        self.toast_overlay.add_toast(toast)

    def new_tab(self, path: Optional[Path] = None, tag: Optional[str] = None) -> None:
        """Open a new path with the given path or tag."""
        if path and path.is_dir():
            navigation_view = HypNavigationBin(initial_path=path)
            self.tab_view.append(navigation_view).set_title(
                navigation_view.view.get_visible_page().get_title()
            )
        elif tag:
            navigation_view = HypNavigationBin(
                initial_tags=self.tab_view.get_selected_page().get_child().tags + [tag]
            )
            self.tab_view.append(navigation_view).set_title(
                navigation_view.view.get_visible_page().get_title()
            )

    def update_zoom(self) -> None:
        """Update the zoom level of all items in the navigation stack"""
        tab_pages = self.tab_view.get_pages()

        tab_index = 0
        while item := tab_pages.get_item(tab_index):
            stack = item.get_child().view.get_navigation_stack()
            page_index = 0
            while page := stack.get_item(page_index):
                child_index = 0
                while child := page.flow_box.get_child_at_index(child_index):
                    child.get_child().zoom(shared.state_schema.get_uint("zoom-level"))

                    child_index += 1
                page_index += 1

            tab_index += 1

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
            self.get_application().set_accels_for_action(f"win.{name}", shortcuts)

    def __on_zoom_in_action(self, *_args: Any) -> None:
        if (zoom_level := shared.state_schema.get_uint("zoom-level")) > 4:
            return

        shared.state_schema.set_uint("zoom-level", zoom_level + 1)
        self.update_zoom()

    def __on_zoom_out_action(self, *_args: Any) -> None:
        if (zoom_level := shared.state_schema.get_uint("zoom-level")) < 2:
            return

        shared.state_schema.set_uint("zoom-level", zoom_level - 1)
        self.update_zoom()

    def __on_close_action(self, *_args: Any) -> None:
        if self.tab_view.get_n_pages() > 1:
            self.tab_view.close_page(self.tab_view.get_selected_page())
        else:
            self.close()
