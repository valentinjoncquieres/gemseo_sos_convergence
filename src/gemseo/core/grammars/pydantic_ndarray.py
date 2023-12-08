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

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import Final
from typing import TypeVar

from numpy import ndarray
from numpy.typing import NDArray
from pydantic import BaseModel
from pydantic import InstanceOf
from pydantic.fields import FieldInfo
from pydantic_core import CoreSchema
from pydantic_core import core_schema
from typing_extensions import Annotated

from gemseo.utils.compatibility.python import get_args
from gemseo.utils.compatibility.python import get_origin

if TYPE_CHECKING:
    from pydantic import GetCoreSchemaHandler

# This is the default dtype of NDArray when it is used without dtype,
# i.e. without NDArray[X].
# We get it by runtime inspection because it is defined in a protected module.
_ScalarType_co: Final[TypeVar] = get_args(get_args(NDArray)[1])[0]


class BaseModelWithNDArray(BaseModel):
    """A base pydantic model that support NumPy array typing.

    This is useful for fields with type annotations like ``NDArray[TYPE]``. This is not
    needed otherwise.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls, __source: type[BaseModel], __handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        for field_name, field_info in tuple(__source.model_fields.items()):
            annotation = field_info.annotation
            if annotation is ndarray or get_origin(annotation) is ndarray:
                __source.model_fields[field_name] = FieldInfo.from_annotated_attribute(
                    annotate(annotation), field_info
                )

        return super().__get_pydantic_core_schema__(__source, __handler)


@lru_cache(maxsize=None)
def annotate(_source_type) -> type[Annotated]:
    """Create a NumPy array type annotation compatible with pydantic.

    This is useful for NDArray[TYPE] like type annotations.
    This is not needed otherwise.

    Args:
        _source_type: The ``NDArray[X]`` annotation.

    Returns:
        The pydantic compatible annotation.
    """
    if _source_type is ndarray:
        return InstanceOf[ndarray]

    if get_origin(_source_type) != ndarray:
        msg = (
            f"Unable to generate a schema for {_source_type}. "
            "It shall be a NDArray based type."
        )
        raise TypeError(msg)

    dtype_ = get_args(get_args(_source_type)[1])[0]
    if dtype_ is _ScalarType_co:
        return InstanceOf[ndarray]

    return Annotated[_source_type, _NDArrayAnnotation]


class _NDArrayAnnotation:
    """A type annotation for validating NumPy arrays with pydantic.

    See pydantic docs for more information.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.chain_schema([
            core_schema.is_instance_schema(ndarray),
            core_schema.no_info_plain_validator_function(
                cls.__get_validator(_source_type)
            ),
        ])

    @staticmethod
    def __get_validator(
        _source_type: Any,
    ) -> Callable[[ndarray], ndarray]:
        """Return a function that can validate NumPy array types.

        Args:
            _source_type: The source type.

        Returns:
            The validator function.
        """
        # The dtype is located at X in ndarray[Any, dtype[X]]
        dtype_ = get_args(get_args(_source_type)[1])[0]

        def validate(data: Any) -> NDArray:
            """Validate a NumPy array.

            Args:
                data: The data to validate.

            Returns:
                The data.

            Raises:
                ValidationError: If the data is not valid.
            """
            # if shape and shape is not Any and array.shape != shape:
            #     msg = f"Input shape should be {shape}: got the shape {array.shape}"
            #     # TODO: use ValidationError
            #     raise ValueError(msg)

            # First check that the source dtype is not catch-all then the actual dtype.
            if dtype_ not in (Any, _ScalarType_co) and data.dtype != dtype_:
                msg = (
                    f"Input dtype should be {dtype_}: "
                    f"got the dtype {data.dtype.type}"
                )
                # TODO: use ValidationError
                raise ValueError(msg)

            return data

        return validate
