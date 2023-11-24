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


def validate_name(
    path: Path, name: str, siblings: Optional[bool] = False
) -> (bool, Optional[str]):
    # TODO: More elegant (cross-platfrom) way to check for invalid paths
    if name in (".", ".."):
        if path.is_dir():
            error = _('A folder cannot be called "{}".').format(name)
        else:
            error = _('A file cannot be called "{}".').format(name)
        return False, error

    if "/" in name:
        if path.is_dir():
            error = _('Folder names cannot conrain "{}".').format("/")
        else:
            error = _('File names cannot conrain "{}".').format("/")
        return False, error

    new_path = Path(path.parent, name) if siblings else path / name

    if new_path.is_dir() and path.is_dir() and new_path != path:
        error = _("A folder with that name already exists.")
        return False, error

    if new_path.is_file() and path.is_file() and new_path != path:
        error = _("A file with that name already exists.")
        return False, error

    if name[0] == ".":
        if path.is_dir():
            warning = _("Folders with “.” at the beginning of their name are hidden.")
        else:
            warning = _("Files with “.” at the beginning of their name are hidden.")
        return True, warning

    return True, None
