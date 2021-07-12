# -*- coding: utf-8 -*-
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
"""Test the function that save and/or show a Matplotlib figure."""
from unittest.mock import patch

import pytest
from matplotlib import pyplot as plt

from gemseo.utils.matplotlib_figure import save_show_figure


@pytest.mark.parametrize("file_path", [None, "file_name.pdf"])
@pytest.mark.parametrize("show", [True, False])
def test_process(tmp_path, pyplot_close_all, file_path, show):
    """Verify that a Matplotlib figure is correctly saved."""
    fig, axes = plt.subplots()

    if file_path is not None:
        file_path = tmp_path / file_path

    with patch("matplotlib.pyplot.savefig"), patch("matplotlib.pyplot.show"):
        save_show_figure(fig, show, file_path)

    if file_path is not None:
        assert file_path.exists()

    plt.fignum_exists(fig.number)
