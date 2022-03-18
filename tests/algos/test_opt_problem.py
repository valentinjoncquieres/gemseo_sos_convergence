# -*- coding: utf-8 -*-
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

from __future__ import division, unicode_literals

from functools import partial
from typing import Dict, Tuple
from unittest import mock

import numpy as np
import pytest
from numpy import allclose, array, array_equal, cos, inf, ndarray, ones, sin, zeros
from scipy.linalg import norm
from scipy.optimize import rosen, rosen_der

from gemseo.algos.database import Database
from gemseo.algos.design_space import DesignSpace
from gemseo.algos.doe.doe_factory import DOEFactory
from gemseo.algos.doe.lib_custom import CustomDOE
from gemseo.algos.doe.lib_pydoe import PyDOE
from gemseo.algos.opt.opt_factory import OptimizersFactory
from gemseo.algos.opt_problem import OptimizationProblem
from gemseo.algos.parameter_space import ParameterSpace
from gemseo.algos.stop_criteria import DesvarIsNan, FunctionIsNan
from gemseo.api import execute_algo
from gemseo.core.doe_scenario import DOEScenario
from gemseo.core.mdofunctions.mdo_function import MDOFunction, MDOLinearFunction
from gemseo.problems.analytical.power_2 import Power2
from gemseo.problems.analytical.rosenbrock import Rosenbrock
from gemseo.problems.sobieski.wrappers import SobieskiProblem, SobieskiStructure
from gemseo.utils.py23_compat import Path

DIRNAME = Path(__file__).parent
FAIL_HDF = DIRNAME / "fail2.hdf5"


@pytest.fixture
def pow2_problem():  # type: (...) -> OptimizationProblem
    design_space = DesignSpace()
    design_space.add_variable("x", 3, l_b=-1.0, u_b=1.0)
    x_0 = np.ones(3)
    design_space.set_current_x(x_0)

    problem = OptimizationProblem(design_space)
    power2 = Power2()
    problem.objective = MDOFunction(
        power2.pow2,
        name="pow2",
        f_type="obj",
        jac=power2.pow2_jac,
        expr="x[0]**2+x[1]**2+x[2]**2",
        args=["x"],
    )
    return problem


def test_init():
    design_space = DesignSpace()
    OptimizationProblem(design_space)


def test_checks():
    n = 3
    design_space = DesignSpace()
    problem = OptimizationProblem(design_space)
    problem.objective = MDOFunction(rosen, name="rosen", f_type="obj", jac=rosen_der)

    with pytest.raises(Exception):
        problem.design_space.set_current_x(np.zeros(n))
    with pytest.raises(Exception):
        problem.design_space.set_upper_bound("x", np.ones(n))
    with pytest.raises(Exception):
        problem.design_space.set_lower_bound("x", -np.ones(n))

    with pytest.raises(ValueError):
        problem.check()

    design_space.add_variable("x")
    problem.check()


def test_callback():
    """Test the execution of a callback."""
    n = 3
    design_space = DesignSpace()
    design_space.add_variable("x", n, l_b=-1.0, u_b=1.0)
    design_space.set_current_x(np.zeros(n))
    problem = OptimizationProblem(design_space)
    problem.objective = MDOFunction(rosen, name="rosen", f_type="obj", jac=rosen_der)
    problem.check()

    call_me = mock.Mock()
    problem.add_callback(call_me)
    problem.preprocess_functions()
    problem.check()

    problem.objective(problem.design_space.get_current_x())
    call_me.assert_called_once()


def test_add_constraints(pow2_problem):
    problem = pow2_problem
    ineq1 = MDOFunction(
        Power2.ineq_constraint1,
        name="ineq1",
        f_type="ineq",
        jac=Power2.ineq_constraint1_jac,
        expr="0.5 -x[0] ** 3",
        args=["x"],
    )
    problem.add_ineq_constraint(ineq1, value=-1)
    assert problem.get_ineq_constraints_number() == 1
    assert problem.get_eq_constraints_number() == 0

    problem.add_ineq_constraint(ineq1, value=-1)
    problem.add_ineq_constraint(ineq1, value=-1)

    assert problem.get_constraints_number() == 3
    assert problem.has_nonlinear_constraints()

    ineq2 = MDOFunction(Power2.ineq_constraint1, name="ineq2")
    with pytest.raises(Exception):
        problem.add_constraint(ineq2, value=None, cstr_type=None)

    problem.add_constraint(ineq1, positive=True)

    problem.constraints = [problem.objective]
    with pytest.raises(ValueError):
        problem.check()


