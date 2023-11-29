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

from pathlib import Path
from typing import Any, Optional

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from hyperplane import shared
from hyperplane.utils.get_color_for_content_type import get_color_for_content_type
from hyperplane.utils.thumbnail import generate_thumbnail


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/item.ui")
class HypItem(Adw.Bin):
    __gtype_name__ = "HypItem"

    clamp: Adw.Clamp = Gtk.Template.Child()
    box: Gtk.Box = Gtk.Template.Child()
    label: Gtk.Label = Gtk.Template.Child()

    thumbnail: Gtk.Overlay = Gtk.Template.Child()
    icon: Gtk.Image = Gtk.Template.Child()
    extension_label: Gtk.Label = Gtk.Template.Child()
    picture: Gtk.Picture = Gtk.Template.Child()
    play_button: Gtk.Box = Gtk.Template.Child()

    dir_thumbnails: Gtk.Box = Gtk.Template.Child()
    dir_thumbnail_1: Gtk.Box = Gtk.Template.Child()
    dir_thumbnail_2: Gtk.Box = Gtk.Template.Child()
    dir_thumbnail_3: Gtk.Box = Gtk.Template.Child()

    item: Gtk.ListItem
    file_info: Gio.FileInfo

    path: Path
    gfile: Gio.File
    content_type: str
    color: str
    thumbnail_path: str

    _gicon: str
    _name: str

    def __init__(self, item, **kwargs) -> None:
        super().__init__(**kwargs)
        self.item = item
        self.__zoom(None, shared.state_schema.get_uint("zoom-level"))
        shared.postmaster.connect("zoom", self.__zoom)

        right_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right_click.connect("pressed", self.__right_click)
        self.add_controller(right_click)

        middle_click = Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)
        middle_click.connect("pressed", self.__middle_click)
        self.add_controller(middle_click)

    def bind(self) -> None:
        """Build the icon after the object has been bound."""
        self.file_info = self.item.get_item()

        self.gfile = self.file_info.get_attribute_object("standard::file")
        self.gicon = self.file_info.get_symbolic_icon()
        self.content_type = self.file_info.get_content_type()
        self.color = get_color_for_content_type(self.content_type)
        display_name = self.file_info.get_display_name()
        self.name = (
            Path(display_name).stem
            if self.content_type != "inode/directory"  # TODO: Should I do it like this?
            else display_name
        )
        self.thumbnail_path = self.file_info.get_attribute_byte_string(
            Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH
        )

        shared.drawing += 1
        # TODO: This seems to only prioritize directories.
        # What's up with that? Does it still work for them?
        if self.get_mapped():
            self.__build()
            return

        GLib.timeout_add(shared.drawing * 2, self.__build)

    def unbind(self) -> None:
        """Cleanup after the object has been unbound from its item."""
        # TODO: Do I need this? Do I need something else?
        self.dir_thumbnail_1.set_visible(False)
        self.dir_thumbnail_2.set_visible(False)
        self.dir_thumbnail_3.set_visible(False)

        self.picture.set_content_fit(Gtk.ContentFit.COVER)

    def __build(self) -> None:
        self.path = Path(self.gfile.get_path())

        self.play_button.set_visible(False)

        if self.path.is_dir():
            self.__build_dir_thumbnail()
        else:
            self.__build_file_thumbnail()

        shared.drawing -= 1

    def __file_thumb_done(self, failed: bool) -> None:
        self.icon.set_visible(failed)
        self.picture.set_visible(not failed)

        if failed:
            self.icon.add_css_class(self.color + "-icon")
            self.thumbnail.add_css_class(self.color + "-background")
            self.extension_label.add_css_class(self.color + "-extension-thumb")
            return

        self.thumbnail.add_css_class("gray-background")
        self.extension_label.add_css_class(self.color + "-extension")

    def __build_file_thumbnail(self) -> None:
        if self.path.is_file() and (suffix := self.path.suffix):
            self.extension_label.set_label(suffix[1:].upper())
            self.extension_label.set_visible(True)
        else:
            self.extension_label.set_visible(False)

        if self.thumbnail_path:
            self.__thumb_callback(Gdk.Texture.new_from_filename(self.thumbnail_path))
            return

        GLib.Thread.new(
            None,
            generate_thumbnail,
            self.gfile,
            self.content_type,
            self.__thumb_callback,
        )

    def __build_dir_thumbnail(self) -> None:
        self.extension_label.set_visible(False)
        self.picture.set_visible(True)
        self.icon.set_visible(False)

        self.picture.set_content_fit(Gtk.ContentFit.FILL)
        self.picture.set_paintable(shared.closed_folder_texture)
        self.thumbnail.add_css_class(self.color + "-background")

        # Return if folder has no children or they can't be listed
        try:
            if not any(self.path.iterdir()):
                return
        except PermissionError:
            return

        self.picture.set_paintable(shared.open_folder_texture)

        index = 0
        for path in self.path.iterdir():
            if index == 3:
                break

            match index:
                case 0:
                    thumbnail = self.dir_thumbnail_1
                    thumbnail.set_visible(True)
                case 1:
                    thumbnail = self.dir_thumbnail_2
                    thumbnail.set_visible(True)
                case 2:
                    thumbnail = self.dir_thumbnail_3
                    thumbnail.set_visible(True)

            index += 1

            gfile = Gio.File.new_for_path(str(path))
            gfile.query_info_async(
                ",".join(
                    (
                        Gio.FILE_ATTRIBUTE_STANDARD_SYMBOLIC_ICON,
                        Gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE,
                        Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH,
                    )
                ),
                Gio.FileQueryInfoFlags.NONE,
                GLib.PRIORITY_DEFAULT,
                None,
                self.__dir_query_callback,
                thumbnail,
            )

    def __dir_thumb_callback(
        self,
        texture: Optional[Gdk.Texture] = None,
        thumbnail: Optional[Gtk.Overlay] = None,
        failed: Optional[bool] = False,
    ) -> None:
        if failed:
            return

        picture = Gtk.Picture.new_for_paintable(texture)
        picture.set_content_fit(Gtk.ContentFit.COVER)
        thumbnail.get_child().set_visible(False)
        thumbnail.add_overlay(picture)

    def __dir_query_callback(
        self, gfile: Gio.File, result: Gio.Task, thumbnail: Gtk.Overlay
    ) -> None:
        try:
            file_info = gfile.query_info_finish(result)
        except GLib.Error:
            return

        if icon := file_info.get_symbolic_icon():
            thumbnail.get_child().set_from_gicon(icon)

        if Path(gfile.get_path()).is_dir():
            thumbnail.add_css_class("light-blue-background")
            thumbnail.get_child().add_css_class("white-icon")
            return

        thumbnail.add_css_class("white-background")
        if not (content_type := file_info.get_content_type()):
            return

        color = get_color_for_content_type(content_type)
        thumbnail.get_child().add_css_class(color + "-icon-light-only")

        if thumbnail_path := file_info.get_attribute_byte_string(
            Gio.FILE_ATTRIBUTE_THUMBNAIL_PATH
        ):
            picture = Gtk.Picture.new_for_filename(thumbnail_path)
            picture.set_content_fit(Gtk.ContentFit.COVER)
            thumbnail.get_child().set_visible(False)
            thumbnail.add_overlay(picture)
            return

        GLib.Thread.new(
            None,
            generate_thumbnail,
            gfile,
            content_type,
            self.__dir_thumb_callback,
            thumbnail,
        )

    def __thumb_callback(
        self,
        texture: Optional[Gdk.Texture] = None,
        failed: Optional[bool] = False,
    ) -> None:
        if failed:
            GLib.idle_add(self.__file_thumb_done, failed)
            return
        self.__file_thumb_done(failed)

        self.picture.set_paintable(texture)

        if self.content_type.split("/")[0] not in ("video", "audio"):
            return

        self.play_button.set_visible(True)

    def __zoom(self, _obj: Any, zoom_level: int) -> None:
        self.clamp.set_maximum_size(50 * zoom_level)
        self.box.set_margin_start(4 * zoom_level)
        self.box.set_margin_end(4 * zoom_level)
        self.box.set_margin_top(4 * zoom_level)
        self.box.set_margin_bottom(4 * zoom_level)

        match zoom_level:
            case 1:
                self.thumbnail.set_size_request(96, 80)
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

        if zoom_level < 2:
            self.icon.set_pixel_size(20)
            self.icon.set_icon_size(Gtk.IconSize.INHERIT)
        else:
            self.icon.set_pixel_size(-1)
            self.icon.set_icon_size(Gtk.IconSize.LARGE)

    def __right_click(self, *_args: Any) -> None:
        if not (
            multi_selection := self.get_parent().get_parent().get_model()
        ).is_selected(pos := self.item.get_position()):
            multi_selection.select_item(pos, True)

        menu_items = {"rename", "copy", "cut", "trash", "open"}
        if self.path.is_dir():
            menu_items.add("open-new-tab")
            menu_items.add("open-new-window")

        self.get_root().set_menu_items(menu_items)

    def __middle_click(self, *_args: Any) -> None:
        # TODO: Open multiple items if multiple are selected
        self.get_parent().get_parent().get_model().select_item(
            self.item.get_position(), True
        )

        self.get_root().new_tab(path=self.path)

    @GObject.Property(type=str)
    def name(self) -> str:
        return self._name

    @name.setter
    def set_name(self, name: str) -> None:
        self._name = name

    @GObject.Property(type=Gio.Icon)
    def gicon(self) -> Gio.Icon:
        return self._gicon

    @gicon.setter
    def set_gicon(self, gicon: Gio.Icon) -> None:
        self._gicon = gicon
