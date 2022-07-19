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
# - Matthias De Lozzo
# - Jean-Christophe Giret
# - François Gallard
# - Antoine DECHAUME
import unittest

from gemseo.algos.opt.opt_factory import OptimizersFactory
from gemseo.post.post_factory import PostFactory
from gemseo.problems.analytical.rosenbrock import Rosenbrock


class TestKMeans(unittest.TestCase):
    """"""

    @classmethod
    def setUpClass(cls):
        problem = Rosenbrock()
        OptimizersFactory().execute(problem, "L-BFGS-B")
        cls.problem = problem
        cls.factory = PostFactory()

    def test_kmeans(self):
        """"""
        if self.factory.is_available("KMeans"):
            self.factory.execute(self.problem, "KMeans", n_clusters=6)
