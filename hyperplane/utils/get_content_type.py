# get_content_type.py
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

from typing import Any

from gi.repository import Gio, GLib


def get_content_type_async(gfile: Gio.File, callback: callable, *args: Any) -> None:
    """A wrapper around gfile.query_info_async."""
    gfile.query_info_async(
        Gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE,
        Gio.FileQueryInfoFlags.NONE,
        GLib.PRIORITY_DEFAULT,
        None,
        _query_callback,
        callback,
        *args,
    )


def _query_callback(
    gfile: Gio.File, result: Gio.Task, callback: callable, *args: Any
) -> None:
    try:
        file_info = gfile.query_info_finish(result)
    except GLib.GError:
        return
    if not (content_type := file_info.get_content_type()):
        return

    # Only call the callback if successful. Content type cannot be NULL.
    callback(gfile, content_type, *args)
