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
from __future__ import annotations

import pytest as pytest
from numpy import array
from numpy import ones
from numpy import zeros

from gemseo.algos.first_order_stop_criteria import is_kkt_residual_norm_reached
from gemseo.algos.opt.factory import OptimizationLibraryFactory
from gemseo.problems.optimization.power_2 import Power2
from gemseo.problems.optimization.rosenbrock import Rosenbrock


@pytest.mark.parametrize("is_optimum", [False, True])
def test_is_kkt_norm_tol_reached_rosenbrock(is_optimum) -> None:
    """Test KKT criterion on Rosenbrock problem."""
    problem = Rosenbrock(l_b=0, u_b=1.0)
    design_point = ones(2) if is_optimum else zeros(2)
    assert (
        is_kkt_residual_norm_reached(
            problem, design_point, kkt_abs_tol=1e-2, kkt_rel_tol=1e-2
        )
        == is_optimum
    )
    assert (
        problem.database.get_function_value(problem.KKT_RESIDUAL_NORM, design_point)
        is not None
    )


@pytest.mark.parametrize("is_optimum", [False, True])
def test_is_kkt_norm_tol_reached_power2(is_optimum) -> None:
    """Test KKT criterion on Power2 problem."""
    problem = Power2()
    problem.preprocess_functions()
    design_point = (
        array([0.5 ** (1.0 / 3.0), 0.5 ** (1.0 / 3.0), 0.9 ** (1.0 / 3.0)])
        if is_optimum
        else ones(3)
    )
    assert (
        is_kkt_residual_norm_reached(
            problem, design_point, kkt_abs_tol=1e-2, kkt_rel_tol=1e-2
        )
        == is_optimum
    )
    assert (
        problem.database.get_function_value(problem.KKT_RESIDUAL_NORM, design_point)
        is not None
    )


@pytest.mark.parametrize("algorithm", ["NLOPT_SLSQP", "SLSQP"])
@pytest.mark.parametrize("problem", [Power2(), Rosenbrock(l_b=0, u_b=1.0)])
def test_kkt_norm_correctly_stored(algorithm, problem) -> None:
    """Test that kkt norm is stored at each iteration requiring gradient."""
    problem.preprocess_functions()
    options = {
        "normalize_design_space": True,
        "kkt_tol_abs": 1e-5,
        "kkt_tol_rel": 1e-5,
        "max_iter": 100,
    }
    problem.reset()
    OptimizationLibraryFactory().execute(problem, algorithm, **options)
    kkt_hist = problem.database.get_function_history(problem.KKT_RESIDUAL_NORM)
    obj_grad_hist = problem.database.get_gradient_history(problem.objective.name)
    obj_hist = problem.database.get_function_history(problem.objective.name)
    assert len(kkt_hist) == obj_grad_hist.shape[0]
    assert len(obj_hist) >= len(kkt_hist)
    assert pytest.approx(problem.get_solution()[0], abs=1e-2) == problem.solution.x_opt
    assert pytest.approx(problem.get_solution()[1], abs=1e-2) == problem.solution.f_opt
