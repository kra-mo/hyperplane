# restore_file.py
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

import shutil
from pathlib import Path
from urllib.parse import quote

from gi.repository import Gio, GLib


def restore_file(path: str, t: int) -> None:
    trash = Gio.File.new_for_uri("trash://")

    files = trash.enumerate_children(
        Gio.FILE_ATTRIBUTE_STANDARD_TARGET_URI
        + ","
        + Gio.FILE_ATTRIBUTE_TRASH_DELETION_DATE
        + ","
        + Gio.FILE_ATTRIBUTE_TRASH_ORIG_PATH,
        Gio.FileAttributeInfoFlags.NONE,
    )

    while info := files.next_file():
        orig_path = info.get_attribute_byte_string(Gio.FILE_ATTRIBUTE_TRASH_ORIG_PATH)
        del_date = info.get_deletion_date()
        uri = info.get_attribute_string(Gio.FILE_ATTRIBUTE_STANDARD_TARGET_URI)

        if not orig_path == path:
            continue

        if not GLib.DateTime.new_from_unix_utc(t).equal(del_date):
            continue

        # Move the item in Trash/files back to the original location
        shutil.move((path := Path(Gio.File.new_for_uri(uri).get_path())), orig_path)

        # Remove the .trashinfo file, double-check that it is the right one
        trashinfo = (
            Path.home()
            / ".local"
            / "share"
            / "Trash"
            / "info"
            / (path.name + ".trashinfo")
        )
        try:
            keyfile = GLib.KeyFile.new()
            keyfile.load_from_file(str(trashinfo), GLib.KeyFileFlags.NONE)
        except GLib.Error:
            return

        if keyfile.get_string("Trash Info", "Path") == quote(orig_path):
            try:
                Gio.File.new_for_path(str(trashinfo)).delete()
            except GLib.Error:
                pass
