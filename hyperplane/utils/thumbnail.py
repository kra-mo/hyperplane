# thumbnail.py
#
# Copyright 2023-2024 kramo
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

"""Utilities for working with thumbnails."""
import logging
from typing import Any, Callable

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GnomeDesktop

from hyperplane.utils.files import get_gfile_path


def generate_thumbnail(
    gfile: Gio.File, content_type: str, callback: Callable, *args: Any
) -> None:
    """
    Generates a thumbnail and passes it to `callback` as a `Gdk.Texture` with any additional args.

    If the thumbnail generation fails, `callback` is called with None and *args.
    """
    factory = GnomeDesktop.DesktopThumbnailFactory.new(
        GnomeDesktop.DesktopThumbnailSize.LARGE
    )
    uri = gfile.get_uri()

    try:
        mtime = (
            gfile.query_info(
                Gio.FILE_ATTRIBUTE_TIME_MODIFIED, Gio.FileQueryInfoFlags.NONE
            )
            .get_modification_date_time()
            .to_unix()
        )
    except (GLib.Error, AttributeError):
        callback(None, *args)
        return

    if not factory.can_thumbnail(uri, content_type, mtime):
        callback(None, *args)
        return

    try:
        thumbnail = factory.generate_thumbnail(uri, content_type)
    except GLib.Error as error:
        if error.matches(Gio.io_error_quark(), Gio.IOErrorEnum.NOT_FOUND):
            # If it cannot get a path for the URI, try the target URI
            try:
                target_uri = gfile.query_info(
                    Gio.FILE_ATTRIBUTE_STANDARD_TARGET_URI,
                    Gio.FileQueryInfoFlags.NONE,
                ).get_attribute_string(Gio.FILE_ATTRIBUTE_STANDARD_TARGET_URI)

                if not target_uri:
                    logging.debug("Cannot thumbnail: %s", error)
                    callback(None, *args)
                    return

                thumbnail = factory.generate_thumbnail(target_uri, content_type)
            except GLib.Error as new_error:
                logging.debug("Cannot thumbnail: %s", new_error)
                callback(None, *args)
                if not new_error.matches(
                    Gio.io_error_quark(), Gio.IOErrorEnum.NOT_FOUND
                ):
                    factory.create_failed_thumbnail(uri, mtime)
                    factory.create_failed_thumbnail(target_uri, mtime)
                return

        try:
            # Fall back to GdkPixbuf
            thumbnail = GdkPixbuf.Pixbuf.new_from_file_at_size(
                str(get_gfile_path(gfile)), 256, 256
            )
        except (GLib.Error, FileNotFoundError):
            logging.debug("Cannot thumbnail: %s", error)
            callback(None, *args)
            factory.create_failed_thumbnail(uri, mtime)
            return

    if not thumbnail:
        callback(None, *args)
        return

    factory.save_thumbnail(thumbnail, uri, mtime)
    callback(Gdk.Texture.new_for_pixbuf(thumbnail), *args)
