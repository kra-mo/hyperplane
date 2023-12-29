from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hyperplane.window import HypWindow

from gi.repository import Gio, GLib

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
    def __init__(self, window: HypWindow) -> None:
        # TODO: this way it works only from the first window
        self.window = window

        connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        Gio.bus_own_name_on_connection(connection, NAME, Gio.BusNameOwnerFlags.NONE, None, None)

        for interface in Gio.DBusNodeInfo.new_for_xml(INTROSPECTION).interfaces:
            try:
                connection.register_object(
                    object_path=PATH,
                    interface_info=interface,
                    method_call_closure=self.on_method_call,
                )
            except Exception:
                #  Another instance already exported at /org/freedesktop/FileManager1
                pass

    def on_method_call(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        method_name: str,
        parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        args = list(parameters.unpack())

        match method_name:
            case "ShowFolders":
                gfiles = [Gio.File.new_for_path(path) for path in args[0]]

                for gfile in gfiles:
                    self.window.new_window(gfile)
            case "ShowItems":
                print(args)  # TODO
            case "ShowItemProperties":
                print(args)  # TODO
            case "Introspect":
                variant = GLib.Variant("(s)", (INTROSPECTION,))
                invocation.return_value(variant)
                return
            case _:
                invocation.return_dbus_error(
                    "{}.Error.NotSupported".format(interface_name), "Unsupported property"
                )

        invocation.return_value(None)
