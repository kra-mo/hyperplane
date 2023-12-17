# postmaster_general.py
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

"""A singleton class for sending signals throughtout the app."""
from gi.repository import GObject


class HypPostmasterGeneral(GObject.Object):
    """A singleton class for sending signals throughtout the app."""

    __gtype_name__ = "HypPostmasterGeneral"

    @GObject.Signal(name="zoom")
    def zoom(self, zoom_level: int) -> None:
        """
        Emitted whenever the zoom level changes.

        All widgets that are affected by zooming should connect to it.
        """

    @GObject.Signal(name="toggle-hidden")
    def toggle_hidden(self) -> None:
        """Emitted when the visibility of hidden files changes."""

    @GObject.Signal(name="tags-changed")
    def tags_changed(self) -> None:
        """
        Emitted whenever the list of tags changes.

        All objects that keep an internal list of tags should connect to this
        and update their list accordingly.
        """
