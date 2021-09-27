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

from copy import deepcopy
from math import cos, exp, log10, sin

import pytest
from numpy import array, complex128, float64, zeros
from numpy.linalg import norm
from scipy.optimize import rosen, rosen_der

from gemseo.api import create_discipline
from gemseo.core.analytic_discipline import AnalyticDiscipline
from gemseo.core.discipline import MDODiscipline
from gemseo.problems.sobieski.wrappers import SobieskiMission
from gemseo.utils.derivatives.gradient_approximator import GradientApproximationFactory
from gemseo.utils.derivatives_approx import (
    ComplexStep,
    DisciplineJacApprox,
    FirstOrderFD,
    comp_best_step,
)


def test_init_first_order_fd():
    """"""
    FirstOrderFD(rosen)


def test_init_complex_step():
    """"""
    cplx = ComplexStep(rosen, 1e-30j)
    assert cplx.step == 1e-30

    grad = cplx.f_gradient(zeros(3))
    assert norm(grad - rosen_der(zeros(3))) < 1e-3

    with pytest.raises(ValueError):
        cplx.f_gradient(zeros(3) + 1j)


def get_x_tests():
    """"""
    return [
        [0.0, 0.0],
        [1.0, 3.0, 5.0],
        [-1.9, 3.7, 4.0, 7, -1.9, 3.7, 4.0, 7],
        [-1.0, 5.0],
    ]


def run_tests(xs, fd_app):
    """

    :param xs: param fd_app:
    :param fd_app:

    """
    for x in xs:
        xa = array(x)
        appeox = fd_app.f_gradient(xa)
        exact = rosen_der(xa)
        err = norm(appeox - exact) / norm(exact)
        assert err < 1e-4


def test_approx_first_order_fd():
    run_tests(get_x_tests(), FirstOrderFD(rosen, 1e-8))


def test_approx_complex_step():
    run_tests(get_x_tests(), ComplexStep(rosen))


def test_approx_complex_step_diff_steps_e60():
    run_tests(get_x_tests(), ComplexStep(rosen, 1e-60))


def test_approx_complex_step_diff_steps_e200():
    run_tests(get_x_tests(), ComplexStep(rosen, 1e-200))


def test_approx_complex_step_diff_steps_e30():
    run_tests(get_x_tests(), ComplexStep(rosen, 1e-30))


def test_abs_der():
    discipline = AnalyticDiscipline("name", {"y": "x", "z": "x"})
    discipline.execute()
    apprx = DisciplineJacApprox(discipline)
    apprx.compute_approx_jac(["z"], ["x"])

    discipline.linearize()
    discipline.jac["z"]["x"] = array([[2.0]])

    assert not apprx.check_jacobian(discipline.jac, ["z"], ["x"], discipline)

    discipline.linearize()
    discipline.jac["z"]["x"] = array([[2.0, 3.0]])

    assert not apprx.check_jacobian(discipline.jac, ["z"], ["x"], discipline)


def test_complex_fail():
    discipline = SobieskiMission("complex128")
    assert discipline.check_jacobian(derr_approx=discipline.COMPLEX_STEP)

    data = deepcopy(discipline.default_inputs)
    data["x_shared"] += 0.1j
    with pytest.raises(ValueError):
        discipline.check_jacobian(data, derr_approx=discipline.COMPLEX_STEP)


@pytest.mark.parametrize("discipline_name", ["Sellar1", "Sellar2"])
def test_auto_step(discipline_name):
    discipline = create_discipline(discipline_name)

    ok = discipline.check_jacobian(auto_set_step=True, threshold=1e-2, step=1e-7)
    assert ok


def test_opt_step():
    x = 0.1
    step = 1e-6
    funcs = [sin, cos, exp]
    jacs = [cos, lambda x: -sin(x), exp]

    for func, jac in zip(funcs, jacs):
        for mult in [1.0, 1e2, 1e-2]:
            for x in [0.0, 1.0, 3.0]:

                f_p = func(mult * (x + step))
                f_x = func(mult * x)
                f_m = func(mult * (x - step))
                trunc_error, cancel_error, opt_step = comp_best_step(
                    f_p, f_x, f_m, step
                )
                if trunc_error is None:
                    continue

                df_app = (func(mult * (x + opt_step)) - f_x) / opt_step
                err = abs(df_app - mult * jac(mult * x))
                full_error = trunc_error + cancel_error
                rel_erro_on_err = abs(log10(abs(full_error)) - log10(abs(err))) < 5
                assert rel_erro_on_err


