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

from gi.repository import Gio, Gtk

from hyperplane import shared
from hyperplane.utils.get_content_type import get_content_type_async


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/item.ui")
class HypItem(Gtk.Box):
    __gtype_name__ = "HypItem"

    label: Gtk.Label = Gtk.Template.Child()
    thumbnail_overlay: Gtk.Overlay = Gtk.Template.Child()

    gfile = Gio.File
    path: Path
    content_type: str

    def __init__(self, path: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.path = path

        if not self.path.exists():
            return

        self.gfile = Gio.File.new_for_path(str(path))
        self.update()

    def update(self) -> None:
        """Update the file name and thumbnail"""
        self.update_label()
        self.connect("map", self.update_thumbnail)

    def update_label(self) -> None:
        """Update the visible name of the file"""
        self.label.set_label(self.path.stem)

    def update_thumbnail(self, *_args: Any) -> None:
        """Update the visible thumbnail of the file"""
        self.thumbnail_overlay.update_icon()
        get_content_type_async(self.gfile, self._content_type_callback)

    def _content_type_callback(self, _gfile: Gio.File, content_type: str) -> None:
        self.content_type = content_type
        self.thumbnail_overlay.update_thumbnail()