def test_getmsg_ineq_constraints(pow2_problem):
    expected = []
    problem = pow2_problem

    ineq_std = MDOFunction(
        Power2.ineq_constraint1,
        name="ineq_std",
        f_type="ineq",
        expr="cstr + cst",
        args=["x"],
    )
    problem.add_constraint(ineq_std)
    expected.append("ineq_std(x): cstr + cst <= 0.0")

    ineq_lo_posval = MDOFunction(
        Power2.ineq_constraint1,
        name="ineq_lo_posval",
        f_type="ineq",
        expr="cstr + cst",
        args=["x"],
    )
    problem.add_constraint(ineq_lo_posval, value=1.0)
    expected.append("ineq_lo_posval(x): cstr + cst <= 1.0")

    ineq_lo_negval = MDOFunction(
        Power2.ineq_constraint1,
        name="ineq_lo_negval",
        f_type="ineq",
        expr="cstr + cst",
        args=["x"],
    )
    problem.add_constraint(ineq_lo_negval, value=-1.0)
    expected.append("ineq_lo_negval(x): cstr + cst <= -1.0")

    ineq_up_negval = MDOFunction(
        Power2.ineq_constraint1,
        name="ineq_up_negval",
        f_type="ineq",
        expr="cstr + cst",
        args=["x"],
    )
    problem.add_constraint(ineq_up_negval, value=-1.0, positive=True)
    expected.append("ineq_up_negval(x): cstr + cst >= -1.0")

    ineq_up_posval = MDOFunction(
        Power2.ineq_constraint1,
        name="ineq_up_posval",
        f_type="ineq",
        expr="cstr + cst",
        args=["x"],
    )
    problem.add_constraint(ineq_up_posval, value=1.0, positive=True)
    expected.append("ineq_up_posval(x): cstr + cst >= 1.0")

    linear_constraint = MDOLinearFunction(array([1, 2]), "lin1", f_type="ineq")
    problem.add_constraint(linear_constraint)
    expected.append("lin1(x!0, x!1): x!0 + 2.00e+00*x!1 <= 0.0")

    linear_constraint = MDOLinearFunction(array([1, 2]), "lin2", f_type="ineq")
    problem.add_constraint(linear_constraint, positive=True, value=-1.0)
    expected.append("lin2(x!0, x!1): x!0 + 2.00e+00*x!1 >= -1.0")

    msg = str(problem)
    for elem in expected:
        assert elem in msg


def test_getmsg_eq_constraints(pow2_problem):
    expected = []
    problem = pow2_problem

    eq_std = MDOFunction(
        Power2.ineq_constraint1,
        name="eq_std",
        f_type="eq",
        expr="cstr + cst",
        args=["x"],
    )
    problem.add_constraint(eq_std)
    expected.append("eq_std(x): cstr + cst == 0.0")

    eq_posval = MDOFunction(
        Power2.ineq_constraint1,
        name="eq_posval",
        f_type="eq",
        expr="cstr + cst",
        args=["x"],
    )
    problem.add_constraint(eq_posval, value=1.0)
    expected.append("eq_posval(x): cstr + cst == 1.0")
    eq_negval = MDOFunction(
        Power2.ineq_constraint1,
        name="eq_negval",
        f_type="eq",
        expr="cstr + cst",
        args=["x"],
    )
    problem.add_constraint(eq_negval, value=-1.0)
    expected.append("eq_negval(x): cstr + cst == -1.0")

    msg = str(problem)
    for elem in expected:
        assert elem in msg


def test_get_dimension(pow2_problem):
    problem = pow2_problem
    problem.u_bounds = None
    problem.l_bounds = None
    dim = 3
    assert problem.get_dimension() == dim
    problem.u_bounds = np.ones(3)
    assert problem.get_dimension() == dim
    problem.l_bounds = -np.ones(3)
    assert problem.get_dimension() == dim


def test_check_format(pow2_problem):
    problem = pow2_problem
    with pytest.raises(TypeError):
        problem.check_format("1")


def test_constraints_dim(pow2_problem):
    problem = pow2_problem
    ineq1 = MDOFunction(
        Power2.ineq_constraint1,
        name="ineq1",
        f_type="ineq",
        jac=Power2.ineq_constraint1_jac,
        expr="0.5 -x[0] ** 3",
        args=["x"],
    )
    problem.add_ineq_constraint(ineq1, value=-1)
    with pytest.raises(Exception):
        problem.get_ineq_cstr_total_dim()
    assert problem.get_eq_constraints_number() == 0
    assert len(problem.get_nonproc_constraints()) == 0
    problem.preprocess_functions()
    assert len(problem.get_nonproc_constraints()) == 1


def test_check():
    # Objective is missing!
    design_space = DesignSpace()
    design_space.add_variable("x", 3, l_b=-1.0, u_b=1.0)
    design_space.set_current_x(np.array([1.0, 1.0, 1.0]))
    problem = OptimizationProblem(design_space)
    with pytest.raises(Exception):
        problem.check()


def test_missing_constjac(pow2_problem):
    problem = pow2_problem
    ineq1 = MDOFunction(sum, name="sum", f_type="ineq", expr="sum(x)", args=["x"])
    problem.add_ineq_constraint(ineq1, value=-1)
    problem.preprocess_functions()
    with pytest.raises(ValueError):
        problem.evaluate_functions(ones(3), eval_jac=True)


def _test_check_bounds(pow2_problem):
    dim = 3
    problem = pow2_problem
    problem.x_0 = np.ones(dim)

    problem.design_space.set_upper_bound("x", np.ones(dim))
    problem.design_space.set_lower_bound("x", np.array(dim * [-1]))
    with pytest.raises(TypeError):
        problem.check()

    problem.design_space.set_lower_bound("x", np.ones(dim))
    problem.design_space.set_upper_bound("x", np.array(dim * [-1]))
    with pytest.raises(TypeError):
        problem.check()

    problem.design_space.set_lower_bound("x", -np.ones(dim + 1))
    problem.design_space.set_upper_bound("x", np.ones(dim))
    with pytest.raises(ValueError):
        problem.check()

    problem.design_space.set_lower_bound("x", -np.ones(dim))
    problem.design_space.set_upper_bound("x", np.ones(dim))
    x_0 = np.ones(dim + 1)
    problem.design_space.set_current_x(x_0)
    with pytest.raises(ValueError):
        problem.check()

    problem.design_space.set_lower_bound("x", np.ones(dim) * 2)
    problem.design_space.set_upper_bound("x", np.ones(dim))
    x_0 = np.ones(dim)
    problem.design_space.set_current_x(x_0)
    with pytest.raises(ValueError):
        problem.check()


def test_pb_type(pow2_problem):
    problem = pow2_problem
    problem.pb_type = "None"
    with pytest.raises(TypeError):
        problem.check()


