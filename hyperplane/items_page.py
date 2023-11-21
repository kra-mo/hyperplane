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
from typing import Any

from gi.repository import Adw, Gio, Gtk

from hyperplane import shared
from hyperplane.item import HypItem


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/items-page.ui")
class HypItemsPage(Adw.NavigationPage):
    __gtype_name__ = "HypItemsPage"

    flow_box: Gtk.FlowBox = Gtk.Template.Child()

    def __init__(self, path: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.path = path
        if self.path == shared.home:
            self.set_title(_("Home"))
        else:
            self.set_title(self.path.name)

        if not self.path.is_dir():
            return

        self.update()

        self.flow_box.connect("child-activated", self.__child_activated)

    def update(self) -> None:
        """Updates the visible items in the view."""
        self.flow_box.remove_all()
        for item in self.path.iterdir():
            self.flow_box.append(HypItem(item))

    def __child_activated(
        self, _flow_box: Gtk.FlowBox, flow_box_child: Gtk.FlowBoxChild
    ) -> None:
        if (item := flow_box_child.get_child()).path.is_file():
            Gio.AppInfo.launch_default_for_uri(item.gfile.get_uri())
        elif item.path.is_dir():
            shared.win.new_page(item.path)
