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

"""Most basic grammar implementation."""

import logging
from typing import Any, Iterable, List, Mapping, Optional, Union

from numpy import ndarray

from gemseo.core.grammars.abstract_grammar import AbstractGrammar
from gemseo.core.grammars.errors import InvalidDataException
from gemseo.utils.py23_compat import Path
from gemseo.utils.string_tools import MultiLineString

LOGGER = logging.getLogger(__name__)


class SimpleGrammar(AbstractGrammar):
    """A Grammar based on the names and types of the elements specified by a
    dictionnary."""

    def __init__(
        self,
        name,  # type: str
        names_to_types=None,  # type: Optional[Mapping[str,type]]
        **kwargs  # type: Union[str,Path]
    ):  # type: (...) -> None
        """
        Args:
            name: The grammar name.
            names_to_types: The mapping defining the data names as keys,
                and data types as values.
                If None, the grammar is empty.
        """
        super(SimpleGrammar, self).__init__(name)
        if names_to_types is None:
            self._names_to_types = {}
        else:
            self._names_to_types = names_to_types
            self._check_types()

    @property
    def data_names(self):  # type: (...) -> List[str]
        """The names of the elements."""
        return list(self._names_to_types.keys())

    @property
    def data_types(self):  # type: (...) -> List[type]
        """The types of the elements."""
        return list(self._names_to_types.values())

    def _check_types(self):  # type: (...) -> None
        """Check that the elements names to types mapping contains only acceptable type
        specifications, ie, are a type or None.

        Raises:
            TypeError: When at least one type specification is not a type.
        """
        for obj_name, obj in self._names_to_types.items():
            if obj is not None and not isinstance(obj, type):
                raise TypeError(
                    (
                        "{} is not a type and cannot be used as a"
                        " type specification for the element named {} in the grammar {}."
                    ).format(obj, obj_name, self.name)
                )

    def add_elements(
        self, **data  # type: Mapping[str,type]
    ):  # type: (...) -> Iterable[str]
        """Add or update elements from their names and types.

        >> grammar.add_elements(a=str, b=int)
        >> grammar.add_elements(**names_to_types)

        Args:
            names_to_types: The names and types to add.
        """
        self._names_to_types.update(**data)
        self._check_types()

    def load_data(
        self,
        data,  # type: Mapping[str,Any]
        raise_exception=True,  # type: bool
    ):  # type: (...) -> Mapping[str,Any]
        self.check(data, raise_exception)
        return data

    def check(
        self,
        data,  # type: Mapping[str,Any]
        raise_exception=True,  # type: bool
    ):  # type: (...) -> None
        """Check the consistency (name and type) of elements with the grammar.

        Args:
            raise_exception: Whether to raise an exception
                when the elements are invalid.

        Raises:
            TypeError: If a data type in the grammar is not a type.
            InvalidDataException:
                * If the passed data is not a dictionary.
                * If a name in the passed data is not in the grammar.
                * If the type of a value in the passed data does not have
                  the specified type in the grammar for the corresponding name.
        """
        failed = False
        if not isinstance(data, Mapping):
            failed = True
            LOGGER.error("Grammar data is not a mapping, in %s.", self.name)
            if raise_exception:
                raise InvalidDataException("Invalid data in: {}.".format(self.name))

        error_message = MultiLineString()
        error_message.add("Invalid data in {}", self.name)
        for element_name, element_type in self._names_to_types.items():
            element_value = data.get(element_name)
            if element_value is None:
                failed = True
                error_message.add(
                    "Missing mandatory elements: {} in grammar {}.".format(
                        element_name, self.name
                    )
                )
            elif element_type is not None and not isinstance(
                element_value, element_type
            ):
                failed = True
                error_message.add(
                    "Wrong input type for: {} in {} got {} instead of {}.".format(
                        element_name, self.name, type(data[element_name]), element_type
                    )
                )

        LOGGER.error(error_message)
        if failed and raise_exception:
            raise InvalidDataException(str(error_message))

    def initialize_from_base_dict(
        self,
        typical_data_dict,  # type: Mapping[str,Any]
    ):  # type: (...) -> None
        self.add_elements(
            **{name: type(value) for name, value in typical_data_dict.items()}
        )

    def get_data_names(self):  # type: (...) -> List[str]
        return self.data_names

    def is_all_data_names_existing(
        self,
        data_names,  # type: Iterable[str]
    ):  # type: (...) -> bool
        get = self._names_to_types.get
        for name in data_names:
            if get(name) is None:
                return False
        return True

    def _update_field(
        self,
        data_name,  # type: str
        data_type,  # type: type
    ):
        """Update the grammar elements from an element name and an element type.

        If there is no element with this name,
        create it and store its type.

        Otherwise,
        update its type.

        Args:
            data_name: The name of the element.
            data_type: The type of the element.
        """
        self._names_to_types[data_name] = data_type

    def get_type_of_data_named(
        self,
        data_name,  # type: str
    ):  # type: (...) -> str
        """Return the element type associated to an element name.

        Args:
            data_name: The name of the element.

        Returns:
            The type of the element associated to the passed element name.

        Raises:
            ValueError: If the name does not correspond to an element name.
        """
        if data_name not in self._names_to_types:
            raise ValueError("Unknown data named: {}.".format(data_name))
        return self._names_to_types[data_name]

    def is_type_array(
        self, data_name  # type: str
    ):  # type: (...) -> bool
        element_type = self.get_type_of_data_named(data_name)
        return issubclass(element_type, ndarray)

    def remove_item(
        self,
        item_name,  # type: str
    ):  # type: (...) -> None
        """Remove an element.

        Args:
            item_name: The name of the element to be removed.

        Raises:
            KeyError: When item_name is not in the grammar.
        """
        del self._names_to_types[item_name]

    def update_from(
        self,
        input_grammar,  # type: AbstractGrammar
    ):  # type: (...) -> None
        """
        Raises:
            TypeError: If the passed grammar is not an :class:`.AbstractGrammar`.
        """
        if not isinstance(input_grammar, AbstractGrammar):
            msg = self._get_update_error_msg(self, input_grammar)
            raise TypeError(msg)

        input_grammar = input_grammar.to_simple_grammar()
        self._names_to_types.update(input_grammar._names_to_types)

    def update_from_if_not_in(
        self,
        input_grammar,  # type: AbstractGrammar
        exclude_grammar,  # type: AbstractGrammar
    ):  # type: (...) -> None
        """
        Raises:
            TypeError: If a passed grammar is not an :class:`.AbstractGrammar`.
            ValueError: If types are inconsistent between both passed grammars.
        """
        if not isinstance(input_grammar, AbstractGrammar) or not isinstance(
            exclude_grammar, AbstractGrammar
        ):
            msg = self._get_update_error_msg(self, input_grammar, exclude_grammar)
            raise TypeError(msg)

        input_grammar = input_grammar.to_simple_grammar()
        exclude_grammar = exclude_grammar.to_simple_grammar()

        for element_name, element_type in zip(
            input_grammar.data_names, input_grammar.data_types
        ):
            if exclude_grammar.is_data_name_existing(element_name):
                ex_element_type = exclude_grammar.get_type_of_data_named(element_name)
                if element_type != ex_element_type:
                    raise ValueError(
                        "Inconsistent grammar update {} != {}.".format(
                            element_type, ex_element_type
                        )
                    )
            else:
                self._names_to_types[element_name] = element_type

    def is_data_name_existing(
        self,
        data_name,  # type: str
    ):  # type: (...) -> bool
        return data_name in self._names_to_types

    def clear(self):  # type: (...) -> None
        self._names_to_types = {}

    def to_simple_grammar(self):  # type: (...) -> SimpleGrammar
        return self
