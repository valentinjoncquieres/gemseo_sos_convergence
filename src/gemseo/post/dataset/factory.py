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
# Contributors:
#    INITIAL AUTHORS - initial API and implementation and/or initial
#                           documentation
#        :author: Matthias De Lozzo
#    OTHER AUTHORS   - MACROSCOPIC CHANGES
"""A factory of dataset plot."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from gemseo.datasets.dataset import Dataset

from gemseo.core.base_factory import BaseFactory
from gemseo.post.dataset.dataset_plot import DatasetPlot


class DatasetPlotFactory(BaseFactory[DatasetPlot]):
    """A factory of dataset plot."""

    _CLASS = DatasetPlot
    _MODULE_NAMES = ("gemseo.post.dataset",)

    def create(
        self,
        plot_name: str,
        dataset: Dataset,
        **options: Any,
    ) -> DatasetPlot:
        """Create a plot for dataset.

        Args:
            plot_name: The name of a plot method for dataset (its class name).
            dataset: The dataset to visualize.
            **options: The additional options specific to this plot method.

        Returns:
            A plot method built from the provided dataset.
        """
        return super().create(plot_name, dataset=dataset, **options)

    @property
    def plots(self) -> list[str]:
        """The available plot methods for dataset."""
        return self.class_names
