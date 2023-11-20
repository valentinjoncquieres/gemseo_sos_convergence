# Copyright 2021 IRT Saint Exupéry, https://www.irt-saintexupery.com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""Benchmark for hashing data."""

from __future__ import annotations

import compare_data

from gemseo.utils.hash import hash_data


class Benchmark(compare_data.Benchmark):
    """Benchmark for hashing data."""

    def _benchmark(self) -> None:
        hash_data(self._data.data)

    def __str__(self) -> str:
        return f"{self._data.items_nb}-{self._data.keys_nb}-{self._data.depth}"


if __name__ == "__main__":
    Benchmark().run()
