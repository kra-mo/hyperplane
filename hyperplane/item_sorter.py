# item_sorter.py
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

"""Main sorter for HypItemsPage."""
from locale import strcoll
from typing import Optional

from gi.repository import Gio, GLib, Gtk

from hyperplane import shared


class HypItemSorter(Gtk.Sorter):
    """Main sorter for HypItemsPage."""

    __gtype_name__ = "HypItemSorter"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        shared.postmaster.connect(
            "sort-changed", lambda *_: self.changed(Gtk.SorterChange.DIFFERENT)
        )

    def do_compare(
        self,
        file_info1: Optional[Gio.FileInfo] = None,
        file_info2: Optional[Gio.FileInfo] = None,
    ) -> int:
        """
        Compares two given items according to the sort order implemented by the sorter.

        Sorters implement a partial order:

        - It is reflexive, ie a = a
        - It is antisymmetric, ie if a < b and b < a, then a = b
        - It is transitive, ie given any 3 items with a ≤ b and b ≤ c, then a ≤ c

        The sorter may signal it conforms to additional constraints
        via the return value of `HypItemSorter.get_order()`.
        """
        if (not file_info1) or (not file_info2):
            return Gtk.Ordering.EQUAL

        # Always sort trashed items by deletion date
        if (
            file_info1.get_attribute_object("standard::file").get_uri_scheme()
            == "trash"
        ):
            return self.__ordering_from_cmpfunc(
                GLib.DateTime.compare(
                    file_info2.get_deletion_date(),
                    file_info1.get_deletion_date(),
                )
            )

        # Always sort recent items by date
        if (
            file_info1.get_attribute_object("standard::file").get_uri_scheme()
            == "recent"
        ):
            try:
                recent_info1 = shared.recent_manager.lookup_item(
                    file_info1.get_attribute_string(
                        Gio.FILE_ATTRIBUTE_STANDARD_TARGET_URI
                    )
                )
                recent_info2 = shared.recent_manager.lookup_item(
                    file_info2.get_attribute_string(
                        Gio.FILE_ATTRIBUTE_STANDARD_TARGET_URI
                    )
                )
            except GLib.Error:
                pass
            else:
                return self.__ordering_from_cmpfunc(
                    GLib.DateTime.compare(
                        recent_info2.get_modified(), recent_info1.get_modified()
                    )
                )

        if shared.schema.get_boolean("folders-before-files"):
            if folders := self.__sort_folders_before_files(file_info1, file_info2):
                return folders

        name1 = file_info1.get_display_name()
        name2 = file_info2.get_display_name()

        # Sort dot-prefixed files last
        if name1.startswith("."):
            if not name2.startswith("."):
                return Gtk.Ordering.LARGER
        elif name2.startswith("."):
            return Gtk.Ordering.SMALLER

        match shared.sort_by:
            case "a-z":
                return self.__ordering_from_cmpfunc(strcoll(name1, name2))

            case "modified":
                mod1 = file_info1.get_modification_date_time()
                mod2 = file_info2.get_modification_date_time()

                if mod1 and mod2:
                    return self.__ordering_from_cmpfunc(mod2.compare(mod1))

            case "created":
                created1 = file_info1.get_creation_date_time()
                created2 = file_info2.get_creation_date_time()

                if created1 and created2:
                    return self.__ordering_from_cmpfunc(created2.compare(created1))

            case "size":
                # No fast way to calculate size for folders so assume they're always bigger
                if folders := self.__sort_folders_before_files(file_info1, file_info2):
                    return folders

                size1 = file_info1.get_size()
                size2 = file_info2.get_size()

                if size2 and size1:
                    if size1 == size2:
                        return Gtk.Ordering.EQUAL

                    return self.__ordering_from_cmpfunc((int(size1 < size2) * 2) - 1)

            case "type":
                type1 = file_info1.get_content_type()
                type2 = file_info2.get_content_type()

                if type1 and type2:
                    return self.__ordering_from_cmpfunc(strcoll(type2, type1))

        # Fall back to A-Z
        return self.__ordering_from_cmpfunc(strcoll(name1, name2))

    def __ordering_from_cmpfunc(self, cmpfunc_result: int) -> Gtk.Ordering:
        # https://gitlab.gnome.org/GNOME/gtk/-/issues/6298
        return Gtk.Ordering(
            ((cmpfunc_result > 0) - (cmpfunc_result < 0))
            * (-1 if shared.sort_reversed else 1)
        )

    def __sort_folders_before_files(
        self, file_info1: Gio.FileInfo, file_info2: Gio.FileInfo
    ) -> Gtk.Ordering:
        dir1 = file_info1.get_content_type() == "inode/directory"
        dir2 = file_info2.get_content_type() == "inode/directory"

        if dir1:
            if not dir2:
                return Gtk.Ordering.SMALLER
        elif dir2:
            return Gtk.Ordering.LARGER

        return None
