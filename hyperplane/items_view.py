# items_view.py
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
from typing import Any

from gi.repository import Adw, Gtk

from hyperplane import shared
from hyperplane.item import HypItem


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/items-view.ui")
class HypItemsView(Gtk.FlowBox):
    __gtype_name__ = "HypItemsView"

    def __init__(self, path: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        if not path.is_dir():
            return

        for item in path.iterdir():
            self.append(Adw.Clamp(maximum_size=160, child=HypItem(item)))
