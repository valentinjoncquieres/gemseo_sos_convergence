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
from __future__ import annotations

import logging
import pickle
from os import remove
from pathlib import Path

import pytest
from numpy import eye
from numpy import ones
from numpy import zeros
from numpy.random import default_rng
from scipy.linalg import norm
from scipy.sparse.linalg import LinearOperator
from scipy.sparse.linalg import aslinearoperator
from scipy.sparse.linalg import spilu

from gemseo.algos.linear_solvers.factory import LinearSolverLibraryFactory
from gemseo.algos.linear_solvers.lib_scipy_linalg import ScipyLinalgAlgos
from gemseo.algos.linear_solvers.linear_problem import LinearProblem

RESIDUALS_TOL = 1e-12


def test_algo_list() -> None:
    """Tests the algo list detection at lib creation."""
    factory = LinearSolverLibraryFactory()
    assert len(factory.algorithms) >= 6
    for algo in ("LGMRES", "GMRES", "BICG", "QMR", "BICGSTAB", "DEFAULT"):
        factory.is_available(algo)


def test_default() -> None:
    """Tests the DEFAULT solver."""
    factory = LinearSolverLibraryFactory()
    rng = default_rng(1)
    n = 5
    problem = LinearProblem(rng.random((n, n)), rng.random(n))
    factory.execute(problem, "DEFAULT", max_iter=1000)
    assert problem.solution is not None
    assert problem.compute_residuals() < RESIDUALS_TOL


@pytest.mark.parametrize("n", [1, 4, 20])
@pytest.mark.parametrize("algo", ["DEFAULT", "LGMRES", "BICGSTAB"])
@pytest.mark.parametrize("use_preconditioner", [True, False])
@pytest.mark.parametrize("use_ilu_precond", [True, False])
@pytest.mark.parametrize("use_x0", [True, False])
def test_linsolve(algo, n, use_preconditioner, use_x0, use_ilu_precond) -> None:
    """Tests the solvers options."""
    factory = LinearSolverLibraryFactory()
    rng = default_rng(1)
    problem = LinearProblem(rng.random((n, n)), rng.random(n))
    options = {
        "max_iter": 100,
        "tol": 1e-14,
        "atol": 1e-13,
        "x0": None,
        "use_ilu_precond": use_ilu_precond,
    }
    if use_preconditioner and not use_ilu_precond:
        options["preconditioner"] = LinearOperator(
            problem.lhs.shape, spilu(problem.lhs).solve
        )
    if algo == "lgmres":
        v = rng.random(n)
        options.update({
            "inner_m": 10,
            "outer_k": 10,
            "outer_v": [(v, problem.lhs.dot(v))],
            "store_outer_av": True,
            "prepend_outer_v": True,
        })
    factory.execute(problem, algo, **options)
    assert problem.solution is not None
    assert problem.compute_residuals() < RESIDUALS_TOL

    assert problem.solution is not None
    assert norm(problem.lhs.dot(problem.solution) - problem.rhs) < RESIDUALS_TOL


def test_common_dtype_cplx() -> None:
    factory = LinearSolverLibraryFactory()
    problem = LinearProblem(eye(2, dtype="complex128"), ones(2))
    factory.execute(problem, "DEFAULT")
    assert problem.compute_residuals() < RESIDUALS_TOL

    problem = LinearProblem(eye(2), ones(2, dtype="complex128"))
    factory.execute(problem, "DEFAULT")
    assert problem.compute_residuals() < RESIDUALS_TOL


