# tag_row.py
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

"""A row in the sidebar representing a tag."""
from typing import Any

from gi.repository import Gdk, Gtk

from hyperplane import shared


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/tag-row.ui")
class HypTagRow(Gtk.Box):
    """A row in the sidebar representing a tag."""

    __gtype_name__ = "HypTagRow"

    image: Gtk.Image = Gtk.Template.Child()
    label: Gtk.Label = Gtk.Template.Child()

    tag: str

    def __init__(self, tag: str, icon_name: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.tag = tag

        self.label.set_label(tag)
        self.image.set_from_icon_name(icon_name)

        right_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right_click.connect("pressed", self.__right_click)
        self.add_controller(right_click)

        middle_click = Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)
        middle_click.connect("pressed", self.__middle_click)
        self.add_controller(middle_click)

    def __right_click(
        self, _gesture: Gtk.GestureClick, _n: int, x: float, y: float
    ) -> None:
        self.get_root().right_clicked_tag = self.tag

        # Disable move up/down actions if the tag is the first/last in the list
        self.get_root().lookup_action("move-tag-up").set_enabled(
            shared.tags[0] != self.tag
        )
        self.get_root().lookup_action("move-tag-down").set_enabled(
            shared.tags[-1] != self.tag
        )

        self.get_root().tag_right_click_menu.unparent()
        self.get_root().tag_right_click_menu.set_parent(self)
        rectangle = Gdk.Rectangle()
        rectangle.x, rectangle.y, rectangle.width, rectangle.height = x, y, 0, 0
        self.get_root().tag_right_click_menu.set_pointing_to(rectangle)
        self.get_root().tag_right_click_menu.popup()

    def __middle_click(self, *_args: Any) -> None:
        self.get_root().new_tab(tags=[self.tag])
