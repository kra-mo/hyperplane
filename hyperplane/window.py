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
from typing import Any, Callable, Iterable, Optional

from gi.repository import Adw, Gio, Gtk

from hyperplane import shared
from hyperplane.items_page import HypItemsPage
from hyperplane.navigation_bin import HypNavigationBin
from hyperplane.tag_row import HypTagRow
from hyperplane.utils.files import get_gfile_path
from hyperplane.utils.tags import add_tags, move_tag, remove_tags


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
    trash_icon: Gtk.Image = Gtk.Template.Child()

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

        self.create_action("forward", self.__on_forward_action)
        self.lookup_action("forward").set_enabled(False)

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

        self.__trash_changed()
        shared.trash_list.connect("notify::n-items", self.__trash_changed)

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
        """Open a new path with the given file or tag."""
        if (
            gfile
            and gfile.query_file_type(Gio.FileQueryInfoFlags.NONE)
            == Gio.FileType.DIRECTORY
        ):
            navigation_view = HypNavigationBin(initial_gfile=gfile)
        elif tag:
            navigation_view = HypNavigationBin(initial_tags=[tag])
        else:
            return

        self.tab_view.append(navigation_view).set_title(
            navigation_view.view.get_visible_page().get_title()
        )

    def new_window(
        self, gfile: Optional[Gio.File] = None, tag: Optional[str] = None
    ) -> None:
        """Open a new window with the given file or tag."""
        if (
            gfile
            and gfile.query_file_type(Gio.FileQueryInfoFlags.NONE)
            == Gio.FileType.DIRECTORY
        ):
            new_bin = HypNavigationBin(initial_gfile=gfile)
        elif tag:
            new_bin = HypNavigationBin(initial_tags=[tag])
        else:
            return

        win = self.get_application().do_activate()
        win.tab_view.close_page(win.tab_view.get_selected_page())
        win.tab_view.append(new_bin)

    def get_visible_page(self) -> HypItemsPage:
        """Return the currently visible HypItemsPage."""
        return self.tab_view.get_selected_page().get_child().view.get_visible_page()

    def update_zoom(self) -> None:
        """Update the zoom level of all items in the navigation stack"""
        shared.postmaster.emit("zoom", shared.state_schema.get_uint("zoom-level"))

    def create_action(
        self, name: str, callback: Callable, shortcuts: Optional[Iterable] = None
    ) -> None:
        """Add a window action.

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
            self.get_visible_page().action_group.lookup_action(action).set_enabled(
                False
            )
        for action in menu_items:
            self.get_visible_page().action_group.lookup_action(action).set_enabled(True)

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

        gfile = self.get_visible_page().gfile
        if not gfile or gfile.get_uri() != "trash:///":
            nav_bin.new_page(Gio.File.new_for_uri("trash://"))

    def __row_activated(self, _box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        nav_bin = self.tab_view.get_selected_page().get_child()

        if row.get_child() == self.sidebar_home:
            gfile = self.get_visible_page().gfile
            if not gfile or gfile.get_path() != str(shared.home):
                nav_bin.new_page(Gio.File.new_for_path(str(shared.home)))
            return

        nav_bin.new_page(tag=row.get_child().tag)

    def __tab_changed(self, *_args: Any) -> None:
        if not self.tab_view.get_selected_page():
            return

        self.set_title(self.get_visible_page().get_title())
        self.__nav_stack_changed()

    def __navigation_changed(self, view: Adw.NavigationView, *_args: Any) -> None:
        self.__hide_search_entry()
        view.get_visible_page().item_filter.changed(Gtk.FilterChange.LESS_STRICT)

        title = view.get_visible_page().get_title()
        if page := self.tab_view.get_page(view.get_parent()):
            page.set_title(title)

        if self.tab_view.get_selected_page() == page:
            self.set_title(title)

        self.__nav_stack_changed()

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

        if "://" in text:
            gfile = Gio.File.new_for_uri(text)
        else:
            gfile = Gio.File.new_for_path(text)

        if (
            not gfile.query_file_type(Gio.FileQueryInfoFlags.NONE)
            == Gio.FileType.DIRECTORY
        ):
            self.send_toast(_("Unable to find path"))
            return

        self.__hide_path_bar()

        if gfile.get_uri() == self.get_visible_page().gfile.get_uri():
            return

        nav_bin.new_page(gfile)

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

    def __on_close_action(self, *_args: Any) -> None:
        if self.tab_view.get_n_pages() > 1:
            self.tab_view.close_page(self.tab_view.get_selected_page())
        else:
            self.close()

    def __on_back_action(self, *_args: Any) -> None:
        self.tab_view.get_selected_page().get_child().view.pop()

    def __on_forward_action(self, *_args: Any) -> None:
        nav_bin = self.tab_view.get_selected_page().get_child()
        if not nav_bin.next_pages:
            return

        nav_bin.view.push(nav_bin.next_pages[-1])

    def __create_window(self, *_args: Any) -> Adw.TabView:
        win = self.get_application().do_activate()

        # Close the initial Home tab
        win.tab_view.close_page(win.tab_view.get_selected_page())
        return win.tab_view

    def __open_tag(self, *_args: Any) -> None:
        # TODO: This is ugly
        self.tab_view.get_selected_page().get_child().new_page(
            tag=self.right_clicked_tag
        )

    def __open_new_tab_tag(self, *_args: Any) -> None:
        self.new_tab(tag=self.right_clicked_tag)

    def __open_new_window_tag(self, *_args: Any) -> None:
        self.new_window(tag=self.right_clicked_tag)

    def __move_tag_up(self, *_args: Any) -> None:
        move_tag(self.right_clicked_tag, up=True)

    def __move_tag_down(self, *_args: Any) -> None:
        move_tag(self.right_clicked_tag, up=False)

    def __remove_tag(self, *_args: Any) -> None:
        remove_tags(self.right_clicked_tag)
        self.send_toast(_("{} removed").format(f'"{self.right_clicked_tag}"'))

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

    def __nav_stack_changed(self) -> None:
        self.lookup_action("back").set_enabled(
            bool(
                self.tab_view.get_selected_page()
                .get_child()
                .view.get_navigation_stack()
                .get_n_items()
                - 1
            )
        )
        self.lookup_action("forward").set_enabled(
            bool(self.tab_view.get_selected_page().get_child().next_pages)
        )

    def __trash_changed(self, *_args: Any) -> None:
        self.trash_icon.set_from_icon_name(
            "user-trash-full-symbolic"
            if shared.trash_list.get_n_items()
            else "user-trash-symbolic"
        )
