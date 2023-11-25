# get_thumbnail.py
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
from typing import Any, Callable, Optional

from gi.repository import Gdk, Gio, GLib, GnomeDesktop


def get_thumbnail_async(
    gfile: Gio.File,
    content_type: str,
    callback: Callable,
    thumbnail_path: Optional[str],
    *args: Any,
) -> None:
    """Get the thumbnail of a file or generate it if one doesn't already exist."""

    # TODO: Maybe put this in some outer scope
    if thumbnail_path:
        callback(gfile, Gdk.Texture.new_from_filename(thumbnail_path), *args)

    gfile.query_info_async(
        Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH,
        Gio.FileQueryInfoFlags.NONE,
        GLib.PRIORITY_DEFAULT,
        None,
        __query_callback,
        content_type,
        callback,
        *args,
    )


def __query_callback(
    gfile: Gio.File, result: Gio.Task, content_type: str, callback: Callable, *args: Any
) -> None:
    try:
        file_info = gfile.query_info_finish(result)
    except GLib.Error:
        return
    if path := file_info.get_attribute_as_string(Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH):
        callback(gfile, Gdk.Texture.new_from_filename(path), *args)
        return

    GLib.Thread.new(None, __generate_thumbnail, gfile, content_type, callback, *args)


def __generate_thumbnail(gfile, content_type, callback, *args) -> None:
    factory = GnomeDesktop.DesktopThumbnailFactory()
    uri = Gio.file_new_for_path(str(gfile.get_path())).get_uri()
    mtime = Path(gfile.get_path()).stat().st_mtime

    if factory.lookup(uri, mtime):
        return

    if not factory.can_thumbnail(uri, content_type, mtime):
        return

    if not (thumbnail := factory.generate_thumbnail(uri, content_type)):
        return

    factory.save_thumbnail(thumbnail, uri, mtime)
    GLib.idle_add(callback, gfile, Gdk.Texture.new_for_pixbuf(thumbnail), *args)
