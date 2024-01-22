# file_properties.py
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

"""Miscellaneous variables for determining file properties."""

from gi.repository import Gio, GLib

DOT_IS_NOT_EXTENSION = {
    "application/x-sharedlib",
    "application/x-executable",
    "application/x-pie-executable",
    "inode/symlink",
}


# This is so nonexistent URIs never match
class _Fake:
    def __eq__(self, o: object):
        return False


class SpecialUris:
    """URIs that point to special directories."""

    if templates_dir := GLib.get_user_special_dir(
        GLib.UserDirectory.DIRECTORY_TEMPLATES
    ):
        templates_uri = Gio.File.new_for_path(templates_dir).get_uri()
    else:
        templates_uri = _Fake()

    if public_dir := GLib.get_user_special_dir(
        GLib.UserDirectory.DIRECTORY_PUBLIC_SHARE
    ):
        public_uri = Gio.File.new_for_path(public_dir).get_uri()
    else:
        public_uri = _Fake()

    if downloads_dir := GLib.get_user_special_dir(
        GLib.UserDirectory.DIRECTORY_DOWNLOAD
    ):
        downloads_uri = Gio.File.new_for_path(downloads_dir).get_uri()
    else:
        downloads_uri = _Fake()

    trash_uri = "trash:///"
    recent_uri = "recent:///"
