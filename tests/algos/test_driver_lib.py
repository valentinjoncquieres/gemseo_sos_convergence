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
"""Driver library tests."""

from __future__ import annotations

import logging
from unittest import mock

import pytest
from numpy import array
from numpy import full

from gemseo.algos._progress_bars.progress_bar import ProgressBar
from gemseo.algos.design_space import DesignSpace
from gemseo.algos.doe.lib_custom import CustomDOE
from gemseo.algos.driver_library import DriverDescription
from gemseo.algos.driver_library import DriverLibrary
from gemseo.algos.opt.factory import OptimizationLibraryFactory
from gemseo.algos.optimization_problem import OptimizationProblem
from gemseo.problems.optimization.power_2 import Power2
from gemseo.utils.testing.helpers import concretize_classes


@pytest.fixture(scope="module")
def power_2() -> Power2:
    """The power-2 problem."""
    problem = Power2()
    problem.database.store(
        array([0.79499653, 0.20792012, 0.96630481]),
        {"pow2": 1.61, "ineq1": -0.0024533, "ineq2": -0.0024533, "eq": -0.00228228},
    )
    return problem


class MyDriver(DriverLibrary):
    def __init__(self) -> None:
        super().__init__()
        self.descriptions = {"algo_name": None}


@pytest.fixture(scope="module")
def optimization_problem():
    """A mock optimization problem."""
    design_space = mock.Mock()
    design_space.dimension = 2
    problem = mock.Mock()
    problem.dimension = 2
    problem.design_space = design_space
    return problem


def test_empty_design_space() -> None:
    """Check that a driver cannot be executed with an empty design space."""
    with concretize_classes(MyDriver):
        driver = MyDriver()
    driver.algo_name = "algo_name"
    with pytest.raises(
        ValueError,
        match=(
            "The algorithm algo_name is not adapted to the problem "
            "because the design space is empty."
        ),
    ):
        driver._check_algorithm("algo_name", OptimizationProblem(DesignSpace()))


def test_max_iter_fail(optimization_problem) -> None:
    """Check that a ValueError is raised for an invalid `max_iter` input."""
    with concretize_classes(MyDriver):
        MyDriver()._pre_run(optimization_problem, None)
    with pytest.raises(ValueError, match="max_iter must be >=1, got -1"):  # noqa: SIM117
        with concretize_classes(MyDriver):
            MyDriver().init_iter_observer(max_iter=-1)


def test_no_algo_fail(optimization_problem) -> None:
    """Check that a ValueError is raised when no algorithm name is set."""
    with (
        pytest.raises(
            ValueError,
            match="Algorithm name must be either passed as "
            "argument or set by the attribute 'algo_name'.",
        ),
        concretize_classes(MyDriver),
    ):
        MyDriver().execute(optimization_problem)


def test_grammar_fail() -> None:
    """Check that a ValueError is raised when the grammar file is not found."""
    with (
        pytest.raises(
            ValueError,
            match=(
                "Neither the options grammar file .+ for the algorithm 'unknown' "
                "nor the options grammar file .+ for the library 'DriverLibrary' "
                "has been found."
            ),
        ),
        concretize_classes(DriverLibrary),
    ):
        DriverLibrary().init_options_grammar("unknown")


def test_require_grad() -> None:
    """Check that an error is raised when a particular gradient method is not given."""

    class MyDriver(DriverLibrary):
        def __init__(self) -> None:
            super().__init__()
            self.descriptions = {
                "SLSQP": DriverDescription(
                    algorithm_name="SLSQP",
                    internal_algorithm_name="SLSQP",
                    require_gradient=True,
                )
            }

    with concretize_classes(MyDriver):
        with pytest.raises(ValueError, match="Algorithm toto is not available."):
            MyDriver().requires_gradient("toto")

        assert MyDriver().requires_gradient("SLSQP")


@pytest.mark.parametrize(
    ("kwargs", "expected"), [({}, "    50%|"), ({"message": "foo"}, "foo  50%|")]
)
def test_new_iteration_callback_xvect(caplog, power_2, kwargs, expected) -> None:
    """Test the new iteration callback."""
    with concretize_classes(DriverLibrary):
        test_driver = DriverLibrary()
    test_driver.problem = power_2
    test_driver._max_time = 0
    test_driver.init_iter_observer(max_iter=2, **kwargs)
    test_driver.new_iteration_callback(array([0, 0]))
    test_driver.new_iteration_callback(array([0, 0]))
    assert expected in caplog.text


