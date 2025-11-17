"""Core models for r2x-sienna."""

from collections import defaultdict
from typing import Annotated

from pydantic import Field

from r2x_sienna.models.base import SiennaComponent


class Service(SiennaComponent):
    """Abstract class for services attached to components."""


class Device(SiennaComponent):
    """Abstract class for devices."""

    available: Annotated[
        bool,
        Field(
            description=(
                "Indicator of whether the component is connected and online (`true`) or disconnected, offline, or down (`false`). "
                "Unavailable components are excluded during simulations"
            )
        ),
    ] = True
    services: list = Field(default_factory=list, description="Services that this component contributes to.")


class StaticInjection(Device):
    """Supertype for all static injection devices."""


class TransmissionInterfaceMap(SiennaComponent):
    mapping: defaultdict[str, list] = defaultdict(list)  # noqa: RUF012


class ReserveMap(SiennaComponent):
    mapping: defaultdict[str, list] = defaultdict(list)  # noqa: RUF012
