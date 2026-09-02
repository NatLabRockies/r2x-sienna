from infrasys.models import InfraSysBaseModel
from pint import Quantity
from pydantic import AliasChoices, Field


class GeoLocation(InfraSysBaseModel):
    """Geographic location supporting both Latitude/Longitude and GeoJSON formats."""

    coordinates: list[float] | list[list[float]]
    type: str


class MinMax(InfraSysBaseModel):
    min: float | Quantity
    max: float | Quantity


class UpDown(InfraSysBaseModel):
    up: float | Quantity
    down: float | Quantity


class Complex(InfraSysBaseModel):
    real: float
    imag: float


class InputOutput(InfraSysBaseModel):
    input: float = Field(validation_alias=AliasChoices("input", "in"))
    output: float = Field(validation_alias=AliasChoices("output", "out"))


class FromTo_ToFrom(InfraSysBaseModel):
    from_to: float | Quantity = Field(validation_alias=AliasChoices("from_to", "from"))
    to_from: float | Quantity = Field(validation_alias=AliasChoices("to_from", "to"))


class StartShut(InfraSysBaseModel):
    startup: float | Quantity
    shutdown: float | Quantity


class StartUpStages(InfraSysBaseModel):
    hot: float | Quantity
    warm: float | Quantity
    cold: float | Quantity


class StartTimeLimits(InfraSysBaseModel):
    hot: float | Quantity
    warm: float | Quantity
    cold: float | Quantity


class TurbinePump(InfraSysBaseModel):
    turbine: float | Quantity
    pump: float | Quantity
