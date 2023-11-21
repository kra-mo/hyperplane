# iterplane.py
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

from pathlib import Path
from typing import Generator, Iterable

from hyperplane import shared


def iterplane(filter_tags: Iterable[str]) -> Generator:
    if not filter_tags:
        return

    tags = {tag: tag in filter_tags for tag in shared.tags}

    yield from __walk(shared.home, tags)


def __walk(node: Path, tags: dict[str:bool]) -> Generator:
    if tags.get(node.name):
        tags.pop(node.name)

    if not sum(tags.values()):
        for child in node.iterdir():
            if child.is_dir():
                # TODO: This is probably not optimal
                if (
                    tuple(
                        tag
                        for tag in shared.tags
                        if tag
                        in (relative_parts := child.relative_to(shared.home).parts)
                    )
                    != relative_parts
                ):
                    yield child
            else:
                yield child

    # TODO: Use Path.walk in Python 3.12
    for child in node.iterdir():
        if not child.is_dir():
            continue
        new_tags = tags
        for tag, value in tags.copy().items():
            if not value:
                if child.name == tag:
                    yield tag
                    new_tags[tag] = True
                    yield from __walk(child, new_tags.copy())
            else:
                if child.name == tag:
                    yield from __walk(child, new_tags.copy())
                else:
                    break
