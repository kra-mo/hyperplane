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

from gi.repository import Adw, Gio, Gtk

from hyperplane import shared
from hyperplane.item import HypItem
from hyperplane.tag import HypTag
from hyperplane.utils.iterplane import iterplane


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/items-page.ui")
class HypItemsPage(Adw.NavigationPage):
    __gtype_name__ = "HypItemsPage"

    flow_box: Gtk.FlowBox = Gtk.Template.Child()

    def __init__(
        self, path: Optional[Path] = None, tag: Optional[str] = None, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.path = path
        self.tag = tag

        if self.path and not self.path.is_dir():
            return

        if self.path == shared.home:
            self.set_title(_("Home"))
        elif self.path:
            self.set_title(self.path.name)

        self.update()

        self.flow_box.connect("child-activated", self.__child_activated)

    def update(self) -> None:
        """Updates the visible items in the view."""
        self.flow_box.remove_all()
        if self.path:
            if self.path == shared.home:
                for item in self.path.iterdir():
                    if item.name not in shared.tags:
                        self.flow_box.append(HypItem(item))
                for tag in shared.tags:
                    self.flow_box.append(HypTag(tag))
                return

            for item in self.path.iterdir():
                self.flow_box.append(HypItem(item))

        elif self.tag:
            for item in iterplane([self.tag]):  # TODO: combine multiple tags
                self.flow_box.append(HypItem(item))

    def __child_activated(
        self, _flow_box: Gtk.FlowBox, flow_box_child: Gtk.FlowBoxChild
    ) -> None:
        if isinstance((item := flow_box_child.get_child()), HypItem):
            if item.path.is_file():
                Gio.AppInfo.launch_default_for_uri(item.gfile.get_uri())
            elif item.path.is_dir():
                shared.win.new_page(item.path)
        elif isinstance(item, HypTag):
            shared.win.new_page(tag=item.name)
