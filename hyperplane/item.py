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

from gi.repository import Gdk, Gio, Gtk

from hyperplane import shared
from hyperplane.utils.get_color_for_content_type import get_color_for_content_type
from hyperplane.utils.get_content_type import get_content_type_async
from hyperplane.utils.get_symbolic_icon import get_symbolic_icon_async
from hyperplane.utils.get_thumbnail import get_thumbnail_async


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

    def _dir_icon_callback(
        self, _gfile: Gio.File, icon: Gio.Icon, thumbnail: Gtk.Overlay
    ) -> None:
        thumbnail.get_child().set_from_gicon(icon)

    def _dir_content_type_callback(
        self, gfile: Gio.File, content_type: str, thumbnail: Gtk.Overlay
    ) -> None:
        path = Path(gfile.get_path())
        if path.is_file():
            thumbnail.add_css_class("solid-white-background")
            color = get_color_for_content_type(content_type)
            thumbnail.get_child().add_css_class(color + "-icon-light-only")
            get_thumbnail_async(
                gfile, content_type, self._dir_thumbnail_callback, thumbnail
            )

        elif path.is_dir():
            thumbnail.add_css_class("light-blue-background")
            thumbnail.get_child().add_css_class("solid-white-icon")

    def _dir_thumbnail_callback(
        self, _gfile: Gio.File, texture: Gdk.Texture, thumbnail: Gtk.Overlay
    ) -> None:
        thumbnail.remove_css_class("solid-white-background")
        thumbnail.add_css_class("light-blue-background")

        picture = Gtk.Picture.new_for_paintable(texture)
        picture.set_content_fit(Gtk.ContentFit.COVER)
        thumbnail.add_overlay(picture)

    def _icon_callback(self, _gfile: Gio.File, icon: Gio.Icon) -> None:
        self.icon.set_from_gicon(icon)

    def _content_type_callback(self, gfile: Gio.File, content_type: str) -> None:
        self.content_type = content_type
        color = get_color_for_content_type(self.content_type)
        self.thumbnail_overlay.add_css_class(color + "-background")

        if self.path.is_file():
            self.icon.add_css_class(color + "-icon")
            self.extension_label.remove_css_class(color + "-extension-thumb")
            self.extension_label.add_css_class(color + "-extension")
            get_thumbnail_async(
                self.gfile, self.content_type, self._thumbnail_callback, color
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

                    thumbnail = Gtk.Overlay(
                        width_request=32,
                        height_request=32,
                        overflow=Gtk.Overflow.HIDDEN,
                    )
                    thumbnail.add_css_class("small-thumbnail")
                    thumbnail.set_child(Gtk.Image())

                    self.dir_thumbnails.append(thumbnail)

                    gfile = Gio.File.new_for_path(str(path))

                    get_symbolic_icon_async(gfile, self._dir_icon_callback, thumbnail)
                    get_content_type_async(
                        gfile, self._dir_content_type_callback, thumbnail
                    )

            self.thumbnail.set_paintable(texture)
            self.thumbnail.set_visible(True)
            self.icon.set_visible(False)

    def _thumbnail_callback(
        self, _gfile: Gio.File, texture: Gdk.Texture, color: str
    ) -> None:
        self.thumbnail.set_paintable(texture)

        for css_class in self.thumbnail_overlay.get_css_classes():
            if "-background" in css_class:
                self.thumbnail_overlay.remove_css_class(css_class)
        self.thumbnail_overlay.add_css_class("gray-background")

        self.thumbnail.set_visible(True)
        self.icon.set_visible(False)
        self.extension_label.remove_css_class(color + "-extension")
        self.extension_label.add_css_class(color + "-extension-thumb")

    def update_thumbnail(self) -> None:
        """Update the visible thumbnail of the file"""
        self.icon.set_visible(True)
        self.thumbnail.set_visible(False)

        if self.path.is_file() and (suffix := self.path.suffix):
            self.extension_label.set_label(suffix[1:].upper())
            self.extension_label.set_visible(True)
        else:
            self.extension_label.set_visible(False)

        get_symbolic_icon_async(self.gfile, self._icon_callback)
        get_content_type_async(self.gfile, self._content_type_callback)
