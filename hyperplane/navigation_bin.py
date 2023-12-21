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

"""
An `AdwBin` with an `AdwNavigationView` child to be used
with `HypItemsPage`s in its navigation stack.
"""
from typing import Any, Iterable, Optional

from gi.repository import Adw, Gio, GLib

from hyperplane.items_page import HypItemsPage


class HypNavigationBin(Adw.Bin):
    """
    An `AdwBin` with an `AdwNavigationView` child to be used
    with `HypItemsPage`s in its navigation stack.
    """

    __gtype_name__ = "HypNavigationBin"

    items_page: HypItemsPage
    view: Adw.NavigationView

    next_pages: list[Adw.NavigationPage]
    tags: list[str] = []

    def __init__(
        self,
        initial_gfile: Optional[Gio.File] = None,
        initial_tags: Optional[Iterable[str]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.view = Adw.NavigationView()
        self.set_child(self.view)

        if initial_gfile:
            self.view.add(HypItemsPage(gfile=initial_gfile))
        elif initial_tags:
            self.tags = list(initial_tags)
            self.view.add(HypItemsPage(tags=self.tags))

        self.view.connect("popped", self.__popped)
        self.view.connect("pushed", self.__pushed)

        self.next_pages = []
        self.view.connect("get-next-page", self.__next_page)

    def new_page(
        self,
        gfile: Optional[Gio.File] = None,
        tag: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> None:
        """Push a new page with the given file or tag to the navigation stack."""
        if gfile:
            self.tags = []
            page = HypItemsPage(gfile=gfile)
        elif tag:
            if tag in self.tags:
                return
            self.tags.append(tag)
            page = HypItemsPage(tags=self.tags.copy())
        elif tags:
            self.tags = list(tags)
            page = HypItemsPage(tags=self.tags.copy())
        else:
            return

        self.view.add(page)
        self.view.push(page)

    def __pushed(self, *_args: Any) -> None:
        page = self.view.get_visible_page()

        # HACK: find a proper way of doing this
        GLib.timeout_add(10, self.get_root().set_focus, page.scrolled_window)

        if not self.next_pages:
            return

        if page == self.next_pages[-1]:
            self.next_pages.pop()
        else:
            for next_page in self.next_pages:
                self.view.remove(next_page)

            self.next_pages = []

    def __popped(
        self,
        _view: Adw.NavigationView,
        page: Adw.NavigationPage,
    ) -> None:
        self.next_pages.append(page)

        self.get_root().set_focus(self.view.get_visible_page().scrolled_window)

        if tags := self.view.get_visible_page().tags:
            self.tags = tags.copy()
        else:
            self.tags = []

    def __next_page(self, *_args: Any) -> None:
        if not self.next_pages:
            return None

        return self.next_pages[-1]