def test_differentiation_method(pow2_problem):
    problem = pow2_problem
    problem.differentiation_method = problem.COMPLEX_STEP
    problem.fd_step = 0.0
    with pytest.raises(ValueError):
        problem.check()
    problem.fd_step = 1e-7 + 1j * 1.0e-7
    problem.check()
    problem.fd_step = 1j * 1.0e-7
    problem.check()

    problem.differentiation_method = problem.FINITE_DIFFERENCES
    problem.fd_step = 0.0
    with pytest.raises(ValueError):
        problem.check()
    problem.fd_step = 1e-7 + 1j * 1.0e-7
    problem.check()


def test_get_dv_names():
    problem = Power2()
    OptimizersFactory().execute(problem, "SLSQP")
    assert problem.design_space.variables_names == ["x"]


def test_get_best_infeasible_point():
    problem = Power2()
    x_opt, f_opt, is_opt_feasible, _ = problem.get_best_infeasible_point()
    assert x_opt is None
    assert f_opt is None
    assert not is_opt_feasible
    problem.preprocess_functions()
    x_0 = problem.design_space.normalize_vect(zeros(3))
    f_val = problem.objective(x_0)
    x_opt, f_opt, is_opt_feasible, opt_fd = problem.get_best_infeasible_point()
    assert is_opt_feasible
    assert (x_opt == zeros(3)).all()
    assert f_opt == f_val
    assert "pow2" in opt_fd

    problem = Power2()
    problem.preprocess_functions()
    x_1 = problem.design_space.normalize_vect(array([-1.0, 0.0, 0.0]))
    problem.evaluate_functions(x_1)
    x_2 = problem.design_space.normalize_vect(array([0.0, -1.0, 0.0]))
    problem.evaluate_functions(x_2)
    x_opt, f_opt, is_opt_feasible, opt_fd = problem.get_best_infeasible_point()
    assert not is_opt_feasible
    assert x_opt is not None
    assert f_opt is not None
    assert len(opt_fd) > 0


def test_feasible_optimum_points():
    problem = Power2()
    with pytest.raises(ValueError):
        problem.get_optimum()

    OptimizersFactory().execute(
        problem, "SLSQP", eq_tolerance=1e-6, ineq_tolerance=1e-6
    )
    feasible_points, _ = problem.get_feasible_points()
    assert len(feasible_points) >= 2
    min_value, solution, is_feasible, _, _ = problem.get_optimum()
    assert (solution == feasible_points[-1]).all()
    assert allclose(min_value, 2.192090802, 9)
    assert allclose(solution[0], 0.79370053, 8)
    assert allclose(solution[1], 0.79370053, 8)
    assert allclose(solution[2], 0.96548938, 8)
    assert is_feasible


def test_nan():
    problem = Power2()
    problem.preprocess_functions()

    with pytest.raises(DesvarIsNan):
        problem.objective(array([1.0, float("nan")]))

    with pytest.raises(FunctionIsNan):
        problem.objective.jac(array([1.0, float("nan")]))

    problem = Power2()
    problem.objective.jac = lambda x: array([float("nan")] * 3)
    problem.preprocess_functions()
    with pytest.raises(FunctionIsNan):
        problem.objective.jac(array([0.1, 0.2, 0.3]))


def test_preprocess_functions():
    """Test the pre-processing of a problem functions."""
    problem = Power2()
    obs1 = MDOFunction(norm, "design Euclidean norm")
    problem.add_observable(obs1)
    obs2 = MDOFunction(partial(norm, inf), "design infinity norm")
    problem.add_observable(obs2)

    # Store the initial functions identities
    obj_id = id(problem.objective)
    cstr_id = set([id(cstr) for cstr in problem.constraints])
    obs_id = set([id(obs) for obs in problem.observables])

    problem.preprocess_functions(normalize=False, round_ints=False)

    # Check that the non-preprocessed functions are the original ones
    assert id(problem.nonproc_objective) == obj_id
    assert set([id(cstr) for cstr in problem.nonproc_constraints]) == cstr_id
    assert set([id(obs) for obs in problem.nonproc_observables]) == obs_id

    # Check that the current problem functions are NOT the original ones
    assert id(problem.objective) != obj_id
    assert set([id(cstr) for cstr in problem.constraints]).isdisjoint(cstr_id)
    assert set([id(obs) for obs in problem.observables]).isdisjoint(obs_id)

    nonproc_constraints = set([repr(cstr) for cstr in problem.nonproc_constraints])
    constraints = set([repr(cstr) for cstr in problem.constraints])
    assert nonproc_constraints == constraints


def test_normalize_linear_function():
    """Test the normalization of linear functions."""
    design_space = DesignSpace()
    lower_bounds = array([-5.0, -7.0])
    upper_bounds = array([11.0, 13.0])
    x_0 = 0.2 * lower_bounds + 0.8 * upper_bounds
    design_space.add_variable("x", 2, l_b=lower_bounds, u_b=upper_bounds, value=x_0)
    objective = MDOLinearFunction(
        array([[2.0, 0.0], [0.0, 3.0]]), "affine", "obj", "x", array([5.0, 7.0])
    )
    low_bnd_value = objective(lower_bounds)
    upp_bnd_value = objective(upper_bounds)
    initial_value = objective(x_0)
    problem = OptimizationProblem(design_space)
    problem.objective = objective
    problem.preprocess_functions(normalize=True, use_database=False, round_ints=False)
    assert allclose(problem.objective(zeros(2)), low_bnd_value)
    assert allclose(problem.objective(ones(2)), upp_bnd_value)
    assert allclose(problem.objective(0.8 * ones(2)), initial_value)


