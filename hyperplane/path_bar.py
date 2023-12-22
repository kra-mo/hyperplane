# path_bar.py
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

"""The path bar in a HypWindow."""
from typing import Optional

from gi.repository import GLib, Gtk

from hyperplane import shared
from hyperplane.path_segment import HypPathSegment


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/path-bar.ui")
class HypPathBar(Gtk.ScrolledWindow):
    """The path bar in a HypWindow."""

    __gtype_name__ = "HypPathBar"

    segments_box: Gtk.Box = Gtk.Template.Child()
    segments: list
    separators: dict
    tags: bool  # Whether the path bar represents tags or a file

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.segments = []
        self.separators = {}
        self.tags = False

    def __remove_child(self, parent: Gtk.Box, child: Gtk.Widget) -> None:
        # This is so GTK doesn't freak out when the child isn't in the box anymore
        if child.get_parent == parent:
            parent.remove(child)

    def remove(self, n: int) -> None:
        """Removes n number of segments form self."""
        for _index in range(n):
            child = self.segments.pop()
            child.set_reveal_child(False)
            GLib.timeout_add(
                child.get_transition_duration(),
                self.__remove_child,
                self.segments_box,
                child,
            )

            if not (sep := self.separators[child]):
                return

            sep.set_reveal_child(False)
            GLib.timeout_add(
                sep.get_transition_duration(),
                self.__remove_child,
                self.segments_box,
                sep,
            )
            self.separators.pop(child)

        if self.tags:
            return

        try:
            self.segments[-1].remove_css_class("inactive-segment")
            self.segments[-2].add_css_class("inactive-segment")
        except IndexError:
            return

    def append(
        self,
        label: str,
        icon_name: Optional[str] = None,
        uri: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> None:
        """Appends a HypPathSegment with `label` to self."""
        if self.segments:
            # Add a separator only if there is more than one item
            sep_label = Gtk.Label.new("+" if self.tags else "/")
            sep_label.add_css_class("heading" if self.tags else "dim-label")

            sep = Gtk.Revealer(
                child=sep_label, transition_type=Gtk.RevealerTransitionType.SLIDE_RIGHT
            )
            self.segments_box.append(sep)
            sep.set_reveal_child(True)
        else:
            sep = None

        path_segment = HypPathSegment(label, icon_name, uri, tag)
        self.segments_box.append(path_segment)

        path_segment.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
        path_segment.set_reveal_child(True)

        self.separators[path_segment] = sep
        self.segments.append(path_segment)

        if self.tags:
            return

        try:
            self.segments[-1].remove_css_class("inactive-segment")
            self.segments[-2].add_css_class("inactive-segment")
        except IndexError:
            return

    def purge(self) -> None:
        """Removes all segments from self."""
        while child := self.segments_box.get_first_child():
            self.segments_box.remove(child)

        self.segments = []
        self.separators = {}
