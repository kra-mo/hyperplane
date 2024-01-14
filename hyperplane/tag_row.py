# tag_row.py
#
# Copyright 2023-2024 kramo
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
from typing import Self

from gi.repository import Gdk, Gtk

from hyperplane import shared
from hyperplane.editable_row import HypEditableRow
from hyperplane.utils.tags import update_tags


class HypTagRow(HypEditableRow):
    """A row in the sidebar representing a tag."""

    __gtype_name__ = "HypTagRow"

    tag: str

    def __init__(self, tag: str, icon_name: str, **kwargs) -> None:
        super().__init__(identifier=f"tag_{tag}", **kwargs)
        self.title = self.tag = tag
        self.icon_name = icon_name
        self.editable = False

        right_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right_click.connect("pressed", self.__right_click)
        self.add_controller(right_click)

        middle_click = Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)
        middle_click.connect(
            "pressed", lambda *_: self.get_root().new_tab(tags=[self.tag])
        )
        self.add_controller(middle_click)

        # Drag and drop
        drag_source = Gtk.DragSource.new()
        drag_source.connect("prepare", self.__drag_prepare)
        drag_source.connect("drag-begin", self.__drag_begin)
        drag_source.set_actions(Gdk.DragAction.MOVE)
        self.box.add_controller(drag_source)

        drop_target = Gtk.DropTarget.new(HypTagRow, Gdk.DragAction.MOVE)
        drop_target.connect("enter", self.__drop_enter)
        drop_target.connect("leave", self.__drop_leave)
        drop_target.connect("drop", self.__drop)
        self.add_controller(drop_target)

    def __drag_prepare(self, _src: Gtk.DragSource, _x: float, _y: float) -> None:
        return Gdk.ContentProvider.new_for_value(self)

    def __drag_begin(self, src: Gtk.DragSource, _drag: Gdk.Drag) -> None:
        src.set_icon(Gtk.WidgetPaintable.new(self.box), -30, 0)

    def __drop_enter(self, target: Gtk.DropTarget, _x: float, _y: float) -> None:
        try:
            gtypes = (
                target.get_current_drop()
                .get_drag()
                .get_content()
                .ref_formats()
                .get_gtypes()
            )
        except TypeError:
            return Gdk.DragAction.MOVE

        if gtypes and gtypes[0].pytype == type(self):
            self.can_open_page = False
            self.add_css_class("sidebar-drop-target")

        return Gdk.DragAction.MOVE

    def __drop_leave(self, _target: Gtk.DropTarget) -> None:
        self.can_open_page = True
        self.remove_css_class("sidebar-drop-target")

    def __drop(self, _target: Gtk.DropTarget, row: Self, _x: float, _y: float) -> None:
        self_index = shared.tags.index(self.tag)
        row_index = shared.tags.index(row.tag)

        shared.tags.insert(
            # Offset the index by 1 if `row.tag` is at a larger index than `self.tag`
            self_index + int(self_index < row_index),
            shared.tags.pop(row_index),
        )

        update_tags()

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
