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
"""The base class for all formulations."""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar

from gemseo.core.base_factory import BaseFactory
from gemseo.core.discipline import MDODiscipline
from gemseo.core.mdofunctions.taylor_polynomials import compute_linear_approximation
from gemseo.scenarios.scenario_results.scenario_result import ScenarioResult
from gemseo.utils.metaclasses import ABCGoogleDocstringInheritanceMeta

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Sequence

    from gemseo.algos.design_space import DesignSpace
    from gemseo.core.execution_sequence import ExecutionSequence
    from gemseo.core.grammars.json_grammar import JSONGrammar
    from gemseo.core.scenario import Scenario

from numpy import arange
from numpy import copy
from numpy import empty
from numpy import in1d
from numpy import ndarray
from numpy import zeros

from gemseo.algos.opt_problem import OptimizationProblem
from gemseo.core.mdofunctions.function_from_discipline import FunctionFromDiscipline
from gemseo.core.mdofunctions.mdo_discipline_adapter_generator import (
    MDODisciplineAdapterGenerator,
)
from gemseo.core.mdofunctions.mdo_function import MDOFunction
from gemseo.disciplines.utils import get_sub_disciplines

LOGGER = logging.getLogger(__name__)


class BaseFormulation(metaclass=ABCGoogleDocstringInheritanceMeta):
    """Base MDO formulation class to be extended in subclasses for use.

    This class creates the :class:`.MDOFunction` instances
    computing the constraints, objective and observables
    from the disciplines
    and add them to the attached :attr:`.opt_problem`.

    It defines the multidisciplinary process, i.e. dataflow and workflow, implicitly.

    By default,

    - the objective is minimized,
    - the type of a constraint is equality,
    - the activation value of a constraint is 0.

    The link between the instances of :class:`.MDODiscipline`,
    the design variables and
    the names of the discipline outputs used as constraints, objective and observables
    is made with the :class:`.MDODisciplineAdapterGenerator`,
    which generates instances of :class:`.MDOFunction` from the disciplines.
    """

    DEFAULT_SCENARIO_RESULT_CLASS_NAME: ClassVar[str] = ScenarioResult.__name__
    """The name of the :class:`.ScenarioResult` class to be used for post-processing."""

    opt_problem: OptimizationProblem
    """The optimization problem generated by the formulation from the disciplines."""

    _objective_name: str | Sequence[str]
    """The name(s) of the discipline output(s) used as objective."""

    _maximize_objective: bool
    """Whether to maximize the objective."""

    NAME: ClassVar[str] = "MDOFormulation"
    """The name of the MDO formulation."""

    def __init__(
        self,
        disciplines: list[MDODiscipline],
        objective_name: str | Sequence[str],
        design_space: DesignSpace,
        maximize_objective: bool = False,
        grammar_type: MDODiscipline.GrammarType = MDODiscipline.GrammarType.JSON,
        **options: Any,
    ) -> None:
        """
        Args:
            disciplines: The disciplines.
            objective_name: The name(s) of the discipline output(s) used as objective.
                If multiple names are passed, the objective will be a vector.
            design_space: The design space.
            maximize_objective: Whether to maximize the objective.
            grammar_type: The type of the input and output grammars.
            **options: The options of the formulation.
        """  # noqa: D205, D212, D415
        self._disciplines = disciplines
        self._objective_name = objective_name
        self.opt_problem = OptimizationProblem(design_space)
        self._maximize_objective = maximize_objective
        self.__grammar_type = grammar_type

    @property
    def _grammar_type(self) -> MDODiscipline.GrammarType:
        """The type of the input and output grammars."""
        return self.__grammar_type

    @property
    def design_space(self) -> DesignSpace:
        """The design space on which the formulation is applied."""
        return self.opt_problem.design_space

    @property
    def disciplines(self) -> list[MDODiscipline]:
        """The disciplines of the MDO process."""
        return self._disciplines

    @staticmethod
    def _check_add_cstr_input(
        output_name: str,
        constraint_type: MDOFunction.ConstraintType,
    ) -> list[str]:
        """Check the output name and constraint type passed to :meth:`.add_constraint`.

        Args:
            output_name: The name of the output to be used as a constraint.
                For instance, if g_1 is given and constraint_type="eq",
                g_1=0 will be added as a constraint to the optimizer.
            constraint_type: The type of constraint.
        """
        # TODO: API: remove useless constraint_type.
        # TODO: API: find a better method name that matches its intent.
        return output_name if isinstance(output_name, list) else [output_name]

    def add_constraint(
        self,
        output_name: str,
        constraint_type: MDOFunction.ConstraintType = MDOFunction.ConstraintType.EQ,
        constraint_name: str = "",
        value: float = 0,
        positive: bool = False,
    ) -> None:
        r"""Add an equality or inequality constraint to the optimization problem.

        An equality constraint is written as :math:`c(x)=a`,
        a positive inequality constraint is written as :math:`c(x)\geq a`
        and a negative inequality constraint is written as :math:`c(x)\leq a`.

        This constraint is in addition to those created by the formulation,
        e.g. consistency constraints in IDF.

        The strategy of repartition of the constraints is defined by the formulation.

        Args:
            output_name: The name(s) of the outputs computed by :math:`c(x)`.
                If several names are given,
                a single discipline must provide all outputs.
            constraint_type: The type of constraint.
            constraint_name: The name of the constraint to be stored.
                If empty,
                the name of the constraint is generated
                from ``output_name``, ``constraint_type``, ``value`` and ``positive``.
            value: The value :math:`a`.
            positive: Whether the inequality constraint is positive.
        """
        output_names = self._check_add_cstr_input(output_name, constraint_type)
        constraint = FunctionFromDiscipline(output_names, self)
        if constraint.linear_candidate:
            constraint = compute_linear_approximation(
                constraint, zeros(constraint.input_dimension)
            )
        constraint.f_type = constraint_type
        if constraint_name:
            constraint.name = constraint_name
            constraint.has_default_name = False
        else:
            constraint.has_default_name = True
        self.opt_problem.add_constraint(constraint, value=value, positive=positive)

    def add_observable(
        self,
        output_names: str | Sequence[str],
        observable_name: str = "",
        discipline: MDODiscipline | None = None,
    ) -> None:
        """Add an observable to the optimization problem.

        The repartition strategy of the observable is defined in the formulation class.

        Args:
            output_names: The name(s) of the output(s) to observe.
            observable_name: The name of the observable.
                If empty, the output name is used by default.
            discipline: The discipline computing the observed outputs.
                If ``None``, the discipline is detected from inner disciplines.
        """
        if isinstance(output_names, str):
            output_names = [output_names]
        obs_fun = FunctionFromDiscipline(output_names, self, discipline=discipline)
        if observable_name:
            obs_fun.name = observable_name
        self.opt_problem.add_observable(obs_fun)

    def get_top_level_disc(self) -> list[MDODiscipline]:
        """Return the disciplines which inputs are required to run the scenario.

        A formulation seeks to
        compute the objective and constraints from the input variables.
        It structures the optimization problem into multiple levels of disciplines.
        The disciplines directly depending on these inputs
        are called top level disciplines.

        By default, this method returns all disciplines.
        This method can be overloaded by subclasses.

        Returns:
            The top level disciplines.
        """
        return self.disciplines

    @staticmethod
    def _get_mask_from_datanames(
        all_data_names: ndarray,
        masked_data_names: ndarray,
    ) -> ndarray:
        """Get a mask of all_data_names for masked_data_names.

        This mask is an array of the size of ``all_data_names``
        with ``True`` values when masked_data_names are in ``all_data_names``.

        Args:
            all_data_names: The main array for mask.
            masked_data_names: The array which masks ``all_data_names``.

        Returns:
            A boolean mask array.
        """
        return in1d(all_data_names, masked_data_names).nonzero()

    def _get_generator_from(
        self,
        output_names: Iterable[str],
        top_level_disc: bool = False,
    ) -> MDODisciplineAdapterGenerator:
        """Create a generator of :class:`.MDOFunction` from the names of the outputs.

        Find a discipline which computes all the provided outputs
        and build the associated :class:`.MDODisciplineAdapterGenerator`.

        Args:
            output_names: The names of the outputs.
            top_level_disc: Whether to search outputs among top level disciplines.

        Returns:
            A generator of :class:`.MDOFunction` instances.

        Raises:
            ValueError: If no discipline is found.
        """
        search_among = self.get_top_level_disc() if top_level_disc else self.disciplines
        for discipline in search_among:
            if discipline.is_all_outputs_existing(output_names):
                return MDODisciplineAdapterGenerator(
                    discipline, self.design_space.variable_sizes
                )

        msg = (
            f"No discipline known by formulation {type(self).__name__}"
            f" has all outputs named {output_names}"
        )
        raise ValueError(msg)

    def _get_generator_with_inputs(
        self,
        input_names: Iterable[str],
        top_level_disc: bool = False,
    ) -> MDODisciplineAdapterGenerator:
        """Create a generator of :class:`.MDOFunction` from the names of the inputs.

        Find a discipline which has all the provided inputs
        and build the associated :class:`.MDODisciplineAdapterGenerator.

        Args:
            input_names: The names of the inputs.
            top_level_disc: Whether to search inputs among the top level disciplines.

        Returns:
            A generator of :class:`.MDOFunction` instances.

        Raises:
            ValueError: If no discipline is found.
        """
        search_among = self.get_top_level_disc() if top_level_disc else self.disciplines
        for discipline in search_among:
            if discipline.is_all_inputs_existing(input_names):
                return MDODisciplineAdapterGenerator(
                    discipline, self.design_space.variable_sizes
                )

        msg = (
            f"No discipline known by formulation {type(self).__name__}"
            f" has all inputs named {input_names}"
        )
        raise ValueError(msg)

    def _get_dv_length(
        self,
        variable_name: str,
    ) -> int:
        """Retrieve the length of a variable.

        This method relies on the size declared in the design space.

        Args:
            variable_name: The name of the variable.

        Returns:
            The size of the variable.
        """
        return self.opt_problem.design_space.variable_sizes[variable_name]

    def _get_dv_indices(
        self,
        names: Iterable[str],
    ) -> dict[str, tuple[int, int, int]]:
        """Return the indices associated with specific variables.

        Args:
            names: The names of the variables.

        Returns:
            For each variable,
            a 3-length tuple
            whose first dimensions are its first and last indices in the design space
            and last dimension is its size.
        """
        start = end = 0
        sizes = self.opt_problem.design_space.variable_sizes
        names_to_indices = {}
        for name in names:
            size = sizes[name]
            end += size
            names_to_indices[name] = (start, end, size)
            start = end

        return names_to_indices

    def unmask_x_swap_order(
        self,
        masking_data_names: Iterable[str],
        x_masked: ndarray,
        all_data_names: Iterable[str] | None = None,
        x_full: ndarray = None,
    ) -> ndarray:
        """Unmask a vector from a subset of names, with respect to a set of names.

        This method eventually swaps the order of the values
        if the order of the data names is inconsistent between these sets.

        Args:
            masking_data_names: The names of the kept data.
            x_masked: The boolean vector to unmask.
            all_data_names: The set of all names.
                If ``None``, use the design variables stored in the design space.
            x_full: The default values for the full vector.
                If ``None``, use the zero vector.

        Returns:
            The vector related to the input mask.

        Raises:
            IndexError: when the sizes of variables are inconsistent.
        """
        if all_data_names is None:
            all_data_names = self.get_optim_variable_names()
        indices = self._get_dv_indices(all_data_names)
        variable_sizes = self.opt_problem.design_space.variable_sizes
        total_size = sum(variable_sizes[var] for var in all_data_names)

        # TODO: The support of sparse Jacobians requires modifications here.
        if x_full is None:
            x_unmask = zeros(total_size, dtype=x_masked.dtype)
        else:
            x_unmask = copy(x_full)

        i_x = 0
        try:
            for key in all_data_names:
                if key in masking_data_names:
                    i_min, i_max, n_x = indices[key]
                    x_unmask[i_min:i_max] = x_masked[i_x : i_x + n_x]
                    i_x += n_x
        except IndexError:
            raise ValueError(
                "Inconsistent input array size of values array "
                "with reference data shape %s" % x_unmask.shape
            ) from None
        return x_unmask

    def mask_x_swap_order(
        self,
        masking_data_names: Iterable[str],
        x_vect: ndarray,
        all_data_names: Iterable[str] | None = None,
    ) -> ndarray:
        """Mask a vector from a subset of names, with respect to a set of names.

        This method eventually swaps the order of the values
        if the order of the data names is inconsistent between these sets.

        Args:
            masking_data_names: The names of the kept data.
            x_vect: The vector to mask.
            all_data_names: The set of all names.
                If ``None``, use the design variables stored in the design space.

        Returns:
            The masked version of the input vector.

        Raises:
            IndexError: when the sizes of variables are inconsistent.
        """
        x_mask = self.get_x_mask_x_swap_order(masking_data_names, all_data_names)
        return x_vect[x_mask]

    def get_x_mask_x_swap_order(
        self,
        masking_data_names: Iterable[str],
        all_data_names: Iterable[str] | None = None,
    ) -> ndarray:
        """Mask a vector from a subset of names, with respect to a set of names.

        This method eventually swaps the order of the values
        if the order of the data names is inconsistent between these sets.

        Args:
            masking_data_names: The names of the kept data.
            all_data_names: The set of all names.
                If ``None``, use the design variables stored in the design space.

        Returns:
            The masked version of the input vector.

        Raises:
            ValueError: If the sizes or the sizes of variables are inconsistent.
        """
        design_space = self.opt_problem.design_space
        if all_data_names is None:
            all_data_names = design_space.variable_names

        variable_sizes = design_space.variable_sizes
        total_size = sum(variable_sizes[var] for var in masking_data_names)
        indices = self._get_dv_indices(all_data_names)
        x_mask = empty(total_size, dtype="int")
        i_masked_min = i_masked_max = 0
        try:
            for key in masking_data_names:
                i_min, i_max, loc_size = indices[key]
                i_masked_max += loc_size
                x_mask[i_masked_min:i_masked_max] = arange(i_min, i_max)
                i_masked_min = i_masked_max
        except KeyError as err:
            msg = (
                "Inconsistent inputs of masking. "
                f"Key {err} is in masking_data_names {masking_data_names} "
                f"but not in provided all_data_names : {all_data_names}!"
            )
            raise ValueError(msg) from None

        return x_mask

    def _remove_unused_variables(self) -> None:
        """Remove variables in the design space that are not discipline inputs."""
        design_space = self.opt_problem.design_space
        disciplines = self.get_top_level_disc()
        all_inputs = {
            var for disc in disciplines for var in disc.get_input_data_names()
        }
        for name in set(design_space.variable_names):
            if name not in all_inputs:
                design_space.remove_variable(name)
                LOGGER.info(
                    "Variable %s was removed from the Design Space, it is not an input"
                    " of any discipline.",
                    name,
                )

    def _remove_sub_scenario_dv_from_ds(self) -> None:
        """Remove the sub scenarios design variables from the design space."""
        for scenario in self.get_sub_scenarios():
            loc_vars = scenario.design_space.variable_names
            for var in loc_vars:
                if var in self.design_space.variable_names:
                    self.design_space.remove_variable(var)

    def _build_objective_from_disc(
        self,
        objective_name: str | Sequence[str],
        discipline: MDODiscipline | None = None,
        top_level_disc: bool = True,
    ) -> None:
        """Build the objective function from the discipline able to compute it.

        Args:
            objective_name: The name(s) of the discipline output(s) used as objective.
                If multiple names are passed, the objective will be a vector.
            discipline: The discipline computing the objective.
                If ``None``, the discipline is detected from the inner disciplines.
            top_level_disc: Whether to search the discipline among the top level ones.
        """
        if isinstance(objective_name, str):
            objective_name = [objective_name]
        obj_mdo_fun = FunctionFromDiscipline(
            objective_name, self, discipline, top_level_disc
        )
        if obj_mdo_fun.linear_candidate:
            obj_mdo_fun = compute_linear_approximation(
                obj_mdo_fun, zeros(obj_mdo_fun.input_dimension)
            )

        self.opt_problem.objective = obj_mdo_fun
        if self._maximize_objective:
            self.opt_problem.change_objective_sign()

    def get_optim_variable_names(self) -> list[str]:
        """Get the optimization unknown names to be provided to the optimizer.

        This is different from the design variable names provided by the user,
        since it depends on the formulation,
        and can include target values for coupling for instance in IDF.

        Returns:
            The optimization variable names.
        """
        return self.opt_problem.design_space.variable_names

    def get_x_names_of_disc(
        self,
        discipline: MDODiscipline,
    ) -> list[str]:
        """Get the design variables names of a given discipline.

        Args:
            discipline: The discipline.

        Returns:
             The names of the design variables.
        """
        optim_variable_names = self.get_optim_variable_names()
        input_names = discipline.get_input_data_names()
        return [name for name in optim_variable_names if name in input_names]

    def get_sub_disciplines(self, recursive: bool = False) -> list[MDODiscipline]:
        """Accessor to the sub-disciplines.

        This method lists the sub scenarios' disciplines. It will list up to one level
        of disciplines contained inside another one unless the ``recursive`` argument is
        set to ``True``.

        Args:
            recursive: If ``True``, the method will look inside any discipline that has
                other disciplines inside until it reaches a discipline without
                sub-disciplines, in this case the return value will not include any
                discipline that has sub-disciplines. If ``False``, the method will list
                up to one level of disciplines contained inside another one, in this
                case the return value may include disciplines that contain
                sub-disciplines.

        Returns:
            The sub-disciplines.
        """
        return get_sub_disciplines(self._disciplines, recursive)

    def get_sub_scenarios(self) -> list[Scenario]:
        """List the disciplines that are actually scenarios.

        Returns:
            The scenarios.
        """
        return [disc for disc in self.disciplines if disc.is_scenario()]

    def _set_default_input_values_from_design_space(self) -> None:
        """Initialize the top level disciplines from the design space."""
        if not self.opt_problem.design_space.has_current_value():
            return

        current_x = self.opt_problem.design_space.get_current_value(as_dict=True)

        for discipline in self.get_top_level_disc():
            input_names = discipline.get_input_data_names()
            to_value = discipline.input_grammar.data_converter.convert_array_to_value
            discipline.default_inputs.update({
                name: to_value(name, value)
                for name, value in current_x.items()
                if name in input_names
            })

    @abstractmethod
    def get_expected_workflow(
        self,
    ) -> list[ExecutionSequence, tuple[ExecutionSequence]]:
        """Get the expected sequence of execution of the disciplines.

        This method is used for the XDSM representation
        and can be overloaded by subclasses.

        For instance:

        * [A, B] denotes the execution of A,
          then the execution of B
        * (A, B) denotes the concurrent execution of A and B
        * [A, (B, C), D] denotes the execution of A,
          then the concurrent execution of B and C,
          then the execution of D.

        Returns:
            A sequence of elements which are either
            an :class:`.ExecutionSequence`
            or a tuple of :class:`.ExecutionSequence` for concurrent execution.
        """

    @abstractmethod
    def get_expected_dataflow(
        self,
    ) -> list[tuple[MDODiscipline, MDODiscipline, list[str]]]:
        """Get the expected data exchange sequence.

        This method is used for the XDSM representation
        and can be overloaded by subclasses.

        Returns:
            The expected sequence of data exchange
            where the i-th item is described by the starting discipline,
            the ending discipline and the coupling variables.
        """

    @classmethod
    def get_default_sub_option_values(cls, **options: str) -> dict:
        """Return the default values of the sub-options of the formulation.

        When some options of the formulation depend on higher level options,
        the default values of these sub-options may be obtained here,
        mainly for use in the API.

        Args:
            **options: The options required to deduce the sub-options grammar.

        Returns:
            Either ``None`` or the sub-options default values.
        """

    @classmethod
    def get_sub_options_grammar(cls, **options: str) -> JSONGrammar:
        """Get the sub-options grammar.

        When some options of the formulation depend on higher level options,
        the schema of the sub-options may be obtained here,
        mainly for use in the API.

        Args:
            **options: The options required to deduce the sub-options grammar.

        Returns:
            Either ``None`` or the sub-options grammar.
        """


class FormulationFactory(BaseFactory):
    """A factory of formulations."""

    def create(
        self,
        formulation_name: str,
        disciplines: Sequence[MDODiscipline],
        objective_name: str,
        design_space: DesignSpace,
        maximize_objective: bool = False,
        **options: Any,
    ) -> BaseFormulation:
        """Create a formulation.

        Args:
            formulation_name: The name of a class implementing a formulation.
            disciplines: The disciplines.
            objective_name: The name(s) of the discipline output(s) used as objective.
                If multiple names are passed, the objective will be a vector.
            design_space: The design space.
            maximize_objective: Whether to maximize the objective.
            **options: The options for the creation of the formulation.
        """
        return super().create(
            formulation_name,
            disciplines=disciplines,
            design_space=design_space,
            objective_name=objective_name,
            maximize_objective=maximize_objective,
            **options,
        )

    @property
    def formulations(self) -> list[str]:
        """The available formulations."""
        return self.class_names