def test_export_hdf(tmp_wd):
    file_path = tmp_wd / "power2.h5"
    problem = Power2()
    OptimizersFactory().execute(problem, "SLSQP")
    problem.export_hdf(file_path, append=True)  # Shall still work now

    def check_pb(imp_pb):
        assert file_path.exists()
        assert str(imp_pb) == str(problem)
        assert str(imp_pb.solution) == str(problem.solution)
        assert file_path.exists()

        assert problem.get_eq_cstr_total_dim() == 1
        assert problem.get_ineq_cstr_total_dim() == 2

    problem.export_hdf(file_path, append=False)

    imp_pb = OptimizationProblem.import_hdf(file_path)
    check_pb(imp_pb)

    problem.export_hdf(file_path, append=True)
    imp_pb = OptimizationProblem.import_hdf(file_path)
    check_pb(imp_pb)
    val = imp_pb.objective(imp_pb.database.get_x_by_iter(1))
    assert isinstance(val, float)
    jac = imp_pb.objective.jac(imp_pb.database.get_x_by_iter(0))
    assert isinstance(jac, ndarray)
    with pytest.raises(ValueError):
        imp_pb.objective(array([1.1254]))


def test_evaluate_functions():
    problem = Power2()
    problem.evaluate_functions(
        x_vect=array([1.0, 0.5, 0.2]),
        eval_jac=True,
        eval_obj=False,
        normalize=False,
    )
    problem.evaluate_functions(normalize=False, no_db_no_norm=True, eval_obj=False)


def test_evaluate_functions_non_preprocessed(constrained_problem):
    """Check the evaluation of non-preprocessed functions."""
    values, jacobians = constrained_problem.evaluate_functions(
        normalize=False, no_db_no_norm=True
    )
    assert set(values.keys()) == {"f", "g", "h"}
    assert values["f"] == pytest.approx(2.0)
    assert values["g"] == pytest.approx(array([1.0]))
    assert values["h"] == pytest.approx(array([1.0, 1.0]))
    assert jacobians == dict()


@pytest.mark.parametrize(
    ["pre_normalize", "eval_normalize", "x_vect"],
    [
        (False, False, array([0.1, 0.2, 0.3])),
        (False, True, array([0.55, 0.6, 0.65])),
        (True, False, array([0.1, 0.2, 0.3])),
        (True, True, array([0.55, 0.6, 0.65])),
    ],
)
def test_evaluate_functions_preprocessed(pre_normalize, eval_normalize, x_vect):
    """Check the evaluation of preprocessed functions."""
    constrained_problem = Power2()
    constrained_problem.preprocess_functions(normalize=pre_normalize)
    values, _ = constrained_problem.evaluate_functions(
        x_vect=x_vect, normalize=eval_normalize
    )
    assert set(values.keys()) == {"pow2", "ineq1", "ineq2", "eq"}
    assert values["pow2"] == pytest.approx(0.14)
    assert values["ineq1"] == pytest.approx(array([0.499]))
    assert values["ineq2"] == pytest.approx(array([0.492]))
    assert values["eq"] == pytest.approx(array([0.873]))


def test_no_normalization():
    problem = Power2()
    OptimizersFactory().execute(problem, "SLSQP", normalize_design_space=False)
    f_opt, _, is_feas, _, _ = problem.get_optimum()
    assert is_feas
    assert abs(f_opt - 2.192) < 0.01


def test_nan_func():
    problem = Power2()

    def nan_func(_):
        return float("nan")

    problem.objective.func = nan_func
    problem.preprocess_functions()
    with pytest.raises(FunctionIsNan):
        problem.objective(zeros(3))


def test_fail_import():
    with pytest.raises(KeyError):
        OptimizationProblem.import_hdf(FAIL_HDF)


def test_append_export(tmp_wd):
    """Test the export of an HDF5 file with append mode.

    Args:
        tmp_wd: Fixture to move into a temporary directory.
    """
    problem = Rosenbrock()
    problem.preprocess_functions()
    func = problem.objective
    file_path_db = "test_pb_append.hdf5"
    # Export empty file
    problem.export_hdf(file_path_db, append=False)

    n_calls = 200
    for i in range(n_calls):
        func(array([0.1, 1.0 / (i + 1.0)]))

    # Export again with append mode
    problem.export_hdf(file_path_db, append=True)

    read_db = Database(file_path_db)
    assert len(read_db) == n_calls

    i += 1
    func(array([0.1, 1.0 / (i + 1.0)]))

    # Export again with identical elements plus a new one.
    problem.export_hdf(file_path_db, append=True)
    read_db = Database(file_path_db)
    assert len(read_db) == n_calls + 1


def test_grad_normalization(pow2_problem):
    problem = pow2_problem
    x_vec = ones(3)
    grad = problem.objective.jac(x_vec)
    problem.preprocess_functions(normalize=True)
    norm_grad = problem.objective.jac(x_vec)

    assert 0.0 == pytest.approx(norm(norm_grad - 2 * grad))

    unnorm_grad = problem.design_space.normalize_vect(norm_grad, minus_lb=False)
    assert 0.0 == pytest.approx(norm(unnorm_grad - grad))


def test_2d_objective():
    disc = SobieskiStructure()
    design_space = SobieskiProblem().read_design_space()
    inputs = disc.get_input_data_names()
    design_space.filter(inputs)
    doe_scenario = DOEScenario([disc], "DisciplinaryOpt", "y_12", design_space)
    doe_scenario.execute({"algo": "DiagonalDOE", "n_samples": 10})


