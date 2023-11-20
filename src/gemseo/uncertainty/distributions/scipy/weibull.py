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
"""The SciPy-based Weibull distribution."""

from __future__ import annotations

from gemseo.uncertainty.distributions.scipy.distribution import SPDistribution


class SPWeibullDistribution(SPDistribution):
    """The SciPy-based Weibull distribution.

    Examples:
        >>> from gemseo.uncertainty.distributions.scipy.weibull import (
        ...     SPWeibullDistribution
        ... )
        >>> distribution = SPWeibullDistribution("u", 0.5, 1.0, 2.0)
        >>> print(distribution)
        weibull_min(location=1, scale=2, shape=0.5)
    """

    def __init__(
        self,
        variable: str = SPDistribution.DEFAULT_VARIABLE_NAME,
        location: float = 0.0,
        scale: float = 1.0,
        shape: float = 1.0,
        use_weibull_min: bool = True,
        dimension: int = 1,
    ) -> None:
        r"""
        Args:
            location: The location parameter of the Weibull distribution.
            scale: The scale parameter of the Weibull distribution.
            shape: The shape parameter of the Weibull distribution.
            use_weibull_min: Whether to use
                the Weibull minimum extreme value distribution
                (the support of the random variable is :math:`[\gamma,+\infty[`)
                or the Weibull maximum extreme value distribution
                (the support of the random variable is :math:`]-\infty[,\gamma]`).
        """  # noqa: D205,D212,D415
        super().__init__(
            variable,
            "weibull_min" if use_weibull_min else "weibull_max",
            {"loc": location, "scale": scale, "c": shape},
            dimension,
            {
                self._LOCATION: location,
                self._SCALE: scale,
                self._SHAPE: shape,
            },
        )
