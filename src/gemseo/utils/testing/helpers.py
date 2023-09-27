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
"""Comparison tools for testing."""
from __future__ import annotations

import contextlib
import sys
from contextlib import nullcontext
from typing import Any
from typing import Final

from matplotlib.testing.decorators import image_comparison as mpl_image_comparison

__ABSTRACTMETHODS__: Final[str] = "__abstractmethods__"


def image_comparison(*args: Any, **kwargs: Any) -> None:
    """Compare matplotlib images generated by the tests with reference ones.

    This overloads :meth:`matplotlib.testing.decorators.image_comparison` by using
    ``"default"`` as ``style`` if missing. Use ``["png"]`` as ``extensions`` if missing.
    """
    if "style" not in kwargs:  # pragma: no cover
        kwargs["style"] = "default"
    if "extensions" not in kwargs:
        kwargs["extensions"] = ["png"]
    tol_py38 = kwargs.pop("tol_py38", None)
    if tol_py38 is not None and sys.version_info < (3, 9):
        kwargs["tol"] = tol_py38
    return mpl_image_comparison(*args, **kwargs)


@contextlib.contextmanager
def concretize_classes(*classes: type) -> None:
    """Context manager forcing classes to be concrete.

    Args:
        *classes: The classes.
    """
    classes_to___abstractmethods__ = {}
    for cls in classes:
        if hasattr(cls, __ABSTRACTMETHODS__):
            classes_to___abstractmethods__[cls] = cls.__abstractmethods__
            del cls.__abstractmethods__

    try:
        yield
    finally:
        for cls, __abstractmethods__ in classes_to___abstractmethods__.items():
            cls.__abstractmethods__ = __abstractmethods__


class do_not_raise(nullcontext):  # noqa: N801
    """Return a context manager like :func:`pytest.raises` but that does nothing."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Args:
            *args: The arguments to match the signature of :func:`pytest.raises`.
            **kwargs: The keyword arguments to match the signature of :func:`pytest.raises`.
        """  # noqa:D205 D212 D415
        super().__init__()
