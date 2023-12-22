# item.py
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

"""An item represeting a file to be set up thorugh a `GtkSignalListItemFactory`."""
from pathlib import Path
from typing import Any, Optional

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk
from gi.repository.GLib import idle_add

from hyperplane import shared
from hyperplane.file_properties import DOT_IS_NOT_EXTENSION
from hyperplane.utils.get_color_for_content_type import get_color_for_content_type
from hyperplane.utils.thumbnail import generate_thumbnail


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/item.ui")
class HypItem(Adw.Bin):
    """An item represeting a file to be set up thorugh a `GtkSignalListItemFactory`."""

    __gtype_name__ = "HypItem"

    clamp: Adw.Clamp = Gtk.Template.Child()
    box: Gtk.Box = Gtk.Template.Child()
    label: Gtk.Label = Gtk.Template.Child()

    thumbnail: Gtk.Overlay = Gtk.Template.Child()
    icon: Gtk.Image = Gtk.Template.Child()
    extension_label: Gtk.Label = Gtk.Template.Child()
    picture: Gtk.Picture = Gtk.Template.Child()
    play_button: Gtk.Box = Gtk.Template.Child()
    play_button_icon: Gtk.Image = Gtk.Template.Child()

    dir_thumbnails: Gtk.Box = Gtk.Template.Child()
    dir_thumbnail_1: Gtk.Box = Gtk.Template.Child()
    dir_thumbnail_2: Gtk.Box = Gtk.Template.Child()
    dir_thumbnail_3: Gtk.Box = Gtk.Template.Child()
    dir_picture_1: Gtk.Picture = Gtk.Template.Child()
    dir_picture_2: Gtk.Picture = Gtk.Template.Child()
    dir_picture_3: Gtk.Picture = Gtk.Template.Child()

    item: Gtk.ListItem
    page: Adw.NavigationPage
    file_info: Gio.FileInfo

    gfile: Gio.File
    is_dir: bool
    content_type: str
    extension: str
    color: str
    edit_name: str

    _gicon: str
    _display_name: str
    _extension: str
    _thumbnail_paintable: Gdk.Paintable

    def __init__(self, item, page, **kwargs) -> None:
        super().__init__(**kwargs)
        self.item = item
        self.page = page

        self.__zoom(None, shared.state_schema.get_uint("zoom-level"))
        shared.postmaster.connect("zoom", self.__zoom)

        right_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right_click.connect("pressed", self.__right_click)
        self.add_controller(right_click)

        middle_click = Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)
        middle_click.connect("pressed", self.__middle_click)
        self.add_controller(middle_click)

        self.thumb_init_classes = self.thumbnail.get_css_classes()
        self.icon_init_classes = self.icon.get_css_classes()
        self.ext_init_classes = self.extension_label.get_css_classes()
        self.dir_thumb_init_classes = self.dir_thumbnail_1.get_css_classes()
        self.dir_icon_init_classes = self.dir_thumbnail_1.get_child().get_css_classes()

    def bind(self) -> None:
        """Build the icon after the object has been bound."""
        self.file_info = self.item.get_item()

        self.gfile = self.file_info.get_attribute_object("standard::file")
        gicon = self.file_info.get_symbolic_icon()

        for icon_name in gicon.get_names():
            if icon_name.endswith("-symbolic") and icon_name in shared.icon_names:
                break
        else:
            gicon = Gio.Icon.new_for_string("text-x-generic-symbolic")

        self.gicon = gicon
        self.content_type = self.file_info.get_content_type()
        self.color = get_color_for_content_type(self.content_type, self.gicon)
        self.edit_name = self.file_info.get_edit_name()

        self.is_dir = self.content_type == "inode/directory"
        display_name = self.file_info.get_display_name()
        if self.is_dir:
            self.display_name = display_name
            self.extension = None
            idle_add(self.picture.set_content_fit, Gtk.ContentFit.FILL)

            self.gfile.enumerate_children_async(
                ",".join(
                    (
                        Gio.FILE_ATTRIBUTE_STANDARD_SYMBOLIC_ICON,
                        Gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE,
                        Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH,
                        Gio.FILE_ATTRIBUTE_STANDARD_NAME,
                    )
                ),
                Gio.FileQueryInfoFlags.NONE,
                GLib.PRIORITY_DEFAULT,
                None,
                self.__dir_children_cb,
            )

        else:
            # Blacklist some MIME types from getting extension badges
            if self.content_type in DOT_IS_NOT_EXTENSION:
                self.display_name = display_name
                self.extension = None
            else:
                self.display_name = Path(display_name).stem
                self.extension = Path(display_name).suffix[1:].upper()
            idle_add(self.picture.set_content_fit, Gtk.ContentFit.COVER)

            if thumbnail_path := self.file_info.get_attribute_byte_string(
                Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH
            ):
                try:
                    texture = Gdk.Texture.new_from_filename(thumbnail_path)
                except GLib.Error:
                    texture = None

                self.__thumbnail_cb(texture)
            elif (
                self.file_info.get_attribute_uint32(
                    Gio.FILE_ATTRIBUTE_FILESYSTEM_USE_PREVIEW
                )
                != Gio.FilesystemPreviewType.NEVER
            ):
                generate_thumbnail(self.gfile, self.content_type, self.__thumbnail_cb)
            else:
                self.__thumbnail_cb()

        idle_add(self.extension_label.set_visible, bool(self.extension))

    def unbind(self) -> None:
        """Cleanup after the object has been unbound from its item."""
        return

    def __dir_children_cb(self, gfile: Gio.File, result: Gio.Task) -> None:
        try:
            files = gfile.enumerate_children_finish(result)
        except GLib.Error:
            self.__thumbnail_cb(shared.closed_folder_texture)
            return

        def done(index) -> None:
            for thumbnail_index in range(1, 4):
                idle_add(
                    getattr(self, f"dir_thumbnail_{thumbnail_index}").set_visible,
                    index + 1 >= thumbnail_index,
                )

            self.__thumbnail_cb(
                shared.open_folder_texture if index else shared.closed_folder_texture
            )

        def next_files_cb(
            enumerator: Gio.FileEnumerator, result: Gio.Task, index: int
        ) -> None:
            if index == 3:
                done(index - 1)
                return

            picture = getattr(self, f"dir_picture_{index + 1}")

            try:
                files_list = enumerator.next_files_finish(result)
            except GLib.Error:
                self.__dir_thumbnail_cb(None, picture)
                done(index)
                return

            try:
                file_info = files_list[0]
            except IndexError:
                self.__dir_thumbnail_cb(None, picture)
                done(index)
                return

            if not (content_type := file_info.get_content_type()):
                self.__dir_thumbnail_cb(None, picture)
                done(index)
                return

            thumbnail = getattr(self, f"dir_thumbnail_{index + 1}")

            index += 1
            files.next_files_async(1, GLib.PRIORITY_DEFAULT, None, next_files_cb, index)

            if gicon := file_info.get_symbolic_icon():
                for icon_name in gicon.get_names():
                    if (
                        icon_name.endswith("-symbolic")
                        and icon_name in shared.icon_names
                    ):
                        break
                else:
                    gicon = Gio.Icon.new_for_string("text-x-generic-symbolic")

                idle_add(thumbnail.get_child().set_from_gicon, gicon)

            if content_type == "inode/directory":
                idle_add(
                    thumbnail.set_css_classes,
                    self.dir_thumb_init_classes
                    + ["light-blue-background", "white-icon"],
                )
                self.__dir_thumbnail_cb(None, picture)
                return

            idle_add(
                thumbnail.set_css_classes,
                self.dir_thumb_init_classes + ["white-background"],
            )

            color = get_color_for_content_type(content_type, gicon)

            idle_add(
                thumbnail.get_child().set_css_classes,
                self.dir_icon_init_classes + [f"{color}-icon-light-only"],
            )

            if thumbnail_path := file_info.get_attribute_byte_string(
                Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH
            ):
                self.__dir_thumbnail_cb(
                    Gdk.Texture.new_from_filename(thumbnail_path), picture
                )
                return

            # HACK: I don't know how else to get a GFile for file_info.
            # Maybe this is the proper way?
            child_gfile = gfile.get_child(file_info.get_name())

            generate_thumbnail(
                child_gfile, content_type, self.__dir_thumbnail_cb, picture
            )

        # TODO: Could be oprimized if I called next_files with 3 the first time
        files.next_files_async(1, GLib.PRIORITY_DEFAULT, None, next_files_cb, 0)

    def __dir_thumbnail_cb(
        self,
        texture: Optional[Gdk.Texture] = None,
        picture: Optional[Gtk.Picture] = None,  # This is not actually optional
    ) -> None:
        idle_add(picture.set_visible, bool(texture))

        if not texture:
            return

        idle_add(picture.set_paintable, texture)

    def __thumbnail_cb(self, texture: Optional[Gdk.Texture] = None) -> None:
        idle_add(
            self.play_button.set_visible,
            texture
            and self.content_type.split("/")[0]
            in (
                "video",
                "audio",
            ),
        )

        idle_add(self.picture.set_visible, bool(texture))
        if not self.is_dir:
            for thumbnail in (
                self.dir_thumbnail_1,
                self.dir_thumbnail_2,
                self.dir_thumbnail_3,
            ):
                idle_add(thumbnail.set_visible, False)

        if texture:
            if self.is_dir:
                idle_add(
                    self.thumbnail.set_css_classes,
                    self.thumb_init_classes + ["dark-blue-background"],
                )
            else:
                idle_add(
                    self.thumbnail.set_css_classes,
                    self.thumb_init_classes + ["gray-background"],
                )

            idle_add(
                self.extension_label.set_css_classes,
                self.ext_init_classes + [f"{self.color}-extension-thumb"],
            )
            self.thumbnail_paintable = texture
            return

        idle_add(
            self.icon.set_css_classes,
            self.icon_init_classes + [f"{self.color}-icon"],
        )
        idle_add(
            self.thumbnail.set_css_classes,
            self.thumb_init_classes + [f"{self.color}-background"],
        )
        idle_add(
            self.extension_label.set_css_classes,
            self.ext_init_classes + [f"{self.color}-extension"],
        )

    def __zoom(self, _obj: Any, zoom_level: int) -> None:
        self.clamp.set_maximum_size(50 * zoom_level)

        box_margin = zoom_level * 3
        self.box.set_margin_start(box_margin)
        self.box.set_margin_end(box_margin)
        self.box.set_margin_top(box_margin)
        self.box.set_margin_bottom(box_margin)

        play_margin = zoom_level * 2 + 8
        self.play_button_icon.set_margin_start(play_margin)
        self.play_button_icon.set_margin_end(play_margin)
        self.play_button_icon.set_margin_top(play_margin)
        self.play_button_icon.set_margin_bottom(play_margin)

        self.play_button_icon.set_pixel_size((zoom_level * 4) + 8)

        match zoom_level:
            case 1:
                # This is not the exact aspect ratio, but it is close enough.
                # It's good for keeping the folder textures sharp.
                # Or not apparently. Whether they are sharp seems really random.
                self.thumbnail.set_size_request(96, 74)
            case 2:
                self.thumbnail.set_size_request(96, 96)
            case _:
                self.thumbnail.set_size_request(40 * zoom_level, 32 * zoom_level)

        if zoom_level < 3:
            self.dir_thumbnails.set_spacing(12)
            self.dir_thumbnails.set_margin_start(10)
            self.dir_thumbnails.set_margin_top(6)
        elif zoom_level < 4:
            self.dir_thumbnails.set_spacing(6)
            self.dir_thumbnails.set_margin_start(6)
            self.dir_thumbnails.set_margin_top(6)
        elif zoom_level < 5:
            self.dir_thumbnails.set_spacing(9)
            self.dir_thumbnails.set_margin_start(8)
            self.dir_thumbnails.set_margin_top(8)
        else:
            self.dir_thumbnails.set_spacing(9)
            self.dir_thumbnails.set_margin_start(7)
            self.dir_thumbnails.set_margin_top(7)

        if zoom_level < 4:
            self.dir_thumbnail_1.set_size_request(32, 32)
            self.dir_thumbnail_2.set_size_request(32, 32)
            self.dir_thumbnail_3.set_size_request(32, 32)
        elif zoom_level < 5:
            self.dir_thumbnail_1.set_size_request(42, 42)
            self.dir_thumbnail_2.set_size_request(42, 42)
            self.dir_thumbnail_3.set_size_request(42, 42)
        else:
            self.dir_thumbnail_1.set_size_request(56, 56)
            self.dir_thumbnail_2.set_size_request(56, 56)
            self.dir_thumbnail_3.set_size_request(56, 56)

        # Pixel size is set instead of icon size because otherwise GTK gets confused
        # and it can lead to graphical glitches after zooming
        if zoom_level < 2:
            self.icon.set_pixel_size(16)
        else:
            self.icon.set_pixel_size(32)

    def __select_self(self) -> None:
        if not (
            multi_selection := self.get_parent().get_parent().get_model()
        ).is_selected(pos := self.item.get_position()):
            multi_selection.select_item(pos, True)

    def __right_click(self, *_args: Any) -> None:
        self.__select_self()

        menu_items = {"rename", "copy", "cut", "trash", "open", "open-with"}
        if self.is_dir:
            menu_items.add("open-new-tab")
            menu_items.add("open-new-window")
        if self.gfile.get_uri().startswith("trash:///"):
            menu_items.remove("trash")
            menu_items.remove("rename")
            if self.gfile.get_uri().count("/") < 4:
                menu_items.add("trash-restore")
                menu_items.add("trash-delete")

        # TODO: Ugly
        self.page.menu_items = menu_items

    def __middle_click(self, *_args: Any) -> None:
        self.__select_self()

        for gfile in self.page.get_selected_gfiles():
            self.get_root().new_tab(gfile)

    @GObject.Property(type=str)
    def display_name(self) -> str:
        """The name of the item visible to the user."""
        return self._display_name

    @display_name.setter
    def set_display_name(self, name: str) -> None:
        self._display_name = name

    @GObject.Property(type=str)
    def extension(self) -> str:
        """The extnesion of the file or None."""
        return self._extension

    @extension.setter
    def set_extension(self, extension: str) -> None:
        self._extension = extension

    @GObject.Property(type=Gio.Icon)
    def gicon(self) -> Gio.Icon:
        """The icon of the item displayed to the user if no thumbnail is available."""
        return self._gicon

    @gicon.setter
    def set_gicon(self, gicon: Gio.Icon) -> None:
        self._gicon = gicon

    @GObject.Property(type=Gdk.Paintable)
    def thumbnail_paintable(self) -> Gdk.Paintable:
        """The paintable used for the thumbnail."""
        return self._thumbnail_paintable

    @thumbnail_paintable.setter
    def set_thumbnail_paintable(self, thumbnail_paintable: Gdk.Paintable) -> None:
        self._thumbnail_paintable = thumbnail_paintable
