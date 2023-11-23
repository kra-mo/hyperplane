# navigation_bin.py
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
from typing import Any, Iterable, Optional

from gi.repository import Adw

from hyperplane.items_page import HypItemsPage


class HypNavigationBin(Adw.Bin):
    __gtype_name__ = "HypNavigationBin"

    items_page: HypItemsPage
    view: Adw.NavigationView

    tags: list[str] = []

    def __init__(
        self,
        initial_path: Optional[Path] = None,
        initial_tags: Optional[Iterable[str]] = None,
        **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.view = Adw.NavigationView()
        self.set_child(self.view)

        if initial_path:
            self.view.push(HypItemsPage(path=initial_path))
        elif initial_tags:
            self.tags = list(initial_tags)
            self.view.push(HypItemsPage(tags=self.tags))

        self.view.connect("popped", self.__popped)

    def new_page(self, path: Optional[Path] = None, tag: Optional[str] = None) -> None:
        """Push a new page with the given path or tag to the navigation stack."""
        if path:
            self.view.push(HypItemsPage(path))
        elif tag:
            self.tags.append(tag)
            self.view.push(HypItemsPage(tags=self.tags))

    def __popped(self, *_args: Any) -> None:
        try:
            self.tags.pop()
        except IndexError:
            pass
