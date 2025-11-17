""" "Base component classes for Sienna models with per-unit support."""

from infrasys import Component
from r2x_core.units._mixins import HasPerUnit
from r2x_sienna.units import ureg
from typing import Annotated
from pydantic import Field, computed_field, field_serializer


class SiennaComponent(HasPerUnit, Component):
    """Base Sienna component with per-unit conversion capabilities.

    This class combines infrasys.Component with r2x-core's HasPerUnit mixin
    to provide unit-aware field formatting and per-unit conversions for all
    Sienna components. It also includes common fields used across Sienna models.

    All Sienna components should inherit from this base class to ensure
    consistent unit handling, system integration, and common field availability.

    Attributes
    ----------
    available : bool, default True
        Whether the component is available for operation.
    category : str, optional
        Category that this component belongs to (e.g., "renewable", "thermal").
    ext : dict
        Additional information and metadata for the component. Quantity objects
        are automatically serialized to their magnitude values.
    class_type : str (computed)
        The class name of the component (computed field).

    Examples
    --------
    Create a custom Sienna component:

    >>> from r2x_core.units._specs import UnitSpec
    >>> from typing import Annotated
    >>> from pydantic import Field
    >>>
    >>> class SiennaGenerator(SiennaComponent):
    ...     name: str
    ...     active_power_limits_max: Annotated[
    ...         float,
    ...         Field(description="Maximum active power"),
    ...         UnitSpec("MW")
    ...     ]
    ...     base_power: Annotated[
    ...         float,
    ...         Field(description="Base power for per-unit calculations"),
    ...         UnitSpec("MW")
    ...     ]
    ...     active_power_limits_max_pu: Annotated[
    ...         float,
    ...         Field(description="Maximum active power in per-unit"),
    ...         UnitSpec("dimensionless", base="base_power")
    ...     ]

    Use the component with per-unit display:

    >>> gen = SiennaGenerator(
    ...     name="Gen1",
    ...     base_power=100.0,
    ...     active_power_limits_max=95.0,
    ...     active_power_limits_max_pu=0.95,
    ...     category="thermal"
    ... )
    >>> print(gen)  # Will show units based on current display mode

    Store additional metadata:

    >>> gen.ext["fuel_type"] = "natural_gas"
    >>> gen.ext["efficiency"] = 0.45 * ureg.dimensionless

    See Also
    --------
    r2x_core.units.HasPerUnit : Mixin providing per-unit conversion capabilities
    infrasys.Component : Base component class from infrasys
    r2x_sienna.units.ureg : Pint unit registry for Sienna

    Notes
    -----
    When components inheriting from SiennaComponent are added to an r2x-core System,
    they automatically receive the system's base power for system-base per-unit
    calculations via the _system_base attribute.

    The ext field automatically handles Pint Quantity serialization, converting
    quantity objects to their magnitude values during JSON serialization.
    """

    available: Annotated[bool, Field(description="Whether the component is available for operation.")] = True

    category: Annotated[str, Field(description="Category that this component belongs to.")] | None = None

    ext: dict = Field(default_factory=dict, description="Additional information of the component.")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def class_type(self) -> str:
        """Get the class name of this component.

        Returns
        -------
        str
            The class name (e.g., "ThermalStandard", "ACBus").
        """
        return type(self).__name__

    @field_serializer("ext", when_used="json")
    def serialize_ext(self, ext: dict) -> dict:
        """Serialize ext field, converting Quantity objects to magnitudes.

        Parameters
        ----------
        ext : dict
            The ext dictionary containing component metadata.

        Returns
        -------
        dict
            Serialized ext dictionary with Quantity objects converted
            to their magnitude values.

        Notes
        -----
        This serializer automatically handles Pint Quantity objects in the
        ext field, converting them to numeric values for JSON serialization.
        """
        serialized_ext = {}
        for key, value in ext.items():
            if isinstance(value, ureg.Quantity):
                serialized_ext[key] = value.magnitude
            else:
                serialized_ext[key] = value
        return serialized_ext
