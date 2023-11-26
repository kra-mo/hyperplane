# item_filter.py
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
from typing import Optional

from gi.repository import Gio, GLib, Gtk

from hyperplane import shared


class HypItemFilter(Gtk.Filter):
    __gtype_name__ = "HypItemFilter"

    def __tag_filter(self, file_info: Gio.FileInfo) -> bool:
        path = Path(file_info.get_attribute_object("standard::file").get_path())
        if not path.is_dir:
            return False
        if (
            tuple(
                tag
                for tag in shared.tags
                if tag in (relative_parts := path.relative_to(shared.home).parts)
            )
            != relative_parts
        ):
            return True

        return False

    def __search_filter(self, file_info: Gio.FileInfo) -> bool:
        if not shared.search:
            return True

        search = shared.search.lower()

        if search in file_info.get_display_name().lower():
            return True

        return False

    def __hidden_filter(self, file_info: Gio.FileInfo) -> bool:
        if shared.show_hidden:
            return True

        try:
            if file_info.get_is_hidden():
                return False
        except GLib.Error:
            pass
        return True

    def do_match(self, file_info: Optional[Gio.FileInfo] = None) -> bool:
        if not file_info:
            return False

        return all(
            (
                self.__search_filter(file_info),
                self.__hidden_filter(file_info),
                self.__tag_filter(file_info),
            )
        )
