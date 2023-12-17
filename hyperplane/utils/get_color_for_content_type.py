# get_color_for_content_type.py
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

"""Returns the color associated with a MIME type."""
from typing import Optional

from gi.repository import Gio


# pylint: disable=too-many-return-statements
def get_color_for_content_type(
    content_type: str, gicon: Optional[Gio.Icon] = None
) -> str:
    """Returns the color associated with a MIME type."""

    if content_type == "inode/directory":
        return "dark-blue"

    # TODO: Certificates don't have a standard mime type
    # TODO: I don't think addon, firmware or applicance are a thing for files
    # TODO: Add special cases like Flatpak

    detailed = {
        "text-html": "blue",
        "application-x-appliance": "gray",
        "application-x-addon": "green",
        "application-rss+xml": "orange",
        "application-x-firmware": "gray",
        "application-x-sharedlib": "green",
        "inode-symlink": "orange",
        "text-x-generic-template": "gray",
        "text-x-preview": "red",
        "text-x-script": "orange",
        "x-office-document-template": "blue",
        "x-office-drawing-template": "orange",
        "x-office-presentation-template": "red",
        "x-office-spreadsheet-template": "green",
    }

    if gicon and (color := detailed.get(gicon.get_names()[0].replace("-symbolic", ""))):
        return color

    generic = {
        "application-x-executable": "blue",
        "application-x-generic": "gray",
        "audio-x-generic": "yellow",
        "font-x-generic": "purple",
        "image-x-generic": "purple",
        "package-x-generic": "orange",
        "text-x-generic": "gray",
        "video-x-generic": "red",
        "x-office-addressbook": "blue",
        "x-office-calendar": "blue",
        "x-office-document": "blue",
        "x-office-spreadsheet": "green",
        "x-office-presentation": "red",
        "x-office-drawing": "orange",
    }

    if gicon and (color := generic.get(gicon.get_names()[-1].replace("-symbolic", ""))):
        return color

    mimes = {
        "application": "gray",
        "audio": "yellow",
        "font": "purple",
        "image": "purple",
        "video": "red",
        "text": "gray",
    }

    if color := mimes.get(content_type.split("/")[0]):
        return color

    # Fallback
    return "gray"
