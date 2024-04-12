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
r"""Joint probability distribution.

Overview
--------

:class:`.BaseJointDistribution` is an abstract class
implementing the concept of `joint probability distribution
<https://en.wikipedia.org/wiki/Joint_probability_distribution>`_.

The joint probability distribution of a set of random variables
is the probability distribution of the random vector
consisting of these random variables.

It takes into account
both the marginal probability distributions of these random variables
and their dependency structure.

A :class:`.BaseJointDistribution` is defined
from a list of :class:`.BaseDistribution` instances
defining the marginals of the random variables
and a copula defining the dependency structure between them.

.. note::

   A copula is a mathematical function used to define the dependence
   between random variables from their cumulative density functions.
   `See more <https://en.wikipedia.org/wiki/Copula_(probability_theory)>`_.

By definition, a joint probability distribution is a probability distribution
Therefore, :class:`.BaseJointDistribution` inherits
from the abstract class :class:`.BaseDistribution`.

Construction
------------

The :class:`.BaseJointDistribution` of a list of given uncertain variables is built
from a list of :class:`.BaseDistribution` objects
implementing the probability distributions of these variables
and from a copula.

Capabilities
------------

Because :class:`.BaseJointDistribution` inherits from :class:`.BaseDistribution`,
we can easily get statistics, such as :attr:`.BaseJointDistribution.mean`,
:attr:`.BaseJointDistribution.standard_deviation`.
We can also get the numerical :attr:`.BaseJointDistribution.range` and
mathematical :attr:`.BaseJointDistribution.support`.

.. note::

    We call mathematical *support* the set of values that the random variable
    can take in theory, e.g. :math:`]-\infty,+\infty[` for a Gaussian variable,
    and numerical *range* the set of values that it can take in practice,
    taking into account the values rounded to zero double precision.
    Both support and range are described in terms of lower and upper bounds

We can also evaluate the cumulative density function
(:meth:`.BaseJointDistribution.compute_cdf`)
for the different marginals of the random variable,
as well as the inverse cumulative density function
(:meth:`.BaseJointDistribution.compute_inverse_cdf`). We can plot them,
either for a given marginal (:meth:`.BaseJointDistribution.plot`)
or for all marginals (:meth:`.BaseJointDistribution.plot_all`).

Lastly, we can compute realizations of the random variable
by means of the :meth:`.BaseJointDistribution.compute_samples` method.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any

from numpy import array
from numpy import concatenate
from numpy import ndarray

from gemseo.uncertainty.distributions.base_distribution import BaseDistribution
from gemseo.utils.string_tools import MultiLineString
from gemseo.utils.string_tools import pretty_repr

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Sequence

LOGGER = logging.getLogger(__name__)


class BaseJointDistribution(BaseDistribution):
    """Joint probability distribution."""

    __copula_name: str
    """The name of the copula method."""

    def __init__(
        self,
        distributions: Sequence[BaseDistribution],
        copula: Any = None,
        variable: str = "",
    ) -> None:
        """
        Args:
            distributions: The marginal distributions.
            copula: A copula distribution
                defining the dependency structure between random variables;
                if ``None``, consider an independent copula.
            variable: The name of the variable, if any;
                otherwise,
                concatenate the names of the random variables
                defined by ``distributions``.
        """  # noqa: D205,D212,D415
        self._marginal_variables = [
            distribution.variable_name for distribution in distributions
        ]
        self.__copula_name = copula.__class__.__name__ if copula is not None else ""
        # TODO: API: set parameters to (distributions, copula) instead of (copula,).
        super().__init__(
            variable or "_".join(self._marginal_variables),
            "Joint",
            (copula,),
            sum(distribution.dimension for distribution in distributions),
        )
        self.marginals = distributions
        msg = MultiLineString()
        msg.indent()
        msg.add("Marginals:")
        msg.indent()
        for distribution in distributions:
            msg.add(
                "{}({}): {}",
                distribution.variable_name,
                distribution.dimension,
                distribution,
            )
        LOGGER.debug("%s", msg)

    def __repr__(self) -> str:
        if self.dimension == 1:
            return repr(self.marginals[0])

        return (
            f"{self.__class__.__name__}({pretty_repr(self.marginals, sort=False)}; "
            f"{self.__copula_name or 'IndependentCopula'})"
        )

    def _set_bounds(
        self,
        distributions: Iterable[BaseDistribution],
    ) -> None:
        """Set the mathematical and numerical bounds (= support and range).

        Args:
            distributions: The distributions.
        """
        self.math_lower_bound = array([])
        self.math_upper_bound = array([])
        self.num_lower_bound = array([])
        self.num_upper_bound = array([])
        for dist in distributions:
            self.math_lower_bound = concatenate((
                self.math_lower_bound,
                dist.math_lower_bound,
            ))
            self.num_lower_bound = concatenate((
                self.num_lower_bound,
                dist.num_lower_bound,
            ))
            self.math_upper_bound = concatenate((
                self.math_upper_bound,
                dist.math_upper_bound,
            ))
            self.num_upper_bound = concatenate((
                self.num_upper_bound,
                dist.num_upper_bound,
            ))

    @property
    def mean(self) -> ndarray:  # noqa: D102
        mean = [marginal.mean for marginal in self.marginals]
        return array(mean).flatten()

    @property
    def standard_deviation(self) -> ndarray:  # noqa: D102
        std = [marginal.standard_deviation for marginal in self.marginals]
        return array(std).flatten()

    def compute_samples(  # noqa: D102
        self,
        n_samples: int = 1,
    ) -> ndarray:
        sample = self.marginals[0].compute_samples(n_samples)
        for marginal in self.marginals[1:]:
            sample = concatenate((sample, marginal.compute_samples(n_samples)), axis=1)
        return sample