def test_observable(pow2_problem):
    """Test the handling of observables.

    Args:
        pow2_problem: The Power2 problem.
    """
    problem = pow2_problem
    design_norm = "design norm"
    observable = MDOFunction(norm, design_norm)
    problem.add_observable(observable)

    # Check that the observable can be found
    assert problem.get_observable(design_norm) is observable
    with pytest.raises(ValueError):
        problem.get_observable("toto")

    # Check that the observable is stored in the database
    OptimizersFactory().execute(problem, "SLSQP")
    database = problem.database
    iter_norms = [norm(key.unwrap()) for key in database.keys()]
    iter_obs = [value[design_norm] for value in database.values()]
    assert iter_obs == iter_norms

    # Check that the observable is exported
    dataset = problem.export_to_dataset("dataset")
    func_data = dataset.get_data_by_group("functions", as_dict=True)
    obs_data = func_data.get(design_norm)
    assert obs_data is not None
    assert func_data[design_norm][:, 0].tolist() == iter_norms
    assert dataset.GRADIENT_GROUP not in dataset.groups
    dataset = problem.export_to_dataset("dataset", export_gradients=True)
    assert dataset.GRADIENT_GROUP in dataset.groups
    name = Database.get_gradient_name("pow2")
    n_iter = len(database)
    n_var = problem.design_space.dimension
    assert dataset.get_data_by_names(name, as_dict=False).shape == (n_iter, n_var)


@pytest.mark.parametrize(
    "filter_non_feasible,as_dict,expected",
    [
        (
            True,
            True,
            {
                "x": array(
                    [[1.0, 1.0, np.power(0.9, 1 / 3)], [0.9, 0.9, np.power(0.9, 1 / 3)]]
                )
            },
        ),
        (
            True,
            False,
            np.array(
                [[1.0, 1.0, np.power(0.9, 1 / 3)], [0.9, 0.9, np.power(0.9, 1 / 3)]]
            ),
        ),
        (
            False,
            True,
            {
                "x": array(
                    [
                        [1.0, 1.0, np.power(0.9, 1 / 3)],
                        [0.9, 0.9, np.power(0.9, 1 / 3)],
                        [0.0, 0.0, 0.0],
                        [0.5, 0.5, 0.5],
                    ]
                )
            },
        ),
        (
            False,
            False,
            np.array(
                [
                    [1.0, 1.0, np.power(0.9, 1 / 3)],
                    [0.9, 0.9, np.power(0.9, 1 / 3)],
                    [0.0, 0.0, 0.0],
                    [0.5, 0.5, 0.5],
                ]
            ),
        ),
    ],
)
def test_get_data_by_names(filter_non_feasible, as_dict, expected):
    """Test if the data is filtered correctly.

    Args:
        filter_non_feasible: If True, remove the non-feasible points from
                the data.
        as_dict: If True, the data is returned as a dictionary.
        expected: The reference data for the test.
    """
    # Create a Power2 instance
    problem = Power2()
    # Add two feasible points
    problem.database.store(
        np.array([1.0, 1.0, np.power(0.9, 1 / 3)]),
        {"pow2": 2.9, "ineq1": -0.5, "ineq2": -0.5, "eq": 0.0},
    )
    problem.database.store(
        np.array([0.9, 0.9, np.power(0.9, 1 / 3)]),
        {"pow2": 2.55, "ineq1": -0.229, "ineq2": -0.229, "eq": 0.0},
    )
    # Add two non-feasible points
    problem.database.store(
        np.array([0.0, 0.0, 0.0]), {"pow2": 0.0, "ineq1": 0.5, "ineq2": 0.5, "eq": 0.9}
    )
    problem.database.store(
        np.array([0.5, 0.5, 0.5]),
        {"pow2": 0.75, "ineq1": 0.375, "ineq2": 0.375, "eq": 0.775},
    )
    # Get the data back
    data = problem.get_data_by_names(
        names=["x"], as_dict=as_dict, filter_non_feasible=filter_non_feasible
    )
    # Check output is filtered when needed
    if as_dict:
        assert np.array_equal(data["x"], expected["x"])
    else:
        assert np.array_equal(data, expected)


def test_gradient_with_random_variables():
    """Check that the Jacobian is correctly computed with random variable."""
    parameter_space = ParameterSpace()
    parameter_space.add_random_variable("x", "OTUniformDistribution")

    problem = OptimizationProblem(parameter_space)
    problem.objective = MDOFunction(lambda x: 3 * x ** 2, "func", jac=lambda x: 6 * x)
    PyDOE().execute(problem, "fullfact", n_samples=3, eval_jac=True)

    data = problem.database.get_func_grad_history("func")

    assert array_equal(data, array([0.0, 3.0, 6.0]))


def test_is_mono_objective():
    """Check the boolean OptimizationProblem.is_mono_objective."""
    design_space = DesignSpace()
    design_space.add_variable("")
    problem = OptimizationProblem(design_space)
    problem.objective = MDOFunction(
        lambda x: array([1.0, 2.0]), name="func", f_type="obj", outvars=["y1", "y2"]
    )

    assert not problem.is_mono_objective

    problem.objective = MDOFunction(
        lambda x: x, name="func", f_type="obj", outvars=["y1"]
    )

    assert problem.is_mono_objective


def test_undefined_differentiation_method():
    """Check that passing an undefined differentiation raises a ValueError."""
    with pytest.raises(
        ValueError,
        match=(
            "'foo' is not a differentiation methods; "
            "available ones are: "
            "'user', 'complex_step', 'finite_differences', 'no_derivatives'."
        ),
    ):
        OptimizationProblem(DesignSpace(), differentiation_method="foo")


@pytest.fixture
def problem():  # type: (...) -> OptimizationProblem
    """A simple optimization problem :math:`max_x x`."""
    design_space = DesignSpace()
    design_space.add_variable("x", l_b=0, u_b=1, value=0.5)
    opt_problem = OptimizationProblem(design_space)
    opt_problem.objective = MDOFunction(lambda x: x, name="func", f_type="obj")
    return opt_problem


