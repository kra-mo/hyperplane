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

"""The main application window."""
from os import sep
from time import time
from typing import Any, Callable, Iterable, Optional

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from hyperplane import shared
from hyperplane.items_page import HypItemsPage
from hyperplane.navigation_bin import HypNavigationBin
from hyperplane.properties import HypPropertiesWindow
from hyperplane.tag_row import HypTagRow
from hyperplane.utils.files import empty_trash, get_gfile_path, validate_name
from hyperplane.utils.tags import add_tags, move_tag, remove_tags


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/window.ui")
class HypWindow(Adw.ApplicationWindow):
    """The main application window."""

    __gtype_name__ = "HypWindow"

    tab_overview: Adw.TabOverview = Gtk.Template.Child()
    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    overlay_split_view: Adw.OverlaySplitView = Gtk.Template.Child()
    tab_view: Adw.TabView = Gtk.Template.Child()
    toolbar_view: Adw.ToolbarView = Gtk.Template.Child()
    sidebar: Gtk.ListBox = Gtk.Template.Child()
    sidebar_home: Gtk.Box = Gtk.Template.Child()
    sidebar_recent: Gtk.Box = Gtk.Template.Child()
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
    file_right_click_menu: Gtk.PopoverMenu = Gtk.Template.Child()

    path_bar_connection: int
    sidebar_items: set
    right_clicked_tag: str
    right_clicked_file: Gio.File

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        if shared.PROFILE == "development":
            self.add_css_class("devel")

        self.tab_view.connect("page-attached", self.__page_attached)
        self.tab_view.connect("close-page", self.__close_page)
        self.closed_tabs = []

        # Set up animations

        target = Adw.PropertyAnimationTarget.new(self.trash_icon, "pixel-size")
        params = Adw.SpringParams.new(0.4, 0.8, 250)
        self.trash_animation = Adw.SpringAnimation.new(
            self.trash_icon, 10, 16, params, target
        )
        self.trash_animation.props.epsilon = 0.015

        self.trash_empty_animation = Adw.SpringAnimation.new(
            self.trash_icon, 22, 16, params, target
        )
        self.trash_empty_animation.props.epsilon = 0.026

        # Create actions

        navigation_view = HypNavigationBin(
            initial_gfile=Gio.File.new_for_path(str(shared.home))
        )
        self.tab_view.append(navigation_view).set_title(
            title := self.get_visible_page().get_title()
        )
        self.set_title(title)

        self.create_action(
            "properties", self.__properties, ("<alt>Return", "<primary>i")
        )

        self.create_action("home", self.__go_home, ("<alt>Home",))
        self.create_action(
            "toggle-path-bar", self.__toggle_path_bar, ("F6", "<primary>l")
        )
        self.create_action("hide-path-bar", self.__hide_path_bar)
        self.create_action("close", self.__close, ("<primary>w",))
        self.create_action("reopen-tab", self.__reopen_tab, ("<primary><shift>t",))
        self.create_action("search", self.__toggle_search_entry, ("<primary>f",))

        self.create_action("back", self.__back)
        self.lookup_action("back").set_enabled(False)

        self.create_action("forward", self.__forward)
        self.lookup_action("forward").set_enabled(False)

        self.create_action(
            "zoom-in",
            self.zoom_in,
            ("<primary>plus", "<Primary>KP_Add", "<primary>equal"),
        )
        self.create_action(
            "zoom-out",
            self.zoom_out,
            ("<primary>minus", "<Primary>KP_Subtract", "<Primary>underscore"),
        )
        self.create_action(
            "reset-zoom", self.__reset_zoom, ("<primary>0", "<primary>KP_0")
        )
        self.create_action("reload", self.__reload, ("<primary>r", "F5"))

        self.create_action("rename", self.__rename, ("F2",))

        # TODO: This is tedious, maybe use GTK Expressions?
        self.create_action("open-sidebar", self.__open_sidebar)
        self.create_action("open-new-tab-sidebar", self.__open_new_tab_sidebar)
        self.create_action("open-new-window-sidebar", self.__open_new_window_sidebar)
        self.create_action("properties-sidebar", self.__properties_sidebar)

        self.create_action("open-tag", self.__open_tag)
        self.create_action("open-new-tab-tag", self.__open_new_tab_tag)
        self.create_action("open-new-window-tag", self.__open_new_window_tag)
        self.create_action("move-tag-up", self.__move_tag_up)
        self.create_action("move-tag-down", self.__move_tag_down)
        self.create_action("remove-tag", self.__remove_tag)

        self.create_action("new-window", self.__new_window, ("<primary>n",))
        self.create_action("new-tab", self.__new_tab, ("<primary>t",))
        self.create_action("tab-overview", self.__tab_overview, ("<primary><shift>o",))
        self.create_action("empty-trash", self.__emptry_trash)

        # Connect signals

        self.sidebar.connect("row-activated", self.__row_activated)
        self.new_tag_box.connect("row-activated", self.__new_tag)
        self.trash_box.connect("row-activated", self.__open_trash)

        self.tab_view.connect("notify::selected-page", self.__tab_changed)
        self.tab_view.connect("create-window", self.__create_window)
        self.tab_overview.connect("create-tab", self.__create_tab)

        self.path_bar.connect("activate", self.__path_bar_activated)
        self.search_entry.connect("search-started", self.__show_search_entry)
        self.search_entry.connect("search-changed", self.__search_changed)
        self.search_entry.connect("stop-search", self.__hide_search_entry)
        self.search_entry.connect("activate", self.__search_activate)
        self.search_button.connect("clicked", self.__toggle_search_entry)

        shared.postmaster.connect("tags-changed", self.__update_tags)

        self.right_click_menu.connect("closed", self.__set_actions)

        self.can_rename = True
        self.rename_item = None
        self.rename_entry.connect("changed", self.__rename_state_changed)
        self.rename_popover.connect("closed", self.__rename_popover_closed)
        self.rename_entry.connect("entry-activated", self.__do_rename)
        self.rename_button.connect("clicked", self.__do_rename)

        # Set up search

        self.searched_page = self.get_visible_page()
        self.search_entry.set_key_capture_widget(self)

        # Build sidebar

        self.sidebar_items = set()
        self.__update_tags()

        self.__trash_changed()
        shared.trash_list.connect("notify::n-items", self.__trash_changed)

        # Set up sidebar actions

        sidebar_items = {
            self.sidebar_recent: Gio.File.new_for_uri("recent://"),
            self.sidebar_home: Gio.File.new_for_path(str(shared.home)),
            self.trash_box.get_first_child(): Gio.File.new_for_uri("trash://"),
        }

        for widget, gfile in sidebar_items.items():
            (right_click := Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)).connect(
                "pressed", self.__sidebar_right_click, gfile
            )

            (middle_click := Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)).connect(
                "pressed", self.__sidebar_middle_click, gfile
            )

            widget.add_controller(right_click)
            widget.add_controller(middle_click)

        self.__set_actions()

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
        self, gfile: Optional[Gio.File] = None, tags: Optional[Iterable[str]] = None
    ) -> None:
        """Open a new path with the given file or tag."""
        if (
            gfile
            and gfile.query_file_type(Gio.FileQueryInfoFlags.NONE)
            == Gio.FileType.DIRECTORY
        ):
            navigation_view = HypNavigationBin(initial_gfile=gfile)
        elif tags:
            navigation_view = HypNavigationBin(initial_tags=tags)
        else:
            return

        self.tab_view.append(navigation_view).set_title(
            navigation_view.view.get_visible_page().get_title()
        )

    def new_window(
        self, gfile: Optional[Gio.File] = None, tags: Optional[Iterable[str]] = None
    ) -> None:
        """Open a new window with the given file or tags."""
        if (
            gfile
            and gfile.query_file_type(Gio.FileQueryInfoFlags.NONE)
            == Gio.FileType.DIRECTORY
        ):
            new_bin = HypNavigationBin(initial_gfile=gfile)
        elif tags:
            new_bin = HypNavigationBin(initial_tags=tags)
        else:
            return

        win = self.get_application().do_activate()
        win.tab_view.close_page(win.tab_view.get_selected_page())
        win.tab_view.append(new_bin)

    def get_nav_bin(self) -> HypNavigationBin:
        """Returns the currently visible HypNavigationBin."""
        return self.tab_view.get_selected_page().get_child()

    def get_visible_page(self) -> HypItemsPage:
        """Return the currently visible HypItemsPage."""
        return self.get_nav_bin().view.get_visible_page()

    def zoom_in(self, *_args: Any) -> None:
        """Increases the zoom level of all views."""

        if (zoom_level := shared.state_schema.get_uint("zoom-level")) > 4:
            return

        shared.state_schema.set_uint("zoom-level", zoom_level + 1)
        self.update_zoom()

    def zoom_out(self, *_args: Any) -> None:
        """Decreases the zoom level of all views."""

        if (zoom_level := shared.state_schema.get_uint("zoom-level")) < 2:
            return

        shared.state_schema.set_uint("zoom-level", zoom_level - 1)
        self.update_zoom()

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
        page = self.get_visible_page().action_group

        actions = {
            "rename": self,
            "copy": page,
            "cut": page,
            "paste": page,
            "trash": page,
            "trash-delete": page,
            "trash-restore": page,
            "empty-trash": self,
            "new-folder": page,
            "select-all": page,
            "open": page,
            "open-new-tab": page,
            "open-new-window": page,
            "open-with": page,
        }

        for action, group in actions.items():
            group.lookup_action(action).set_enabled(action in menu_items)

    def __properties(self, *_args: Any) -> None:
        page = self.get_visible_page()

        gfiles = [page.gfile] if page.right_click_view else page.get_selected_gfiles()
        page.right_click_view = False

        if (
            not gfiles
        ):  # If the keyboard shortcut was triggered, but no items are selected
            gfiles = [page.gfile]

        # TODO: Allow viewing properties of multiple files
        properties = HypPropertiesWindow(gfiles[0])
        properties.set_transient_for(self)
        properties.present()

    def __update_tags(self, *_args: Any) -> None:
        for item in self.sidebar_items:
            self.sidebar.remove(item.get_parent())

        self.sidebar_items = set()

        for tag in reversed(shared.tags):
            self.sidebar_items.add(row := HypTagRow(tag, "user-bookmarks-symbolic"))
            self.sidebar.insert(row, 2)

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

            if (
                # Replace characters that wouldn't be valid with similar ones
                text := entry.get_text()
                .strip()
                .replace("/", "⧸")
                .replace("\n", " ")
            ) in shared.tags:
                self.send_toast(_('A category named "{}" already exists').format(text))
                return

            if text in (".", ".."):
                self.send_toast(_("A category cannot be named {}").format(f'"{text}"'))
                return

            add_tags(text)

        def handle_response(_dialog: Adw.MessageDialog, response: str) -> None:
            if response == "add":
                add_tag()

        entry.connect("entry-activated", add_tag)
        dialog.connect("response", handle_response)
        dialog.choose()

    def __open_trash(self, *_args: Any) -> None:
        if self.overlay_split_view.get_collapsed():
            self.overlay_split_view.set_show_sidebar(False)

        gfile = self.get_visible_page().gfile
        if (not gfile) or (gfile.get_uri() != "trash:///"):
            self.get_nav_bin().new_page(Gio.File.new_for_uri("trash://"))

    def __row_activated(self, _box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        if self.overlay_split_view.get_collapsed():
            self.overlay_split_view.set_show_sidebar(False)

        nav_bin = self.get_nav_bin()

        if (child := row.get_child()) == self.sidebar_home:
            gfile = self.get_visible_page().gfile
            if (not gfile) or (gfile.get_path() != str(shared.home)):
                nav_bin.new_page(Gio.File.new_for_path(str(shared.home)))
            return

        if child == self.sidebar_recent:
            gfile = self.get_visible_page().gfile
            if (not gfile) or (gfile.get_uri() != "recent:///"):
                nav_bin.new_page(Gio.File.new_for_uri("recent://"))
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

    def __close_page(self, _view: Adw.TabView, page: Adw.TabPage) -> None:
        # TODO: I thought registering a handler meant just connecting to the signal
        # but apparently not?
        # Regardless, this still works since the default handler does what I want anyway
        child = page.get_child()
        child.unparent()
        self.closed_tabs.append((child, page.get_title()))

    def __reopen_tab(self, *_args: Any) -> None:
        try:
            page, title = self.closed_tabs.pop()
        except IndexError:
            return
        self.tab_view.append(page).set_title(title)

    def __path_bar_activated(self, entry, *_args: Any) -> None:
        text = entry.get_text().strip()
        nav_bin = self.get_nav_bin()

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
                        path
                        if isinstance(path, str)
                        else (
                            str(path)
                            if str(path) == sep  # If the path is root
                            else str(path) + sep
                        )
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
        self.get_nav_bin().new_page(Gio.File.new_for_path(str(shared.home)))

    def __close(self, *_args: Any) -> None:
        if self.tab_view.get_n_pages() > 1:
            self.tab_view.close_page(self.tab_view.get_selected_page())
        else:
            self.close()

    def __back(self, *_args: Any) -> None:
        self.get_nav_bin().view.pop()

    def __forward(self, *_args: Any) -> None:
        nav_bin = self.get_nav_bin()
        if not nav_bin.next_pages:
            return

        nav_bin.view.push(nav_bin.next_pages[-1])

    def __reset_zoom(self, *_args: Any) -> None:
        shared.state_schema.reset("zoom-level")
        self.update_zoom()

    def __reload(self, *_args: Any) -> None:
        self.get_visible_page().reload()

    def __create_window(self, *_args: Any) -> Adw.TabView:
        win = self.get_application().do_activate()

        # Close the initial Home tab
        win.tab_view.close_page(win.tab_view.get_selected_page())
        return win.tab_view

    def __create_tab(self, *_args: Any) -> Adw.TabPage:
        page = self.tab_view.append(
            HypNavigationBin(initial_gfile=Gio.File.new_for_path(str(shared.home)))
        )

        page.set_title(_("Home"))
        return page

    def __open_sidebar(self, *_args: Any) -> None:
        self.get_nav_bin().new_page(self.right_clicked_file)

    def __open_new_tab_sidebar(self, *_args: Any) -> None:
        self.new_tab(self.right_clicked_file)

    def __open_new_window_sidebar(self, *_args: Any) -> None:
        self.new_window(self.right_clicked_file)

    def __properties_sidebar(self, *_args: Any) -> None:
        properties = HypPropertiesWindow(self.right_clicked_file)
        properties.set_transient_for(self)
        properties.present()

    def __open_tag(self, *_args: Any) -> None:
        self.get_nav_bin().new_page(tag=self.right_clicked_tag)

    def __open_new_tab_tag(self, *_args: Any) -> None:
        self.new_tab(tags=[self.right_clicked_tag])

    def __open_new_window_tag(self, *_args: Any) -> None:
        self.new_window(tags=[self.right_clicked_tag])

    def __move_tag_up(self, *_args: Any) -> None:
        move_tag(self.right_clicked_tag, up=True)

    def __move_tag_down(self, *_args: Any) -> None:
        move_tag(self.right_clicked_tag, up=False)

    def __remove_tag(self, *_args: Any) -> None:
        remove_tags(self.right_clicked_tag)
        self.send_toast(_("{} removed").format(f'"{self.right_clicked_tag}"'))

    def __new_tab(self, *_args: Any) -> None:
        page = self.get_visible_page()
        self.new_tab(gfile=page.gfile, tags=page.tags)

    def __new_window(self, *_args: Any) -> None:
        page = self.get_visible_page()
        self.new_window(gfile=page.gfile, tags=page.tags)

    def __tab_overview(self, *_args: Any) -> None:
        self.tab_overview.set_open(not self.tab_overview.get_open())

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
                "empty-trash",
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
        self.lookup_action("forward").set_enabled(bool(self.get_nav_bin().next_pages))

    def __trash_changed(self, *_args: Any) -> None:
        self.trash_icon.set_from_icon_name(
            "user-trash-full-symbolic"
            if shared.trash_list.get_n_items()
            else "user-trash-symbolic"
        )

    def __rename(self, *_args: Any) -> None:
        page = self.get_visible_page()

        try:
            position = page.get_selected_positions()[0]
        except IndexError:
            return

        page.multi_selection.select_item(position, True)

        children = page.grid_view.observe_children()

        child = children.get_item(position)
        self.rename_popover.set_parent(child)

        item = child.get_first_child()

        if item.is_dir:
            self.rename_label.set_label(_("Rename Folder"))
        else:
            self.rename_label.set_label(_("Rename File"))

        self.rename_entry.set_text(item.edit_name)

        self.rename_popover.popup()
        self.rename_entry.select_region(0, len(item.display_name))
        self.rename_item = item

    def __do_rename(self, *_args: Any) -> None:
        if not self.rename_item:
            return

        self.rename_popover.popdown()
        try:
            new_file = self.rename_item.gfile.set_display_name(
                self.rename_entry.get_text().strip()
            )
        except GLib.Error:
            pass
        else:
            shared.undo_queue[time()] = ("rename", new_file, self.rename_item.edit_name)

    def __rename_popover_closed(self, *_args: Any) -> None:
        self.rename_popover.unparent()

    def __rename_state_changed(self, *_args: Any) -> None:
        if (not self.rename_popover.is_visible()) or (not self.rename_item):
            return

        text = self.rename_entry.get_text().strip()

        if not text:
            self.can_rename = False
            self.rename_button.set_sensitive(False)
            self.rename_revealer.set_reveal_child(False)
            return

        self.can_rename, message = validate_name(self.rename_item.gfile, text, True)
        self.rename_button.set_sensitive(self.can_rename)
        self.rename_revealer.set_reveal_child(bool(message))
        if message:
            self.rename_revealer_label.set_label(message)

    def __sidebar_right_click(
        self, gesture: Gtk.GestureClick, _n: int, x: float, y: float, gfile: Gio.File
    ) -> None:
        self.right_clicked_file = gfile

        self.lookup_action("empty-trash").set_enabled(
            gfile.get_uri() == "trash:///" and shared.trash_list.get_n_items()
        )

        self.file_right_click_menu.unparent()
        self.file_right_click_menu.set_parent(gesture.get_widget())
        rectangle = Gdk.Rectangle()
        rectangle.x, rectangle.y, rectangle.width, rectangle.height = x, y, 0, 0
        self.file_right_click_menu.set_pointing_to(rectangle)
        self.file_right_click_menu.popup()

    def __sidebar_middle_click(
        self, _gesture: Gtk.GestureClick, _n: int, _x: float, _y: float, gfile: Gio.File
    ) -> None:
        self.new_tab(gfile)

    def __emptry_trash(self, *_args: Any) -> None:
        dialog = Adw.MessageDialog.new(
            self,
            _("Empty all Items From Trash?"),
            _("All items in the Trash will be permamently deleted."),
        )

        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("empty", _("Empty Trash"))

        dialog.set_default_response("empty")
        dialog.set_response_appearance("empty", Adw.ResponseAppearance.DESTRUCTIVE)

        def handle_response(_dialog: Adw.MessageDialog, response: str) -> None:
            if response == "empty":
                empty_trash()
                self.get_root().trash_empty_animation.play()

        dialog.connect("response", handle_response)
        dialog.present()
