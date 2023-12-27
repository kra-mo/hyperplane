# path_entry.py
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

"""An entry for navigating to paths or tags."""
from typing import Any

from gi.repository import Gio, GObject, Gtk

from hyperplane import shared


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/path-entry.ui")
class HypPathEntry(Gtk.Entry):
    """An entry for navigating to paths or tags."""

    __gtype_name__ = "HypPathEntry"

    completer = Gio.FilenameCompleter.new()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.connect("activate", self.__activate)
        self.connect("changed", self.__complete)
        self.prev_text = ""
        self.prev_completion = ""

    @GObject.Signal(name="hide-entry")
    def hide(self) -> None:
        """
        Emitted to indicate that the entry is done and should be hidden.

        Containers of this widget should connect to it and react accordingly.
        """

    def __complete(self, *_args: Any) -> None:
        text = self.get_text()

        # If the user is typing a tag, return
        if text.startswith("//"):
            return

        if completion := self.completer.get_completion_suffix(text):
            # If a deletion happened, return
            # There is probably a more logical way to do this
            if (
                (len(completion) == 2 and not self.prev_completion.endswith(completion))
                or completion.endswith(self.prev_completion)
                or (
                    self.prev_text.startswith(text)
                    and self.prev_completion.endswith(completion)
                )
            ):
                self.prev_text = text
                self.prev_completion = completion
                return

            self.prev_text = text
            self.prev_completion = completion

            text_length = self.get_text_length()
            new_text = text + completion

            # Set the buffer directly so GTK doesn't freak out
            self.get_buffer().set_text(new_text, len(new_text))
            self.select_region(text_length, -1)

    def __activate(self, entry, *_args: Any) -> None:
        text = entry.get_text().strip()

        if text.startswith("//"):
            tags = list(
                tag
                for tag in shared.tags
                if tag in text.lstrip("/").rstrip("/").split("//")
            )

            if not tags:
                self.get_root().send_toast(_("No such tags"))
                return

            self.emit("hide-entry")
            self.get_root().new_page(tags=tags)
            return

        if "://" in text:
            gfile = Gio.File.new_for_uri(text)
        else:
            gfile = Gio.File.new_for_path(text)

        if (
            not gfile.query_file_type(Gio.FileQueryInfoFlags.NONE)
            == Gio.FileType.DIRECTORY
        ):
            self.get_root().send_toast(_("Unable to find path"))
            return

        self.emit("hide-entry")

        self.get_root().new_page(gfile)
