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

    _active: bool

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
        if self.tag:
            self.emit("open-tag", self.tag)
            return

        if self.uri:
            if self.active:  # pylint: disable=using-constant-test
                return

            self.emit("open-gfile", Gio.File.new_for_uri(self.uri))

    @GObject.Signal(name="open-tag")
    def open_tag(self, _tag: str) -> None:
        """Signals to the path bar that `tag` should be opened as the only tag."""

    @GObject.Signal(name="open-gfile")
    def open_gfile(self, _gfile: Gio.File) -> None:
        """Signals to the path bar that `gfile` should be opened."""

    @GObject.Property(type=bool, default=True)
    def active(self) -> bool:
        """Whether the segment is the currently active one."""
        return self._active

    @active.setter
    def set_active(self, active) -> None:
        self._active = active
        (self.remove_css_class if active else self.add_css_class)("inactive-segment")

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