def test_parallel_differentiation(problem):
    """Check that parallel_differentiation is taken into account."""
    assert not problem.parallel_differentiation
    problem.parallel_differentiation = True
    assert problem.parallel_differentiation


def test_parallel_differentiation_options(problem):
    """Check that parallel_differentiation_options is taken into account."""
    assert not problem.parallel_differentiation_options
    problem.parallel_differentiation_options = {"step": 1e-10}
    assert problem.parallel_differentiation_options == {"step": 1e-10}


def test_parallel_differentiation_setting_after_functions_preprocessing(problem):
    """Check that parallel differentiation cannot be changed after preprocessing."""
    problem.preprocess_functions()
    expected_message = (
        "The parallel differentiation cannot be changed "
        "because the functions have already been pre-processed."
    )
    with pytest.raises(
        RuntimeError,
        match=expected_message,
    ):
        problem.parallel_differentiation = "user"
    with pytest.raises(
        RuntimeError,
        match=expected_message,
    ):
        problem.parallel_differentiation_options = {}


def test_database_name(problem):
    """Check the name of the database."""
    DOEFactory().execute(problem, "fullfact", n_samples=1)
    problem.database.name = "my_database"
    dataset = problem.export_to_dataset()
    assert dataset.name == problem.database.name
    dataset = problem.export_to_dataset("dataset")
    assert dataset.name == "dataset"


@pytest.mark.parametrize(
    "skip_int_check,expected_message",
    [
        (
            True,
            "Forcing the execution of an algorithm that does not handle "
            "integer variables.",
        ),
        (
            False,
            "Algorithm L-BFGS-B is not adapted to the problem, it does not handle "
            "integer variables.\n"
            "Execution may be forced setting the 'skip_int_check' argument "
            "to 'True'.",
        ),
    ],
)
def test_int_opt_problem(skip_int_check, expected_message, caplog):
    """Test the execution of an optimization problem with integer variables.

    Args:
        skip_int_check: Whether to skip the integer variable handling check
            of the selected algorithm.
        expected_message: The expected message to be recovered from the logger or
            the ValueError message.
        caplog: Fixture to access and control log capturing.
    """
    f_1 = MDOFunction(sin, name="f_1", jac=cos, expr="sin(x)")
    design_space = DesignSpace()
    design_space.add_variable(
        "x", 1, l_b=1, u_b=3, value=1 * ones(1), var_type="integer"
    )
    problem = OptimizationProblem(design_space)
    problem.objective = -f_1

    if skip_int_check:
        OptimizersFactory().execute(
            problem,
            "L-BFGS-B",
            normalize_design_space=True,
            skip_int_check=skip_int_check,
        )
        assert expected_message in caplog.text
        assert problem.get_optimum()[1] == array([2.0])
    else:
        with pytest.raises(ValueError, match=expected_message):
            OptimizersFactory().execute(
                problem,
                "L-BFGS-B",
                normalize_design_space=True,
                skip_int_check=skip_int_check,
            )


@pytest.fixture(scope="module")
def constrained_problem():  # type: (...) -> OptimizationProblem
    """A constrained optimisation problem with multidimensional constraints."""
    design_space = DesignSpace()
    design_space.add_variable("x", 2, value=1.0)
    objective = MDOFunction(lambda x: x.sum(), "f")
    constraint_1d = MDOFunction(lambda x: x[0], "g")
    constraint_2d = MDOFunction(lambda x: x, "h")
    problem = OptimizationProblem(design_space)
    problem.objective = objective
    problem.add_constraint(constraint_1d, cstr_type="ineq")
    problem.add_constraint(constraint_2d, cstr_type="eq")
    return problem


@pytest.mark.parametrize(
    ["names", "dimensions"],
    [(None, {"f": 1, "g": 1, "h": 2}), (["g", "h"], {"g": 1, "h": 2})],
)
def test_get_functions_dimensions(constrained_problem, names, dimensions):
    """Check the computation of the functions dimensions."""
    assert constrained_problem.get_functions_dimensions(names) == dimensions


@pytest.mark.parametrize(
    ["design", "n_unsatisfied"],
    [
        (array([0.0, 0.0]), 0),
        (array([-1.0, 0.0]), 1),
        (array([-1.0, -1.0]), 2),
        (array([1.0, 1.0]), 3),
    ],
)
def test_get_number_of_unsatisfied_constraints(
    constrained_problem, design, n_unsatisfied
):
    """Check the computation of the number of unsatisfied constraints."""
    assert (
        constrained_problem.get_number_of_unsatisfied_constraints(design)
        == n_unsatisfied
    )


def test_get_scalar_constraints_names(constrained_problem):
    """Check the computation of the scalar constraints names."""
    scalar_names = constrained_problem.get_scalar_constraints_names()
    assert set(scalar_names) == {
        "g",
        "h{}0".format(DesignSpace.SEP),
        "h{}1".format(DesignSpace.SEP),
    }


def test_observables_callback():
    """Test that the observables are called properly."""
    problem = Power2()
    obs1 = MDOFunction(norm, "design_norm")
    problem.add_observable(obs1)
    problem.database.store(
        array([0.79499653, 0.20792012, 0.96630481]),
        {"pow2": 1.61, "ineq1": -0.0024533, "ineq2": -0.0024533, "eq": -0.00228228},
    )

    problem.preprocess_functions(normalize=False)
    problem.execute_observables_callback(
        last_x=array([0.79499653, 0.20792012, 0.96630481])
    )

    assert obs1.n_calls == 1


