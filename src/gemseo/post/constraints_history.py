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
#    INITIAL AUTHORS - API and implementation and/or documentation
#        :author: Pierre-Jean Barjhoux
#    OTHER AUTHORS   - MACROSCOPIC CHANGES
"""A matrix of constraint history plots."""
from __future__ import annotations

from math import ceil
from typing import Sequence

from matplotlib import pyplot
from matplotlib.ticker import MaxNLocator
from numpy import abs as np_abs
from numpy import arange
from numpy import atleast_2d
from numpy import atleast_3d
from numpy import diff
from numpy import flip
from numpy import interp
from numpy import max as np_max
from numpy import sign
from numpy import where

from gemseo.algos.opt_problem import OptimizationProblem
from gemseo.post.core.colormaps import PARULA
from gemseo.post.core.colormaps import RG_SEISMIC
from gemseo.post.opt_post_processor import OptPostProcessor
from gemseo.utils.compatibility.matplotlib import SymLogNorm


class ConstraintsHistory(OptPostProcessor):
    """A matrix of constraint history plots.

    A blue line represents the values of a constraint w.r.t. the iterations.

    A background color indicates
    whether the constraint is satisfied (green), active (white) or violated (red).

    A vertical black line indicates the last iteration (or pseudo-iteration)
    where the constraint is (or should be) active.
    """

    DEFAULT_FIG_SIZE = (11.0, 11.0)

    def __init__(  # noqa:D107
        self,
        opt_problem: OptimizationProblem,
    ) -> None:
        super().__init__(opt_problem)
        self.cmap = PARULA
        self.ineq_cstr_cmap = RG_SEISMIC
        self.eq_cstr_cmap = "seismic"

    def _plot(
        self,
        constraint_names: Sequence[str],
    ) -> None:
        """
        Args:
            constraint_names: The names of the constraints.

        Raises:
            ValueError: When an element of ``constraint_names`` is not a function name.
        """  # noqa: D205, D212, D415
        all_constraint_names = self.opt_problem.constraint_names.keys()
        for constraint_name in constraint_names:
            if constraint_name not in all_constraint_names:
                raise ValueError(
                    "Cannot build constraints history plot, "
                    f"function {constraint_name} is not among the constraints names "
                    "or does not exist."
                )

        constraint_names = self.opt_problem.get_function_names(constraint_names)
        constraint_history, constraint_names, _ = self.database.get_history_array(
            constraint_names, add_dv=False
        )

        # harmonization of tables format because constraints can be vectorial
        # or scalars. *vals.shape[0] = iteration, *vals.shape[1] = cstr values
        constraint_history = atleast_3d(constraint_history)
        constraint_history = constraint_history.reshape(
            (
                constraint_history.shape[0],
                constraint_history.shape[1] * constraint_history.shape[2],
            )
        )

        # prepare the main window
        fig, axes = pyplot.subplots(
            nrows=ceil(len(constraint_names) / 2),
            ncols=2,
            sharex=True,
            figsize=self.DEFAULT_FIG_SIZE,
        )

        fig.suptitle("Evolution of the constraints w.r.t. iterations", fontsize=14)

        iterations = arange(len(constraint_history))
        # for each subplot
        for history, name, axe in zip(
            constraint_history.T, constraint_names, axes.ravel()
        ):
            # prepare the graph
            axe.grid(True)
            axe.set_title(name)
            axe.xaxis.set_major_locator(MaxNLocator(integer=True))
            axe.axhline(0.0, color="k", linewidth=2)

            # plot values in lines
            axe.plot(iterations, history)

            # Plot color bars
            maximum = np_max(np_abs(history))
            axe.imshow(
                atleast_2d(history),
                cmap=self.ineq_cstr_cmap,
                interpolation="nearest",
                aspect="auto",
                norm=SymLogNorm(linthresh=1.0, vmin=-maximum, vmax=maximum),
                alpha=0.6,
            )

            # Plot a vertical line at the last iteration (or pseudo-iteration)
            # where the constraint is (or should be) active.
            indices_before_sign_change = where(diff(sign(history)))[0]
            if indices_before_sign_change.size != 0:
                index_before_last_sign_change = indices_before_sign_change[-1]
                indices = [
                    index_before_last_sign_change,
                    index_before_last_sign_change + 1,
                ]
                constraint_values = history[indices]
                iteration_values = iterations[indices]
                if constraint_values[1] < constraint_values[0]:
                    constraint_values = flip(constraint_values)
                    iteration_values = flip(iteration_values)

                axe.axvline(
                    interp(0.0, constraint_values, iteration_values),
                    color="k",
                    linewidth=2,
                )

        self._add_figure(fig)
