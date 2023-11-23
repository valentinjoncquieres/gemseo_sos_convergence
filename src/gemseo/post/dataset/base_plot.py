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
"""A base plot class."""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Iterable
from typing import NamedTuple

from gemseo.utils.file_path_manager import FilePathManager
from gemseo.utils.metaclasses import ABCGoogleDocstringInheritanceMeta
from gemseo.utils.string_tools import repr_variable

if TYPE_CHECKING:
    from gemseo.datasets.dataset import Dataset
    from gemseo.post.dataset.plot_settings import PlotSettings


class BasePlot(metaclass=ABCGoogleDocstringInheritanceMeta):
    """A base plot class.

    A :class:`.DatasetPlot` defines a graphical concept
    (e.g. radar chart, lines, etc.)
    while a :class:`.BasePlot` with the same class name implements this concept
    from a visualization library.

    The graphical concept uses both common settings
    (e.g. figure size, colors, x-label, etc.)
    and specific ones
    (e.g. bar width for a bar plot, radial ticks for a radar chart, etc.).
    """

    _common_dataset: Dataset
    """The dataset passed to the :class:`.DatasetPlot`."""

    _common_settings: PlotSettings
    """The settings common to many plot classes."""

    _specific_settings: NamedTuple
    """The settings specific to this plot class."""

    _file_path_manager: FilePathManager
    """The manager of figure file paths."""

    def __init__(
        self,
        dataset: Dataset,
        common_settings: PlotSettings,
        specific_settings: NamedTuple,
        *specific_data: Any,
        **engine_parameters: Any,
    ) -> None:
        """
        Args:
            dataset: The dataset passed to the :class:`.DatasetPlot`.
                To be used when an information item is missing in ``*specific_data``.
            common_settings: The settings common to many plot classes.
            specific_settings: The settings specific to this plot class.
            *specific_data: The data specific to this plot class.
            **engine_parameters: The parameters specific to the plot engine.
        """  # noqa:  D205 D212 D415
        self._common_dataset = dataset
        self._common_settings = common_settings
        self._specific_settings = specific_settings
        self._file_path_manager = FilePathManager(
            FilePathManager.FileType.FIGURE,
            default_name=FilePathManager.to_snake_case(self.__class__.__name__),
        )

    @property
    @abstractmethod
    def figures(self) -> list[Any]:
        """The figures."""

    @abstractmethod
    def show(self) -> None:
        """Display the plot."""

    def save(
        self,
        file_path: str | Path,
        directory_path: str | Path,
        file_name: str,
        file_format: str,
    ) -> tuple[str]:
        """Save the plot on the disk."""
        if file_path:
            file_path = Path(file_path)

        file_path = self._file_path_manager.create_file_path(
            file_path=file_path,
            directory_path=directory_path,
            file_name=file_name,
            file_extension=file_format,
        )
        return self._save(file_path)

    @abstractmethod
    def _save(self, file_path: str | Path) -> tuple[str]:
        """Save the plot on the disk."""

    @classmethod
    def _stringify_color(cls, color: str | tuple[float, float, float, float]) -> str:
        """Cast a color to string.

        Args:
            color: The name of a color or its RGBA code with percentages.

        Returns:
            The color.
        """
        if isinstance(color, str):
            return color

        r, g, b, a = color
        return f"rgba({int(r * 255)},{int(g * 255)},{int(b * 255)},{a})"

    def _get_variable_names(
        self,
        dataset_columns: Iterable[tuple],
    ) -> list[str]:
        """Return the names of the variables from the columns of a pandas DataFrame.

        Args:
            dataset_columns: The columns of a :class:`.Dataset`.

        Returns:
            The names of the variables.
        """
        variable_names = []
        for dataset_column in dataset_columns:
            name = dataset_column[1]
            variable_names.append(
                repr_variable(
                    name,
                    dataset_column[2],
                    self._common_dataset.variable_names_to_n_components[name],
                )
            )

        return variable_names