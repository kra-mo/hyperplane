# volumes_box.py
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

"""A self-updating ListBox of mountable volumes."""
from gi.repository import Adw, Gio, GObject, Gtk, Pango

from hyperplane import shared


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/volumes-box.ui")
class HypVolumesBox(Adw.Bin):
    """
    A self-updating `GtkListBox` (wrapped in an `AdwBin`) of mountable volumes.

    To be used in a sidebar.
    """

    __gtype_name__ = "HypVolumesBox"

    list_box = Gtk.Template.Child()

    volume_monitor = Gio.VolumeMonitor.get()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.actions = {}
        self.build()

        self.list_box.connect("row-activated", lambda _box, row: self.actions[row]())

    def build(self) -> None:
        """(Re)builds the sidebar. This is called automatically on `__init__`."""
        self.list_box.remove_all()

        for volume in self.volume_monitor.get_volumes():
            box = Gtk.Box(spacing=12, margin_start=6, margin_end=6)
            box.append(Gtk.Image.new_from_gicon(volume.get_symbolic_icon()))
            box.append(
                Gtk.Label(ellipsize=Pango.EllipsizeMode.END, label=volume.get_name())
            )

            row = Gtk.ListBoxRow(child=box)

            if mount := volume.get_mount():
                self.actions[row] = lambda *_, mount=mount: self.emit(
                    "open-gfile", mount.get_root()
                )
            else:
                self.actions[row] = lambda *_, volume=volume, row=row: volume.mount(
                    Gio.MountMountFlags.NONE,
                    Gtk.MountOperation.new(self.get_root()),
                    callback=self.__mount_finish,
                    user_data=row,
                )

            self.list_box.append(row)

    @GObject.Signal(name="open-gfile")
    def open_gfile(self, _gfile: Gio.File) -> None:
        """Signals to the main window that it should open `gfile`."""

    def __mount_finish(
        self,
        volume: Gio.Volume,
        _result: Gio.AsyncResult,
        row: Gtk.ListBoxRow,
    ) -> None:
        # TODO: I have no idea how PyGObject handles errors here
        # https://docs.gtk.org/gio/method.Volume.mount_finish.html

        self.emit("open-gfile", gfile := volume.get_mount().get_root())

        # Make clicking the row open the mount instead of tyring to mount again
        self.actions[row] = (lambda *_: self.emit("open-gfile", gfile),)