def test_not_converged(caplog) -> None:
    """Tests the cases when convergence fails and save_when_fail option."""
    factory = LinearSolverLibraryFactory()
    rng = default_rng(1)
    n = 100
    problem = LinearProblem(rng.random((n, n)), rng.random(n))
    lib = factory.create("ScipyLinalgAlgos")
    caplog.set_level(logging.WARNING)
    lib.solve(
        problem, "BICGSTAB", max_iter=2, save_when_fail=True, use_ilu_precond=False
    )
    assert not problem.is_converged
    assert "The linear solver BICGSTAB did not converge." in caplog.text

    with Path(lib.save_fpath).open("rb") as f:
        problem2 = pickle.load(f)
    remove(lib.save_fpath)
    assert (problem2.lhs == problem.lhs).all()
    assert (problem2.rhs == problem.rhs).all()

    lib.solve(
        problem, "BICGSTAB", max_iter=2, save_when_fail=True, use_ilu_precond=True
    )
    assert problem.is_converged
    assert (problem.solution == lib.solution).all()


@pytest.mark.parametrize("seed", range(3))
def test_hard_conv(tmp_wd, seed) -> None:
    rng = default_rng(seed)
    n = 300
    problem = LinearProblem(rng.random((n, n)), rng.random(n))
    LinearSolverLibraryFactory().execute(
        problem,
        "DEFAULT",
        max_iter=3,
        store_residuals=True,
        use_ilu_precond=True,
        tol=1e-14,
    )

    assert problem.compute_residuals() < 1e-10


def test_inconsistent_options() -> None:
    problem = LinearProblem(ones((2, 2)), ones(2))

    with pytest.raises(ValueError, match="Inconsistent Preconditioner shape"):
        LinearSolverLibraryFactory().execute(
            problem, "DEFAULT", preconditioner=ones((3, 3))
        )

    with pytest.raises(ValueError, match="Inconsistent initial guess shape"):
        LinearSolverLibraryFactory().execute(problem, "DEFAULT", x0=ones(3))

    with pytest.raises(
        ValueError,
        match="Use either 'use_ilu_precond' or provide 'preconditioner', but not both.",
    ):
        LinearSolverLibraryFactory().execute(
            problem, "DEFAULT", preconditioner=ones((2, 2)), use_ilu_precond=True
        )


def test_runtime_error() -> None:
    problem = LinearProblem(zeros((2, 2)), ones(2))
    with pytest.raises(RuntimeError, match="Factor is exactly singular"):
        LinearSolverLibraryFactory().execute(problem, "DEFAULT", use_ilu_precond=False)


def test_default_solver() -> None:
    """Tests the default linear solver sequence.

    Consider the default solver when the matrix A is either a NumPy array or a SciPy
    LinearOperator. In the latter case, the final step using direct method cannot be
    used leading to an unconverged problem.
    """
    rng = default_rng(123456789)

    lhs, rhs = rng.normal(size=(30, 30)), ones(30)
    options = {"tol": 1e-12, "max_iter": 1, "inner_m": 1}

    # Linear system eventually solved using direct method and considered converged
    problem = LinearProblem(lhs, rhs)
    LinearSolverLibraryFactory().execute(
        problem, "DEFAULT", use_ilu_precond=False, **options
    )
    assert problem.is_converged

    # Linear system left unsolved since no direct method applied
    problem = LinearProblem(aslinearoperator(lhs), rhs)
    LinearSolverLibraryFactory().execute(
        problem, "DEFAULT", use_ilu_precond=False, **options
    )
    assert not problem.is_converged


def test_check_info() -> None:
    lib = ScipyLinalgAlgos()
    lib.problem = LinearProblem(zeros((2, 2)), ones(2))
    with pytest.raises(RuntimeError, match="illegal input or breakdown"):
        lib._check_solver_info(-1, {})


def test_factory() -> None:
    assert "ScipyLinalgAlgos" in LinearSolverLibraryFactory().linear_solvers


def test_algo_none() -> None:
    lib = ScipyLinalgAlgos()
    problem = LinearProblem(zeros((2, 2)), ones(2))
    with pytest.raises(ValueError, match="Algorithm name must be either passed as"):
        lib.execute(problem)


def test_library_name() -> None:
    """Check the library name."""
    assert ScipyLinalgAlgos.LIBRARY_NAME == "SciPy"
