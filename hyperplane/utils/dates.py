# dates.py
#
# Copyright 2022-2024 kramo
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

"""Miscellaneous utilities for working with dates."""
from typing import Any

from gi.repository import GLib


def relative_date(
    date_time: GLib.DateTime,
) -> Any:  # pylint: disable=too-many-return-statements
    """Gets a relative date (compared to now) for a `GDateTime`."""

    # Return "-" instead of 1970
    if not date_time.to_unix():
        return "-"

    n_days = GLib.DateTime.new_now_utc().difference(date_time) / 86400000000

    if n_days == 0:
        return _("Today")
    if n_days == 1:
        return _("Yesterday")
    if n_days <= (day_of_week := date_time.get_day_of_week()):
        return date_time.format("%A")
    if n_days <= day_of_week + 7:
        return _("Last Week")
    if n_days <= (day_of_month := date_time.get_day_of_month()):
        return _("This Month")
    if n_days <= day_of_month + 30:
        return _("Last Month")
    if n_days < (day_of_year := date_time.get_day_of_year()):
        return date_time.format("%B")
    if n_days <= day_of_year + 365:
        return _("Last Year")
    return date_time.format("%Y")
