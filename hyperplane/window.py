# window.py
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

from os import sep
from pathlib import Path
from time import time
from typing import Any, Callable, Iterable, Optional

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Xdp, XdpGtk4

from hyperplane import shared
from hyperplane.items_page import HypItemsPage
from hyperplane.navigation_bin import HypNavigationBin
from hyperplane.tag_row import HypTagRow
from hyperplane.utils.files import (
    copy,
    get_copy_path,
    get_gfile_display_name,
    get_gfile_path,
    move,
    restore,
    rm,
    trash_rm,
)
from hyperplane.utils.tags import add_tags, move_tag, remove_tags
from hyperplane.utils.validate_name import validate_name


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/window.ui")
class HypWindow(Adw.ApplicationWindow):
    __gtype_name__ = "HypWindow"

    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    tab_view: Adw.TabView = Gtk.Template.Child()
    toolbar_view: Adw.ToolbarView = Gtk.Template.Child()
    sidebar: Gtk.ListBox = Gtk.Template.Child()
    sidebar_home: Gtk.Box = Gtk.Template.Child()
    new_tag_box: Gtk.ListBox = Gtk.Template.Child()
    trash_box: Gtk.ListBox = Gtk.Template.Child()

    title_stack: Gtk.Stack = Gtk.Template.Child()
    window_title: Adw.WindowTitle = Gtk.Template.Child()
    path_bar_clamp: Adw.Clamp = Gtk.Template.Child()
    path_bar: Gtk.Entry = Gtk.Template.Child()
    search_entry_clamp: Adw.Clamp = Gtk.Template.Child()
    search_entry: Gtk.SearchEntry = Gtk.Template.Child()
    search_button: Gtk.ToggleButton = Gtk.Template.Child()

    rename_popover: Gtk.Popover = Gtk.Template.Child()
    rename_label: Gtk.Label = Gtk.Template.Child()
    rename_entry: Adw.EntryRow = Gtk.Template.Child()
    rename_revealer: Gtk.Revealer = Gtk.Template.Child()
    rename_revealer_label: Gtk.Label = Gtk.Template.Child()
    rename_button: Gtk.Button = Gtk.Template.Child()

    right_click_menu: Gtk.PopoverMenu = Gtk.Template.Child()
    tag_right_click_menu: Gtk.PopoverMenu = Gtk.Template.Child()

    undo_queue: dict = {}
    cut_page: Optional[HypItemsPage] = None
    path_bar_connection: int
    sidebar_items: set
    right_clicked_tag: str

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        if shared.PROFILE == "development":
            self.add_css_class("devel")

        self.tab_view.connect("page-attached", self.__page_attached)

        # Create actions

        navigation_view = HypNavigationBin(
            initial_gfile=Gio.File.new_for_path(str(shared.home))
        )
        self.tab_view.append(navigation_view).set_title(
            title := self.get_visible_page().get_title()
        )
        self.set_title(title)

        self.create_action("home", self.__go_home, ("<alt>Home",))
        self.create_action(
            "toggle-path-bar", self.__toggle_path_bar, ("F6", "<primary>l")
        )
        self.create_action("hide-path-bar", self.__hide_path_bar)
        self.create_action("close", self.__on_close_action, ("<primary>w",))
        self.create_action("search", self.__toggle_search_entry, ("<primary>f",))
        self.create_action("back", self.__on_back_action)
        self.lookup_action("back").set_enabled(False)
        self.create_action(
            "zoom-in",
            self.__on_zoom_in_action,
            ("<primary>plus", "<Primary>KP_Add", "<primary>equal"),
        )
        self.create_action(
            "zoom-out",
            self.__on_zoom_out_action,
            ("<primary>minus", "<Primary>KP_Subtract", "<Primary>underscore"),
        )
        self.create_action(
            "reset-zoom", self.__reset_zoom, ("<primary>0", "<primary>KP_0")
        )
        self.create_action("reload", self.__reload, ("<primary>r", "F5"))

        self.create_action("undo", self.__undo, ("<primary>z",))
        self.create_action("open", self.__open, ("Return", "<primary>o"))
        self.create_action("open-new-tab", self.__open_new_tab, ("<primary>Return",))
        self.create_action(
            "open-new-window", self.__open_new_window, ("<shift>Return",)
        )
        self.create_action("open-with", self.__open_with)
        self.create_action("new-folder", self.__new_folder, ("<primary><shift>n",))
        self.create_action("copy", self.__copy, ("<primary>c",))
        self.create_action("cut", self.__cut, ("<primary>x",))
        self.create_action("paste", self.__paste, ("<primary>v",))
        self.create_action("select-all", self.__select_all, ("<primary>a",))
        self.create_action("rename", self.__rename, ("F2",))
        self.create_action("trash", self.__trash, ("Delete",))
        self.create_action("trash-delete", self.__trash_delete, ("Delete",))
        self.create_action("trash-restore", self.__trash_restore)

        # TODO: This is tedious, maybe use GTK Expressions?
        self.create_action("open-tag", self.__open_tag)
        self.create_action("open-new-tab-tag", self.__open_new_tab_tag)
        self.create_action("open-new-window-tag", self.__open_new_window_tag)
        self.create_action("move-tag-up", self.__move_tag_up)
        self.create_action("move-tag-down", self.__move_tag_down)
        self.create_action("remove-tag", self.__remove_tag)

        # Connect signals

        self.sidebar.connect("row-activated", self.__row_activated)
        self.new_tag_box.connect("row-activated", self.__new_tag)
        self.trash_box.connect("row-activated", self.__open_trash)

        self.tab_view.connect("notify::selected-page", self.__tab_changed)
        self.tab_view.connect("create-window", self.__create_window)

        self.path_bar.connect("activate", self.__path_bar_activated)
        self.search_entry.connect("search-started", self.__show_search_entry)
        self.search_entry.connect("search-changed", self.__search_changed)
        self.search_entry.connect("stop-search", self.__hide_search_entry)
        self.search_entry.connect("activate", self.__search_activate)
        self.search_button.connect("clicked", self.__toggle_search_entry)

        shared.postmaster.connect("tags-changed", self.__update_tags)

        self.right_click_menu.connect("closed", self.__set_actions)

        self.__set_actions()

        # Set up search

        self.searched_page = self.get_visible_page()
        self.search_entry.set_key_capture_widget(self)

        # Build sidebar

        self.sidebar_items = set()
        self.__update_tags()

    def send_toast(self, message: str, undo: bool = False) -> None:
        """Displays a toast with the given message and optionally an undo button in the window."""
        toast = Adw.Toast.new(message)
        toast.set_priority(Adw.ToastPriority.HIGH)
        toast.set_use_markup(False)
        if undo:
            toast.set_button_label(_("Undo"))
        self.toast_overlay.add_toast(toast)

        return toast

    def new_tab(
        self, gfile: Optional[Gio.File] = None, tag: Optional[str] = None
    ) -> None:
        """Open a new path with the given path or tag."""
        if (
            gfile
            and gfile.query_file_type(Gio.FileQueryInfoFlags.NONE)
            == Gio.FileType.DIRECTORY
        ):
            navigation_view = HypNavigationBin(initial_gfile=gfile)
            self.tab_view.append(navigation_view).set_title(
                navigation_view.view.get_visible_page().get_title()
            )
        elif tag:
            navigation_view = HypNavigationBin(initial_tags=[tag])
            self.tab_view.append(navigation_view).set_title(
                navigation_view.view.get_visible_page().get_title()
            )

    def get_visible_page(self) -> HypItemsPage:
        """Return the currently visible HypItemsPage."""
        return self.tab_view.get_selected_page().get_child().view.get_visible_page()

    def update_zoom(self) -> None:
        """Update the zoom level of all items in the navigation stack"""
        shared.postmaster.emit("zoom", shared.state_schema.get_uint("zoom-level"))

    def create_action(
        self, name: str, callback: Callable, shortcuts: Optional[Iterable] = None
    ) -> None:
        """Add an application action.

        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
        """
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.get_application().set_accels_for_action(f"win.{name}", shortcuts)

    def set_menu_items(self, menu_items: Iterable[str]) -> None:
        """Disables all right-click menu items not in `menu_items`."""
        actions = {
            "rename",
            "copy",
            "cut",
            "paste",
            "trash",
            "trash-delete",
            "trash-restore",
            "new-folder",
            "select-all",
            "open",
            "open-new-tab",
            "open-new-window",
        }

        for action in actions.difference(menu_items):
            self.lookup_action(action).set_enabled(False)
        for action in menu_items:
            self.lookup_action(action).set_enabled(True)

    def get_gfiles_from_positions(self, positions: list[int]) -> list[Gio.File]:
        """Get a list of GFiles corresponding to positions in the ListModel."""
        paths = []
        multi_selection = self.get_visible_page().multi_selection

        for position in positions:
            paths.append(
                multi_selection.get_item(position).get_attribute_object(
                    "standard::file"
                )
            )

        return paths

    def get_paths_from_positions(self, positions: list[int]) -> list[Path]:
        """Get a list of file paths corresponding to positions in the ListModel."""
        paths = []
        multi_selection = self.get_visible_page().multi_selection

        for position in positions:
            try:
                path = get_gfile_path(
                    multi_selection.get_item(position).get_attribute_object(
                        "standard::file"
                    )
                )
            except FileNotFoundError:
                continue

            paths.append(path)

        return paths

    def get_selected_items(self) -> list[int]:
        """Gets the list of positions for selected items in the grid view."""
        bitset = self.get_visible_page().multi_selection.get_selection()
        not_empty, bitset_iter, position = Gtk.BitsetIter.init_first(bitset)

        if not not_empty:
            return []

        positions = [position]

        while True:
            next_val, pos = bitset_iter.next()
            if not next_val:
                break
            positions.append(pos)

        return positions

    def __update_tags(self, *_args: Any) -> None:
        for item in self.sidebar_items:
            self.sidebar.remove(item.get_parent())

        self.sidebar_items = set()

        for tag in reversed(shared.tags):
            self.sidebar_items.add(row := HypTagRow(tag, "user-bookmarks-symbolic"))
            self.sidebar.insert(row, 1)

    def __new_tag(self, *_args: Any) -> None:
        dialog = Adw.MessageDialog.new(self, _("New Category"))

        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("add", _("Add"))

        dialog.set_default_response("add")
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)

        (preferences_group := Adw.PreferencesGroup(width_request=360)).add(
            entry := Adw.EntryRow(title=_("Name"))
        )
        dialog.set_extra_child(preferences_group)

        def add_tag(*_args: Any) -> None:
            dialog.close()

            if (text := entry.get_text().strip()) in shared.tags:
                # TODO: Use a revealer and insensitivity here instead of a toast
                self.send_toast(_('A category named "{}" already exists').format(text))
                return

            # TODO: Present this to the user
            if (not text) or ("/" in text) or ("\n" in text) or (text in (".", "..")):
                return

            add_tags(text)

        def handle_response(_dialog: Adw.MessageDialog, response: str) -> None:
            if response == "add":
                add_tag()

        entry.connect("entry-activated", add_tag)
        dialog.connect("response", handle_response)
        dialog.choose()

    def __open_trash(self, *_args: Any) -> None:
        nav_bin = self.tab_view.get_selected_page().get_child()

        if self.get_visible_page().gfile.get_uri() != "trash:///":
            nav_bin.new_page(Gio.File.new_for_uri("trash://"))

    def __row_activated(self, _box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        nav_bin = self.tab_view.get_selected_page().get_child()

        if row.get_child() == self.sidebar_home:
            if self.get_visible_page().gfile.get_path() != str(shared.home):
                nav_bin.new_page(Gio.File.new_for_path(str(shared.home)))
            return

        nav_bin.new_page(tag=row.get_child().tag)

    def __tab_changed(self, *_args: Any) -> None:
        if not self.tab_view.get_selected_page():
            return

        self.set_title(self.get_visible_page().get_title())
        self.lookup_action("back").set_enabled(
            bool(
                self.tab_view.get_selected_page()
                .get_child()
                .view.get_navigation_stack()
                .get_n_items()
                - 1
            )
        )

    def __navigation_changed(self, view: Adw.NavigationView, *_args: Any) -> None:
        self.__hide_search_entry()
        view.get_visible_page().item_filter.changed(Gtk.FilterChange.LESS_STRICT)

        title = view.get_visible_page().get_title()
        if page := self.tab_view.get_page(view.get_parent()):
            page.set_title(title)

        if self.tab_view.get_selected_page() == page:
            self.set_title(title)

        self.lookup_action("back").set_enabled(
            bool(
                self.tab_view.get_selected_page()
                .get_child()
                .view.get_navigation_stack()
                .get_n_items()
                - 1
            )
        )

    def __page_attached(self, _view: Adw.TabView, page: Adw.TabPage, _pos: int) -> None:
        page.get_child().view.connect("popped", self.__navigation_changed)
        page.get_child().view.connect("pushed", self.__navigation_changed)

    def __path_bar_activated(self, entry, *_args: Any) -> None:
        text = entry.get_text().strip()
        nav_bin = self.tab_view.get_selected_page().get_child()

        if text.startswith("//"):
            self.__hide_path_bar()
            tags = list(
                tag
                for tag in shared.tags
                if tag in text.lstrip("/").rstrip("/").split("//")
            )
            if not tags:
                self.send_toast(_("No such tags"))
            if tags == self.get_visible_page().tags:
                return
            nav_bin.new_page(tags=tags)
            return

        if (path := Path(text)).is_dir():
            self.__hide_path_bar()
            if path == get_gfile_path(self.get_visible_page().gfile):
                return
            nav_bin.new_page(Gio.File.new_for_path(str(path)))
            return

        self.send_toast(_("Unable to find path"))

    def __title_stack_set_child(self, new: Gtk.Widget) -> None:
        old = self.title_stack.get_visible_child()
        if old == new:
            return

        self.title_stack.set_visible_child(new)

        match old:
            case self.search_entry_clamp:
                self.search_button.set_active(False)
                self.search_entry.set_text("")
                shared.search = ""
                self.searched_page.item_filter.changed(Gtk.FilterChange.LESS_STRICT)
            case self.path_bar_clamp:
                if self.path_bar_connection:
                    self.path_bar.disconnect(self.path_bar_connection)
                    self.path_bar_connection = None

        match new:
            case self.search_entry_clamp:
                self.search_button.set_active(True)
                self.searched_page = self.get_visible_page()

                self.set_focus(self.search_entry)
            case self.path_bar_clamp:
                if (page := self.get_visible_page()).gfile:
                    try:
                        path = get_gfile_path(page.gfile, uri_fallback=True)
                    except FileNotFoundError:
                        path = ""  # Fallback blank string
                    self.path_bar.set_text(
                        path if isinstance(path, str) else str(path) + sep
                    )
                elif page.tags:
                    self.path_bar.set_text("//" + "//".join(page.tags) + "//")

                self.set_focus(self.path_bar)
                self.path_bar.select_region(-1, -1)

                self.path_bar_connection = self.path_bar.connect(
                    "notify::has-focus", self.__path_bar_focus
                )
            case self.window_title:
                # HACK: Keep track of the last focused item and scroll to that instead
                self.set_focus(grid_view := self.get_visible_page().grid_view)
                grid_view.scroll_to(0, Gtk.ListScrollFlags.FOCUS)

    def __toggle_search_entry(self, *_args: Any) -> None:
        if self.title_stack.get_visible_child() != self.search_entry_clamp:
            self.__show_search_entry()
            return

        self.__hide_search_entry()

    def __show_search_entry(self, *_args: Any) -> None:
        self.__title_stack_set_child(self.search_entry_clamp)

    def __hide_search_entry(self, *_args: Any) -> None:
        if self.title_stack.get_visible_child() != self.search_entry_clamp:
            return

        self.__title_stack_set_child(self.window_title)

    def __search_activate(self, *_args: Any) -> None:
        self.get_visible_page().activate(None, 0)

    def __search_changed(self, entry: Gtk.SearchEntry) -> None:
        shared.search = entry.get_text().strip()
        self.searched_page.item_filter.changed(Gtk.FilterChange.DIFFERENT)

    def __show_path_bar(self, *_args: Any) -> None:
        self.__title_stack_set_child(self.path_bar_clamp)

    def __hide_path_bar(self, *_args: Any) -> None:
        if self.title_stack.get_visible_child() != self.path_bar_clamp:
            return

        self.__title_stack_set_child(self.window_title)

    def __toggle_path_bar(self, *_args: Any) -> None:
        if self.title_stack.get_visible_child() != self.path_bar_clamp:
            self.__show_path_bar()
            return

        self.__hide_path_bar()

    def __path_bar_focus(self, entry: Gtk.Entry, *_args: Any) -> None:
        if not entry.has_focus():
            self.__hide_path_bar()

    def __go_home(self, *_args: Any) -> None:
        self.tab_view.get_selected_page().get_child().new_page(
            Gio.File.new_for_path(str(shared.home))
        )

    def __on_zoom_in_action(self, *_args: Any) -> None:
        if (zoom_level := shared.state_schema.get_uint("zoom-level")) > 4:
            return

        shared.state_schema.set_uint("zoom-level", zoom_level + 1)
        self.update_zoom()

    def __on_zoom_out_action(self, *_args: Any) -> None:
        if (zoom_level := shared.state_schema.get_uint("zoom-level")) < 2:
            return

        shared.state_schema.set_uint("zoom-level", zoom_level - 1)
        self.update_zoom()

    def __reset_zoom(self, *_args: Any) -> None:
        shared.state_schema.reset("zoom-level")
        self.update_zoom()

    def __on_close_action(self, *_args: Any) -> None:
        if self.tab_view.get_n_pages() > 1:
            self.tab_view.close_page(self.tab_view.get_selected_page())
        else:
            self.close()

    def __on_back_action(self, *_args: Any) -> None:
        self.tab_view.get_selected_page().get_child().view.pop()

    def __create_window(self, *_args: Any) -> Adw.TabView:
        win = self.get_application().do_activate()

        # Close the initial Home tab
        win.tab_view.close_page(win.tab_view.get_selected_page())
        return win.tab_view

    def __undo(self, obj: Any, *_args: Any) -> None:
        # If the focus is in a text field, return
        # HACK: This should be more elegant
        if isinstance(self.get_focus(), Gtk.Editable):
            return

        if not self.undo_queue:
            return

        if isinstance(obj, Adw.Toast):
            index = obj
        else:
            index = tuple(self.undo_queue.keys())[-1]
        item = self.undo_queue[index]

        # TODO: Lookup the pages with the paths and update those
        match item[0]:
            case "copy":
                for trash_item in item[1]:
                    if trash_item.is_dir():
                        rm(trash_item)
                    else:
                        trash_item.unlink(missing_ok=True)
            case "cut":
                for paths in item[1]:
                    if paths[1].exists():
                        move(paths[1], paths[0])
            case "rename":
                try:
                    item[1].set_display_name(item[2])
                except GLib.Error:
                    pass
            case "trash":
                for trash_item in item[1]:
                    restore(*trash_item)

        if isinstance(index, Adw.Toast):
            index.dismiss()
        self.undo_queue.popitem()

    def __open(self, *_args: Any) -> None:
        if isinstance(self.get_focus(), Gtk.Editable):
            return

        if len(positions := self.get_selected_items()) > 1:
            # TODO: Maybe switch to newly opened tab like Nautilus?
            self.__open_new_tab(None, None, positions)
            return

        self.get_visible_page().activate(None, positions[0])

    def __open_new_tab(
        self, _obj: Any, _parameter: Any, positions: Optional[list[int]] = None
    ) -> None:
        if isinstance(self.get_focus(), Gtk.Editable):
            return

        if not positions:
            positions = self.get_selected_items()

        paths = self.get_paths_from_positions(positions)

        for path in paths:
            if not path.is_dir():
                continue
            self.new_tab(Gio.File.new_for_path(str(path)))

    def __open_new_window(self, *_args: Any) -> None:
        paths = self.get_paths_from_positions(self.get_selected_items())

        for path in paths:
            if not path.is_dir():
                continue
            new_bin = HypNavigationBin(initial_gfile=Gio.File.new_for_path(str(path)))

            win = shared.app.do_activate()
            win.tab_view.close_page(win.tab_view.get_selected_page())
            win.tab_view.append(new_bin)

    def __open_with(self, *_args: Any) -> None:
        portal = Xdp.Portal()
        parent = XdpGtk4.parent_new_gtk(self)
        gfiles = self.get_gfiles_from_positions(self.get_selected_items())
        if not gfiles:
            return

        # TODO: Is there any way to open multiple files?
        portal.open_uri(parent, gfiles[0].get_uri(), Xdp.OpenUriFlags.ASK)

    def __open_tag(self, *_args: Any) -> None:
        if isinstance(self.get_focus(), Gtk.Editable):
            return

        # TODO: This is ugly
        self.tab_view.get_selected_page().get_child().new_page(
            tag=self.right_clicked_tag
        )

    def __open_new_tab_tag(self, *_args: Any) -> None:
        if isinstance(self.get_focus(), Gtk.Editable):
            return

        self.new_tab(tag=self.right_clicked_tag)

    def __open_new_window_tag(self, *_args: Any) -> None:
        if isinstance(self.get_focus(), Gtk.Editable):
            return

        new_bin = HypNavigationBin(initial_tags=[self.right_clicked_tag])
        win = shared.app.do_activate()
        win.tab_view.close_page(win.tab_view.get_selected_page())
        win.tab_view.append(new_bin)

    def __move_tag_up(self, *_args: Any) -> None:
        move_tag(self.right_clicked_tag, up=True)

    def __move_tag_down(self, *_args: Any) -> None:
        move_tag(self.right_clicked_tag, up=False)

    def __remove_tag(self, *_args: Any) -> None:
        remove_tags(self.right_clicked_tag)
        self.send_toast(_("{} removed").format(f'"{self.right_clicked_tag}"'))

    # TODO: Do I really need this? Nautilus has refresh, but I don't know how they monitor.
    def __reload(self, *_args: Any) -> None:
        dir_list = self.get_visible_page().dir_list
        if isinstance(dir_list, Gtk.DirectoryList):
            dir_list.set_monitored(False)
            dir_list.set_monitored(True)
            return

        if isinstance(dir_list, Gtk.FlattenListModel):
            model = dir_list.get_model()
            index = 0
            while item := model.get_item(index):
                item.set_monitored(False)
                item.set_monitored(True)
                index += 1

    def __new_folder(self, *_args: Any) -> None:
        if isinstance(self.get_focus(), Gtk.Editable):
            return

        path = None

        if (page := self.get_visible_page()).tags:
            path = Path(shared.home, *(tag for tag in shared.tags if tag in page.tags))

        if not path:
            try:
                path = get_gfile_path(page.gfile)
            except FileNotFoundError:
                return

        dialog = Adw.MessageDialog.new(self, _("New Folder"))

        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("create", _("Create"))

        dialog.set_default_response("create")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)

        preferences_group = Adw.PreferencesGroup(width_request=360)
        revealer_label = Gtk.Label(
            margin_start=6,
            margin_end=6,
            margin_top=12,
        )
        preferences_group.add(revealer := Gtk.Revealer(child=revealer_label))
        preferences_group.add(entry := Adw.EntryRow(title=_("Folder name")))
        dialog.set_extra_child(preferences_group)

        dialog.set_response_enabled("create", False)
        can_create = False

        def set_incative(*_args: Any) -> None:
            nonlocal can_create
            nonlocal path

            if not (text := entry.get_text().strip()):
                can_create = False
                dialog.set_response_enabled("create", False)
                revealer.set_reveal_child(False)
                return

            can_create, message = validate_name(Gio.File.new_for_path(str(path)), text)
            dialog.set_response_enabled("create", can_create)
            revealer.set_reveal_child(bool(message))
            if message:
                revealer_label.set_label(message)

        def create_folder(*_args: Any):
            nonlocal can_create
            nonlocal path

            if not can_create:
                return

            Path(path, entry.get_text().strip()).mkdir(parents=True, exist_ok=True)
            dialog.close()

        def handle_response(_dialog: Adw.MessageDialog, response: str) -> None:
            if response == "create":
                create_folder()

        dialog.connect("response", handle_response)
        entry.connect("entry-activated", create_folder)
        entry.connect("changed", set_incative)

        dialog.choose()

    def __copy(self, *_args: Any) -> None:
        if isinstance(self.get_focus(), Gtk.Editable):
            return

        self.cut_page = None
        clipboard = Gdk.Display.get_default().get_clipboard()
        if not (items := self.get_gfiles_from_positions(self.get_selected_items())):
            return

        provider = Gdk.ContentProvider.new_for_value(Gdk.FileList.new_from_array(items))

        clipboard.set_content(provider)

    def __cut(self, _obj: Any, *args: Any) -> None:
        if isinstance(self.get_focus(), Gtk.Editable):
            return

        self.__copy(*args)
        self.cut_page = self.get_visible_page()

    def __paste(self, *_args: Any) -> None:
        if isinstance(self.get_focus(), Gtk.Editable):
            return

        clipboard = Gdk.Display.get_default().get_clipboard()
        paths = []

        if not clipboard.get_formats().contain_gtype(Gdk.FileList):
            return

        def __cb(clipboard, result) -> None:
            nonlocal paths

            try:
                file_list = clipboard.read_value_finish(result)
            except GLib.Error:
                self.cut_page = None
                return

            page = self.get_visible_page()
            for gfile in file_list:
                if page.tags:
                    dst = Path(
                        shared.home,
                        *(tag for tag in shared.tags if tag in page.tags),
                    )
                else:
                    try:
                        dst = get_gfile_path(page.gfile)
                    except FileNotFoundError:
                        continue
                try:
                    src = get_gfile_path(gfile)
                except (
                    TypeError,  # If the value being pasted isn't a pathlike
                    FileNotFoundError,
                ):
                    continue
                if not src.exists():
                    continue

                dst = dst / src.name

                if self.cut_page:
                    try:
                        move(src, dst)
                    except FileExistsError:
                        self.send_toast(
                            _("A folder with that name already exists.")
                            if src.is_dir()
                            else _("A file with that name already exists.")
                        )
                        continue
                    else:
                        paths.append((src, dst))

                else:
                    try:
                        copy(src, dst)
                    except FileExistsError:
                        dst = get_copy_path(dst)
                        copy(src, dst)

                    paths.append(dst)

            if self.cut_page:
                self.undo_queue[time()] = ("cut", paths)
            else:
                self.undo_queue[time()] = ("copy", paths)
            self.cut_page = None

        clipboard.read_value_async(Gdk.FileList, GLib.PRIORITY_DEFAULT, None, __cb)

    def __select_all(self, *_args: Any) -> None:
        if isinstance(self.get_focus(), Gtk.Editable):
            return

        self.get_visible_page().multi_selection.select_all()

    def __rename(self, *_args: Any) -> None:
        if isinstance(self.get_focus(), Gtk.Editable):
            return

        # TODO: Maybe make it stop iteration on first item?
        try:
            position = self.get_selected_items()[0]
        except IndexError:
            return
        # TODO: Get edit name from gfile
        gfile = self.get_gfiles_from_positions([position])[0]

        try:
            path = get_gfile_path(gfile)
        except FileNotFoundError:
            return

        multi_selection = self.get_visible_page().multi_selection
        multi_selection.select_item(position, True)

        children = self.get_visible_page().grid_view.observe_children()

        # TODO: This may be slow
        index = 0
        while item := children.get_item(index):
            if item.get_first_child().gfile == gfile:
                (popover := self.rename_popover).set_parent(item)
                break
            index += 1

        if path.is_dir():
            self.rename_label.set_label(_("Rename Folder"))
        else:
            self.rename_label.set_label(_("Rename File"))

        entry = self.rename_entry
        entry.set_text(path.name)

        button = self.rename_button
        revealer = self.rename_revealer
        revealer_label = self.rename_revealer_label
        can_rename = True

        def rename(obj: Any, *_args: Any) -> None:
            if isinstance(obj, Gio.SimpleAction) and (
                not self.get_visible_page().is_focus()
            ):
                return

            popover.popdown()
            try:
                old_name = path.name
                new_file = gfile.set_display_name(entry.get_text().strip())
            except GLib.Error:
                pass
            else:
                self.undo_queue[time()] = ("rename", new_file, old_name)

        def set_incative(*_args: Any) -> None:
            nonlocal can_rename
            nonlocal path

            if not popover.is_visible():
                return

            text = entry.get_text().strip()

            if not text:
                can_rename = False
                button.set_sensitive(False)
                revealer.set_reveal_child(False)
                return

            can_rename, message = validate_name(
                Gio.File.new_for_path(str(path)), text, True
            )
            button.set_sensitive(can_rename)
            revealer.set_reveal_child(bool(message))
            if message:
                revealer_label.set_label(message)

        def unparent(popover):
            popover.unparent()

        popover.connect("notify::visible", set_incative)
        popover.connect("closed", unparent)
        entry.connect("changed", set_incative)
        entry.connect("entry-activated", rename)
        button.connect("clicked", rename)

        popover.popup()
        entry.select_region(0, len(path.name) - len("".join(path.suffixes)))

    def __trash(self, *args) -> None:
        if isinstance(self.get_focus(), Gtk.Editable):
            return

        gfiles = self.get_gfiles_from_positions(self.get_selected_items())

        # When the Delete key is pressed but the user is in the trash
        if gfiles and gfiles[0].get_uri().startswith("trash://"):
            self.__trash_delete(*args)

        files = []
        n = 0
        for gfile in gfiles:
            try:
                gfile.trash()
            except GLib.Error:
                pass
            else:
                try:
                    files.append((get_gfile_path(gfile), int(time())))
                except FileNotFoundError:
                    continue
                else:
                    n += 1

        if not n:
            return

        if n > 1:
            message = _("{} files moved to trash").format(n)
        elif n:
            # TODO: Use the GFileInfo's display name maybe
            message = _("{} moved to trash").format(
                f'"{files[0][0].name}"'  # pylint: disable=undefined-loop-variable
            )

        toast = self.send_toast(message, undo=True)
        self.undo_queue[toast] = ("trash", files)
        toast.connect("button-clicked", self.__undo)

    def __trash_delete(self, *args: Any) -> None:
        if isinstance(self.get_focus(), Gtk.Editable):
            return

        gfiles = self.get_gfiles_from_positions(self.get_selected_items())

        # When the Delete key is pressed but the user is not in the trash
        if gfiles and (not gfiles[0].get_uri().startswith("trash://")):
            self.__trash_delete(*args)

        def delete():
            for gfile in gfiles:
                trash_rm(gfile)

        match len(gfiles):
            case 0:
                return
            case 1:
                # TODO: Blocking I/O for this? Really?
                msg = _("Are you sure you want to permanently delete {}?").format(
                    f'"{get_gfile_display_name(gfiles[0])}"'
                )
            case _:
                # The variable is the number of items to be deleted
                msg = _(
                    "Are you sure you want to permanently delete the {} selected items?"
                ).format(len(gfiles))

        dialog = Adw.MessageDialog.new(self, msg)
        dialog.set_body(_("If you delete an item, it will be permanently lost."))

        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("delete", _("Delete"))

        dialog.set_default_response("delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def handle_response(_dialog: Adw.MessageDialog, response: str) -> None:
            if response == "delete":
                delete()

        dialog.connect("response", handle_response)
        dialog.present()

    def __trash_restore(self, *_args: Any) -> None:
        if isinstance(self.get_focus(), Gtk.Editable):
            return

        gfiles = self.get_gfiles_from_positions(self.get_selected_items())

        for gfile in gfiles:
            restore(gfile=gfile)

    def __set_actions(self, *_args: Any) -> None:
        self.set_menu_items(
            {
                "rename",
                "copy",
                "cut",
                "paste",
                "trash",
                "trash-delete",
                "trash-restore",
                "new-folder",
                "select-all",
                "open",
                "open-new-tab",
                "open-new-window",
                "open-with",
            }
        )
