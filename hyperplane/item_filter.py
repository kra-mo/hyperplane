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

"""Main filter for HypItemsPage."""
from typing import Optional

from gi.repository import Gio, GLib, Gtk

from hyperplane import shared
from hyperplane.utils.tags import path_represents_tags


class HypItemFilter(Gtk.Filter):
    """Main filter for HypItemsPage."""

    __gtype_name__ = "HypItemFilter"

    def __tag_filter(self, file_info: Gio.FileInfo) -> bool:
        if not shared.tags:
            return True

        if file_info.get_content_type() != "inode/directory":
            return True

        if not (path := file_info.get_attribute_object("standard::file").get_path()):
            return True

        if not path_represents_tags(path):
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
        """Checks if the given `item` is matched by the filter or not."""
        if not file_info:
            return False

        return all(
            (
                self.__search_filter(file_info),
                self.__hidden_filter(file_info),
                self.__tag_filter(file_info),
            )
        )
