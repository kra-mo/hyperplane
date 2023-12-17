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


# pylint: disable=too-many-return-statements
def get_color_for_content_type(content_type: str) -> str:
    """Returns the color associated with a MIME type."""
    if content_type == "inode/directory":
        return "dark-blue"

    match content_type.split("/")[0]:
        case "audio":
            return "yellow"
        case "application":
            return "blue"
        case "image":
            return "purple"
        case "video":
            return "red"
        case "text":
            return "gray"
        case "font":
            return "gray"
        case _:
            return "gray"
