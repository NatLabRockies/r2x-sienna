from functools import singledispatch
from typing import Any

from infrasys.component import Component
from infrasys.function_data import XYCoords
from infrasys.models import InfraSysBaseModel
from infrasys.value_curves import InputOutputCurve
from pint import Quantity

from r2x_sienna.models import Arc, Complex, FromTo_ToFrom, InputOutput, MinMax, UpDown
from r2x_sienna.models.costs import OperationalCost
from r2x_sienna.parser import PARAMETRIZED_TYPES

PARAMETRIZED_OUTPUT_TYPES = {"value_curve", "function_data", "loss"}
OUTPUT_METADATA = {"__metadata__", "internal"}
PARAMETRIZED_FIELDS = {"direction"}


@singledispatch
def serialize_value(value: Any, field: str = "") -> Any:
    if isinstance(value, (int, float, str, bool)):
        return value
    return None


@serialize_value.register
def _(value: Quantity, field: str = "") -> float:
    return value.magnitude


@serialize_value.register
def _(value: MinMax, field: str = "") -> dict[str, Any]:
    return {"min": value.min, "max": value.max}


@serialize_value.register
def _(value: FromTo_ToFrom, field: str = "") -> dict[str, Any]:
    if field in ("b", "g"):
        return {"from": value.from_to, "to": value.to_from}
    return {"from_to": value.from_to, "to_from": value.to_from}


@serialize_value.register
def _(value: UpDown, field: str = "") -> dict[str, Any]:
    return {"up": value.up, "down": value.down}


@serialize_value.register
def _(value: InputOutput, field: str = "") -> dict[str, Any]:
    return {"in": value.input, "out": value.output}


@serialize_value.register
def _(value: Complex, field: str = "") -> dict[str, Any]:
    return {"real": value.real, "imag": value.imag}


@serialize_value.register
def _(value: XYCoords, field: str = "") -> dict[str, float]:
    return {"x": value.x, "y": value.y}


@serialize_value.register(OperationalCost)
@serialize_value.register(InputOutputCurve)
def _(value: InfraSysBaseModel, field: str = "") -> dict[str, Any]:
    return _serialize_parametric_object(value)


@serialize_value.register
def _(value: Component, field: str = "") -> dict[str, str]:
    return {"value": str(value.uuid)}


@serialize_value.register
def _(value: list, field: str = "") -> list[dict[str, str]]:
    return [{"value": str(comp.uuid)} for comp in value if isinstance(comp, Component)]


def _serialize_parametric_object(obj: InfraSysBaseModel) -> dict[str, Any]:
    output_dict: dict[str, Any] = {}
    parametric_types: set[str] = set()

    for key in obj.model_fields_set:
        attribute = getattr(obj, key)

        if isinstance(attribute, InfraSysBaseModel):
            if key in PARAMETRIZED_OUTPUT_TYPES:
                parametric_types.add(attribute.__class__.__name__)

            nested_output = _serialize_parametric_object(attribute)
            if "__metadata__" not in nested_output:
                nested_output["__metadata__"] = {
                    "module": "InfrastructureSystems",
                    "type": attribute.__class__.__name__,
                }
            output_dict[key] = nested_output
        elif isinstance(attribute, list):
            serialized_list = []
            for item in attribute:
                serialized_item = serialize_value(item, key)
                serialized_list.append(serialized_item if serialized_item is not None else item)
            output_dict[key] = serialized_list
        else:
            serialized = serialize_value(attribute, key)
            output_dict[key] = serialized if serialized is not None else attribute

    metadata: dict[str, Any] = {
        "module": "InfrastructureSystems" if not isinstance(obj, OperationalCost) else "PowerSystems",
        "type": obj.__class__.__name__,
    }

    if parametric_types:
        metadata["parameters"] = list(parametric_types)

    output_dict["__metadata__"] = metadata

    return output_dict


def _serialize_field_value(component: Component, field: str) -> Any:
    value = getattr(component, field)
    return serialize_value(value, field)


def _get_parametrized_type(field: str, value: Any) -> str | None:
    for key, values in PARAMETRIZED_TYPES.items():
        if values.get(field) == value:
            return key
    return None


def _add_psy_metadata(component: Component, data: dict[str, Any]) -> dict[str, Any]:
    cls = type(component)
    data["__metadata__"] = {"module": "PowerSystems", "type": cls.__name__}

    if isinstance(component, Component):
        data["internal"] = {
            "uuid": {"value": data.pop("uuid")},
            "ext": None,
            "unit_info": None,
        }

    parametrized_fields = component.model_fields_set & PARAMETRIZED_FIELDS
    if parametrized_fields:
        data["__metadata__"]["construct_with_parameters"] = True
        for parametrized_field in parametrized_fields:
            parameter = _get_parametrized_type(parametrized_field, getattr(component, parametrized_field))
            data["__metadata__"]["parameters"] = [parameter]

    return data


def serialize_component_to_psy(
    component: Component, include: dict[str, list] | None = None
) -> dict[str, Any] | None:
    custom_values = {}
    for field in component.__class__.model_fields:
        if field not in type(component).model_fields:
            continue

        value = _serialize_field_value(component, field)
        if value is not None:
            custom_values[field] = value

    data = component.model_dump(mode="json", by_alias=True, round_trip=True)
    data = _add_psy_metadata(component, data)
    data.update(custom_values)

    if not include:
        include = {}

    component_type_fields = set(component.__class__.model_fields.keys())
    data = {
        key: value
        for key, value in data.items()
        if key in include or key in OUTPUT_METADATA or key in component_type_fields
    }

    if not data:
        return None

    if isinstance(component, Arc):
        if "from_to" in data:
            data["from"] = data.pop("from_to")
        if "to_from" in data:
            data["to"] = data.pop("to_from")

    return data
