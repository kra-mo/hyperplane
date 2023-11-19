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

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from hyperplane import shared
from hyperplane.utils.get_color_for_content_type import get_color_for_content_type
from hyperplane.utils.get_thumbnail import get_thumbnail


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/item.ui")
class HypItem(Gtk.Box):
    __gtype_name__ = "HypItem"

    label: Gtk.Label = Gtk.Template.Child()
    thumbnail_overlay: Gtk.Overlay = Gtk.Template.Child()
    icon: Gtk.Image = Gtk.Template.Child()
    extension_label: Gtk.Label = Gtk.Template.Child()
    thumbnail: Gtk.Picture = Gtk.Template.Child()
    dir_thumbnails: Gtk.Box = Gtk.Template.Child()

    gfile = Gio.File
    file_info: Gio.FileInfo
    path: Path
    content_type: str

    def __init__(self, path: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.path = path

        if not self.path.exists():
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

    def _thumbnail_query_callback(
        self, gfile: Gio.File, result: Gio.Task, color: str
    ) -> None:
        try:
            file_info = gfile.query_info_finish(result)
        except GLib.GError:
            return

        if path := file_info.get_attribute_as_string(Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH):
            texture = Gdk.Texture.new_from_filename(path)
        elif pixbuf := get_thumbnail(self.path, self.content_type):
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
        else:
            return

        self.thumbnail.set_paintable(texture)
        self.thumbnail.set_visible(True)
        self.icon.set_visible(False)
        self.extension_label.remove_css_class(color + "-extension")
        self.extension_label.add_css_class(color + "-extension-thumb")

    def _dir_icon_query_callback(
        self, gfile: Gio.File, result: Gio.Task, thumbnail: Adw.Bin
    ) -> None:
        try:
            file_info = gfile.query_info_finish(result)
        except GLib.GError:
            return
        if icon := file_info.get_symbolic_icon():
            thumbnail.get_child().set_from_gicon(icon)

    def _dir_content_type_query_callback(
        self, gfile: Gio.File, result: Gio.Task, thumbnail: Adw.Bin
    ) -> None:
        path = Path(gfile.get_path())
        try:
            file_info = gfile.query_info_finish(result)
        except GLib.GError:
            return
        content_type = file_info.get_content_type()
        if content_type:
            if path.is_file():
                thumbnail.add_css_class("solid-white-background")
                color = get_color_for_content_type(content_type)
                thumbnail.get_child().add_css_class(color + "-icon-light-only")
                gfile.query_info_async(
                    Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH,
                    Gio.FileQueryInfoFlags.NONE,
                    GLib.PRIORITY_DEFAULT,
                    None,
                    self._dir_thumbnail_query_callback,
                    thumbnail,
                    content_type,
                )
            elif path.is_dir():
                thumbnail.add_css_class("light-blue-background")
                thumbnail.get_child().add_css_class("solid-white-icon")

    def _dir_thumbnail_query_callback(
        self, gfile: Gio.File, result: Gio.Task, thumbnail: Adw.Bin, content_type: str
    ) -> None:
        try:
            file_info = gfile.query_info_finish(result)
        except GLib.GError:
            return

        if path := file_info.get_attribute_as_string(Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH):
            texture = Gdk.Texture.new_from_filename(path)
        elif pixbuf := get_thumbnail(Path(gfile.get_path()), content_type):
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
        else:
            return

        overlay = Gtk.Overlay()
        picture = Gtk.Picture.new_for_paintable(texture)
        picture.set_content_fit(Gtk.ContentFit.COVER)
        overlay.add_overlay(picture)
        thumbnail.set_child(overlay)

    def _icon_query_callback(self, gfile: Gio.File, result: Gio.Task) -> None:
        try:
            file_info = gfile.query_info_finish(result)
        except GLib.GError:
            return
        if icon := file_info.get_symbolic_icon():
            self.icon.set_from_gicon(icon)

    def _content_type_query_callback(self, gfile: Gio.File, result: Gio.Task) -> None:
        try:
            file_info = gfile.query_info_finish(result)
        except GLib.GError:
            return
        self.content_type = file_info.get_content_type()
        if self.content_type:
            color = get_color_for_content_type(self.content_type)
            self.thumbnail_overlay.add_css_class(color + "-background")

            if self.path.is_file():
                self.icon.add_css_class(color + "-icon")
                self.extension_label.remove_css_class(color + "-extension-thumb")
                self.extension_label.add_css_class(color + "-extension")
                self.gfile.query_info_async(
                    Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH,
                    Gio.FileQueryInfoFlags.NONE,
                    GLib.PRIORITY_DEFAULT,
                    None,
                    self._thumbnail_query_callback,
                    color,
                )
            elif self.path.is_dir():
                if not any(self.path.iterdir()):
                    texture = Gdk.Texture.new_from_resource(
                        shared.PREFIX + "/assets/folder-closed.svg"
                    )
                else:
                    texture = Gdk.Texture.new_from_resource(
                        shared.PREFIX + "/assets/folder-open.svg"
                    )

                    index = 0
                    for path in self.path.iterdir():
                        if index == 3:
                            break

                        if not path.exists():
                            continue

                        index += 1

                        thumbnail = Adw.Bin(
                            width_request=32,
                            height_request=32,
                            overflow=Gtk.Overflow.HIDDEN,
                        )
                        thumbnail.add_css_class("small-thumbnail")
                        thumbnail.set_child(Gtk.Image())

                        self.dir_thumbnails.append(thumbnail)

                        # TODO: Same here
                        if path.is_file() and getsize(str(path)) == 0:
                            thumbnail.get_child().set_from_icon_name(
                                "text-x-generic-symbolic"
                            )
                            thumbnail.add_css_class("solid-white-background")
                            thumbnail.get_child().add_css_class("gray-icon-light-only")
                            continue

                        gfile = Gio.File.new_for_path(str(path))

                        gfile.query_info_async(
                            Gio.FILE_ATTRIBUTE_STANDARD_SYMBOLIC_ICON,
                            Gio.FileQueryInfoFlags.NONE,
                            GLib.PRIORITY_DEFAULT,
                            None,
                            self._dir_icon_query_callback,
                            thumbnail,
                        )

                        gfile.query_info_async(
                            Gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE,
                            Gio.FileQueryInfoFlags.NONE,
                            GLib.PRIORITY_DEFAULT,
                            None,
                            self._dir_content_type_query_callback,
                            thumbnail,
                        )

                self.thumbnail.set_paintable(texture)
                self.thumbnail.set_visible(True)
                self.icon.set_visible(False)

    def update_thumbnail(self) -> None:
        """Update the visible thumbnail of the file"""
        self.icon.set_visible(True)
        self.thumbnail.set_visible(False)

        if self.path.is_file() and (suffix := self.path.suffix):
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
