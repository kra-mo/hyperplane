# new_file_dialog.py
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

"""A dialog for creating a new file based on a template."""
import logging
from pathlib import Path
from typing import Any, Optional

from gi.repository import Adw, Gio, GLib, Gtk

from hyperplane import shared
from hyperplane.file_properties import DOT_IS_NOT_EXTENSION
from hyperplane.utils.files import validate_name
from hyperplane.utils.symbolics import get_color_for_symbolic, get_symbolic


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/new-file-dialog.ui")
class HypNewFileDialog(Adw.Window):
    """A dialog for creating a new file based on a template."""

    __gtype_name__ = "HypNewFileDialog"

    active_gfile: Optional[Gio.File] = None

    toolbar_view: Adw.ToolbarView = Gtk.Template.Child()
    templates_folder_button: Gtk.Button = Gtk.Template.Child()
    files_page: Adw.PreferencesPage = Gtk.Template.Child()
    files_group: Adw.PreferencesGroup = Gtk.Template.Child()
    navigation_view: Adw.NavigationView = Gtk.Template.Child()
    name_page: Adw.NavigationPage = Gtk.Template.Child()
    name_text_view: Gtk.TextView = Gtk.Template.Child()
    icon_bin: Adw.Bin = Gtk.Template.Child()
    create_button: Gtk.Button = Gtk.Template.Child()
    warning_revealer: Gtk.Revealer = Gtk.Template.Child()
    warning_revealer_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self, dst: Gio.File, **kwargs) -> None:
        super().__init__(**kwargs)
        self.dst = dst
        self.can_create = True

        self.templates_dir = GLib.get_user_special_dir(
            GLib.UserDirectory.DIRECTORY_TEMPLATES
        )

        if not self.templates_dir:
            return

        self.templates_dir = Gio.File.new_for_path(self.templates_dir)

        if self.__get_template_children(self.templates_dir, self.files_group):
            self.toolbar_view.set_content(self.files_page)

        self.name_text_view.add_controller(controller := Gtk.ShortcutController.new())
        controller.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("Return"),
                Gtk.CallbackAction.new(self.__copy_active_gfile),
            )
        )
        self.create_button.connect("clicked", self.__copy_active_gfile)
        self.templates_folder_button.connect("clicked", self.__open_templates)
        self.name_text_view.get_buffer().connect("changed", self.__text_changed)

    def __get_template_children(
        self, gfile: Gio.File, group: Adw.PreferencesGroup
    ) -> None:
        enumerator = gfile.enumerate_children(
            ",".join(
                (
                    Gio.FILE_ATTRIBUTE_STANDARD_NAME,
                    Gio.FILE_ATTRIBUTE_STANDARD_DISPLAY_NAME,
                    Gio.FILE_ATTRIBUTE_STANDARD_SYMBOLIC_ICON,
                    Gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE,
                )
            ),
            Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS,
        )

        any_items = False
        while file_info := enumerator.next_file():
            basename = file_info.get_name()

            if (not (child := gfile.get_child(basename))) or (
                not (display_name := file_info.get_display_name())
            ):
                continue

            content_type = file_info.get_content_type()

            if content_type == "inode/directory":
                # Nested templates
                new_page = Adw.NavigationPage(title=display_name)
                new_page.set_child(toolbar_view := Adw.ToolbarView())
                toolbar_view.add_top_bar(Adw.HeaderBar())
                toolbar_view.set_content(page := Adw.PreferencesPage())
                page.add(child_group := Adw.PreferencesGroup())

                row = Adw.ActionRow(title=display_name, activatable=True)
                row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
                row.connect("activated", lambda *_: self.navigation_view.push(new_page))
                group.add(row)

                self.__get_template_children(child, child_group)

                any_items = True
                continue

            if gicon := file_info.get_symbolic_icon():
                gicon = get_symbolic(gicon)

            row = Adw.ActionRow(title=display_name, activatable=True)
            row.connect(
                "activated",
                self.__file_selected,
                content_type,
                gicon,
                display_name,
                child,
            )

            if content_type and gicon:
                row.add_prefix(
                    image := Gtk.Image(
                        gicon=gicon,
                        valign=Gtk.Align.CENTER,
                        margin_top=9,
                        margin_bottom=9,
                    )
                )

                color = get_color_for_symbolic(content_type, gicon)

                image.add_css_class(color + "-icon")
                image.add_css_class(color + "-background")
                image.add_css_class("circular-icon")

            row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))

            group.add(row)
            any_items = True

        return any_items

    def __open_templates(self, *_args: Any) -> None:
        self.close()
        self.get_transient_for().new_page(self.templates_dir)

    def __copy_active_gfile(self, *_args: Any) -> None:
        if not self.can_create:
            return

        self.close()

        buffer = self.name_text_view.get_buffer()

        if not (
            text := buffer.get_text(
                buffer.get_start_iter(), buffer.get_end_iter(), False
            ).strip()
        ):
            logging.warning("No file name provided for template")
            return

        try:
            child = self.dst.get_child_for_display_name(text)
        except GLib.Error as error:
            logging.error("Cannot create template file: %s", error)
            return

        self.active_gfile.copy_async(
            child, Gio.FileCopyFlags.NONE, GLib.PRIORITY_DEFAULT
        )

    def __file_selected(
        self,
        _row: Adw.ActionRow,
        content_type: Optional[str],
        gicon: Optional[Gio.Icon],
        display_name: str,
        gfile: Gio.File,
    ) -> None:
        self.active_gfile = gfile

        if content_type and gicon:
            self.icon_bin.set_child(
                image := Gtk.Image(
                    icon_size=Gtk.IconSize.LARGE, gicon=gicon, valign=Gtk.Align.CENTER
                )
            )

            color = get_color_for_symbolic(content_type, gicon)

            image.add_css_class(color + "-icon")
            image.add_css_class(color + "-background")
            image.add_css_class("circular-icon")
        else:
            self.icon_bin.set_child(None)

        buffer = self.name_text_view.get_buffer()
        buffer.set_text(display_name)

        self.navigation_view.push(self.name_page)

        start = buffer.get_start_iter()
        end = buffer.get_iter_at_offset(
            len(display_name)
            if content_type in DOT_IS_NOT_EXTENSION
            else len(Path(display_name).stem)
        )

        buffer.select_range(start, end)

    def __text_changed(self, buffer: Gtk.TextBuffer) -> None:
        text = buffer.get_text(
            buffer.get_start_iter(), buffer.get_end_iter(), False
        ).strip()

        if not text:
            self.can_create = False
            self.create_button.set_sensitive(False)
            self.warning_revealer.set_reveal_child(False)
            return

        self.can_create, message = validate_name(self.dst, text)
        self.create_button.set_sensitive(self.can_create)
        self.warning_revealer.set_reveal_child(bool(message))
        if message:
            self.warning_revealer_label.set_label(message)
