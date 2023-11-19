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

from gi.repository import Adw, Gtk

from hyperplane import shared
from hyperplane.items_view import HypItemsView


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/window.ui")
class HypWindow(Adw.ApplicationWindow):
    __gtype_name__ = "HypWindow"

    scrolled_window: Gtk.ScrolledWindow = Gtk.Template.Child()
    navigation_view: Adw.NavigationView = Gtk.Template.Child()

    items_view: HypItemsView = HypItemsView(shared.home)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        if shared.PROFILE == "development":
            self.add_css_class("devel")

        self.scrolled_window.set_child(self.items_view)

        self.navigation_view.connect("popped", self._update_items_view)
        self.navigation_view.connect("pushed", self._update_items_view)

    def _update_items_view(
        self, navigation_view: Adw.NavigationView, *_args: Any
    ) -> None:
        self.items_view = (
            navigation_view.get_visible_page().get_child().get_child().get_child()
        )

    def new_page(self, path: Path) -> None:
        if path == self.items_view.path:
            return

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_child(HypItemsView(path))
        self.navigation_view.push(Adw.NavigationPage.new(scrolled_window, path.name))
