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

"""Utilities for working with thumbnails."""
from logging import debug
from typing import Any, Callable

from gi.repository import Gdk, Gio, GLib, GnomeDesktop


def generate_thumbnail(
    gfile: Gio.File, content_type: str, callback: Callable, *args: Any
) -> None:
    """
    Generates a thumbnail and passes it to `callback` as a `Gdk.Texture` with any additional args.

    If the thumbnail generation fails,
    `callback` will be called with the `failed` kwarg set to True.

    Callbacks for successful thumbnailing will automatically be called with `GLib.idle_add`
    but failed ones won't.
    """
    factory = GnomeDesktop.DesktopThumbnailFactory()
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
        return

    if not factory.can_thumbnail(uri, content_type, mtime):
        callback(failed=True)
        return

    try:
        thumbnail = factory.generate_thumbnail(uri, content_type)
    except GLib.Error as error:
        if not error.matches(Gio.io_error_quark(), Gio.IOErrorEnum.NOT_FOUND):
            debug("Cannot thumbnail: %s", error)
            callback(failed=True)
            return

        # If it cannot get a path for the URI, try the target URI
        # TODO: I cannot currently test thumbnailing. Do I need this?
        try:
            target_uri = gfile.query_info(
                Gio.FILE_ATTRIBUTE_STANDARD_TARGET_URI,
                Gio.FileQueryInfoFlags.NONE,
            ).get_attribute_string(Gio.FILE_ATTRIBUTE_STANDARD_TARGET_URI)

            if not target_uri:
                debug("Cannot thumbnail: %s", error)
                callback(failed=True)
                return

            thumbnail = factory.generate_thumbnail(target_uri, content_type)
        except GLib.Error as new_error:
            debug("Cannot thumbnail: %s", new_error)
            callback(failed=True)
            return

    if not thumbnail:
        callback(failed=True)
        return

    factory.save_thumbnail(thumbnail, uri, mtime)
    GLib.idle_add(callback, Gdk.Texture.new_for_pixbuf(thumbnail), *args)
