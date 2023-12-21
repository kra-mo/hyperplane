# properties.py
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

"""The item properties window."""
from stat import S_IEXEC
from typing import Any

from gi.repository import Adw, Gio, GLib, Gtk, Pango

from hyperplane import shared
from hyperplane.utils.files import get_gfile_path
from hyperplane.utils.get_color_for_content_type import get_color_for_content_type


class HypPropertiesWindow(Adw.Window):
    """The item properties window."""

    def __init__(self, gfile: Gio.File, **kwargs) -> None:
        super().__init__(default_width=480, modal=True, title=_("Properties"), **kwargs)

        self.add_controller(shortcut_controller := Gtk.ShortcutController())
        shortcut_controller.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("Escape"),
                Gtk.CallbackAction.new(lambda *_: self.close()),
            )
        )

        attributes = {
            # Basic info
            Gio.FILE_ATTRIBUTE_STANDARD_DISPLAY_NAME,
            Gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE,
            Gio.FILE_ATTRIBUTE_STANDARD_SYMBOLIC_ICON,
            Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH,
            Gio.FILE_ATTRIBUTE_STANDARD_SIZE,
            Gio.FILE_ATTRIBUTE_STANDARD_TYPE,
            # History
            Gio.FILE_ATTRIBUTE_TIME_ACCESS,
            Gio.FILE_ATTRIBUTE_TIME_MODIFIED,
            Gio.FILE_ATTRIBUTE_TIME_CREATED,
            # Permissions
            Gio.FILE_ATTRIBUTE_OWNER_USER,
            Gio.FILE_ATTRIBUTE_OWNER_GROUP,
            Gio.FILE_ATTRIBUTE_ACCESS_CAN_READ,
            Gio.FILE_ATTRIBUTE_ACCESS_CAN_WRITE,
            Gio.FILE_ATTRIBUTE_ACCESS_CAN_EXECUTE,
            Gio.FILE_ATTRIBUTE_SELINUX_CONTEXT,
        }

        file_info = gfile.query_info(",".join(attributes), Gio.FileQueryInfoFlags.NONE)

        # fmt: off
        display_name = file_info.get_display_name()
        content_type = file_info.get_content_type()
        gicon = file_info.get_symbolic_icon()
        thumbnail_path = file_info.get_attribute_byte_string(Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH)
        size = file_info.get_size()
        file_type = file_info.get_file_type()
        access = file_info.get_access_date_time()
        modified = file_info.get_modification_date_time()
        created = file_info.get_creation_date_time()
        owner = file_info.get_attribute_string(Gio.FILE_ATTRIBUTE_OWNER_USER)
        group = file_info.get_attribute_as_string(Gio.FILE_ATTRIBUTE_OWNER_GROUP)
        can_read = file_info.get_attribute_as_string(Gio.FILE_ATTRIBUTE_ACCESS_CAN_READ)
        can_write = file_info.get_attribute_as_string(Gio.FILE_ATTRIBUTE_ACCESS_CAN_WRITE)
        can_execute = file_info.get_attribute_as_string(Gio.FILE_ATTRIBUTE_ACCESS_CAN_EXECUTE)
        security_context = file_info.get_attribute_as_string(Gio.FILE_ATTRIBUTE_SELINUX_CONTEXT)
        # fmt: on

        page = Adw.PreferencesPage()
        page.add_css_class("properties-page")
        toolbar_view = Adw.ToolbarView(content=page)
        toolbar_view.add_top_bar(Adw.HeaderBar(show_title=False))
        navigation_view = Adw.NavigationView()
        navigation_view.add(Adw.NavigationPage.new(toolbar_view, _("Properties")))

        self.set_content(navigation_view)

        # Stop threads after the window is closed
        self.stop = False
        self.connect("close-request", self.__stop)

        if gicon or thumbnail_path:
            page.add(icon_group := Adw.PreferencesGroup())

            if thumbnail_path:
                picture = Gtk.Picture.new_for_filename(thumbnail_path)
                picture.set_content_fit(Gtk.ContentFit.COVER)
                picture.add_css_class("item-thumbnail")
                picture.add_css_class("thumbnail-picture")
                picture.add_css_class("gray-background")

                icon_group.add(
                    Adw.Clamp(
                        child=Adw.Clamp(child=picture, maximum_size=150),
                        maximum_size=120,
                        orientation=Gtk.Orientation.VERTICAL,
                    )
                )

            elif gicon:
                icon_group.add(image := Gtk.Image(gicon=gicon, halign=Gtk.Align.CENTER))
                image.set_icon_size(Gtk.IconSize.LARGE)

                color = get_color_for_content_type(content_type, gicon)

                image.add_css_class(color + "-icon")
                image.add_css_class(color + "-background")
                image.add_css_class("circular-icon")

            if display_name or content_type or size:
                if display_name:
                    page.add(title_group := Adw.PreferencesGroup())
                    title_group.add(
                        label := Gtk.Label(
                            justify=Gtk.Justification.CENTER,
                            wrap=True,
                            wrap_mode=Pango.WrapMode.WORD_CHAR,
                            ellipsize=Pango.EllipsizeMode.END,
                            lines=3,
                            label=display_name,
                        )
                    )
                    label.add_css_class("title-3")

                if content_type and not file_type == Gio.FileType.DIRECTORY:
                    title_group.add(
                        Gtk.Label(
                            justify=Gtk.Justification.CENTER,
                            ellipsize=Pango.EllipsizeMode.END,
                            margin_top=6,
                            label=Gio.content_type_get_description(content_type),
                        )
                    )

                if size and not file_type == Gio.FileType.DIRECTORY:
                    title_group.add(
                        Gtk.Label(
                            justify=Gtk.Justification.CENTER,
                            ellipsize=Pango.EllipsizeMode.END,
                            margin_top=6,
                            label=GLib.format_size(size),
                        )
                    )

                elif file_type == Gio.FileType.DIRECTORY:
                    folder_size_box = Gtk.Box(
                        margin_top=6, spacing=6, halign=Gtk.Align.CENTER
                    )
                    folder_size_box.append(
                        folder_size_label := Gtk.Label(
                            justify=Gtk.Justification.CENTER,
                            ellipsize=Pango.EllipsizeMode.END,
                            label=_("Empty Folder"),
                        )
                    )
                    folder_size_box.append(
                        folder_size_spinner := Gtk.Spinner(valign=Gtk.Align.BASELINE)
                    )
                    title_group.add(folder_size_box)

                    size = 0

                    def add_to_size(enumerator, enumerator_gfile) -> None:
                        nonlocal size

                        if self.stop:
                            return

                        while file_info := enumerator.next_file():
                            basename = file_info.get_name()

                            child_gfile = enumerator_gfile.get_child(basename)

                            if file_info.get_file_type() == Gio.FileType.DIRECTORY:
                                try:
                                    child_enumerator = child_gfile.enumerate_children(
                                        ",".join(
                                            (
                                                Gio.FILE_ATTRIBUTE_STANDARD_NAME,
                                                Gio.FILE_ATTRIBUTE_STANDARD_SIZE,
                                                Gio.FILE_ATTRIBUTE_STANDARD_TYPE,
                                            )
                                        ),
                                        Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS,
                                    )
                                except GLib.Error:
                                    pass
                                else:
                                    add_to_size(child_enumerator, child_gfile)

                            if not (next_size := file_info.get_size()):
                                continue

                            size += next_size

                            GLib.idle_add(
                                folder_size_label.set_label, GLib.format_size(size)
                            )

                    try:
                        enumerator = gfile.enumerate_children(
                            ",".join(
                                (
                                    Gio.FILE_ATTRIBUTE_STANDARD_NAME,
                                    Gio.FILE_ATTRIBUTE_STANDARD_SIZE,
                                    Gio.FILE_ATTRIBUTE_STANDARD_TYPE,
                                )
                            ),
                            Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS,
                        )
                    except GLib.Error:
                        pass
                    else:

                        def stop_loading(thread: GLib.Thread):
                            nonlocal folder_size_spinner
                            thread.join()
                            folder_size_spinner.stop()
                            folder_size_spinner.set_visible(False)

                        # The way I'm doing this is slow but at least
                        # I don't reach the file descriptor limit
                        folder_size_spinner.start()
                        GLib.Thread.new(
                            None,
                            stop_loading,
                            GLib.Thread.new(None, add_to_size, enumerator, gfile),
                        )

            if gfile.get_uri() == "trash:///":
                page.add(trash_group := Adw.PreferencesGroup())

                trash_group.add(
                    trash_items_row := Adw.ActionRow(
                        title=_("Items"), subtitle=str(shared.trash_list.get_n_items())
                    )
                )
                trash_items_row.add_css_class("property")
                trash_items_row.set_subtitle_selectable(True)

            if access or modified or created:
                page.add(history_group := Adw.PreferencesGroup())

                for date, title in {
                    access: _("Accessed"),
                    modified: _("Modified"),
                    created: _("Created"),
                }.items():
                    if date:
                        access_row = Adw.ActionRow(
                            title=title,
                            subtitle=access.format(r"%c"),
                            subtitle_selectable=True,
                        )
                        access_row.add_css_class("property")
                        history_group.add(access_row)

            can_be_executable = content_type and Gio.content_type_can_be_executable(
                content_type
            )

            if can_be_executable or owner or group or security_context:
                page.add(permission_group := Adw.PreferencesGroup())

                if owner or group or security_context:

                    def permission_row_activated(*_args: Any) -> None:
                        permissions_page = Adw.PreferencesPage()
                        if owner:
                            permissions_page.add(user_group := Adw.PreferencesGroup())
                            user_group.add(owner_row := Adw.ActionRow(title=_("Owner")))
                            owner_row.add_suffix(Gtk.Label.new(owner))

                            if owner == GLib.get_user_name():
                                user_group.add(
                                    access_row := Adw.ActionRow(title=_("Access"))
                                )
                                access_row.add_suffix(
                                    Gtk.Label.new(
                                        _("Read and write")
                                        if can_read and can_write
                                        else _("Read-only")
                                        if can_read
                                        else _("None")
                                    )
                                )
                        if group:
                            permissions_page.add(group_group := Adw.PreferencesGroup())
                            group_group.add(
                                group_row := Adw.ActionRow(title=_("Group"))
                            )
                            group_row.add_suffix(Gtk.Label.new(group))

                        if security_context:
                            permissions_page.add(
                                security_context_group := Adw.PreferencesGroup()
                            )
                            security_context_group.add(
                                security_context_row := Adw.ActionRow(
                                    title=_("Security Context"),
                                    subtitle=security_context,
                                    subtitle_selectable=True,
                                )
                            )
                            security_context_row.add_css_class("property")

                        permissions_toolbar_view = Adw.ToolbarView(
                            content=permissions_page
                        )
                        permissions_toolbar_view.add_top_bar(Adw.HeaderBar())
                        navigation_view.push(
                            Adw.NavigationPage.new(
                                permissions_toolbar_view, _("Permissions")
                            )
                        )

                    permission_group.add(
                        permission_row := Adw.ActionRow(
                            title="Permissions", activatable=True
                        )
                    )
                    permission_row.add_suffix(
                        Gtk.Image.new_from_icon_name("go-next-symbolic")
                    )
                    permission_row.connect("activated", permission_row_activated)

                if can_be_executable:
                    permission_group.add(
                        exec_row := Adw.SwitchRow(title=_("Executable as Program"))
                    )

                    # IF the active property was changed by the app.
                    # This is to avoid an infinite loop.
                    my_change = False

                    def set_executable(*_args: Any) -> None:
                        nonlocal my_change

                        if my_change:
                            my_change = False
                            return

                        try:
                            path = get_gfile_path(gfile)
                            path.chmod(path.stat().st_mode ^ S_IEXEC)
                        except (FileNotFoundError, OSError):
                            my_change = True
                            exec_row.set_active(not exec_row.get_active())

                    exec_row.set_active(can_execute == "TRUE")
                    exec_row.connect("notify::active", set_executable)

    def __stop(self, *_args: Any) -> None:
        self.stop = True
