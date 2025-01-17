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
"""A factory of sensitivity analyses."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from gemseo.core.base_factory import BaseFactory
from gemseo.uncertainty.sensitivity.base_sensitivity_analysis import (
    BaseSensitivityAnalysis,
)
from gemseo.utils.constants import READ_ONLY_EMPTY_DICT

if TYPE_CHECKING:
    from collections.abc import Collection
    from collections.abc import Iterable
    from collections.abc import Mapping

    from gemseo.algos.driver_library import DriverLibraryOptionType
    from gemseo.algos.parameter_space import ParameterSpace
    from gemseo.core.discipline import MDODiscipline


class SensitivityAnalysisFactory(BaseFactory):
    """A factory of sensitivity analyses."""

    _CLASS = BaseSensitivityAnalysis
    _MODULE_NAMES = ("gemseo.uncertainty.sensitivity",)

    def create(
        self,
        sensitivity_analysis: str,
        disciplines: Collection[MDODiscipline],
        parameter_space: ParameterSpace,
        n_samples: int | None = None,
        output_names: Iterable[str] = (),
        algo: str = "",
        algo_options: Mapping[str, DriverLibraryOptionType] = READ_ONLY_EMPTY_DICT,
        formulation: str = "MDF",
        **formulation_options: Any,
    ) -> BaseSensitivityAnalysis:
        """Create the sensitivity analysis.

        Args:
            sensitivity_analysis: The name of a class
                defining a sensitivity analysis.
            disciplines: The discipline or disciplines to use for the analysis.
            parameter_space: A parameter space.
            n_samples: A number of samples.
                If ``None``, the number of samples is computed by the algorithm.
            output_names: The disciplines' outputs to be considered for the analysis.
                If empty, use all the outputs.
            algo: The name of the DOE algorithm.
                If empty, use the :attr:`.BaseSensitivityAnalysis.DEFAULT_DRIVER`.
            algo_options: The options of the DOE algorithm.
            formulation: The name of the :class:`.MDOFormulation` to sample the
                disciplines.
            **formulation_options: The options of the :class:`.MDOFormulation`.

        Returns:
            A sensitivity analysis.
        """
        return super().create(
            sensitivity_analysis,
            disciplines=disciplines,
            parameter_space=parameter_space,
            n_samples=n_samples,
            output_names=output_names,
            algo=algo,
            algo_options=algo_options,
            formulation=formulation,
            **formulation_options,
        )

    @property
    def available_sensitivity_analyses(self) -> list[str]:
        """The available classes for sensitivity analysis."""
        return self.class_names
