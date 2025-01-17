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
#        :author: Damien Guenot
#        :author: Francois Gallard, refactoring
#    OTHER AUTHORS   - MACROSCOPIC CHANGES
"""Optimization library wrappers base class."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any
from typing import Final

import numpy

from gemseo.algos._unsuitability_reason import _UnsuitabilityReason
from gemseo.algos.driver_library import DriverDescription
from gemseo.algos.driver_library import DriverLibrary
from gemseo.algos.first_order_stop_criteria import KKTReached
from gemseo.algos.first_order_stop_criteria import is_kkt_residual_norm_reached
from gemseo.algos.first_order_stop_criteria import kkt_residual_computation
from gemseo.algos.optimization_problem import OptimizationProblem
from gemseo.algos.stop_criteria import FtolReached
from gemseo.algos.stop_criteria import XtolReached
from gemseo.algos.stop_criteria import is_f_tol_reached
from gemseo.algos.stop_criteria import is_x_tol_reached

if TYPE_CHECKING:
    from collections.abc import Mapping

    from numpy import ndarray

    from gemseo.core.mdofunctions.mdo_function import MDOFunction


@dataclass
class OptimizationAlgorithmDescription(DriverDescription):
    """The description of an optimization algorithm."""

    handle_equality_constraints: bool = False
    """Whether the optimization algorithm handles equality constraints."""

    handle_inequality_constraints: bool = False
    """Whether the optimization algorithm handles inequality constraints."""

    handle_multiobjective: bool = False
    """Whether the optimization algorithm handles multiple objectives."""

    positive_constraints: bool = False
    """Whether the optimization algorithm requires positive constraints."""

    problem_type: OptimizationProblem.ProblemType = (
        OptimizationProblem.ProblemType.NON_LINEAR
    )
    """The type of problem (see :attr:`.OptimizationProblem.ProblemType`)."""


class OptimizationLibrary(DriverLibrary):
    """Base optimization library defining a collection of optimization algorithms.

    Typically used as:

    #. Instantiate an :class:`.OptimizationLibrary`.
    #. Select the algorithm with :attr:`.algo_name`.
    #. Solve an :class:`.OptimizationProblem` with :meth:`.execute`.

    Notes:
        The missing current values
        of the :class:`.DesignSpace` attached to the :class:`.OptimizationProblem`
        are automatically initialized
        with the method :meth:`.DesignSpace.initialize_missing_current_values`.
    """

    MAX_ITER = "max_iter"
    F_TOL_REL = "ftol_rel"
    F_TOL_ABS = "ftol_abs"
    X_TOL_REL = "xtol_rel"
    X_TOL_ABS = "xtol_abs"
    _KKT_TOL_ABS = "kkt_tol_abs"
    _KKT_TOL_REL = "kkt_tol_rel"
    STOP_CRIT_NX = "stop_crit_n_x"
    # Maximum step for the line search
    LS_STEP_SIZE_MAX = "max_ls_step_size"
    # Maximum number of line search steps (per iteration).
    LS_STEP_NB_MAX = "max_ls_step_nb"
    MAX_FUN_EVAL = "max_fun_eval"
    MAX_TIME = "max_time"
    PG_TOL = "pg_tol"
    SCALING_THRESHOLD: Final[str] = "scaling_threshold"
    VERBOSE = "verbose"

    __DEFAULT_FTOL_ABS: Final[float] = 0.0
    """The default absolute tolerance for the objective."""

    __DEFAULT_FTOL_REL: Final[float] = 0.0
    """The default relative tolerance for the objective."""

    __DEFAULT_XTOL_ABS: Final[float] = 0.0
    """The default absolute tolerance for the design variables."""

    __DEFAULT_XTOL_REL: Final[float] = 0.0
    """The default relative tolerance for the design variables."""

    __DEFAULT_KKT_ABS_TOL: Final[float] = 0.0
    """The default absolute tolerance for the Karush-Kuhn-Tucker (KKT) conditions."""

    __DEFAULT_KKT_REL_TOL: Final[float] = 0.0
    """The default relative tolerance for the Karush-Kuhn-Tucker (KKT) conditions."""

    __DEFAULT_STOP_CRIT_N_X: Final[int] = 3
    """The default minimum number of iterations to assess tolerance."""

    def __init__(self) -> None:  # noqa:D107
        super().__init__()
        self._ftol_abs = self.__DEFAULT_FTOL_ABS
        self._ftol_rel = self.__DEFAULT_FTOL_REL
        self._xtol_abs = self.__DEFAULT_XTOL_ABS
        self._xtol_rel = self.__DEFAULT_XTOL_REL
        self.__kkt_abs_tol = self.__DEFAULT_KKT_ABS_TOL
        self.__kkt_rel_tol = self.__DEFAULT_KKT_REL_TOL
        self.__ref_kkt_norm = None
        self._stop_crit_n_x = self.__DEFAULT_STOP_CRIT_N_X

    def __algorithm_handles(self, algo_name: str, eq_constraint: bool):
        """Check if the algorithm handles equality or inequality constraints.

        Args:
            algo_name: The name of the algorithm.
            eq_constraint: Whether the constraints are equality ones.

        Returns:
            Whether the algorithm handles the passed type of constraints.
        """
        if algo_name not in self.descriptions:
            msg = f"Algorithm {algo_name} not in library {self.__class__.__name__}."
            raise KeyError(msg)

        if eq_constraint:
            return self.descriptions[algo_name].handle_equality_constraints

        return self.descriptions[algo_name].handle_inequality_constraints

    def check_equality_constraint_support(self, algo_name: str) -> bool:
        """Check if an algorithm handles equality constraints.

        Args:
            algo_name: The name of the algorithm.

        Returns:
            Whether the algorithm handles equality constraints.
        """
        return self.__algorithm_handles(algo_name, True)

    def check_inequality_constraint_support(self, algo_name: str) -> bool:
        """Check if an algorithm handles inequality constraints.

        Args:
            algo_name: The name of the algorithm.

        Returns:
            Whether the algorithm handles inequality constraints.
        """
        return self.__algorithm_handles(algo_name, False)

    def check_positivity_constraint_requirement(self, algo_name: str) -> bool:
        """Check if an algorithm requires positivity constraints.

        Args:
            algo_name: The name of the algorithm.

        Returns:
            Whether the algorithm requires positivity constraints.
        """
        return self.descriptions[algo_name].positive_constraints

    def _check_constraints_handling(
        self, algo_name: str, problem: OptimizationProblem
    ) -> None:
        """Check if problem and algorithm are consistent for constraints handling."""
        if problem.has_eq_constraints() and not self.check_equality_constraint_support(
            algo_name
        ):
            msg = (
                "Requested optimization algorithm "
                f"{algo_name} can not handle equality constraints."
            )
            raise ValueError(msg)
        if (
            problem.has_ineq_constraints()
            and not self.check_inequality_constraint_support(algo_name)
        ):
            msg = (
                "Requested optimization algorithm "
                f"{algo_name} can not handle inequality constraints."
            )
            raise ValueError(msg)

    def get_right_sign_constraints(self):
        """Transform the problem constraints into their opposite sign counterpart.

        This is done if the algorithm requires positive constraints.
        """
        if (
            self.problem.has_ineq_constraints()
            and self.check_positivity_constraint_requirement(self.algo_name)
        ):
            return [-constraint for constraint in self.problem.constraints]
        return self.problem.constraints

    def _pre_run(
        self, problem: OptimizationProblem, algo_name: str, **options: Any
    ) -> None:
        """To be overridden by subclasses.

        Specific method to be executed just before _run method call.

        The missing current values of the :class:`.DesignSpace` are initialized
        with the method :meth:`.DesignSpace.initialize_missing_current_values`.

        Args:
            problem: The optimization problem.
            algo_name: The name of the algorithm.
            **options: The options of the algorithm,
                see the associated JSON file.
        """
        super()._pre_run(problem, algo_name, **options)
        self._check_constraints_handling(algo_name, problem)

        if self.MAX_ITER in options:
            max_iter = options[self.MAX_ITER]
        elif (
            self.MAX_ITER in self.OPTIONS_MAP
            and self.OPTIONS_MAP[self.MAX_ITER] in options
        ):
            max_iter = options[self.OPTIONS_MAP[self.MAX_ITER]]
        else:
            msg = "Could not determine the maximum number of iterations."
            raise ValueError(msg)

        self._ftol_rel = options.get(self.F_TOL_REL, self.__DEFAULT_FTOL_REL)
        self._ftol_abs = options.get(self.F_TOL_ABS, self.__DEFAULT_FTOL_ABS)
        self._xtol_rel = options.get(self.X_TOL_REL, self.__DEFAULT_XTOL_REL)
        self._xtol_abs = options.get(self.X_TOL_ABS, self.__DEFAULT_XTOL_ABS)
        self.__ineq_tolerance = options.get(self.INEQ_TOLERANCE, problem.ineq_tolerance)
        self._stop_crit_n_x = options.get(
            self.STOP_CRIT_NX, self.__DEFAULT_STOP_CRIT_N_X
        )
        self.__kkt_abs_tol = options.get(self._KKT_TOL_ABS, None)
        self.__kkt_rel_tol = options.get(self._KKT_TOL_REL, None)
        self.init_iter_observer(max_iter)
        require_gradient = self.descriptions[self.algo_name].require_gradient
        if (
            self.__kkt_abs_tol is not None or self.__kkt_rel_tol is not None
        ) and require_gradient:
            problem.add_callback(
                self._check_kkt_from_database, each_new_iter=False, each_store=True
            )
        problem.design_space.initialize_missing_current_values()
        if problem.differentiation_method == self.DifferentiationMethod.COMPLEX_STEP:
            problem.design_space.to_complex()
        # First, evaluate all functions at x_0. Some algorithms don't do this
        function_values, _ = self.problem.evaluate_functions(
            eval_jac=require_gradient,
            eval_obj=True,
            eval_observables=False,
            normalize=options.get(
                self.NORMALIZE_DESIGN_SPACE_OPTION, self._NORMALIZE_DS
            ),
        )
        scaling_threshold = options.get(self.SCALING_THRESHOLD)
        if scaling_threshold is not None:
            self.problem.objective = self.__scale(
                self.problem.objective,
                function_values[self.problem.objective.name],
                scaling_threshold,
            )
            self.problem.constraints = [
                self.__scale(
                    constraint, function_values[constraint.name], scaling_threshold
                )
                for constraint in self.problem.constraints
            ]
            self.problem.observables = [
                self.__scale(
                    observable, function_values[observable.name], scaling_threshold
                )
                for observable in self.problem.observables
            ]

    @classmethod
    def _get_unsuitability_reason(
        cls,
        algorithm_description: OptimizationAlgorithmDescription,
        problem: OptimizationProblem,
    ) -> _UnsuitabilityReason:
        reason = super()._get_unsuitability_reason(algorithm_description, problem)
        if reason:
            return reason

        if (
            problem.has_eq_constraints()
            and not algorithm_description.handle_equality_constraints
        ):
            return _UnsuitabilityReason.EQUALITY_CONSTRAINTS

        if (
            problem.has_ineq_constraints()
            and not algorithm_description.handle_inequality_constraints
        ):
            return _UnsuitabilityReason.INEQUALITY_CONSTRAINTS

        if (
            problem.pb_type == problem.ProblemType.NON_LINEAR
            and algorithm_description.problem_type == problem.ProblemType.LINEAR
        ):
            return _UnsuitabilityReason.NON_LINEAR_PROBLEM

        return reason

    def new_iteration_callback(self, x_vect: ndarray) -> None:
        """Verify the design variable and objective value stopping criteria.

        Raises:
            FtolReached: If the defined relative or absolute function
                tolerance is reached.
            XtolReached: If the defined relative or absolute x tolerance
                is reached.
        """
        # First check if the max_iter is reached and update the progress bar
        super().new_iteration_callback(x_vect)
        if is_f_tol_reached(
            self.problem, self._ftol_rel, self._ftol_abs, self._stop_crit_n_x
        ):
            raise FtolReached

        if is_x_tol_reached(
            self.problem, self._xtol_rel, self._xtol_abs, self._stop_crit_n_x
        ):
            raise XtolReached

    def _check_kkt_from_database(self, x_vect: ndarray) -> None:
        """Verify, if required, KKT norm stopping criterion at each database storage.

        Raises:
            KKTReached: If the absolute tolerance on the KKT residual is reached.
        """
        check_kkt = True
        function_names = [
            self.problem.get_objective_name(),
            *self.problem.get_constraint_names(),
        ]
        database = self.problem.database
        for function_name in function_names:
            if (
                database.get_function_value(
                    database.get_gradient_name(function_name), x_vect
                )
                is None
            ) or (database.get_function_value(function_name, x_vect) is None):
                check_kkt = False
                break
        if check_kkt and (self.__ref_kkt_norm is None):
            self.__ref_kkt_norm = kkt_residual_computation(
                self.problem, x_vect, self.__ineq_tolerance
            )

        if check_kkt and is_kkt_residual_norm_reached(
            self.problem,
            x_vect,
            kkt_abs_tol=self.__kkt_abs_tol,
            kkt_rel_tol=self.__kkt_rel_tol,
            ineq_tolerance=self.__ineq_tolerance,
            reference_residual=self.__ref_kkt_norm,
        ):
            raise KKTReached

    @staticmethod
    def __scale(
        function: MDOFunction,
        function_value: Mapping[str, ndarray],
        scaling_threshold: float,
    ) -> MDOFunction:
        """Scale a function based on its value on the current design values.

        Args:
            function: The function.
            function_value: The function value of reference for scaling.
            scaling_threshold: The threshold on the reference function value
                that triggers scaling.

        Returns:
            The scaled function.
        """
        reference_values = numpy.absolute(function_value)
        threshold_reached = reference_values > scaling_threshold
        if not threshold_reached.any():
            return function

        scaled_function = function / numpy.where(
            threshold_reached, reference_values, 1.0
        )
        # Use same function name for consistency with name used in database
        scaled_function.name = function.name
        return scaled_function
