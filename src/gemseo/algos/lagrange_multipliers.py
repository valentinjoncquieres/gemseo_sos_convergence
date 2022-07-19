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
#
# Contributors:
# - Jean-Christophe Giret
# - François Gallard
# - Matthias De Lozzo
# - Benoit Pauwels
# - Antoine DECHAUME
# - Simone Coniglio
# - Gilberto Ruiz Jiménez
"""Implementation of the Lagrange multipliers."""
from __future__ import annotations

import logging

from numpy import arange
from numpy import array
from numpy import atleast_2d
from numpy import concatenate
from numpy import ndarray
from numpy import where
from numpy import zeros
from numpy.linalg import matrix_rank
from numpy.linalg import norm
from scipy.optimize import linprog
from scipy.optimize import nnls

from gemseo.algos.design_space import DesignSpace
from gemseo.algos.opt_problem import OptimizationProblem
from gemseo.third_party.prettytable import PrettyTable

LOGGER = logging.getLogger(__name__)


class LagrangeMultipliers:
    r"""Class that implements the computation of Lagrange Multipliers.

    Denote :math:`x^\ast` an optimal solution of the optimization problem
    below.

    .. math::
        \begin{aligned}
            & \text{Minimize}    & & f(x) \\
            & \text{relative to} & & x \\
            & \text{subject to}  & & \left\{\begin{aligned}
                                                & g(x)\le0, \\
                                                & h(x)=0, \\
                                                & \ell\le x\le u.
                                     \end{aligned}\right.
        \end{aligned}

    If the constraints are qualified at :math:`x^\ast` then the Lagrange
    multipliers of :math:`x^\ast` are the vectors :math:`\lambda_g`,
    :math:`\lambda_h`, :math:`\lambda_\ell` and :math:`\lambda_u` satisfying

    .. math::
        \left\{\begin{aligned}
            &\frac{\partial f}{\partial x}(x^\ast)
            +\lambda_g^\top\frac{\partial g}{\partial x}(x^\ast)
            +\lambda_h^\top\frac{\partial h}{\partial x}(x^\ast)
            +\sum_j\lambda_{\ell,j}+\sum_j\lambda_{u,j}
            =0,\\
            &\lambda_{g,i}\ge0\text{ if }g_i(x^\ast)=0,
            \text{ otherwise }\lambda_{g,i}=0,\\
            &\lambda_{\ell,j}\le0\text{ if }x^\ast_j=\ell_j,
            \text{ otherwise }\lambda_{\ell,j}=0,\\
            &\lambda_{u,j}\ge0\text{ if }x^\ast_j=u_j,
            \text{ otherwise }\lambda_{u,j}=0.
        \end{aligned}\right.
    """
    LOWER_BOUNDS = "lower_bounds"
    UPPER_BOUNDS = "upper_bounds"
    INEQUALITY = "inequality"
    EQUALITY = "equality"
    CSTR_LABELS = [LOWER_BOUNDS, UPPER_BOUNDS, INEQUALITY, EQUALITY]

    def __init__(self, opt_problem: OptimizationProblem) -> None:
        """
        Args:
            opt_problem: The optimization problem
                on which Lagrange multipliers shall be computed.
        """
        self._check_inputs(opt_problem)
        self.opt_problem = opt_problem
        self.active_lb_names = []
        self.active_ub_names = []
        self.active_ineq_names = []
        self.active_eq_names = []
        self.lagrange_multipliers = None
        self.__normalized = opt_problem.preprocess_options.get(
            "is_function_input_normalized", False
        )

    @staticmethod
    def _check_inputs(opt_problem: OptimizationProblem) -> None:
        """Verify that an problem is an instance of :class:`.OptimizationProblem`.

        Args:
            opt_problem: The optimization problem
                on which Lagrange multipliers shall be computed.

        Raises:
            ValueError: When the problem is not an :class:`.OptimizationProblem`
                or when the problem was not solved.
        """
        if not isinstance(opt_problem, OptimizationProblem):
            raise ValueError(
                "LagrangeMultipliers must be initialized with an OptimizationProblem."
            )
        if opt_problem.solution is None:
            raise ValueError("The optimization problem was not solved.")

    def compute(
        self, x_vect: ndarray, ineq_tolerance: float = 1e-6, rcond: float = -1
    ) -> dict[str, tuple[list[str], ndarray]]:
        """Compute the Lagrange multipliers, as a post-processing of the optimal point.

        This solves:

        (d ActiveConstraints)'               d Objective
        (-------------------)  . Lambda = -  -----------
        (d X                )                d X

        Args:
            x_vect: The optimal point on which the multipliers shall be computed.
            ineq_tolerance: The tolerance on inequality constraints.
            rcond: The cut-off ratio for small singular values of the Jacobian
               (see scipy.linalg.lsq).

        Returns:
            The Lagrange multipliers.
        """
        LOGGER.info("Computation of Lagrange multipliers")

        # Check feasibility
        self._check_feasibility(x_vect)

        # get jacobian of all active constraints, and an
        # ordered list of their name
        jac_act, _ = self._get_jac_act(x_vect, ineq_tolerance)
        if jac_act is None:
            # There is no active constraint
            multipliers = []
            self._store_multipliers(multipliers)
            return self.lagrange_multipliers
        lhs = jac_act.T
        act_constr_nb = lhs.shape[1]
        rank = matrix_rank(lhs)
        LOGGER.info("Found %s active constraints", str(act_constr_nb))
        LOGGER.info("Rank of jacobian = %s", str(rank))
        if act_constr_nb > rank:
            LOGGER.warning("Number of active constraints > rank !")

        # get jacobian of objective
        obj_jac = self._get_obj_jac(x_vect)
        rhs = -obj_jac.T

        # Compute the Lagrange multipliers as a feasible solution of a
        # linear optimization problem
        act_eq_constr_nb = len(self.active_eq_names)
        bounds = [(0, None)] * (act_constr_nb - act_eq_constr_nb) + [
            (None, None)
        ] * act_eq_constr_nb
        optim_result = linprog(zeros(act_constr_nb), A_eq=lhs, b_eq=rhs, bounds=bounds)
        if optim_result.status == 2:
            LOGGER.warning("Lagrange multipliers appear not to exist")
        if optim_result.success:
            mul = optim_result.x
        else:
            # If the linear optimization failed then obtain the Lagrange
            # multipliers as a solution of a least-square problem
            mul, residuals = nnls(lhs, rhs)
            LOGGER.info("Residuals norm = %s", str(norm(residuals)))

        # stores multipliers in a dictionary
        self._store_multipliers(mul)

        return self.lagrange_multipliers

    def _check_feasibility(self, x_vect: ndarray) -> None:
        """Check that the given point is in the design space and satisfies all
        constraints.

        Args:
            x_vect: The point at which the Lagrange multipliers are to be computed.
        """
        problem = self.opt_problem

        # Check that the point is within bounds
        problem.design_space.check_membership(x_vect)

        # Check that the point satisfies other constraints
        values, _ = problem.evaluate_functions(
            x_vect, eval_obj=False, normalize=False, no_db_no_norm=True
        )
        feasible = problem.is_point_feasible(values)
        if not feasible:
            LOGGER.warning("Infeasible point, Lagrange multipliers may not exist.")

    def _get_act_bound_jac(self, act_bounds: dict[str, ndarray]):
        """Return the Jacobian of the active bounds.

        The constraints sign is not taken into account (matrix is made of 0 and 1).

        Args:
            act_bounds: The active bounds.

        Returns:
            The Jacobian of the active bounds
            and the name of each component of each function.
        """
        dspace = self.opt_problem.design_space
        x_dim = dspace.dimension
        dim_act = sum(len(where(bnd)[0]) for bnd in act_bounds.values())
        if dim_act == 0:
            return None, []
        act_array = concatenate([act_bounds[var] for var in dspace.variables_names])

        bnd_jac = zeros((dim_act, x_dim))

        if self.__normalized:
            norm_factor = dspace.get_upper_bounds() - dspace.get_lower_bounds()
            act_jac = norm_factor[act_array]
        else:
            act_jac = 1.0
        bnd_jac[arange(dim_act), act_array] = act_jac
        indexed_varnames = array(dspace.get_indexed_variables_names())
        act_b_names = indexed_varnames[act_array].tolist()
        return bnd_jac, act_b_names

    def __get_act_ineq_jac(
        self, x_vect: ndarray, ineq_tolerance: float = 1e-6
    ) -> tuple[ndarray, list[str]]:
        """Return the Jacobian of the active inequality constraints.

        Args:
            x_vect: The point at which the Jacobian is computed.
            ineq_tolerance: The tolerance for the inequality constraints.

        Returns:
            The Jacobian of the active inequality constraints
            and the name of each component of each function.
        """
        # retrieves the active functions and the indices :
        # a function is active if at least
        # one of its component (in case of multidimensional constraints) is
        # active
        act_func = self.opt_problem.get_active_ineq_constraints(x_vect, ineq_tolerance)

        dspace = self.opt_problem.design_space

        if self.__normalized:
            x_vect = dspace.normalize_vect(x_vect)
        jac = []
        names = []

        for func, act_set in act_func.items():
            if True in act_set:
                ineq_jac = func.jac(x_vect)
                if len(ineq_jac.shape) == 1:
                    # Make sure the Jacobian is a 2-dimensional array
                    ineq_jac = ineq_jac.reshape((1, x_vect.size))
                else:
                    ineq_jac = ineq_jac[act_set, :]
                jac.append(ineq_jac)
                if func.dim == 1:
                    names.append(func.name)
                else:
                    names += [
                        self._get_component_name(func.name, i)
                        for i, active in enumerate(act_set)
                        if active
                    ]
        if jac:
            jac = concatenate(jac)
        else:
            jac = None
        return jac, names

    def _get_act_eq_jac(self, x_vect: ndarray) -> tuple[ndarray, list[str]]:
        """Return The Jacobian of the active equality constraints.

        Args:
            x_vect: The point at which the Jacobian is computed.

        Returns:
            The Jacobian of the active equality constraints
            and the name of each component of each function.
        """
        eq_functions = self.opt_problem.get_eq_constraints()
        # loop on equality functions
        # NB: as the solution (x_vect) is supposed to be feasible,
        # all functions (on all dimensions) are supposed to be active
        jac = []
        names = []
        dspace = self.opt_problem.design_space

        if self.__normalized:
            x_vect = dspace.normalize_vect(x_vect)

        for eq_function in eq_functions:
            eq_jac = atleast_2d(eq_function.jac(x_vect))
            jac.append(eq_jac)
            if eq_function.dim == 1:
                names.append(eq_function.name)
            else:
                names += [
                    self._get_component_name(eq_function.name, i)
                    for i in range(eq_jac.shape[0])
                ]
        if jac:
            jac = concatenate(jac)
        else:
            jac = None
        return jac, names

    def _get_obj_jac(self, x_vect: ndarray) -> ndarray:
        """Return the Jacobian of the objective.

        Args:
            x_vect: The point at which the Jacobian is computed.

        Returns:
            The Jacobian of the objective.
        """
        if self.__normalized:
            x_vect = self.opt_problem.design_space.normalize_vect(x_vect)

        return self.opt_problem.objective.jac(x_vect)

    def _get_jac_act(
        self, x_vect: ndarray, ineq_tolerance: float = 1e-6
    ) -> tuple[ndarray, list[str]]:
        """Return the Jacobian of the active constraints.

        Args:
            x_vect: The point at which the Jacobian is computed.
            ineq_tolerance: The tolerance for the inequality constraints.

        Returns:
            The Jacobian of the active constraints
            and the name of each component of each function.
        """
        # Bounds jacobian
        dspace = self.opt_problem.design_space
        act_lb, act_ub = dspace.get_active_bounds(x_vect, tol=ineq_tolerance)
        lb_jac_act, self.active_lb_names = self._get_act_bound_jac(act_lb)
        if lb_jac_act is not None:
            lb_jac_act *= -1
        ub_jac_act, self.active_ub_names = self._get_act_bound_jac(act_ub)

        # inequality names
        tol = ineq_tolerance
        ineq_jac, self.active_ineq_names = self.__get_act_ineq_jac(x_vect, tol)
        # equality names
        eq_jac, eq_names_act = self._get_act_eq_jac(x_vect)
        self.active_eq_names = eq_names_act

        names = (
            self.active_lb_names
            + self.active_ub_names
            + self.active_ineq_names
            + eq_names_act
        )
        jacobians = [
            jacobian
            for jacobian in [lb_jac_act, ub_jac_act, ineq_jac, eq_jac]
            if jacobian is not None
        ]
        if jacobians:
            jac_act_arr = concatenate(jacobians, axis=0)
        else:
            # There no active constraint
            jac_act_arr = None

        return jac_act_arr, names

    def _store_multipliers(self, multipliers: ndarray) -> None:
        """Store the Lagrange multipliers in the attribute :attr:`lagrange_multipliers`.

        Args:
            multipliers: The Lagrange multipliers.
        """
        lag = {}

        i_min = 0
        n_act = len(self.active_lb_names)
        if n_act > 0:
            l_b_mult = multipliers[i_min : i_min + n_act]
            lag[self.LOWER_BOUNDS] = (self.active_lb_names, l_b_mult)
            i_min += n_act
            wrong_inds = where(l_b_mult < 0.0)[0]
            if wrong_inds.size > 0:
                names_neg = array(self.active_lb_names)[wrong_inds]
                LOGGER.warning(
                    "Negative Lagrange multipliers for "
                    "lower bounds on variables"
                    "%s !",
                    str(names_neg),
                )
        n_act = len(self.active_ub_names)
        if n_act > 0:
            u_b_mult = multipliers[i_min : i_min + n_act]
            lag[self.UPPER_BOUNDS] = (self.active_ub_names, u_b_mult)
            i_min += n_act
            wrong_inds = where(u_b_mult < 0.0)[0]
            if wrong_inds.size > 0:
                names_neg = array(self.active_ub_names)[wrong_inds]
                LOGGER.warning(
                    "Negative Lagrange multipliers for "
                    "upper bounds on variables"
                    "%s !",
                    str(names_neg),
                )
        n_act = len(self.active_ineq_names)
        if n_act > 0:
            ineq_mult = multipliers[i_min : i_min + n_act]
            lag[self.INEQUALITY] = (self.active_ineq_names, ineq_mult)
            i_min += n_act
            wrong_inds = where(ineq_mult < 0.0)[0]
            if wrong_inds.size > 0:
                names_neg = array(self.active_ineq_names)[wrong_inds]
                LOGGER.warning(
                    "Negative Lagrange multipliers for "
                    "inequality constraints"
                    "%s !",
                    str(names_neg),
                )
        if self.active_eq_names:
            lag[self.EQUALITY] = (
                self.active_eq_names,
                multipliers[i_min : i_min + n_act],
            )
            i_min += n_act

        self.lagrange_multipliers = lag

    def _initialize_multipliers(self) -> dict[str, dict[str, ndarray]]:
        """Initialize the Lagrange multipliers with zeros.

        Returns:
            The Lagrange multipliers.
        """
        problem = self.opt_problem
        multipliers = dict()

        # Bound-constraints
        indexed_varnames = problem.design_space.get_indexed_variables_names()
        multipliers[self.LOWER_BOUNDS] = dict.fromkeys(indexed_varnames, 0.0)
        multipliers[self.UPPER_BOUNDS] = dict.fromkeys(indexed_varnames, 0.0)

        # Inequality-constraints
        multipliers[self.INEQUALITY] = {
            func.name if func.dim == 1 else self._get_component_name(func.name, i): 0.0
            for func in problem.get_ineq_constraints()
            for i in range(func.dim)
        }

        # Equality-constraints
        multipliers[self.EQUALITY] = {
            func.name if func.dim == 1 else self._get_component_name(func.name, i): 0.0
            for func in problem.get_eq_constraints()
            for i in range(func.dim)
        }

        return multipliers

    def get_multipliers_arrays(self) -> dict[str, dict[str, ndarray]]:
        """Return the Lagrange multipliers (zero and nonzero) as arrays.

        Returns:
            The Lagrange multipliers.
        """
        problem = self.opt_problem
        design_space = problem.design_space

        # Convert to dictionaries
        multipliers = dict()
        for label in self.CSTR_LABELS:
            names, mults = self.lagrange_multipliers.get(label, ([], array([])))
            multipliers[label] = dict(zip(names, mults))

        # Add the Lagrange multipliers equal to zero
        multipliers_init = self._initialize_multipliers()
        for label in self.CSTR_LABELS:
            multipliers_init[label].update(multipliers[label])

        # Cast the multipliers as arrays
        mult_arrays = dict()
        # Bound-constraints multipliers
        mult_arrays[self.LOWER_BOUNDS] = dict()
        mult_arrays[self.UPPER_BOUNDS] = dict()
        for name in design_space.variables_names:
            indexed_varnames = design_space.get_indexed_variables_names()
            var_low_mult = array(
                [
                    multipliers_init[self.LOWER_BOUNDS][comp_name]
                    for comp_name in indexed_varnames
                ]
            )
            mult_arrays[self.LOWER_BOUNDS][name] = var_low_mult
            var_upp_mult = array(
                [
                    multipliers_init[self.UPPER_BOUNDS][comp_name]
                    for comp_name in indexed_varnames
                ]
            )
            mult_arrays[self.UPPER_BOUNDS][name] = var_upp_mult
        # Inequality-constraints multipliers
        ineq_mult = multipliers_init[self.INEQUALITY]
        mult_arrays[self.INEQUALITY] = dict()
        for func in problem.get_ineq_constraints():
            func_mult = array(
                [
                    ineq_mult[
                        func.name
                        if func.dim == 1
                        else self._get_component_name(func.name, index)
                    ]
                    for index in range(func.dim)
                ]
            )
            mult_arrays[self.INEQUALITY][func.name] = func_mult
        # Equality-constraints multipliers
        eq_mult = multipliers_init[self.EQUALITY]
        mult_arrays[self.EQUALITY] = dict()
        for func in problem.get_eq_constraints():
            func_mult = array(
                [
                    eq_mult[
                        func.name
                        if func.dim == 1
                        else self._get_component_name(func.name, index)
                    ]
                    for index in range(func.dim)
                ]
            )
            mult_arrays[self.EQUALITY][func.name] = func_mult

        return mult_arrays

    @staticmethod
    def _get_component_name(name: str, index: int) -> str:
        """Return the name of a variable component.

        Args:
            name: The name of the variable.
            index: The index of the component.

        Returns:
            The name of the variable component.
        """
        return f"{name}{DesignSpace.SEP}{index}"

    def _get_pretty_table(self) -> PrettyTable:
        """Display the Lagrange Multipliers."""
        table = PrettyTable(
            ["Constraint type", "Constraint name", "Lagrange Multiplier"]
        )

        for cstr_type, nam_val in self.lagrange_multipliers.items():
            for name, value in zip(nam_val[0], nam_val[1]):
                table.add_row([cstr_type, name, value])

        return table

    def __str__(self, *args, **kwargs) -> str:
        return f"Lagrange multipliers:\n{self._get_pretty_table().get_string()}"
