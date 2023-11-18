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

from gi.repository import Gio, GnomeDesktop


def get_thumbnail(path, mime_type):
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
