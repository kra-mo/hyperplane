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
from hyperplane.utils.get_content_type import get_content_type_async


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

    def __init__(self, path: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.path = path

        if not self.path.exists():
            return

        self.gfile = Gio.File.new_for_path(str(path))
        self.__zoom(None, shared.state_schema.get_uint("zoom-level"))
        self.build()

        right_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right_click.connect("pressed", self.__right_click)
        self.add_controller(right_click)

        middle_click = Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)
        middle_click.connect("pressed", self.__middle_click)
        self.add_controller(middle_click)

        shared.postmaster.connect("zoom", self.__zoom)

    def build(self) -> None:
        """Update the file name and thumbnail."""
        self.label.set_label(self.path.name if self.path.is_dir() else self.path.stem)
        self._map_connection = self.connect("map", self.build_thumbnail)

    def build_thumbnail(self, _object: Any) -> None:
        """Build the thumbnail of the file."""
        self.disconnect(self._map_connection)
        self.thumbnail.build_icon()
        get_content_type_async(self.gfile, self.__content_type_callback)

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
        else:
            self.thumbnail.dir_thumbnails.set_spacing(6)
            self.thumbnail.dir_thumbnails.set_margin_start(6)
            self.thumbnail.dir_thumbnails.set_margin_top(6)

        if zoom_level < 2:
            self.thumbnail.icon.set_pixel_size(20)
            self.thumbnail.icon.set_icon_size(Gtk.IconSize.INHERIT)
        else:
            self.thumbnail.icon.set_pixel_size(-1)
            self.thumbnail.icon.set_icon_size(Gtk.IconSize.LARGE)

    def __content_type_callback(self, _gfile: Gio.File, content_type: str) -> None:
        self.content_type = content_type
        self.thumbnail.build_thumbnail()

    def __right_click(self, *_args: Any) -> None:
        if (
            self.get_parent()
            not in (flow_box := self.get_parent().get_parent()).get_selected_children()
        ):
            flow_box.unselect_all()
            flow_box.select_child(self.get_parent())

        self.get_parent().get_parent().get_parent().get_parent().get_parent().set_menu_items(
            {
                "rename",
                "copy",
                "cut",
                "trash",
                "open",
                "open-new-tab",
                "open-new-window",
            }
        )

    def __middle_click(self, *_args: Any) -> None:
        (flow_box := self.get_parent().get_parent()).unselect_all()
        flow_box.select_child(self.get_parent())

        self.get_root().new_tab(path=self.path)