@pytest.mark.parametrize(
    "indices,expected_sequence,expected_variables_indices",
    [
        ({"y": None}, [0, 1, 2, 3, 4], {"x": [0, 1], "y": [0, 1, 2]}),
        ({"y": Ellipsis}, [0, 1, 2, 3, 4], {"x": [0, 1], "y": [0, 1, 2]}),
        ({"y": 1}, [0, 1, 3], {"x": [0, 1], "y": [1]}),
        ({"y": [2, 4]}, [0, 1, 4, 6], {"x": [0, 1], "y": [2, 4]}),
        ({"y": slice(0, 2)}, [0, 1, 2, 3], {"x": [0, 1], "y": [0, 1]}),
        ({}, [0, 1, 2, 3, 4], {"x": [0, 1], "y": [0, 1, 2]}),
    ],
)
def test_compute_io_indices(indices, expected_sequence, expected_variables_indices):
    """Check that input and output indices are correctly computed from indices."""
    (
        indices_sequence,
        variables_indices,
    ) = DisciplineJacApprox._compute_variables_indices(
        indices, ["x", "y"], {"y": 3, "x": 2}
    )
    assert indices_sequence == expected_sequence
    assert variables_indices == expected_variables_indices


def test_load_and_dump(tmp_wd):
    """Check the loading and dumping of a reference Jacobian."""
    discipline = AnalyticDiscipline("name", {"y": "x", "z": "x"})
    discipline.execute()
    apprx = DisciplineJacApprox(discipline)
    apprx.compute_approx_jac(["z"], ["x"])
    discipline.linearize()
    discipline.jac["z"]["x"] = array([[2.0]])
    file_name = "reference_jacobian.pkl"
    assert not apprx.check_jacobian(
        discipline.jac,
        ["z"],
        ["x"],
        discipline,
        reference_jacobian_path=tmp_wd / file_name,
        save_reference_jacobian=True,
    )

    assert not apprx.check_jacobian(
        discipline.jac,
        ["z"],
        ["x"],
        discipline,
        reference_jacobian_path=tmp_wd / file_name,
    )


class ToyDiscipline(MDODiscipline):
    def __init__(self, dtype=float64):
        super(ToyDiscipline, self).__init__()
        self.input_grammar.initialize_from_data_names(["x1", "x2"])
        self.output_grammar.initialize_from_data_names(["y1", "y2"])
        self.default_inputs = {
            "x1": array([1.0], dtype=dtype),
            "x2": array([1.0, 1.0], dtype=dtype),
        }
        self.dtype = dtype

    def _run(self):
        self.local_data["y1"] = self.local_data["x1"] + 2 * self.local_data["x2"][0]
        self.local_data["y2"] = array(
            [
                self.local_data["x1"][0]
                + 2 * self.local_data["x2"][0]
                + 3 * self.local_data["x2"][1],
                2 * self.local_data["x1"][0]
                + 4 * self.local_data["x2"][0]
                + 6 * self.local_data["x2"][1],
            ]
        )

    def _compute_jacobian(self, inputs=None, outputs=None):
        self.jac = {
            "y1": {
                "x1": array([[1.0]], dtype=self.dtype),
                "x2": array([[2.0, 0.0]], dtype=self.dtype),
            },
            "y2": {
                "x1": array([[1.0], [2.0]], dtype=self.dtype),
                "x2": array([[2.0, 3.0], [4.0, 6.0]], dtype=self.dtype),
            },
        }


@pytest.mark.parametrize("inputs", [["x1"], ["x2"], ["x1", "x2"]])
@pytest.mark.parametrize("outputs", [["y1"], ["y2"], ["y1", "y2"]])
@pytest.mark.parametrize("indices", [None, {"x1": 0}, {"y2": 1}, {"x1": 0, "y2": 1}])
@pytest.mark.parametrize("dtype", [float64, complex128])
def test_indices(inputs, outputs, indices, dtype):
    discipline = ToyDiscipline(dtype=dtype)
    discipline.linearize(force_all=True)
    apprx = DisciplineJacApprox(discipline)
    assert apprx.check_jacobian(
        discipline.jac, outputs, inputs, discipline, indices=indices
    )


def test_factory():
    factory = GradientApproximationFactory()
    assert "ComplexStep" in factory.gradient_approximators
    assert factory.is_available("ComplexStep")

    def function(x):
        return 2 * x

    assert isinstance(factory.create("FirstOrderFD", function), FirstOrderFD)
    assert isinstance(factory.create("finite_differences", function), FirstOrderFD)
    assert isinstance(
        factory.create("finite_differences", function, step=1e-3), FirstOrderFD
    )
    assert isinstance(factory.create("complex_step", function), ComplexStep)
