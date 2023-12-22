# path_segment.py
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

"""A segment in a HypPathBar."""
from typing import Any, Optional

from gi.repository import Adw, Gio, GObject, Gtk

from hyperplane import shared


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/path-segment.ui")
class HypPathSegment(Gtk.Revealer):
    """A segment in a HypPathBar."""

    __gtype_name__ = "HypPathSegment"

    button: Gtk.Button = Gtk.Template.Child()
    button_content: Adw.ButtonContent = Gtk.Template.Child()

    def __init__(
        self,
        label: str,
        icon_name: Optional[str] = None,
        uri: Optional[str] = None,
        tag: Optional[str] = None,
        **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.icon_name = icon_name
        self.label = label
        self.uri = uri
        self.tag = tag

        self.button.connect("clicked", self.__navigate)

    def __navigate(self, *_args: Any) -> None:
        # HACK: Do this properly
        nav_bin = self.get_root().get_nav_bin()

        if self.tag:
            nav_bin.new_page(tags=[self.tag])
            return

        if self.uri:
            nav_bin.new_page(Gio.File.new_for_uri(self.uri))

    @GObject.Property(type=str)
    def icon_name(self) -> str:
        """An optional icon for the path segment."""
        return self.button_content.get_icon_name()

    @icon_name.setter
    def set_icon_name(self, icon_name: str) -> None:
        if not icon_name:
            self.button_content.set_visible(False)
            return
        self.button_content.set_icon_name(icon_name)

    @GObject.Property(type=str)
    def label(self) -> str:
        """The label of the path segment."""
        return (
            self.button_content.get_label()
            if self.icon_name
            else self.button.get_label()
        )

    @label.setter
    def set_label(self, label: str) -> None:
        (self.button_content if self.icon_name else self.button).set_label(label)