def test_approximated_jacobian_wrt_uncertain_variables():
    """Check that the approximated Jacobian wrt uncertain variables is correct."""
    uspace = ParameterSpace()
    uspace.add_random_variable("u", "OTNormalDistribution")
    problem = OptimizationProblem(uspace)
    problem.differentiation_method = problem.FINITE_DIFFERENCES
    problem.objective = MDOFunction(lambda u: u, "func")
    CustomDOE().execute(problem, "CustomDOE", samples=array([[0.0]]), eval_jac=True)
    grad = problem.database.get_func_grad_history("func")
    assert grad[0, 0] == pytest.approx(1.0, abs=1e-3)


@pytest.fixture
def rosenbrock_lhs():  # type: (...) -> Tuple[Rosenbrock,Dict[str,ndarray]]
    """The Rosenbrock problem after evaluation and its start point."""
    problem = Rosenbrock()
    problem.add_observable(MDOFunction(lambda x: sum(x), "obs"))
    problem.add_constraint(MDOFunction(lambda x: sum(x), "cstr"), cstr_type="ineq")
    start_point = problem.design_space.get_current_x_dict()
    execute_algo(problem, "lhs", n_samples=3, algo_type="doe")
    return problem, start_point


def test_reset(rosenbrock_lhs):
    """Check the default behavior of OptimizationProblem.reset."""
    problem, start_point = rosenbrock_lhs
    nonproc_functions = (
        [problem.nonproc_objective]
        + problem.nonproc_constraints
        + problem.nonproc_observables
        + problem.nonproc_new_iter_observables
    )
    problem.reset()
    assert len(problem.database) == 0
    assert problem.database.get_max_iteration() == 0
    assert not problem._OptimizationProblem__functions_are_preprocessed
    for key, val in problem.design_space.get_current_x_dict().items():
        assert (start_point[key] == val).all()

    functions = (
        [problem.objective]
        + problem.constraints
        + problem.observables
        + problem.new_iter_observables
    )
    for func, nonproc_func in zip(functions, nonproc_functions):
        assert id(func) == id(nonproc_func)

    assert problem.nonproc_objective is None
    assert problem.nonproc_constraints == []
    assert problem.nonproc_observables == []
    assert problem.nonproc_new_iter_observables == []


def test_reset_database(rosenbrock_lhs):
    """Check OptimizationProblem.reset without database reset."""
    problem, start_point = rosenbrock_lhs
    problem.reset(database=False)
    assert len(problem.database) == 3
    assert problem.database.get_max_iteration() == 3


def test_reset_current_iter(rosenbrock_lhs):
    """Check OptimizationProblem.reset without current_iter reset."""
    problem, start_point = rosenbrock_lhs
    problem.reset(current_iter=False)
    assert len(problem.database) == 0
    assert problem.database.get_max_iteration() == 3


def test_reset_design_space(rosenbrock_lhs):
    """Check OptimizationProblem.reset without design_space reset."""
    problem, start_point = rosenbrock_lhs
    problem.reset(design_space=False)
    for key, val in problem.design_space.get_current_x_dict().items():
        assert (start_point[key] != val).any()


def test_reset_functions(rosenbrock_lhs):
    """Check OptimizationProblem.reset without reset the number of function calls."""
    problem, start_point = rosenbrock_lhs
    problem.reset(function_calls=False)
    assert problem.objective.n_calls == 3


def test_reset_preprocess(rosenbrock_lhs):
    """Check OptimizationProblem.reset without functions pre-processing reset."""
    problem, start_point = rosenbrock_lhs
    problem.reset(preprocessing=False)
    assert problem._OptimizationProblem__functions_are_preprocessed
    functions = (
        [problem.objective]
        + problem.constraints
        + problem.observables
        + problem.new_iter_observables
    )
    nonproc_functions = (
        [problem.nonproc_objective]
        + problem.nonproc_constraints
        + problem.nonproc_observables
        + problem.nonproc_new_iter_observables
    )
    for func, nonproc_func in zip(functions, nonproc_functions):
        assert id(func) != id(nonproc_func)

    assert problem.nonproc_objective is not None
    assert len(problem.nonproc_constraints) == len(problem.constraints)
    assert len(problem.nonproc_observables) == len(problem.observables)
    assert len(problem.nonproc_new_iter_observables) == len(
        problem.new_iter_observables
    )


def test_function_string_representation_from_hdf():
    """Check the string representation of a function when importing a HDF5 file.

    The commented code is the one used for creating the HDF5 file.
    """
    # design_space = DesignSpace()
    # design_space.add_variable("x0", l_b=0.0, u_b=1.0, value=0.5)
    # design_space.add_variable("x1", l_b=0.0, u_b=1.0, value=0.5)
    # problem = OptimizationProblem(design_space)
    # problem.objective = MDOFunction(lambda x: x[0] + x[1], "f", args=["x0", "x1"])
    # problem.constraints.append(
    #     MDOFunction(lambda x: x[0] + x[1], "g", args=["x0", "x1"])
    # )
    # problem.export_hdf("opt_problem_to_check_string_representation.hdf5")

    new_problem = OptimizationProblem.import_hdf(
        DIRNAME / "opt_problem_to_check_string_representation.hdf5"
    )
    assert str(new_problem.objective) == "f(x0, x1)"
    assert str(new_problem.constraints[0]) == "g(x0, x1)"


@pytest.mark.parametrize(["name", "dimension"], [("f", 1), ("g", 1), ("h", 2)])
def test_get_function_dimension(constrained_problem, name, dimension):
    """Check the output dimension of a problem function."""
    assert constrained_problem.get_function_dimension(name) == dimension


