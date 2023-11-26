# item.py
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

from gi.repository import Adw, Gdk, Gio, Gtk

from hyperplane import shared


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/item.ui")
class HypItem(Adw.Bin):
    __gtype_name__ = "HypItem"

    clamp: Adw.Clamp = Gtk.Template.Child()
    box: Gtk.Box = Gtk.Template.Child()
    thumbnail: Gtk.Overlay = Gtk.Template.Child()
    label: Gtk.Label = Gtk.Template.Child()

    gfile = Gio.File
    path: Path
    content_type: str

    # TODO: Remove path property
    def __init__(self, item: Gtk.ListItem, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.__setup(item)

    def __setup(self, item: Gtk.ListItem) -> None:
        """Set up permanent properties."""
        self.item = item
        self.__zoom(None, shared.state_schema.get_uint("zoom-level"))
        shared.postmaster.connect("zoom", self.__zoom)

        right_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right_click.connect("pressed", self.__right_click)
        self.add_controller(right_click)

        middle_click = Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)
        middle_click.connect("pressed", self.__middle_click)
        self.add_controller(middle_click)

    def bind(self, gfile, icon, content_type, thumbnail_path) -> None:
        """Set up widget with file attributes."""
        self.gfile = gfile
        self.path = Path(gfile.get_path())
        self.label.set_label(self.path.name if self.path.is_dir() else self.path.stem)
        self.__build_thumbnail(icon, content_type, thumbnail_path)

    def __build_thumbnail(self, icon, content_type, thumbnail_path) -> None:
        self.thumbnail.set_item(self)
        self.thumbnail.build_icon(icon)
        self.content_type = content_type
        self.thumbnail.build_thumbnail(thumbnail_path)

    def __zoom(self, _obj: Any, zoom_level: int) -> None:
        self.clamp.set_maximum_size(50 * zoom_level)
        self.box.set_margin_start(4 * zoom_level)
        self.box.set_margin_end(4 * zoom_level)
        self.box.set_margin_top(4 * zoom_level)
        self.box.set_margin_bottom(4 * zoom_level)

        match zoom_level:
            case 1:
                self.thumbnail.set_size_request(96, 80)
            case 2:
                self.thumbnail.set_size_request(96, 96)
            case _:
                self.thumbnail.set_size_request(40 * zoom_level, 32 * zoom_level)

        if zoom_level < 3:
            self.thumbnail.dir_thumbnails.set_spacing(12)
            self.thumbnail.dir_thumbnails.set_margin_start(10)
            self.thumbnail.dir_thumbnails.set_margin_top(6)
        elif zoom_level < 4:
            self.thumbnail.dir_thumbnails.set_spacing(6)
            self.thumbnail.dir_thumbnails.set_margin_start(6)
            self.thumbnail.dir_thumbnails.set_margin_top(6)
        elif zoom_level < 5:
            self.thumbnail.dir_thumbnails.set_spacing(9)
            self.thumbnail.dir_thumbnails.set_margin_start(8)
            self.thumbnail.dir_thumbnails.set_margin_top(8)
        else:
            self.thumbnail.dir_thumbnails.set_spacing(9)
            self.thumbnail.dir_thumbnails.set_margin_start(7)
            self.thumbnail.dir_thumbnails.set_margin_top(7)

        if zoom_level < 4:
            self.thumbnail.dir_thumbnail_1.set_size_request(32, 32)
            self.thumbnail.dir_thumbnail_2.set_size_request(32, 32)
            self.thumbnail.dir_thumbnail_3.set_size_request(32, 32)
        elif zoom_level < 5:
            self.thumbnail.dir_thumbnail_1.set_size_request(42, 42)
            self.thumbnail.dir_thumbnail_2.set_size_request(42, 42)
            self.thumbnail.dir_thumbnail_3.set_size_request(42, 42)
        else:
            self.thumbnail.dir_thumbnail_1.set_size_request(56, 56)
            self.thumbnail.dir_thumbnail_2.set_size_request(56, 56)
            self.thumbnail.dir_thumbnail_3.set_size_request(56, 56)

        if zoom_level < 2:
            self.thumbnail.icon.set_pixel_size(20)
            self.thumbnail.icon.set_icon_size(Gtk.IconSize.INHERIT)
        else:
            self.thumbnail.icon.set_pixel_size(-1)
            self.thumbnail.icon.set_icon_size(Gtk.IconSize.LARGE)

    def __right_click(self, *_args: Any) -> None:
        if not (
            multi_selection := self.get_parent().get_parent().get_model()
        ).is_selected(pos := self.item.get_position()):
            multi_selection.select_item(pos, True)

        menu_items = {"rename", "copy", "cut", "trash", "open"}
        if self.path.is_dir():
            menu_items.add("open-new-tab")
            menu_items.add("open-new-window")

        self.get_root().get_visible_page().set_menu_items(menu_items)

    def __middle_click(self, *_args: Any) -> None:
        # TODO: Open multiple items if multiple are selected
        self.get_parent().get_parent().get_model().select_item(
            self.item.get_position(), True
        )

        self.get_root().new_tab(path=self.path)
