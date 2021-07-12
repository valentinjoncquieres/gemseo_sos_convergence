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
#    INITIAL AUTHORS - initial API and implementation and/or initial
#                           documentation
#        :author: Matthias De Lozzo
#    OTHER AUTHORS   - MACROSCOPIC CHANGES
"""Test Gaussian process regression algorithm module."""
from __future__ import division, unicode_literals

import pytest
from numpy import allclose, array, ndarray

from gemseo.algos.design_space import DesignSpace
from gemseo.core.analytic_discipline import AnalyticDiscipline
from gemseo.core.dataset import Dataset
from gemseo.core.doe_scenario import DOEScenario
from gemseo.mlearning.api import import_regression_model
from gemseo.mlearning.regression.gpr import GaussianProcessRegression
from gemseo.mlearning.transform.scaler.scaler import Scaler
from gemseo.utils.data_conversion import DataConversion

LEARNING_SIZE = 9


@pytest.fixture
def dataset():  # type: (...) -> Dataset
    """The dataset used to train the regression algorithms."""
    expressions_dict = {"y_1": "1+2*x_1+3*x_2", "y_2": "-1-2*x_1-3*x_2"}
    discipline = AnalyticDiscipline("func", expressions_dict)
    discipline.set_cache_policy(discipline.MEMORY_FULL_CACHE)
    design_space = DesignSpace()
    design_space.add_variable("x_1", l_b=0.0, u_b=1.0)
    design_space.add_variable("x_2", l_b=0.0, u_b=1.0)
    scenario = DOEScenario([discipline], "DisciplinaryOpt", "y_1", design_space)
    scenario.execute({"algo": "fullfact", "n_samples": LEARNING_SIZE})
    return discipline.cache.export_to_dataset("dataset_name")


@pytest.fixture
def model(dataset):  # type: (...) -> GaussianProcessRegression
    """A trained GaussianProcessRegression."""
    gpr = GaussianProcessRegression(dataset)
    gpr.learn()
    return gpr


@pytest.fixture
def model_with_transform(dataset):  # type: (...) -> GaussianProcessRegression
    """A trained GaussianProcessRegression with inputs scaling."""
    gpr = GaussianProcessRegression(dataset, transformer={"inputs": Scaler()})
    gpr.learn()
    return gpr


def test_constructor(dataset):
    """Test construction."""
    gpr = GaussianProcessRegression(dataset)
    assert gpr.algo is not None


def test_learn(dataset):
    """Test learn."""
    gpr = GaussianProcessRegression(dataset)
    gpr.learn()
    assert gpr.algo is not None


def test_predict(model):
    """Test prediction."""
    input_value = {"x_1": array([1.0]), "x_2": array([2.0])}
    prediction = model.predict(input_value)
    assert isinstance(prediction, dict)
    assert "y_1" in prediction
    assert "y_2" in prediction
    assert isinstance(prediction["y_1"], ndarray)
    assert prediction["y_1"].shape == (1,)
    assert isinstance(prediction["y_2"], ndarray)
    assert prediction["y_2"].shape == (1,)
    assert allclose(prediction["y_1"], -prediction["y_2"], 1e-2)


def test_predict_std(model):
    """Test std prediction."""
    input_value = {"x_1": array([1.0]), "x_2": array([1.0])}
    prediction_std = model.predict_std(input_value)
    assert allclose(prediction_std, 0, atol=1e-3)
    input_value = {"x_1": array([1.0]), "x_2": array([2.0])}
    prediction_std = model.predict_std(input_value)
    assert prediction_std > 0
    input_value = DataConversion.dict_to_array(input_value, model.input_names)
    assert model.predict_std(input_value) == prediction_std


def test_predict_std_with_transform(model_with_transform):
    """Test std prediction with data transformation."""
    input_value = {"x_1": array([1.0]), "x_2": array([1.0])}
    prediction_std = model_with_transform.predict_std(input_value)
    assert allclose(prediction_std, 0, atol=1e-3)
    input_value = {"x_1": array([1.0]), "x_2": array([2.0])}
    prediction_std = model_with_transform.predict_std(input_value)
    assert prediction_std > 0


def test_save_and_load(model, tmp_path):
    """Test save and load."""
    dirname = model.save(path=str(tmp_path))
    imported_model = import_regression_model(dirname)
    input_value = {"x_1": array([1.0]), "x_2": array([2.0])}
    out1 = model.predict(input_value)
    out2 = imported_model.predict(input_value)
    for name, value in out1.items():
        assert allclose(value, out2[name], 1e-3)
