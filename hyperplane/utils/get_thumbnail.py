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
from typing import Any

from gi.repository import Gdk, Gio, GLib, GnomeDesktop


def get_thumbnail_async(
    gfile: Gio.File, content_type: str, callback: callable, *args: Any
) -> None:
    """A wrapper around gfile.query_info_async."""
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
    gfile: Gio.File, result: Gio.Task, content_type: str, callback: callable, *args: Any
) -> None:
    try:
        file_info = gfile.query_info_finish(result)
    except GLib.GError:
        return
    if path := file_info.get_attribute_as_string(Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH):
        texture = Gdk.Texture.new_from_filename(path)
    elif pixbuf := __generate_thumbnail(Path(gfile.get_path()), content_type):
        texture = Gdk.Texture.new_for_pixbuf(pixbuf)
    else:
        return

    # Only call the callback if successful. Content type cannot be NULL.
    callback(gfile, texture, *args)


def __generate_thumbnail(path, mime_type):
    factory = GnomeDesktop.DesktopThumbnailFactory()
    uri = Gio.file_new_for_path(str(path)).get_uri()
    mtime = path.stat().st_mtime

    if factory.lookup(uri, mtime):
        return None

    if not factory.can_thumbnail(uri, mime_type, mtime):
        return None

    if not (thumbnail := factory.generate_thumbnail(uri, mime_type)):
        return None

    factory.save_thumbnail(thumbnail, uri, mtime)
    return thumbnail
