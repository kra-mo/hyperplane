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
import logging
from itertools import chain
from time import time
from typing import Any, Callable, Iterable, Optional, Self

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from hyperplane import shared
from hyperplane.editable_row import HypEditableRow
from hyperplane.items_page import HypItemsPage
from hyperplane.navigation_bin import HypNavigationBin
from hyperplane.path_bar import HypPathBar
from hyperplane.path_entry import HypPathEntry
from hyperplane.properties import HypPropertiesWindow
from hyperplane.tag_row import HypTagRow
from hyperplane.utils.create_message_dialog import create_message_dialog
from hyperplane.utils.files import (
    clear_recent_files,
    copy,
    empty_trash,
    get_copy_gfile,
    get_gfile_display_name,
    validate_name,
)
from hyperplane.utils.tags import add_tags, move_tag, remove_tags
from hyperplane.volumes_box import HypVolumesBox


@Gtk.Template(resource_path=shared.PREFIX + "/gtk/window.ui")
class HypWindow(Adw.ApplicationWindow):
    """The main application window."""

    __gtype_name__ = "HypWindow"

    # Main view
    tab_overview: Adw.TabOverview = Gtk.Template.Child()
    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    overlay_split_view: Adw.OverlaySplitView = Gtk.Template.Child()
    tab_view: Adw.TabView = Gtk.Template.Child()
    toolbar_view: Adw.ToolbarView = Gtk.Template.Child()

    # Sidebar
    sidebar: Gtk.ListBox = Gtk.Template.Child()
    sidebar_action_bar: Gtk.ActionBar = Gtk.Template.Child()
    home_row: Gtk.Box = Gtk.Template.Child()
    recent_row: Gtk.Box = Gtk.Template.Child()
    new_tag_box: Gtk.ListBox = Gtk.Template.Child()
    trash_box: Gtk.ListBox = Gtk.Template.Child()
    trash_row: HypEditableRow = Gtk.Template.Child()
    volumes_box: HypVolumesBox = Gtk.Template.Child()

    # Header bar, action bar
    title_stack: Gtk.Stack = Gtk.Template.Child()
    path_bar_clamp: Adw.Clamp = Gtk.Template.Child()
    path_bar: HypPathBar = Gtk.Template.Child()
    path_entry_clamp: Adw.Clamp = Gtk.Template.Child()
    path_entry: HypPathEntry = Gtk.Template.Child()
    search_entry_clamp: Adw.Clamp = Gtk.Template.Child()
    search_entry: Gtk.SearchEntry = Gtk.Template.Child()
    search_button: Gtk.ToggleButton = Gtk.Template.Child()
    header_bar_view_button: Gtk.Button = Gtk.Template.Child()
    action_bar_view_button: Gtk.Button = Gtk.Template.Child()

    # Rename popover
    rename_popover: Gtk.Popover = Gtk.Template.Child()
    rename_label: Gtk.Label = Gtk.Template.Child()
    rename_entry: Adw.EntryRow = Gtk.Template.Child()
    rename_revealer: Gtk.Revealer = Gtk.Template.Child()
    rename_revealer_label: Gtk.Label = Gtk.Template.Child()
    rename_button: Gtk.Button = Gtk.Template.Child()

    # Right-click menus
    right_click_menu: Gtk.PopoverMenu = Gtk.Template.Child()
    tag_right_click_menu: Gtk.PopoverMenu = Gtk.Template.Child()
    file_right_click_menu: Gtk.PopoverMenu = Gtk.Template.Child()

    path_entry_connection: int
    sidebar_tag_rows: set
    right_clicked_tag: str

    def __init__(
        self,
        initial_gfile: Optional[Gio.File],
        initial_tags: Optional[Iterable[str]],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.select_uri = None

        if shared.PROFILE == "development":
            self.add_css_class("devel")

        self.tab_view.connect("page-attached", self.__page_attached)
        self.tab_view.connect("close-page", self.__close_page)
        self.closed_tabs = []

        # Set up animations

        # Make the label not move around during animations
        self.trash_row.box.set_spacing(0)
        self.trash_row.box.set_margin_start(0)
        self.trash_row.image.set_size_request(28, -1)
        self.trash_row.label.set_margin_start(6)

        target = Adw.PropertyAnimationTarget.new(self.trash_row.image, "pixel-size")
        params = Adw.SpringParams.new(0.4, 0.8, 250)
        self.trash_animation = Adw.SpringAnimation.new(
            self.trash_row.image, 10, 16, params, target
        )
        self.trash_animation.props.epsilon = 0.015

        self.trash_empty_animation = Adw.SpringAnimation.new(
            self.trash_row.image, 22, 16, params, target
        )
        self.trash_empty_animation.props.epsilon = 0.026

        # Create actions
        navigation_view = HypNavigationBin(
            initial_gfile=initial_gfile, initial_tags=initial_tags
        )

        self.tab_view.append(navigation_view).set_title(
            title := (page := self.get_visible_page()).get_title()
        )

        self.path_bar.update(page.gfile, page.tags)
        self.set_title(title)

        self.create_action(
            "properties", self.__properties, ("<alt>Return", "<primary>i")
        )

        self.create_action("home", self.__go_home, ("<alt>Home",))
        self.create_action(
            "toggle-path-entry", self.__toggle_path_entry, ("F6", "<primary>l")
        )
        self.create_action("hide-path-entry", self.__hide_path_entry)
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
        self.create_action("empty-trash", self.__empty_trash)
        self.create_action("clear-recents", self.__clear_recents)

        self.create_action("edit-sidebar", self.__edit_sidebar)
        self.create_action("end-edit-sidebar", self.__end_edit_sidebar)

        # Connect signals
        self.sidebar.connect("row-activated", self.__row_activated)
        self.new_tag_box.connect("row-activated", self.__new_tag)
        self.trash_box.connect("row-activated", self.__open_trash)

        self.tab_view.connect("notify::selected-page", self.__tab_changed)
        self.tab_view.connect("create-window", self.__create_window)
        self.tab_overview.connect("create-tab", self.__create_tab)

        self.search_entry.connect("search-started", self.__show_search_entry)
        self.search_entry.connect("search-changed", self.__search_changed)
        self.search_entry.connect("stop-search", self.__hide_search_entry)
        self.search_entry.connect("activate", self.__search_activate)
        self.search_button.connect("clicked", self.__toggle_search_entry)

        self.path_entry.connect("hide-entry", self.__hide_path_entry)

        shared.postmaster.connect("tags-changed", self.__update_tags)
        shared.postmaster.connect("sidebar-edited", self.__sidebar_edited)
        shared.postmaster.connect(
            "trash-emptied", lambda *_: self.trash_empty_animation.play()
        )
        shared.postmaster.connect("view-changed", self.__view_changed)
        self.__view_changed()

        self.right_click_menu.connect("closed", self.__set_actions)
        self.__set_actions()

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
        self.sidebar_tag_rows = set()
        self.__update_tags()

        self.__trash_changed()
        shared.trash_list.connect("notify::n-items", self.__trash_changed)

        # Set up sidebar actions
        self.sidebar_rows = {
            # TODO: Hide this if file history is disabled system-wide
            self.recent_row: Gio.File.new_for_uri("recent://"),
            self.home_row: shared.home,
            self.trash_row: Gio.File.new_for_uri("trash://"),
        }

        for widget, gfile in self.sidebar_rows.items():
            (right_click := Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)).connect(
                "pressed", self.__sidebar_right_click, gfile
            )

            (middle_click := Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)).connect(
                "pressed", self.__sidebar_middle_click, gfile
            )

            widget.add_controller(right_click)
            widget.add_controller(middle_click)

        # Drag and drop
        self.drop_target = Gtk.DropTarget.new(
            GObject.TYPE_NONE, Gdk.DragAction.COPY | Gdk.DragAction.MOVE
        )
        self.drop_target.set_gtypes((Gdk.Texture, Gdk.FileList, str))
        self.drop_target.connect("drop", self.__drop)
        self.tab_view.add_controller(self.drop_target)

    def send_toast(self, message: str, undo: bool = False) -> None:
        """Displays a toast with the given message and optionally an undo button in the window."""
        toast = Adw.Toast.new(message)
        toast.set_priority(Adw.ToastPriority.HIGH)
        toast.set_use_markup(False)
        if undo:
            toast.set_button_label(_("Undo"))
        self.toast_overlay.add_toast(toast)

        return toast

    def new_page(self, *args, **kwargs) -> None:
        """
        Open a new page with the given file or tag.

        All arguments are passed to `HypNavigationBin.new_page()` directly.
        """
        self.get_nav_bin().new_page(*args, **kwargs)

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
        if gfile and (
            gfile.query_file_type(Gio.FileQueryInfoFlags.NONE) != Gio.FileType.DIRECTORY
        ):
            logging.error(
                "Cannot open new window, %s is not a directory.", gfile.get_uri()
            )
            return

        self.get_application().do_activate(gfile, tags)

    def get_nav_bin(self) -> HypNavigationBin:
        """Returns the currently visible HypNavigationBin."""
        return self.tab_view.get_selected_page().get_child()

    def get_visible_page(self) -> HypItemsPage:
        """Return the currently visible HypItemsPage."""
        return self.get_nav_bin().view.get_visible_page()

    def zoom_in(self, *_args: Any) -> None:
        """Increases the zoom level of all views."""
        key = "grid-zoom-level" if shared.grid_view else "list-zoom-level"
        max_zoom_level = 5

        if (zoom_level := shared.state_schema.get_uint(key)) >= max_zoom_level:
            return

        shared.state_schema.set_uint(key, (zoom_level := zoom_level + 1))
        self.update_zoom(zoom_level)

    def zoom_out(self, *_args: Any) -> None:
        """Decreases the zoom level of all views."""
        key = "grid-zoom-level" if shared.grid_view else "list-zoom-level"

        # The minimum zoom level is 1 for grid and 0 for list view
        min_zoom_level = 0 + int(shared.grid_view)

        if (zoom_level := shared.state_schema.get_uint(key)) <= min_zoom_level:
            return

        shared.state_schema.set_uint(key, (zoom_level := zoom_level - 1))
        self.update_zoom(zoom_level)

    def update_zoom(self, zoom_level: Optional[int] = None) -> None:
        """
        Update the zoom level of all items in the navigation stack

        If `zoom-level` is not provided, it will be read from dconf.
        """

        shared.postmaster.emit(
            "zoom",
            zoom_level
            or shared.state_schema.get_uint(
                "grid-zoom-level" if shared.grid_view else "list-zoom-level"
            ),
        )

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

    def show_path_entry(self) -> None:
        """Shows the path entry in the header bar."""
        self.__title_stack_set_child(self.path_entry_clamp)

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
            "clear-recents": self,
            "new-folder": page,
            "new-file": page,
            "select-all": page,
            "open": page,
            "open-new-tab": page,
            "open-new-window": page,
            "open-with": page,
            "properties": self,
        }

        for action, group in actions.items():
            group.lookup_action(action).set_enabled(action in menu_items)

    def __properties(self, *_args: Any) -> None:
        page = self.get_visible_page()

        gfiles = (
            [page.gfile]
            if page.view_right_clicked and page.gfile
            else page.get_selected_gfiles()
        )
        page.view_right_clicked = False

        if (
            not gfiles
        ):  # If the keyboard shortcut was triggered, but no items are selected
            if page.gfile:
                gfiles = [page.gfile]
            else:
                return

        # TODO: Allow viewing properties of multiple files
        properties = HypPropertiesWindow(gfiles[0])
        properties.set_transient_for(self)
        properties.present()

    def __update_tags(self, *_args: Any) -> None:
        for tag_row in self.sidebar_tag_rows:
            self.sidebar.remove(tag_row)

        self.sidebar_tag_rows = set()

        for tag_row in reversed(shared.tags):
            self.sidebar_tag_rows.add(
                row := HypTagRow(tag_row, "user-bookmarks-symbolic")
            )
            self.sidebar.insert(row, 2)

    def __new_tag(self, *_args: Any) -> None:
        (preferences_group := Adw.PreferencesGroup(width_request=360)).add(
            entry := Adw.EntryRow(title=_("Name"))
        )

        def add_tag(*_args: Any) -> None:
            dialog.close()

            if (
                # Replace characters that wouldn't be valid with similar ones
                text := entry.get_text()
                .strip()
                .replace("/", "⧸")
                .replace("\n", " ")
            ) in shared.tags:
                self.send_toast(_("A category named “{}” already exists").format(text))
                return

            if text in (".", ".."):
                self.send_toast(_("A category cannot be called {}").format(f"“{text}”"))
                return

            add_tags(text)

        dialog = create_message_dialog(
            self,
            _("New Category"),
            (_("Cancel"), None, None, None, False),
            (_("Add"), None, Adw.ResponseAppearance.SUGGESTED, add_tag, True),
            body=_(
                "Existing folders with the same name will be added to the category."
            ),
            extra_child=preferences_group,
        )

        entry.connect("entry-activated", add_tag)
        dialog.choose()

    def __open_trash(self, *_args: Any) -> None:
        if self.overlay_split_view.get_collapsed():
            self.overlay_split_view.set_show_sidebar(False)

        self.new_page(Gio.File.new_for_uri("trash://"))

    def __row_activated(self, _box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        if self.overlay_split_view.get_collapsed():
            self.overlay_split_view.set_show_sidebar(False)

        if (child := row) == self.home_row:
            self.new_page(shared.home)
            return

        if child == self.recent_row:
            self.new_page(Gio.File.new_for_uri("recent://"))
            return

        self.new_page(tag=row.tag)

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
            case self.path_entry_clamp:
                if self.path_entry_connection:
                    self.path_entry.disconnect(self.path_entry_connection)
                    self.path_entry_connection = None

        match new:
            case self.search_entry_clamp:
                self.search_button.set_active(True)
                self.searched_page = self.get_visible_page()

                self.set_focus(self.search_entry)
            case self.path_entry_clamp:
                page = self.get_visible_page()
                self.path_entry.new_path(page.gfile, page.tags)

                self.path_entry.select_region(0, -1)
                self.set_focus(self.path_entry)
                self.path_entry_connection = self.path_entry.connect(
                    "notify::has-focus", self.__path_entry_focus
                )
            case self.path_bar_clamp:
                self.set_focus(self.get_visible_page().view)

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

        self.__title_stack_set_child(self.path_bar_clamp)

    def __search_activate(self, *_args: Any) -> None:
        self.get_visible_page().activate(None, 0)

    def __search_changed(self, entry: Gtk.SearchEntry) -> None:
        shared.search = entry.get_text().strip()
        self.searched_page.item_filter.changed(Gtk.FilterChange.DIFFERENT)

    def __hide_path_entry(self, *_args: Any) -> None:
        if self.title_stack.get_visible_child() != self.path_entry_clamp:
            return

        self.__title_stack_set_child(self.path_bar_clamp)

    def __toggle_path_entry(self, *_args: Any) -> None:
        if self.title_stack.get_visible_child() != self.path_entry_clamp:
            self.show_path_entry()
            return

        self.__hide_path_entry()

    def __path_entry_focus(self, entry: Gtk.Entry, *_args: Any) -> None:
        if not entry.has_focus():
            self.__hide_path_entry()

    def __go_home(self, *_args: Any) -> None:
        self.new_page(shared.home)

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
        shared.state_schema.reset(
            "grid-zoom-level" if shared.grid_view else "list-zoom-level"
        )
        self.update_zoom()

    def __reload(self, *_args: Any) -> None:
        self.get_visible_page().reload()

    def __create_window(self, *_args: Any) -> Adw.TabView:
        win = self.get_application().do_activate()

        # Close the initial Home tab
        win.tab_view.close_page(win.tab_view.get_selected_page())
        return win.tab_view

    def __create_tab(self, *_args: Any) -> Adw.TabPage:
        page = self.tab_view.append(HypNavigationBin(initial_gfile=shared.home))

        page.set_title(_("Home"))
        return page

    def __open_sidebar(self, *_args: Any) -> None:
        self.new_page(shared.right_clicked_file)

    def __open_new_tab_sidebar(self, *_args: Any) -> None:
        self.new_tab(shared.right_clicked_file)

    def __open_new_window_sidebar(self, *_args: Any) -> None:
        self.new_window(shared.right_clicked_file)

    def __properties_sidebar(self, *_args: Any) -> None:
        properties = HypPropertiesWindow(shared.right_clicked_file)
        properties.set_transient_for(self)
        properties.present()

    def __open_tag(self, *_args: Any) -> None:
        self.new_page(tag=self.right_clicked_tag)

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
        self.send_toast(_("{} removed").format(f"“{self.right_clicked_tag}”"))

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
                "clear-recents",
                "new-folder",
                "new-file",
                "select-all",
                "open",
                "open-new-tab",
                "open-new-window",
                "open-with",
                "properties",
            }
        )

    def __nav_stack_changed(self) -> None:
        page = self.get_visible_page()

        self.path_bar.update(page.gfile, page.tags)

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
        self.trash_row.icon_name = (
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

        item = page.items[position]
        self.rename_popover.set_parent(item)

        if item.is_dir:
            self.rename_label.set_label(_("Rename Folder"))
        else:
            self.rename_label.set_label(_("Rename File"))

        self.rename_entry.set_text(item.edit_name)

        self.rename_popover.popup()
        self.rename_entry.select_region(0, len(item.stem))
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

    def __view_changed(self, *_args: Any) -> None:
        for button in (self.header_bar_view_button, self.action_bar_view_button):
            button.set_icon_name(
                "view-grid-symbolic" if shared.grid_view else "view-list-symbolic"
            )

    def __sidebar_right_click(
        self, gesture: Gtk.GestureClick, _n: int, x: float, y: float, gfile: Gio.File
    ) -> None:
        shared.right_clicked_file = gfile

        self.lookup_action("empty-trash").set_enabled(
            gfile.get_uri() == "trash:///" and shared.trash_list.get_n_items()
        )
        self.lookup_action("clear-recents").set_enabled(
            gfile.get_uri() == "recent:///" and bool(shared.recent_manager.get_items())
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

    def __empty_trash(self, *_args: Any) -> None:
        create_message_dialog(
            self,
            _("Empty all Items From Trash?"),
            (_("Cancel"), None, None, None, False),
            (
                _("Empty Trash"),
                None,
                Adw.ResponseAppearance.DESTRUCTIVE,
                empty_trash,
                True,
            ),
            body=_("All items in the Trash will be permanently deleted."),
        ).choose()

    def __clear_recents(self, *_args: Any) -> None:
        clear_recent_files()

    def __edit_sidebar(self, *_args: Any) -> None:
        self.sidebar_action_bar.set_revealed(True)

        for row in chain(
            self.sidebar_rows, self.sidebar_tag_rows, self.volumes_box.rows.values()
        ):
            row.start_edit()

    def __end_edit_sidebar(self, *_args: Any) -> None:
        self.sidebar_action_bar.set_revealed(False)

        for row in chain(
            self.sidebar_rows, self.sidebar_tag_rows, self.volumes_box.rows.values()
        ):
            row.end_edit()

        shared.postmaster.emit("sidebar-edited")

    def __sidebar_edited(self, win: Self) -> None:
        if win == self:
            return

        for row in chain(
            self.sidebar_rows, self.sidebar_tag_rows, self.volumes_box.rows.values()
        ):
            row.set_active()

    def __drop(
        self,
        drop_target: Gtk.DropTarget,
        value: Gdk.Texture | Gdk.FileList | str,
        _x: float,
        _y: float,
    ):
        page = self.get_visible_page()
        page.multi_selection.unselect_all()

        if page.gfile and not page.gfile.query_info(
            Gio.FILE_ATTRIBUTE_ACCESS_CAN_WRITE, Gio.FileQueryInfoFlags.NONE
        ).get_attribute_boolean(Gio.FILE_ATTRIBUTE_ACCESS_CAN_WRITE):
            self.send_toast(_("The location is not writable"))
            return False

        if isinstance(value, Gdk.FileList):
            dst = self.get_visible_page().get_dst()
            for src in value:
                uri = src.get_uri()

                if uri == dst.get_uri():
                    self.send_toast(_("You cannot move a folder into itself"))
                    return False

                try:
                    child = dst.get_child_for_display_name(get_gfile_display_name(src))
                except GLib.Error:
                    return False

                if uri == child.get_uri():
                    return False

            self.__drop_file_list(
                value,
                drop_target.get_current_drop().get_drag().get_selected_action()
                if drop_target.get_current_drop().get_drag()
                else Gdk.DragAction.COPY,
            )
            return True

        if isinstance(value, Gdk.Texture):
            GLib.Thread.new(None, self.__drop_texture, value)
            return True

        if isinstance(value, str):
            self.__drop_text(value)
            return True

        return False

    def __drop_file_list(self, file_list: Gdk.FileList, action: Gdk.DragAction) -> None:
        # TODO: This is copy-paste from HypItemsPage.__paste()
        dst = self.get_visible_page().get_dst()
        move = action == Gdk.DragAction.MOVE

        files = []

        for src in file_list:
            try:
                if not (
                    child := dst.get_child_for_display_name(get_gfile_display_name(src))
                ):
                    continue
            except GLib.Error:
                continue
            else:
                try:
                    copy(src, child)
                except FileExistsError:
                    try:
                        copy(src, get_copy_gfile(child))
                    except (FileExistsError, FileNotFoundError):
                        continue

                files.append((src, child) if move else child)

        shared.undo_queue[time()] = ("move" if move else "copy", files)

    def __drop_texture(self, texture: Gdk.Texture) -> None:
        # TODO: Again, copy-paste from HypItemsPage.__paste()
        dst = self.get_visible_page().get_dst()

        texture_bytes = texture.save_to_png_bytes()

        dst = dst.get_child_for_display_name(_("Dropped Image") + ".png")

        if dst.query_exists():
            dst = get_copy_gfile(dst)
            try:
                stream = dst.create_readwrite(Gio.FileCreateFlags.NONE)
            except GLib.Error:
                return
        else:
            try:
                stream = dst.create_readwrite(Gio.FileCreateFlags.NONE)
            except GLib.Error:
                return

        output = stream.get_output_stream()
        output.write_bytes(texture_bytes)

    def __drop_text(self, text: str) -> None:
        # TODO: Again again, copy-paste from HypItemsPage.__paste()
        if not text:  # If text is an empty string
            return

        dst = self.get_visible_page().get_dst()

        dst = dst.get_child_for_display_name(_("Dropped Text") + ".txt")

        if dst.query_exists():
            dst = get_copy_gfile(dst)
            try:
                stream = dst.create_readwrite(Gio.FileCreateFlags.NONE)
            except GLib.Error:
                return
        else:
            try:
                stream = dst.create_readwrite(Gio.FileCreateFlags.NONE)
            except GLib.Error:
                return

        output = stream.get_output_stream()
        output.write(text.encode("utf-8"))
