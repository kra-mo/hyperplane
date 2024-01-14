# undo.py
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

"""Utilities for interacting with the undo queue."""
import logging
from typing import Any

from gi.repository import Adw, GLib

from hyperplane import shared
from hyperplane.utils.files import YouAreStupid, move, restore, rm


def undo(obj: Any, *_args: Any) -> None:
    """Undoes an action in the undo queue."""

    if not shared.undo_queue:
        return

    if isinstance(obj, Adw.Toast):
        index = obj
    else:
        index = tuple(shared.undo_queue.keys())[-1]

    item = shared.undo_queue[index]

    match item[0]:
        case "copy":
            for copy_item in item[1]:
                try:
                    rm(copy_item)
                except FileNotFoundError:
                    logging.debug("Cannot undo copy: File doesn't exist anymore.")

        case "move":
            for gfiles in item[1]:
                try:
                    move(gfiles[1], gfiles[0])
                except FileExistsError:
                    logging.debug("Cannot undo move: File exists.")
                except YouAreStupid:
                    logging.debug("Cannot undo move: Someone is being stupid.")

        case "rename":
            try:
                item[1].set_display_name(item[2])
            except GLib.Error as error:
                logging.debug("Cannot undo rename: %s", error)

        case "trash":
            for trash_item in item[1]:
                restore(*trash_item)

    if isinstance(index, Adw.Toast):
        index.dismiss()

    shared.undo_queue.popitem()
