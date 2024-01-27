# guide.py
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

"""A window showcasing the features of the app."""
from gi.repository import Adw, Gtk

from hyperplane import shared


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/guide.ui")
class HypGuide(Adw.Dialog):
    """A window showcasing the features of the app."""

    __gtype_name__ = "HypGuide"

    carousel: Adw.Carousel = Gtk.Template.Child()
    page_1: Adw.StatusPage = Gtk.Template.Child()
    tags_picture: Gtk.Picture = Gtk.Template.Child()
    folders_picture: Gtk.Picture = Gtk.Template.Child()
    folder_picture: Gtk.Picture = Gtk.Template.Child()

    button_1: Gtk.Button = Gtk.Template.Child()
    button_2: Gtk.Button = Gtk.Template.Child()
    button_3: Gtk.Button = Gtk.Template.Child()
    button_4: Gtk.Button = Gtk.Template.Child()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        self.page_1.set_icon_name(shared.APP_ID)
        self.tags_picture.set_resource(shared.PREFIX + "/assets/welcome-tags.svg")
        self.folders_picture.set_resource(shared.PREFIX + "/assets/welcome-folders.svg")
        self.folder_picture.set_paintable(shared.closed_folder_texture)

    @Gtk.Template.Callback()
    def _next_page(self, _widget: Gtk.Widget) -> None:
        self.carousel.scroll_to(
            self.carousel.get_nth_page(pos := self.carousel.get_position() + 1), True
        )
        self.set_focus(getattr(self, f"button_{int(pos) + 1}"))
