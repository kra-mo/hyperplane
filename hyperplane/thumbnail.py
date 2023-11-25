# thumbnail.py
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
from hyperplane.item import HypItem
from hyperplane.utils.get_color_for_content_type import get_color_for_content_type
from hyperplane.utils.get_content_type import get_content_type_async
from hyperplane.utils.get_symbolic_icon import get_symbolic_icon_async
from hyperplane.utils.get_thumbnail import get_thumbnail_async


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/thumbnail.ui")
class HypThumb(Gtk.Overlay):
    __gtype_name__ = "HypThumb"

    item: HypItem
    icon: Gtk.Image = Gtk.Template.Child()
    extension_label: Gtk.Label = Gtk.Template.Child()
    thumbnail: Gtk.Picture = Gtk.Template.Child()
    play_button: Gtk.Box = Gtk.Template.Child()

    dir_thumbnails: Gtk.Box = Gtk.Template.Child()
    dir_thumbnail_1: Gtk.Box = Gtk.Template.Child()
    dir_thumbnail_2: Gtk.Box = Gtk.Template.Child()
    dir_thumbnail_3: Gtk.Box = Gtk.Template.Child()

    def set_item(self, item) -> None:
        self.item = item

    def build_icon(self, icon: Gio.Icon) -> None:
        """Build the symbolic icon and badge representing the file."""
        self.icon.set_visible(True)
        self.thumbnail.set_visible(False)

        self.__build_extension()
        self.icon.set_from_gicon(icon)

    def build_thumbnail(self, thumbnail_path: str) -> None:
        """Build the thumbnail of the file."""
        color = get_color_for_content_type(self.item.content_type)
        self.add_css_class(color + "-background")
        self.thumbnail.set_content_fit(Gtk.ContentFit.COVER)
        self.dir_thumbnail_1.set_visible(False)
        self.dir_thumbnail_2.set_visible(False)
        self.dir_thumbnail_3.set_visible(False)

        if self.item.path.is_file():
            self.icon.add_css_class(color + "-icon")
            self.extension_label.remove_css_class(color + "-extension-thumb")
            self.extension_label.add_css_class(color + "-extension")
            get_thumbnail_async(
                self.item.gfile,
                self.item.content_type,
                self.__thumbnail_callback,
                thumbnail_path,
                color,
            )
        elif self.item.path.is_dir():
            self.thumbnail.set_content_fit(Gtk.ContentFit.FILL)

            texture = Gdk.Texture.new_from_resource(
                shared.PREFIX + "/assets/folder-closed.svg"
            )

            try:
                if any(self.item.path.iterdir()):
                    texture = Gdk.Texture.new_from_resource(
                        shared.PREFIX + "/assets/folder-open.svg"
                    )

                    index = 0
                    for path in self.item.path.iterdir():
                        if index == 3:
                            break

                        if not path.exists():
                            continue

                        match index:
                            case 0:
                                thumbnail = self.dir_thumbnail_1
                                self.dir_thumbnail_1.set_visible(True)
                            case 1:
                                thumbnail = self.dir_thumbnail_2
                                self.dir_thumbnail_2.set_visible(True)
                            case 2:
                                thumbnail = self.dir_thumbnail_3
                                self.dir_thumbnail_3.set_visible(True)

                        index += 1

                        gfile = Gio.File.new_for_path(str(path))

                        get_symbolic_icon_async(
                            gfile, self.__dir_icon_callback, thumbnail
                        )
                        get_content_type_async(
                            gfile, self.__dir_content_type_callback, thumbnail
                        )
            except PermissionError:
                pass

            self.thumbnail.set_paintable(texture)
            self.thumbnail.set_visible(True)
            self.icon.set_visible(False)

    def __build_extension(self, *_args: Any) -> None:
        if self.item.path.is_file() and (suffix := self.item.path.suffix):
            self.extension_label.set_label(suffix[1:].upper())
            self.extension_label.set_visible(True)
        else:
            self.extension_label.set_visible(False)

    def __dir_icon_callback(
        self, _gfile: Gio.File, icon: Gio.Icon, thumbnail: Gtk.Overlay
    ) -> None:
        thumbnail.get_child().set_from_gicon(icon)

    def __dir_thumbnail_callback(
        self, _gfile: Gio.File, texture: Gdk.Texture, thumbnail: Gtk.Overlay
    ) -> None:
        thumbnail.remove_css_class("white-background")
        thumbnail.add_css_class("light-blue-background")

        picture = Gtk.Picture.new_for_paintable(texture)
        picture.set_content_fit(Gtk.ContentFit.COVER)
        thumbnail.get_child().set_visible(False)
        thumbnail.add_overlay(picture)

    def __dir_content_type_callback(
        self, gfile: Gio.File, content_type: str, thumbnail: Gtk.Overlay
    ) -> None:
        path = Path(gfile.get_path())
        if path.is_file():
            thumbnail.add_css_class("white-background")
            color = get_color_for_content_type(content_type)
            thumbnail.get_child().add_css_class(color + "-icon-light-only")
            get_thumbnail_async(
                gfile, content_type, self.__dir_thumbnail_callback, None, thumbnail
            )

        elif path.is_dir():
            thumbnail.add_css_class("light-blue-background")
            thumbnail.get_child().add_css_class("white-icon")

    def __thumbnail_callback(
        self, _gfile: Gio.File, texture: Gdk.Texture, color: str
    ) -> None:
        self.thumbnail.set_paintable(texture)

        for css_class in self.get_css_classes():
            if "-background" in css_class:
                self.remove_css_class(css_class)
        self.add_css_class("gray-background")

        self.thumbnail.set_visible(True)
        self.icon.set_visible(False)
        self.extension_label.remove_css_class(color + "-extension")
        self.extension_label.add_css_class(color + "-extension-thumb")

        if self.item.content_type.split("/")[0] in ("video", "audio"):
            self.play_button.set_visible(True)
