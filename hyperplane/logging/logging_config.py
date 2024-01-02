# logging_config.py
#
# Copyright 2023 Geoffrey Coulaud
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

"""Configures application-wide logging."""
from logging import config


def logging_config() -> None:
    """Configures application-wide logging."""
    config.dictConfig(
        {
            "version": 1,
            "formatters": {
                "console_formatter": {
                    "format": "%(levelname)s - %(message)s",
                    "class": "hyperplane.logging.color_log_formatter.ColorLogFormatter",
                },
            },
            "handlers": {
                "console_handler": {
                    "class": "logging.StreamHandler",
                    "formatter": "console_formatter",
                    "level": "DEBUG",
                },
            },
            "root": {
                "level": "NOTSET",
                "handlers": ["console_handler"],
            },
        }
    )
