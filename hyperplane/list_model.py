# list_model.py
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

from typing import Any, Optional, Type

from gi.repository import Gio, GObject, Gtk

from hyperplane.utils.iterplane import iterplane


class HypListModel(GObject.Object, Gio.ListModel):
    __gtype_name__: "HypListModel"

    def __init__(
        self,
        attributes: Optional[str] = None,
        gfile: Optional[Gio.File] = None,
        tags: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.lists = []
        self.gfiles = []
        self.infos = {}

        if gfile:
            self.lists.append(Gtk.DirectoryList.new(attributes))
            self.gfiles = [gfile]
        else:
            self.gfiles = tuple(
                Gio.File.new_for_path(str(path)) for path in iterplane(tags)
            )

            for _path in self.gfiles:
                self.lists.append(Gtk.DirectoryList.new(attributes))

        self.list_store = Gio.ListStore.new(self.lists[-1].get_item_type())
        self.list_store.connect("items-changed", self.__items_changed)

        for index, dir_list in enumerate(self.lists):
            self.infos[dir_list] = set()
            dir_list.connect("notify::loading", self.__loading)
            dir_list.connect("notify::error", self.__error)
            dir_list.set_file(self.gfiles[index])

    def __error(self, *args):
        print(*args)

    def __loading(self, dir_list, *_args) -> None:
        if dir_list.is_loading():
            return

        for info in self.infos[dir_list]:
            self.list_store.remove(self.list_store.find(info)[1])

        infos = set()

        pos = 0
        while item := dir_list.get_item(pos):
            self.list_store.append(item)
            infos.add(item)
            pos += 1

        self.infos[dir_list] = infos

    def set_monitored(self, *args) -> None:
        for dir_list in self.lists:
            dir_list.set_monitored(*args)

    def __items_changed(self, *args) -> None:
        self.items_changed(*args[1:])

    def do_get_item(self, *args) -> Optional[GObject.Object]:
        """Get the item at position."""
        return self.list_store.get_item(*args)

    def do_get_item_type(self, *args) -> Type:
        """Gets the type of the items in list."""
        return self.list_store.get_item_type(*args)

    def do_get_n_items(self, *args) -> int:
        """Gets the number of items in list."""
        return self.list_store.get_n_items(*args)
