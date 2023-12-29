# filemanager_dbus.py
#
# Copyright 2023 Benedek Dévényi
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


"""https://www.freedesktop.org/wiki/Specifications/file-manager-interface/"""
from __future__ import annotations

from gi.repository import Gio, GLib

from hyperplane import shared
from hyperplane.properties import HypPropertiesWindow

INTROSPECTION = """
<node xmlns:doc="http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
  <interface name="org.freedesktop.DBus.Introspectable">
    <method name="Introspect">
      <arg name="data" direction="out" type="s"/>
    </method>
  </interface>
  <interface name='org.freedesktop.FileManager1'>
    <method name='ShowFolders'>
      <arg type='as' name='URIs' direction='in'/>
      <arg type='s' name='StartupId' direction='in'/>
    </method>
    <method name='ShowItems'>
      <arg type='as' name='URIs' direction='in'/>
      <arg type='s' name='StartupId' direction='in'/>
    </method>
    <method name='ShowItemProperties'>
      <arg type='as' name='URIs' direction='in'/>
      <arg type='s' name='StartupId' direction='in'/>
    </method>
  </interface>
</node>
"""


NAME = "org.freedesktop.FileManager1"
PATH = "/org/freedesktop/FileManager1"


class FileManagerDBusServer:
    """https://www.freedesktop.org/wiki/Specifications/file-manager-interface/"""

    def __init__(self) -> None:
        connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        Gio.bus_own_name_on_connection(
            connection, NAME, Gio.BusNameOwnerFlags.NONE, None, None
        )

        for interface in Gio.DBusNodeInfo.new_for_xml(INTROSPECTION).interfaces:
            try:
                connection.register_object(
                    object_path=PATH,
                    interface_info=interface,
                    method_call_closure=self.__on_method_call,
                )
            except Exception:  # pylint: disable=broad-exception-caught
                #  Another instance already exported at /org/freedesktop/FileManager1
                ...

    def __on_method_call(
        self,
        _connection: Gio.DBusConnection,
        _sender: str,
        _object_path: str,
        interface_name: str,
        method_name: str,
        parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        args = tuple(parameters.unpack())

        match method_name:
            case "ShowFolders":
                gfiles = tuple(Gio.File.new_for_uri(uri) for uri in args[0])

                for gfile in gfiles:
                    shared.app.do_activate(gfile)

            case "ShowItems":
                gfiles = tuple(Gio.File.new_for_uri(uri) for uri in args[0])

                for gfile in gfiles:
                    if not (parent := gfile.get_parent()):
                        continue

                    win = shared.app.do_activate(parent)
                    win.select_uri = gfile.get_uri()

            case "ShowItemProperties":
                gfiles = tuple(Gio.File.new_for_uri(uri) for uri in args[0])

                for gfile in gfiles:
                    if not (parent := gfile.get_parent()):
                        continue

                    win = shared.app.do_activate(parent)

                    properties = HypPropertiesWindow(gfile)
                    properties.set_transient_for(win)
                    properties.present()

            case "Introspect":
                variant = GLib.Variant("(s)", (INTROSPECTION,))
                invocation.return_value(variant)
                return

            case _:
                invocation.return_dbus_error(
                    f"{interface_name}.Error.NotSupported",
                    "Unsupported property",
                )

        invocation.return_value(None)
