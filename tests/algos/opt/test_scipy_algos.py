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
#      :author: Francois Gallard
#    OTHER AUTHORS   - MACROSCOPIC CHANGES
from __future__ import annotations

from unittest import TestCase
from warnings import warn

import pytest
from numpy import allclose
from numpy import array
from numpy import inf
from scipy.optimize.optimize import rosen
from scipy.optimize.optimize import rosen_der
from scipy.sparse import csr_array

from gemseo.algos.design_space import DesignSpace
from gemseo.algos.opt.factory import OptimizationLibraryFactory
from gemseo.algos.opt.lib_scipy import ScipyOpt
from gemseo.algos.opt.optimization_library import OptimizationLibrary as OptLib
from gemseo.algos.optimization_problem import OptimizationProblem
from gemseo.core.mdofunctions.mdo_function import MDOFunction
from gemseo.core.mdofunctions.mdo_linear_function import MDOLinearFunction
from gemseo.problems.optimization.rosenbrock import Rosenbrock
from gemseo.utils.testing.opt_lib_test_base import OptLibraryTestBase


class TestScipy(TestCase):
    """"""

    OPT_LIB_NAME = "ScipyOpt"

    def test_init(self) -> None:
        """"""
        factory = OptimizationLibraryFactory()
        if factory.is_available(self.OPT_LIB_NAME):
            factory.create(self.OPT_LIB_NAME)

    def test_display(self) -> None:
        """"""
        algo_name = "SLSQP"
        OptLibraryTestBase.generate_one_test(
            self.OPT_LIB_NAME, algo_name=algo_name, max_iter=10, disp=True
        )

    def test_handles_cstr(self) -> None:
        """"""
        algo_name = "TNC"
        self.assertRaises(
            Exception,
            OptLibraryTestBase.generate_one_test,
            self.OPT_LIB_NAME,
            algo_name=algo_name,
            max_iter=10,
        )

    def test_algorithm_suited(self) -> None:
        """"""
        algo_name = "SLSQP"
        opt_library = OptLibraryTestBase.generate_one_test(
            self.OPT_LIB_NAME, algo_name=algo_name, max_iter=10
        )

        assert not opt_library.is_algorithm_suited(
            opt_library.descriptions["TNC"], opt_library.problem
        )

        opt_library.problem.pb_type = OptimizationProblem.ProblemType.NON_LINEAR
        opt_library.descriptions[
            "SLSQP"
        ].problem_type = OptimizationProblem.ProblemType.LINEAR
        assert not opt_library.is_algorithm_suited(
            opt_library.descriptions["SLSQP"], opt_library.problem
        )

    def test_positive_constraints(self) -> None:
        """"""
        algo_name = "SLSQP"
        opt_library = OptLibraryTestBase.generate_one_test(
            self.OPT_LIB_NAME, algo_name=algo_name, max_iter=10
        )
        assert opt_library.check_positivity_constraint_requirement(algo_name)
        assert not opt_library.check_positivity_constraint_requirement("TNC")

    def test_fail_opt(self) -> None:
        """"""
        algo_name = "SLSQP"
        problem = Rosenbrock()

        def i_fail(x):
            if rosen(x) < 1e-3:
                raise ValueError(x)
            return rosen(x)

        problem.objective = MDOFunction(i_fail, "rosen")
        self.assertRaises(
            Exception, OptimizationLibraryFactory().execute, problem, algo_name
        )

    def test_tnc_options(self) -> None:
        """"""
        algo_name = "TNC"
        OptLibraryTestBase.generate_one_test_unconstrained(
            self.OPT_LIB_NAME,
            algo_name=algo_name,
            max_iter=100,
            disp=True,
            maxCGit=178,
            pg_tol=1e-8,
            eta=-1.0,
            ftol_rel=1e-10,
            xtol_rel=1e-10,
            max_ls_step_size=0.5,
            minfev=4,
        )

    def test_lbfgsb_options(self) -> None:
        """"""
        algo_name = "L-BFGS-B"
        OptLibraryTestBase.generate_one_test_unconstrained(
            self.OPT_LIB_NAME,
            algo_name=algo_name,
            max_iter=100,
            disp=True,
            maxcor=12,
            pg_tol=1e-8,
            max_fun_eval=20,
        )
        self.assertRaises(
            Exception,
            OptLibraryTestBase.generate_one_test_unconstrained,
            self.OPT_LIB_NAME,
            algo_name=algo_name,
            max_iter="100",
            disp=True,
            maxcor=12,
            pg_tol=1e-8,
            max_fun_eval=1000,
        )

        opt_library = OptLibraryTestBase.generate_one_test_unconstrained(
            self.OPT_LIB_NAME, algo_name=algo_name, max_iter=100, max_time=0.0000000001
        )
        assert opt_library.problem.solution.message.startswith("Maximum time reached")

    def test_slsqp_options(self) -> None:
        """"""
        algo_name = "SLSQP"
        OptLibraryTestBase.generate_one_test(
            self.OPT_LIB_NAME,
            algo_name=algo_name,
            max_iter=100,
            disp=True,
            ftol_rel=1e-10,
        )

    def test_normalization(self) -> None:
        """Runs a problem with one variable to be normalized and three not to be
        normalized."""
        design_space = DesignSpace()
        design_space.add_variable(
            "x1", 1, DesignSpace.DesignVariableType.FLOAT, -1.0, 1.0, 0.0
        )
        design_space.add_variable(
            "x2", 1, DesignSpace.DesignVariableType.FLOAT, -inf, 1.0, 0.0
        )
        design_space.add_variable(
            "x3", 1, DesignSpace.DesignVariableType.FLOAT, -1.0, inf, 0.0
        )
        design_space.add_variable(
            "x4", 1, DesignSpace.DesignVariableType.FLOAT, -inf, inf, 0.0
        )
        problem = OptimizationProblem(design_space)
        problem.objective = MDOFunction(rosen, "Rosenbrock", "obj", rosen_der)
        OptimizationLibraryFactory().execute(
            problem, "L-BFGS-B", normalize_design_space=True
        )
        OptimizationLibraryFactory().execute(
            problem, "L-BFGS-B", normalize_design_space=False
        )

    def test_xtol_ftol_activation(self) -> None:
        def run_pb(algo_options):
            design_space = DesignSpace()
            design_space.add_variable(
                "x1", 2, DesignSpace.DesignVariableType.FLOAT, -1.0, 1.0, 0.0
            )
            problem = OptimizationProblem(design_space)
            problem.objective = MDOFunction(rosen, "Rosenbrock", "obj", rosen_der)
            res = OptimizationLibraryFactory().execute(
                problem, "L-BFGS-B", **algo_options
            )
            return res, problem

        for tol_name in (
            OptLib.F_TOL_ABS,
            OptLib.F_TOL_REL,
            OptLib.X_TOL_ABS,
            OptLib.X_TOL_REL,
        ):
            res, pb = run_pb({tol_name: 1e10})
            assert tol_name in res.message
            # Check that the criteria is activated as ap
            assert len(pb.database) == 3


