# volumes_box.py
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

"""
A self-updating `GtkListBox` (wrapped in an `AdwBin`) of mountable volumes.

To be used in a sidebar.
"""
import logging
from typing import Any, Optional

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from hyperplane import shared
from hyperplane.editable_row import HypEditableRow
from hyperplane.navigation_bin import HypNavigationBin


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/volumes-box.ui")
class HypVolumesBox(Adw.Bin):
    """
    A self-updating `GtkListBox` (wrapped in an `AdwBin`) of mountable volumes.

    To be used in a sidebar.
    """

    __gtype_name__ = "HypVolumesBox"

    list_box: Gtk.ListBox = Gtk.Template.Child()
    right_click_menu: Gtk.PopoverMenu = Gtk.Template.Child()

    volume_monitor = Gio.VolumeMonitor.get()

    _visible_rows: int
    _has_any: bool

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.visible_rows = 0
        self.has_any = False

        self.actions = {}
        self.rows = {}
        self.build()

        self.volume_monitor.connect("volume-changed", self.__volume_changed)
        self.volume_monitor.connect(
            "volume-added", lambda _monitor, volume: self.add_volume(volume)
        )
        self.volume_monitor.connect(
            "volume-removed", lambda _monitor, volume: self.remove_volume(volume)
        )

        self.list_box.connect("row-activated", lambda _box, row: self.actions[row]())

    def build(self) -> None:
        """(Re)builds the sidebar. This is called automatically on `__init__`."""
        self.list_box.remove_all()

        for volume in self.volume_monitor.get_volumes():
            self.add_volume(volume)

    def add_volume(self, volume: Gio.Volume) -> None:
        """
        Adds `volume` to the sidebar.

        This is done automatically for any new volumes
        so in most cases, calling this should not be necessary.
        """

        row = HypEditableRow(
            identifier=f"volume_{volume.get_identifier(Gio.VOLUME_IDENTIFIER_KIND_UUID)}"
        )

        def set_visible_rows(row: HypEditableRow, *_args: Any) -> None:
            # Add 1 if the widget is visible, subtract 1 otherwise
            self.visible_rows += 2 * int(row.get_visible()) - 1

        self.visible_rows += row.get_visible()
        row.connect("notify::visible", set_visible_rows)

        row.title = volume.get_name()
        row.image.set_from_gicon(volume.get_symbolic_icon())

        if volume.can_eject():
            eject_button = Gtk.Button(
                icon_name="media-eject-symbolic", valign=Gtk.Align.CENTER
            )
            eject_button.add_css_class("flat")
            eject_button.add_css_class("sidebar-button")

            def eject_with_operation_finish(
                volume: Gio.Volume, result: Gio.AsyncResult
            ) -> None:
                try:
                    volume.eject_with_operation_finish(result)
                except GLib.Error as error:
                    logging.error('Unable to eject "%s": %s', volume.get_name(), error)
                    return

            def do_eject(volume: Gio.Volume) -> None:
                volume.eject_with_operation(
                    Gio.MountUnmountFlags.NONE,
                    Gtk.MountOperation.new(),
                    callback=eject_with_operation_finish,
                )

            def eject() -> None:
                # TODO: This sucks so much

                if not (mount := volume.get_mount()):
                    return

                location = mount.get_default_location()

                # What if you wanted to itertools.chain but Alice said:
                # Return Value
                # Type: GtkSelectionModel
                store = Gio.ListStore.new(Gtk.SelectionModel)
                for model in (
                    window.tab_view.get_pages() for window in shared.app.get_windows()
                ):
                    store.append(model)
                tabs = Gtk.FlattenListModel.new(store)

                tab_index = 0
                while tab := tabs.get_item(tab_index):
                    nav_bin = tab.get_child()
                    stack = nav_bin.view.get_navigation_stack()

                    # This nesting is hell.
                    nav_index = 0
                    while page := stack.get_item(nav_index):
                        nav_index += 1
                        if not page.gfile:
                            continue

                        if not (
                            location.get_relative_path(page.gfile)
                            or location.get_uri() == page.gfile.get_uri()
                        ):
                            continue

                        tab_view = page.get_root().tab_view

                        tab_view.insert(
                            navigation_bin := HypNavigationBin(shared.home),
                            tab_view.get_page_position(tab),
                        ).set_title(navigation_bin.view.get_visible_page().get_title())
                        tab_view.close_page(tab)
                        break

                    tab_index += 1

                    # Why the fuck does this work but not timeout_add on the
                    # fucking method itself?????????

                    # Add half a second of delay to make sure all fds are closed by Hyperplane
                    GLib.timeout_add(500, do_eject, volume)

            eject_button.connect("clicked", lambda *_: eject())

            row.box.insert_child_after(eject_button, row.label)

        self.rows[volume] = row
        self.__volume_changed(None, volume)

        (right_click := Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)).connect(
            "pressed", self.__right_click, volume
        )

        (middle_click := Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)).connect(
            "pressed", self.__middle_click, volume
        )

        row.add_controller(right_click)
        row.add_controller(middle_click)

        (self.list_box.prepend if volume.can_eject() else self.list_box.append)(row)

    def remove_volume(self, volume: Gio.Volume) -> None:
        """
        Removes `volume` from the sidebar.

        This is done automatically for any removed volumes
        so in most cases, calling this should not be necessary.
        """

        # If the row is not in the sidebar
        if not (row := self.rows.get(volume)):
            return

        self.visible_rows -= int(row.get_visible())

        self.list_box.remove(row)
        self.actions.pop(row)

    @property
    def visible_rows(self) -> int:
        """
        The number of rows currently visible.

        This is used for showing/hiding the separator via `has-any`.
        """
        return self._visible_rows

    @visible_rows.setter
    def visible_rows(self, n: int) -> None:
        self._visible_rows = n
        self.has_any = bool(self.visible_rows)

    @GObject.Property(type=bool, default=False)
    def has_any(self) -> str:
        """Whether the row is actually editable."""
        return self._has_any

    @has_any.setter
    def set_has_any(self, has_any: bool) -> None:
        self._has_any = has_any

    def __right_click(
        self,
        gesture: Gtk.GestureClick,
        _n: int,
        x: float,
        y: float,
        volume: Gio.Volume,
    ) -> None:
        # Mount if not mounted
        # TODO: Maybe it should still display the menu afterwards
        # instead of opening the drive
        if not (mount := volume.get_mount()):
            self.actions[self.rows[volume]]()
            return

        shared.right_clicked_file = mount.get_default_location()

        self.right_click_menu.unparent()
        self.right_click_menu.set_parent(gesture.get_widget())
        rectangle = Gdk.Rectangle()
        rectangle.x, rectangle.y, rectangle.width, rectangle.height = x, y, 0, 0
        self.right_click_menu.set_pointing_to(rectangle)
        self.right_click_menu.popup()

    def __middle_click(
        self,
        _gesture: Gtk.GestureClick,
        _n: int,
        _x: float,
        _y: float,
        volume: Gio.Volume,
    ) -> None:
        # Mount if not mounted
        # TODO: Maybe it should still open in a new tab afterwards
        if not (mount := volume.get_mount()):
            self.actions[self.rows[volume]]()
            return

        self.get_root().new_tab(mount.get_default_location())

    def __volume_changed(
        self,
        _monitor: Optional[Gio.VolumeMonitor],
        volume: Gio.Volume,
    ) -> None:
        # If the row is not in the sidebar
        if not (row := self.rows.get(volume)):
            return

        if mount := volume.get_mount():
            self.actions[row] = lambda *_, mount=mount: self.get_root().new_page(
                mount.get_default_location()
            )
        else:
            self.actions[row] = lambda *_, volume=volume, row=row: volume.mount(
                Gio.MountMountFlags.NONE,
                Gtk.MountOperation.new(self.get_root()),
                callback=self.__mount_finish,
            )

    def __mount_finish(self, volume: Gio.Volume, result: Gio.AsyncResult) -> None:
        try:
            volume.mount_finish(result)
        except GLib.Error as error:
            if error.matches(Gio.io_error_quark(), Gio.IOErrorEnum.ALREADY_MOUNTED):
                # Try the activation root.
                # This works for MTP volumes, not sure if I should be doing it though
                if root := volume.get_activation_root():
                    self.get_root().new_page(root)
            else:
                logging.error(
                    'Unable to mount volume "%s": %s', volume.get_name(), error
                )
            return

        self.get_root().new_page(volume.get_mount().get_default_location())