def test_get_function_dimension_unknown(constrained_problem):
    """Check the output dimension of an unknown problem function."""
    with pytest.raises(ValueError, match="The problem has no function named unknown."):
        constrained_problem.get_function_dimension("unknown")


@pytest.fixture()
def design_space():  # type: (...) -> mock.Mock
    """A design space."""
    design_space = mock.Mock()
    design_space.get_current_x = mock.Mock()
    return design_space


@pytest.fixture()
def function():  # type: (...) -> mock.Mock
    """A function."""
    function = mock.MagicMock(return_value=1.0)
    function.name = "f"
    return function


@pytest.mark.parametrize(["expects_normalized"], [(True,), (False,)])
def test_get_function_dimension_no_dim(function, design_space, expects_normalized):
    """Check the implicitly defined output dimension of a problem function."""
    function.has_dim = mock.Mock(return_value=False)
    function.expects_normalized_inputs = expects_normalized
    design_space.has_current_x = mock.Mock(return_value=True)
    problem = OptimizationProblem(design_space)
    problem.objective = function
    problem.get_x0_normalized = mock.Mock()
    assert problem.get_function_dimension(function.name) == 1
    if expects_normalized:
        problem.get_x0_normalized.assert_called_once()
        design_space.get_current_x.assert_not_called()
    else:
        problem.get_x0_normalized.assert_not_called()
        design_space.get_current_x.assert_called_once()


def test_get_function_dimension_unavailable(function, design_space):
    """Check the unavailable output dimension of a problem function."""
    function.has_dim = mock.Mock(return_value=False)
    design_space.has_current_x = mock.Mock(return_value=False)
    problem = OptimizationProblem(design_space)
    problem.objective = function
    with pytest.raises(
        RuntimeError,
        match="The output dimension of function {} is not available.".format(
            function.name
        ),
    ):
        problem.get_function_dimension(function.name)


@pytest.mark.parametrize("categorize", [True, False])
@pytest.mark.parametrize("export_gradients", [True, False])
def test_dataset_missing_values(categorize, export_gradients):
    """Test the export of a database with missing values to a dataset.

    Args:
        categorize: If True, remove the non-feasible points from
                the data.
        export_gradients: If True, export the gradient to the dataset.
    """
    problem = Power2()
    # Add a complete evaluation.
    problem.database.store(
        np.array([1.0, 1.0, 1.0]),
        {
            "pow2": 3.0,
            "Iter": [1],
            "design norm": 1.7320508075688772,
            "@pow2": array([2.0, 2.0, 2.0]),
        },
    )
    # Add a point with missing values.
    problem.database.store(np.array([-1.0, -1.0, -1.0]), {"Iter": [2]})
    # Add a complete evaluation.
    problem.database.store(
        np.array([-1.77635684e-15, 1.33226763e-15, 4.44089210e-16]),
        {
            "pow2": 5.127595883936577e-30,
            "Iter": [3],
            "design norm": 2.2644195468014703e-15,
            "@pow2": array([-3.55271368e-15, 2.66453526e-15, 8.88178420e-16]),
        },
    )
    # Add one evaluation with complete function data but missing gradient.
    problem.database.store(
        np.array([0.0, 0.0, 0.0]), {"pow2": 0.0, "Iter": [4], "design norm": 0.0}
    )
    # Another point with missing values.
    problem.database.store(
        np.array([0.5, 0.5, 0.5]),
        {"Iter": [5]},
    )
    # Export to a dataset.
    dataset = problem.export_to_dataset(
        categorize=categorize, export_gradients=export_gradients
    )
    # Check that the missing values are exported as NaN.
    if categorize:
        if export_gradients:
            assert dataset.data["functions"][3].all() == np.array([0.0, 0.0]).all()
            assert (
                dataset.data["gradients"][3].all()
                == np.array([np.nan, np.nan, np.nan]).all()
            )
        else:
            assert (
                dataset.data["functions"][1].all() == np.array([np.nan, np.nan]).all()
            )

    else:
        if export_gradients:
            assert (
                dataset.data["parameters"][3].all()
                == np.array([0.0, 0.0, 0.0, 0.0, 0.0, np.nan, np.nan, np.nan]).all()
            )
        else:
            assert (
                dataset.data["parameters"][4].all()
                == np.array([0.5, 0.5, 0.5, np.nan, np.nan]).all()
            )


@pytest.fixture
def problem_for_eval_obs_jac() -> OptimizationProblem:
    """An optimization problem to check the option eval_obs_jac."""
    design_space = DesignSpace()
    design_space.add_variable("x", l_b=0.0, u_b=1.0, value=0.5)

    problem = OptimizationProblem(design_space)
    problem.differentiation_method = problem.FINITE_DIFFERENCES
    problem.objective = MDOFunction(lambda x: x, "f", jac=lambda x: 1)
    problem.add_constraint(
        MDOFunction(lambda x: x, "c", f_type="ineq", jac=lambda x: 1)
    )
    problem.add_observable(MDOFunction(lambda x: x, "o", jac=lambda x: 1))
    return problem


@pytest.mark.parametrize(
    "options",
    [
        {"algo_name": "SLSQP", "algo_type": "opt", "max_iter": 1},
        {"algo_name": "fullfact", "algo_type": "doe", "n_samples": 1},
    ],
)
@pytest.mark.parametrize("eval_obs_jac", [True, False])
def test_observable_jac(problem_for_eval_obs_jac, options, eval_obs_jac):
    """Check that the observable derivatives are computed when eval_obs_jac is True."""
    execute_algo(problem_for_eval_obs_jac, eval_obs_jac=eval_obs_jac, **options)
    assert problem_for_eval_obs_jac.database.contains_dataname("@o") is eval_obs_jac
