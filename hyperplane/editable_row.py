# editable_row.py
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

"""A row in the sidebar representing a tag."""
from typing import Optional

from gi.repository import GLib, GObject, Gtk, Pango

from hyperplane import shared
from hyperplane.hover_page_opener import HypHoverPageOpener


class HypEditableRow(Gtk.ListBoxRow, HypHoverPageOpener):
    """A row in the sidebar representing a tag."""

    __gtype_name__ = "HypEditableRow"

    _identifier: str
    _editable: bool
    _active: bool

    # This is built in Python, because
    # TypeError: Inheritance from classes with @Gtk.Template decorators is not allowed at this time

    # HACK: *slaps roof of class* this baby can fit so mcuh spaghetti in her

    def __init__(self, identifier: Optional[str] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        HypHoverPageOpener.__init__(self)

        self.image = Gtk.Image.new()
        self.label = Gtk.Label(ellipsize=Pango.EllipsizeMode.END)

        self.box = Gtk.Box(spacing=12, margin_start=6)
        self.box.append(self.image)
        self.box.append(self.label)

        self.check = Gtk.CheckButton(active=True)
        self.check.add_css_class("sidebar-check-button")
        self.check_revealer = Gtk.Revealer(
            child=self.check,
            halign=Gtk.Align.END,
            hexpand=True,
            visible=False,
            transition_type=Gtk.RevealerTransitionType.SLIDE_LEFT,
        )

        self.box.append(self.check_revealer)

        self.set_child(self.box)

        self.editable = True
        self.identifier = identifier

    @GObject.Property(type=str)
    def identifier(self) -> str:
        """The identifier for the row used in dconf."""
        return self._identifier

    @identifier.setter
    def set_identifier(self, identifier: str) -> None:
        if not identifier:
            return

        self._identifier = identifier

        self.set_active()

    @GObject.Property(type=bool, default=True)
    def editable(self) -> str:
        """Whether the row is actually editable."""
        return self._editable

    @editable.setter
    def set_editable(self, editable: bool) -> None:
        self._editable = editable

    @GObject.Property(type=str)
    def icon_name(self) -> str:
        """The icon name for self."""
        return self.image.get_icon_name()

    @icon_name.setter
    def set_icon_name(self, icon_name: str) -> None:
        self.image.set_from_icon_name(icon_name)

    @GObject.Property(type=str)
    def title(self) -> str:
        """The title for self."""
        self.label.get_label()

    @title.setter
    def set_title(self, title: str) -> None:
        self.label.set_label(title)

    def start_edit(self) -> None:
        """Reveals the check button for editing."""
        self.set_visible(True)

        self.check.set_sensitive(self.editable)
        self.check_revealer.set_visible(True)
        self.check_revealer.set_reveal_child(True)

    def end_edit(self) -> None:
        """Saves the edits and updates the row accordingly."""
        self.check_revealer.set_reveal_child(False)
        GLib.timeout_add(
            self.check_revealer.get_transition_duration(),
            self.check_revealer.set_visible,
            False,
        )

        var = shared.schema.get_value("hidden-locations")

        if self.check.get_active():
            children = []
            write = False

            for index in range(var.n_children()):
                child = var.get_child_value(index)
                if not child.get_string() == self.identifier:
                    children.append(child)
                    continue

                write = True

            if not write:
                return

            var = GLib.Variant.new_array(GLib.VariantType.new("s"), children)
        else:
            self.set_visible(False)
            children = []
            for index in range(var.n_children()):
                child = var.get_child_value(index)
                if child.get_string() == self.identifier:
                    continue
                children.append(child)

            children.append(GLib.Variant.new_string(self.identifier))
            var = GLib.Variant.new_array(GLib.VariantType.new("s"), children)

        shared.schema.set_value("hidden-locations", var)

    def set_active(self) -> None:
        """
        Sets the checkmark to active/inactive based on dconf.

        This should only be called extenally
        if the sidebar has been changed from a different window.
        """

        var = shared.schema.get_value("hidden-locations")
        for index in range(var.n_children()):
            if var.get_child_value(index).get_string() == self.identifier:
                self.check.set_active(False)
                break
        else:
            self.check.set_active(True)

        # If we are not in edit mode
        if not self.check_revealer.get_reveal_child():
            self.set_visible(self.check.get_active())
