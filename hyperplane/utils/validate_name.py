# validate_name.py
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
from typing import Optional

from gi.repository import Gio

from hyperplane.utils.files import get_gfile_path


def validate_name(
    gfile: Gio.File, name: str, siblings: Optional[bool] = False
) -> (bool, Optional[str]):
    try:
        path = Path(get_gfile_path(gfile))
    except FileNotFoundError:
        # Assume that locations without paths are not writable
        # TODO: This may be incorrect
        return False, _("The path is not writable.")

    is_dir = path.is_dir()
    is_file = (not is_dir) and (path.exists())

    # TODO: More elegant (cross-platfrom) way to check for invalid paths
    if name in (".", ".."):
        if is_dir:
            error = _('A folder cannot be called "{}".').format(name)
        else:
            error = _('A file cannot be called "{}".').format(name)
        return False, error

    if "/" in name:
        if is_dir:
            error = _('Folder names cannot conrain "{}".').format("/")
        else:
            error = _('File names cannot conrain "{}".').format("/")
        return False, error

    new_path = Path(path.parent, name) if siblings else path / name
    new_is_dir = new_path.is_dir()
    new_is_file = (not new_is_dir) and (new_path.exists())

    if new_is_dir and is_dir and new_path != path:
        error = _("A folder with that name already exists.")
        return False, error

    if new_is_file and is_file and new_path != path:
        error = _("A file with that name already exists.")
        return False, error

    if name[0] == ".":
        if is_dir:
            warning = _("Folders with “.” at the beginning of their name are hidden.")
        else:
            warning = _("Files with “.” at the beginning of their name are hidden.")
        return True, warning

    return True, None
