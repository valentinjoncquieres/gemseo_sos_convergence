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
#        :author: Francois Gallard
#    OTHER AUTHORS   - MACROSCOPIC CHANGES
#        :author: Benoit Pauwels - Stacked data management
#               (e.g. iteration index)
#        :author: Gilberto Ruiz Jimenez
"""An MDOFunction subclass to support formulations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from numpy import isnan

from gemseo.algos.database import Database
from gemseo.algos.stop_criteria import DesvarIsNan
from gemseo.algos.stop_criteria import FunctionIsNan
from gemseo.algos.stop_criteria import MaxIterReachedException
from gemseo.core.mdofunctions.mdo_function import MDOFunction

if TYPE_CHECKING:
    from gemseo.algos.optimization_problem import OptimizationProblem
    from gemseo.typing import NumberArray


class NormDBFunction(MDOFunction):
    """An :class:`.MDOFunction` object to be evaluated from a database."""

    def __init__(
        self,
        orig_func: MDOFunction,
        normalize: bool,
        is_observable: bool,
        optimization_problem: OptimizationProblem,
    ) -> None:
        """
        Args:
            orig_func: The original function to be wrapped.
            normalize: If ``True``, then normalize the function's input vector.
            is_observable: If ``True``, new_iter_listeners are not called
                when function is called (avoid recursive call).
            optimization_problem: The optimization problem object that contains
                the function.
        """  # noqa: D205, D212, D415
        self.__orig_func = orig_func
        self.__is_observable = is_observable
        self.__optimization_problem = optimization_problem

        # For performance
        design_space = self.__optimization_problem.design_space
        self.__unnormalize_vect = design_space.unnormalize_vect
        # self.__round_vect = design_space.round_vect
        self.__unnormalize_grad = design_space.unnormalize_grad
        self.__evaluate_orig_func = self.__orig_func.evaluate
        self.__jac_orig_func = orig_func.jac
        self.__is_max_iter_reached = self.__optimization_problem.is_max_iter_reached

        super().__init__(
            self._func_to_wrap,
            orig_func.name,
            jac=self._jac_to_wrap,
            f_type=orig_func.f_type,
            expr=orig_func.expr,
            input_names=orig_func.input_names,
            dim=orig_func.dim,
            output_names=orig_func.output_names,
            special_repr=orig_func.special_repr,
            original_name=orig_func.original_name,
            expects_normalized_inputs=normalize,
        )

    def _func_to_wrap(self, x_vect: NumberArray) -> NumberArray:
        """Compute the function to be passed to the optimizer.

        Args:
            x_vect: The value of the design variables.

        Returns:
            The evaluation of the function for this value of the design variables.

        Raises:
            DesvarIsNan: If the design variables contain a NaN value.
            FunctionIsNan: If a function returns a NaN value when evaluated.
            MaxIterReachedException: If the maximum number of iterations has been
                reached.
        """
        # TODO: Add a dedicated function check_has_nan().
        if isnan(x_vect).any():
            msg = f"Design Variables contain a NaN value: {x_vect}"
            raise DesvarIsNan(msg)
        normalize = self.expects_normalized_inputs
        if normalize:
            xn_vect = x_vect
            xu_vect = self.__unnormalize_vect(xn_vect)
        else:
            xu_vect = x_vect
            xn_vect = None
        # For performance, hash once, and reuse in get/store methods
        database = self.__optimization_problem.database
        hashed_xu = database.get_hashable_ndarray(xu_vect)
        # try to retrieve the evaluation
        value = database.get_function_value(self.name, hashed_xu)

        if value is None:
            if not database.get(hashed_xu) and self.__is_max_iter_reached():
                raise MaxIterReachedException

            # if not evaluated yet, evaluate
            if normalize:
                value = self.__evaluate_orig_func(xn_vect)
            else:
                value = self.__evaluate_orig_func(xu_vect)
            if self.__optimization_problem.stop_if_nan and isnan(value).any():
                msg = f"The function {self.name} is NaN for x={xu_vect}"
                raise FunctionIsNan(msg)
            # store (x, f(x)) in database
            database.store(hashed_xu, {self.name: value})

        return value

    def _jac_to_wrap(self, x_vect: NumberArray) -> NumberArray:
        """Compute the gradient of the function to be passed to the optimizer.

        Args:
            x_vect: The value of the design variables.

        Returns:
            The evaluation of the gradient for this value of the design variables.

        Raises:
            FunctionIsNan: If the design variables contain a NaN value.
                If the evaluation of the jacobian results in a NaN value.
        """
        # TODO: Add a dedicated function check_has_nan().
        if isnan(x_vect).any():
            msg = f"Design Variables contain a NaN value: {x_vect}"
            raise FunctionIsNan(msg)
        normalize = self.expects_normalized_inputs
        if normalize:
            xn_vect = x_vect
            xu_vect = self.__unnormalize_vect(xn_vect)
        else:
            xu_vect = x_vect
            xn_vect = None

        database = self.__optimization_problem.database
        design_space = self.__optimization_problem.design_space

        # try to retrieve the evaluation
        jac_u = database.get_function_value(
            Database.get_gradient_name(self.name), xu_vect
        )
        if jac_u is None:
            if not database.get(xu_vect) and self.__is_max_iter_reached():
                raise MaxIterReachedException

            # if not evaluated yet, evaluate
            if self.expects_normalized_inputs:
                jac_n = self.__jac_orig_func(xn_vect)
                jac_u = self.__unnormalize_grad(jac_n)
            else:
                jac_u = self.__jac_orig_func(xu_vect)
                jac_n = None
            if isnan(jac_u.data).any() and self.__optimization_problem.stop_if_nan:
                msg = f"Function {self.name}'s Jacobian is NaN for x={xu_vect}"
                raise FunctionIsNan(msg)
            func_name_to_value = {Database.get_gradient_name(self.name): jac_u}
            # store (x, j(x)) in database
            database.store(xu_vect, func_name_to_value)
        else:
            jac_n = design_space.normalize_grad(jac_u)

        if self.expects_normalized_inputs:
            return jac_n.real
        return jac_u.real
