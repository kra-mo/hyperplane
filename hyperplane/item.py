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

from os.path import getsize
from pathlib import Path
from typing import Any

from gi.repository import Gdk, Gio, GLib, Gtk

from hyperplane import shared
from hyperplane.utils.get_thumbnail import get_thumbnail


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/item.ui")
class HypItem(Gtk.Box):
    __gtype_name__ = "HypItem"

    label: Gtk.Label = Gtk.Template.Child()
    thumbnail_overlay: Gtk.Overlay = Gtk.Template.Child()
    icon: Gtk.Image = Gtk.Template.Child()
    extension_label: Gtk.Label = Gtk.Template.Child()
    thumbnail: Gtk.Picture = Gtk.Template.Child()

    gfile = Gio.File
    file_info: Gio.FileInfo
    path: Path
    content_type: str

    def __init__(self, path: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.path = path

        if not self.path.exists():
            self.label.set_label("-")
            return

        self.gfile = Gio.File.new_for_path(str(path))

        self.file_info = Gio.FileInfo()
        self.update()

    def update(self) -> None:
        """Update the file name and thumbnail"""
        self.update_label()
        self.update_thumbnail()

    def update_label(self) -> None:
        """Update the visible name of the file"""
        self.label.set_label(self.path.stem)

    def _thumbnail_query_callback(self, _source: Any, result: Gio.Task) -> None:
        try:
            file_info = self.gfile.query_info_finish(result)
        except GLib.GError:
            return

        if path := file_info.get_attribute_as_string(Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH):
            texture = Gdk.Texture.new_from_filename(path)
        elif thumbnail := get_thumbnail(self.path, self.content_type):
            texture = Gdk.Texture.new_for_pixbuf(thumbnail)
        else:
            return

        self.thumbnail.set_paintable(texture)
        self.thumbnail.set_visible(True)
        self.icon.set_visible(False)

    def _icon_query_callback(self, _source: Any, result: Gio.Task) -> None:
        try:
            file_info = self.gfile.query_info_finish(result)
        except GLib.GError:
            return
        if icon := file_info.get_symbolic_icon():
            self.icon.set_from_gicon(icon)

    def _content_type_query_callback(self, _source: Any, result: Gio.Task) -> None:
        try:
            file_info = self.gfile.query_info_finish(result)
        except GLib.GError:
            return
        self.content_type = file_info.get_content_type()
        if self.content_type:
            match self.content_type.split("/")[0]:
                case "inode":
                    color = "blue"
                case "audio":
                    color = "yellow"
                case "application":
                    color = "blue"
                case "image":
                    color = "purple"
                case "video":
                    color = "red"
                case "text":
                    color = "gray"
                case "font":
                    color = "gray"
                case _:
                    color = "gray"
            self.thumbnail_overlay.add_css_class(color + "-background")
            self.icon.add_css_class(color + "-icon")
            self.extension_label.add_css_class(color + "-extension")

            self.gfile.query_info_async(
                Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH,
                Gio.FileQueryInfoFlags.NONE,
                GLib.PRIORITY_DEFAULT,
                None,
                self._thumbnail_query_callback,
            )

    def update_thumbnail(self) -> None:
        """Update the visible thumbnail of the file"""
        self.icon.set_visible(True)
        self.thumbnail.set_visible(False)

        if suffix := self.path.suffix:
            self.extension_label.set_label(suffix[1:].upper())
            self.extension_label.set_visible(True)
        else:
            self.extension_label.set_visible(False)

        # TODO: There doesn't seem to be a symbolic for empty files. Open an issue.
        if self.path.is_file() and getsize(str(self.path)) == 0:
            self.icon.set_from_icon_name("text-x-generic-symbolic")
            self.thumbnail_overlay.add_css_class("gray-background")
            self.icon.add_css_class("gray-icon")
            self.extension_label.add_css_class("gray-extension")
            return

        self.gfile.query_info_async(
            Gio.FILE_ATTRIBUTE_STANDARD_SYMBOLIC_ICON,
            Gio.FileQueryInfoFlags.NONE,
            GLib.PRIORITY_DEFAULT,
            None,
            self._icon_query_callback,
        )

        self.gfile.query_info_async(
            Gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE,
            Gio.FileQueryInfoFlags.NONE,
            GLib.PRIORITY_DEFAULT,
            None,
            self._content_type_query_callback,
        )
