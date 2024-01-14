# hover_page_opener.py
#
# Copyright 2024 kramo
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

"""
`GtkWidget`s inheriting from this class will become targets for
opening a page representing their items while a DnD operation is ongoing.
"""
from typing import Any, Iterable, Optional

from gi.repository import Gio, GLib, Gtk


class HypHoverPageOpener:
    """
    `GtkWidget`s inheriting from this class will become targets for
    opening a page representing their items while a DnD operation is ongoing.

    They must have either a `gfile`, `tag` or `tags` attribute.

    The class should only be used by widgets inside a `HypWindow`.
    """

    gfile: Optional[Gio.File]
    tag: Optional[str]
    tags: Optional[Iterable[str]]

    def __init__(self) -> None:
        self.can_open_page = True

        self.drop_controller_motion = Gtk.DropControllerMotion.new()
        self.drop_controller_motion.connect("enter", self.__dnd_motion_enter)
        Gtk.Widget.add_controller(self, self.drop_controller_motion)

    def __hover_open(self, *_args: Any) -> None:
        win = Gtk.Widget.get_root(self)

        if self.drop_controller_motion.contains_pointer():
            win.new_page(
                getattr(self, "gfile", None),
                getattr(self, "tag", None),
                getattr(self, "tags", None),
            )

    def __dnd_motion_enter(self, *_args: Any) -> None:
        if self.can_open_page:
            GLib.timeout_add(500, self.__hover_open)
