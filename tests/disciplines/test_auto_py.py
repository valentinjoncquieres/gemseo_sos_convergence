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
#                         documentation
#        :author: Francois Gallard
#    OTHER AUTHORS   - MACROSCOPIC CHANGES
import re
from pathlib import Path

import pytest
from gemseo.algos.opt_problem import OptimizationProblem
from gemseo.api import create_design_space
from gemseo.api import create_mda
from gemseo.api import create_scenario
from gemseo.api import execute_algo
from gemseo.core.mdofunctions.mdo_function import MDOFunction
from gemseo.core.parallel_execution import DiscParallelExecution
from gemseo.disciplines.auto_py import AutoPyDiscipline
from gemseo.disciplines.auto_py import to_arrays_dict
from numpy import array
from numpy import ones
from numpy import zeros
from scipy.optimize import rosen
from scipy.optimize import rosen_der


def create_ds(n):
    design_space = create_design_space()
    design_space.add_variable("x", n, l_b=-2 * ones(n), u_b=2 * ones(n), value=zeros(n))
    return design_space


def f1(y2=1.0, z=2.0):
    y1 = z + y2
    return y1


def f2(y1=2.0, z=2.0):
    y2 = z + 2 * y1
    y3 = 14
    return y2, y3


def f3(x=1.0):
    if x > 0:
        y = -x
        return y
    y = 2 * x
    return y


def f4(x=1.0):
    if x > 0:
        y = -x
        return y
    y = 2 * x
    return y, x


def test_basic():
    """Test a basic auto-discipline execution."""
    d1 = AutoPyDiscipline(f1)
    d1.execute()

    assert d1.local_data["y1"] == f1()

    d2 = AutoPyDiscipline(f2)
    d2.execute()
    assert d2.local_data["y2"] == f2()[0]


def test_write_schema(tmp_wd):
    """Test the writing of the schema."""
    d1 = AutoPyDiscipline(f1, write_schema=True)
    d1.execute()
    for trailer in ["input", "output"]:
        path = Path(f"f1_{trailer}.json")
        assert path.is_file()


def test_use_arrays():
    """Test the use of arrays."""
    d1 = AutoPyDiscipline(f1, use_arrays=True)
    d1.execute()
    assert d1.local_data["y1"] == f1()
    d1.execute({"x1": array([1.0]), "z": array([2.0])})
    assert d1.local_data["y1"] == f1()


def test_mda():
    """Test a MDA of AutoPyDisciplines."""
    d1 = AutoPyDiscipline(f1)
    d2 = AutoPyDiscipline(f2)
    mda = create_mda("MDAGaussSeidel", [d1, d2])
    mda.execute()


def test_fail_wrongly_formatted_function():
    """Test that a wrongly formatted function cannot be used."""
    AutoPyDiscipline(f3)
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Inconsistent definition of return statements in function: ('y', 'x') != ('y',)."
        ),
    ):
        AutoPyDiscipline(f4)


def test_fail_not_a_python_function():
    """Test the failure if a Python function is not provided."""
    not_a_function = 2
    with pytest.raises(TypeError, match="py_func must be callable."):
        AutoPyDiscipline(not_a_function)


def test_jac_pb():
    """Test the AutoPyDiscipline with Jacobian provided."""
    max_iter = 100
    n = 4
    algo = "L-BFGS-B"

    design_space = create_ds(n)
    pb = OptimizationProblem(design_space)
    pb.objective = MDOFunction(rosen, "rosen", jac=rosen_der)
    execute_algo(pb, algo, max_iter=max_iter)
    fopt_ref = pb.solution.f_opt

    design_space = create_ds(n)
    auto_rosen = AutoPyDiscipline(rosen, rosen_der)
    scn = create_scenario(auto_rosen, "DisciplinaryOpt", "r", design_space)
    scn.execute({"algo": algo, "max_iter": max_iter})
    scn_opt = scn.optimization_result.f_opt

    assert fopt_ref == scn_opt

    auto_rosen = AutoPyDiscipline(rosen)
    with pytest.raises(RuntimeError, match="The analytic Jacobian is missing."):
        auto_rosen._compute_jacobian()


@pytest.mark.parametrize("input", [{"a": [1.0]}, {"a": array([1.0])}])
def test_to_arrays_dict(input):
    """Test the function to_arrays_dict."""
    output = to_arrays_dict(input)
    assert output["a"] == array([1.0])


def test_multiprocessing():
    """Test the execution of an AutoPyDiscipline in multiprocessing."""
    d1 = AutoPyDiscipline(f1)
    d2 = AutoPyDiscipline(f2)

    parallel_execution = DiscParallelExecution([d1, d2], n_processes=2)
    parallel_execution.execute(
        [
            {"y2": array([2.0]), "z": array([1.0])},
            {"y1": array([5.0]), "z": array([3.0])},
        ]
    )

    assert d1.local_data["y1"] == f1(2.0, 1.0)
    assert d2.local_data["y2"] == f2(5.0, 3.0)[0]


@pytest.mark.parametrize(
    "name,expected", [("custom_name", "custom_name"), (None, "f1")]
)
def test_auto_py_name(name, expected):
    """Test that the name of the AutoPyDiscipline is set correctly."""
    d1 = AutoPyDiscipline(f1, name=name)
    assert d1.name == expected
