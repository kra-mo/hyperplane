# preferences.py
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

"""The main preferences window."""
from typing import Any

from gi.repository import Adw, Gio, Gtk

from hyperplane import shared


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/preferences.ui")
class HypPreferencesWindow(Adw.PreferencesWindow):
    """The main preferences window."""

    __gtype_name__ = "HypPreferencesWindow"

    folders_switch_row = Gtk.Template.Child()

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        # TODO: Refresh on change
        shared.schema.bind(
            "folders-before-files",
            self.folders_switch_row,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
