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

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from gemseo.mlearning.classification.algos.factory import ClassifierFactory
from gemseo.problems.dataset.iris import create_iris_dataset

if TYPE_CHECKING:
    from gemseo.datasets.io_dataset import IODataset


@pytest.fixture()
def dataset() -> IODataset:
    """The Iris dataset used to train the classification algorithms."""
    return create_iris_dataset(as_io=True)


def test_constructor() -> None:
    """Test factory constructor."""
    factory = ClassifierFactory()
    # plugins may add classes
    assert set(factory.models) <= {
        "KNNClassifier",
        "RandomForestClassifier",
        "SVMClassifier",
    }


def test_create(dataset) -> None:
    """Test the creation of a model from data."""
    factory = ClassifierFactory()
    knn = factory.create("KNNClassifier", data=dataset)
    assert hasattr(knn, "parameters")


def test_load(dataset, tmp_wd) -> None:
    """Test the loading of a model from data."""
    factory = ClassifierFactory()
    knn = factory.create("KNNClassifier", data=dataset)
    knn.learn()
    dirname = knn.to_pickle()
    loaded_knn = factory.load(dirname)
    assert hasattr(loaded_knn, "parameters")


def test_available_models() -> None:
    """Test the getter of available classification models."""
    factory = ClassifierFactory()
    assert "KNNClassifier" in factory.models


def test_is_available() -> None:
    """Test the existence of a classification model."""
    factory = ClassifierFactory()
    assert factory.is_available("KNNClassifier")
    assert not factory.is_available("Dummy")