suite_tests = OptLibraryTestBase()
for test_method in suite_tests.generate_test("SCIPY"):
    setattr(TestScipy, test_method.__name__, test_method)


def test_library_name() -> None:
    """Check the library name."""
    assert ScipyOpt.LIBRARY_NAME == "SciPy"


@pytest.fixture(params=[True, False])
def jacobians_are_sparse(request) -> bool:
    """Whether the Jacobians of MDO Functions are sparse or not."""
    return request.param


@pytest.fixture()
def opt_problem(jacobians_are_sparse: bool) -> OptimizationProblem:
    """A linear optimization problem.

    Args:
        sparse_jacobian: Whether the objective and constraints Jacobians are sparse.

    Returns:
        The linear optimization problem.
    """
    design_space = DesignSpace()
    design_space.add_variable("x", l_b=0.0, u_b=1.0, value=1.0)
    design_space.add_variable("y", l_b=0.0, u_b=5.0, value=5)
    design_space.add_variable("z", l_b=0.0, u_b=5.0, value=0)

    problem = OptimizationProblem(design_space)

    array_ = csr_array if jacobians_are_sparse else array
    input_names = ["x", "y", "z"]

    problem.objective = MDOLinearFunction(
        array_([1.0, 1.0, -1]), "f", MDOFunction.FunctionType.OBJ, input_names, -1.0
    )
    problem.add_ineq_constraint(
        MDOLinearFunction(array_([0, 0.5, -0.25]), "g", input_names=input_names),
        0.333,
        True,
    )
    problem.add_eq_constraint(
        MDOLinearFunction(array_([-2.0, 1.0, 1.0]), "h", input_names=input_names)
    )

    return problem


def test_recasting_sparse_jacobians(opt_problem) -> None:
    """Test that sparse Jacobians are recasted as dense arrays.

    The SLSQP algorithm from SciPy does not support sparse Jacobians. The fact that the
    optimizer can be executed and converges implies that the MDOFunctions' Jacobians are
    indeed recast as dense NumPy arrays before being sent to SciPy.
    """
    optimization_result = OptimizationLibraryFactory().execute(
        opt_problem, "SLSQP", atol=1e-10
    )
    assert allclose(optimization_result.f_opt, -0.001, atol=1e-10)


@pytest.mark.parametrize(
    "initial_simplex", [None, [[0.6, 0.6], [0.625, 0.6], [0.6, 0.625]]]
)
def test_nelder_mead(initial_simplex) -> None:
    """Test the Nelder-Mead algorithm on the Rosenbrock problem."""
    problem = Rosenbrock()
    opt = OptimizationLibraryFactory().execute(
        problem, algo_name="NELDER-MEAD", max_iter=800, initial_simplex=initial_simplex
    )
    x_opt, f_opt = problem.get_solution()
    assert opt.x_opt == pytest.approx(x_opt, abs=1.0e-3)
    assert opt.f_opt == pytest.approx(f_opt, abs=1.0e-3)


def test_tnc_maxiter(caplog):
    """Check that TNC no longer receives the unknown maxiter option."""
    problem = Rosenbrock()
    with pytest.warns() as record:
        OptimizationLibraryFactory().execute(problem, algo_name="TNC", max_iter=2)
        warn("foo", UserWarning)  # noqa: B028

    assert len(record) == 1
