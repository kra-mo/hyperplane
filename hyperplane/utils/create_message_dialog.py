# create_message_dialog.py
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

"""Returns an `AdwMessageDialog` with the given properties."""
from typing import Callable, Optional

from gi.repository import Adw, Gtk


def create_message_dialog(
    parent: Gtk.Window,
    heading: str,
    *responses: tuple[
        str,  # Name
        Optional[str],  # ID
        Optional[Adw.ResponseAppearance],  # Appearance
        Optional[Callable],  # Callback
        bool,  # Default
    ],
    body: Optional[str] = None,
    extra_child: Optional[Gtk.Widget] = None,
) -> Adw.MessageDialog:
    """Returns an `AdwMessageDialog` with the given properties."""
    dialog = Adw.MessageDialog.new(parent, heading, body)

    if extra_child:
        dialog.set_extra_child(extra_child)

    callables = {}

    for index, response in enumerate(responses):
        response_id = response[1] or str(index)

        dialog.add_response(response_id, response[0])

        if response[2]:
            dialog.set_response_appearance(response_id, response[2])

        if response[3]:
            callables[response_id] = response[3]

        if response[4]:
            dialog.set_default_response(response_id)

    def handle_response(_dialog: Adw.MessageDialog, response: str) -> None:
        if response in callables:
            callables[response]()

    dialog.connect("response", handle_response)
    return dialog