@pytest.mark.parametrize("activate_progress_bar", [False, True])
def test_progress_bar(activate_progress_bar, caplog) -> None:
    """Check the activation of the progress bar from the options of a DriverLibrary."""
    driver = OptimizationLibraryFactory().create("SLSQP")
    driver.execute(Power2(), activate_progress_bar=activate_progress_bar)
    assert (
        isinstance(driver._DriverLibrary__progress_bar, ProgressBar)
        is activate_progress_bar
    )
    assert (
        "Solving optimization problem with algorithm SLSQP" in caplog.text
    ) is activate_progress_bar


def test_common_options() -> None:
    """Check that the options common to all the drivers are in the option grammar."""
    with concretize_classes(MyDriver):
        driver = MyDriver()
    driver.init_options_grammar("AlgoName")
    assert driver.option_grammar.names == {
        DriverLibrary.ROUND_INTS_OPTION,
        DriverLibrary.NORMALIZE_DESIGN_SPACE_OPTION,
        DriverLibrary.USE_DATABASE_OPTION,
        DriverLibrary._DriverLibrary__RESET_ITERATION_COUNTERS_OPTION,
    }
    assert not driver.option_grammar.required_names


@pytest.fixture()
def driver_library() -> DriverLibrary:
    """A driver library."""
    with concretize_classes(DriverLibrary):
        driver_library = DriverLibrary()

    design_space = DesignSpace()
    design_space.add_variable("x", 1, "float", -2, 3, 1)
    driver_library.problem = OptimizationProblem(design_space)
    return driver_library


@pytest.mark.parametrize(
    ("as_dict", "x0", "lower_bounds", "upper_bounds"),
    [(False, 0.6, 0, 1), (True, {"x": 0.6}, {"x": 0}, {"x": 1})],
)
def test_get_x0_and_bounds_vects_normalized_as_ndarrays(
    driver_library, as_dict, x0, lower_bounds, upper_bounds
) -> None:
    """Check the getting of the normalized initial values and bounds."""
    assert driver_library.get_x0_and_bounds(True, as_dict) == (
        pytest.approx(x0),
        lower_bounds,
        upper_bounds,
    )


@pytest.mark.parametrize(
    ("as_dict", "x0", "lower_bounds", "upper_bounds"),
    [(False, 1, -2, 3), (True, {"x": 1}, {"x": -2}, {"x": 3})],
)
def test_get_x0_and_bounds_vects_non_normalized(
    driver_library, as_dict, x0, lower_bounds, upper_bounds
) -> None:
    """Check the getting of the non-normalized initial values and bounds."""
    assert driver_library.get_x0_and_bounds(False, as_dict) == (
        x0,
        lower_bounds,
        upper_bounds,
    )


@pytest.mark.parametrize("name", ["new_iter_listener", "store_listener"])
def test_clear_listeners(name):
    """Check clear_listeners."""
    problem = Power2()
    getattr(problem.database, f"add_{name}")(sum)
    driver = CustomDOE()
    driver.execute(problem, samples=array([[1, 2, 3]]))
    assert getattr(problem.database, f"_Database__{name}s") == [sum]


@pytest.mark.parametrize("max_dimension", [1, 3])
def test_max_design_space_dimension_to_log(max_dimension, caplog):
    """Check the cap on the dimension of a design space to log."""
    problem = Power2()
    initial_space_string = problem.design_space._get_string_representation(
        False, "   over the design space"
    ).replace("\n", "\n      ")
    CustomDOE().execute(
        problem,
        samples=full((1, 3), pow(0.9, 1.0 / 3.0)),
        max_design_space_dimension_to_log=max_dimension,
    )

    # Check the logging of the initial design space
    assert (max_dimension >= 3) == (
        ("gemseo.algos.driver_library", logging.INFO, initial_space_string)
        in caplog.record_tuples
    )

    # Check the logging of the final design space
    assert (max_dimension >= 3) == (
        (
            "gemseo.algos.driver_library",
            logging.INFO,
            problem.design_space._get_string_representation(False)
            .replace("Design space", "      Design space")
            .replace("\n", "\n         "),
        )
        in caplog.record_tuples
    )
