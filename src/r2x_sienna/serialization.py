from functools import singledispatch
from math import isinf
from typing import Any

from infrasys.component import Component
from infrasys.function_data import XYCoords
from infrasys.models import InfraSysBaseModel
from infrasys.value_curves import InputOutputCurve
from pint import Quantity
from r2x_core import HasUnits

from r2x_sienna.models import Arc, Complex, FromTo_ToFrom, InputOutput, MinMax, StartUpStages, UpDown
from r2x_sienna.models.branch import (
    Line,
    MonitoredLine,
    ThreeWindingTransformer,
    TwoTerminalVSCLine,
    TwoWindingTransformer,
)
from r2x_sienna.models.costs import OperationalCost
from r2x_sienna.parser import PARAMETRIZED_TYPES

PARAMETRIZED_OUTPUT_TYPES = {"value_curve", "function_data", "loss"}
OUTPUT_METADATA = {"__metadata__", "internal"}
PARAMETRIZED_FIELDS = {"direction"}
# Fields that PowerSystems.jl declares non-nullable but fills from constructor defaults when omitted.
PSY_DEFAULTED_FIELDS: dict[type, tuple[str, ...]] = {
    Line: ("g",),
    MonitoredLine: ("g",),
    ThreeWindingTransformer: ("rating_primary", "rating_secondary", "rating_tertiary"),
    TwoTerminalVSCLine: (
        "max_dc_current_from",
        "max_dc_current_to",
        "rating_from",
        "rating_to",
        "voltage_limits_from",
        "voltage_limits_to",
    ),
}
# JSON cannot represent infinity; PowerSystems.jl uses these finite sentinels instead.
PSY_INFINITE_VALUES = {
    "time_at_status": 1e4,  # INFINITE_TIME
    "energy_import_weekly_limit": 1e6,  # INFINITE_BOUND
    "energy_export_weekly_limit": 1e6,  # INFINITE_BOUND
}


def _psy_finite_value(field: str, value: Any) -> Any:
    if isinstance(value, float) and isinf(value) and value > 0 and field in PSY_INFINITE_VALUES:
        return PSY_INFINITE_VALUES[field]
    return value


# Fields PowerSystems.jl 5.12 requires as non-null with no constructor default, but that Python allows unset.
PSY_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "AreaInterchange": ("from_area", "to_area"),
    "DiscreteControlledACBranch": ("r", "x", "rating"),
    "EnergyReservoirStorage": ("bus",),
    "HydroDispatch": ("bus",),
    "HydroPumpTurbine": ("bus",),
    "HydroTurbine": ("bus",),
    "InterruptiblePowerLoad": (
        "active_power",
        "reactive_power",
        "max_active_power",
        "max_reactive_power",
        "base_power",
        "operation_cost",
    ),
    "InterruptibleStandardLoad": ("operation_cost",),
    "Line": ("r", "x", "b", "rating"),
    "MonitoredLine": ("r", "x", "b", "flow_limits", "rating", "angle_limits"),
    "PhaseShiftingTransformer": ("r", "x", "primary_shunt", "base_power"),
    "PowerLoad": ("active_power", "reactive_power", "base_power", "max_active_power", "max_reactive_power"),
    "RenewableDispatch": ("bus",),
    "RenewableNonDispatch": ("bus",),
    "ShiftablePowerLoad": ("operation_cost",),
    "Source": ("bus",),
    "SynchronousCondenser": ("bus",),
    "TapTransformer": ("r", "x", "primary_shunt", "base_power"),
    "ThermalMultiStart": ("bus",),
    "ThermalStandard": ("bus",),
    "Transformer2W": ("r", "x", "primary_shunt", "base_power"),
    "TwoTerminalLCCLine": ("r",),
    "TwoTerminalVSCLine": ("rating",),
    "VariableReserve": ("requirement",),
}


def missing_psy_required_fields(data: dict[str, Any]) -> list[str]:
    """Return PowerSystems.jl-required fields that a serialized component leaves unset."""
    component_type = data.get("__metadata__", {}).get("type", "")
    return [field for field in PSY_REQUIRED_FIELDS.get(component_type, ()) if data.get(field) is None]


def fill_psy_safe_defaults(data: dict[str, Any], system_base_power: float) -> list[str]:
    """Fill unset PowerSystems.jl-required fields that have a principled value.

    Values mean "nothing there" (no shunt, no reactive demand), reuse the component's own data,
    or use the exported system base, matching the transformer upgrade defaults. Fields without a
    correct default, such as ``bus``, ``r``, ``x``, or ``rating``, are left for the caller to report.
    """
    component_type = data.get("__metadata__", {}).get("type", "")
    filled: list[str] = []

    def fill(field: str, value: Any) -> None:
        if data.get(field) is None and value is not None:
            data[field] = value
            filled.append(f"{field}={value}")

    if component_type in ("Transformer2W", "TapTransformer", "PhaseShiftingTransformer"):
        fill("base_power", system_base_power)
        fill("primary_shunt", {"real": 0.0, "imag": 0.0})
    if component_type in ("Line", "MonitoredLine"):
        fill("b", {"from": 0.0, "to": 0.0})
    if component_type == "MonitoredLine" and data.get("rating") is not None:
        fill("flow_limits", {"from_to": data["rating"], "to_from": data["rating"]})
    if component_type in ("PowerLoad", "InterruptiblePowerLoad"):
        fill("reactive_power", 0.0)
        fill("max_active_power", data.get("active_power"))
        fill("max_reactive_power", data.get("reactive_power"))
        fill("base_power", system_base_power)
    return filled


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
def _(value: StartUpStages, field: str = "") -> dict[str, Any]:
    return {"hot": value.hot, "warm": value.warm, "cold": value.cold}


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

    # Emit defaulted fields too: PowerSystems.jl cost constructors require them. Every nullable
    # PowerSystems.jl cost or curve field defaults to nothing, so None values are omitted.
    for key in type(obj).model_fields:
        attribute = getattr(obj, key)
        if attribute is None:
            continue
        if isinstance(attribute, StartUpStages):
            output_dict[key] = serialize_value(attribute, key)
            continue

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
            output_dict[key] = _psy_finite_value(key, serialized if serialized is not None else attribute)

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
    metadata: dict[str, Any] = {"module": "PowerSystems", "type": cls.__name__}
    data["__metadata__"] = metadata

    if isinstance(component, Component):
        data["internal"] = {
            "uuid": {"value": data.pop("uuid")},
            "ext": None,
            "unit_info": None,
        }

    parametrized_fields = component.model_fields_set & PARAMETRIZED_FIELDS
    if parametrized_fields:
        parameters: list[str] = []
        for parametrized_field in parametrized_fields:
            parameter = _get_parametrized_type(parametrized_field, getattr(component, parametrized_field))
            if parameter is not None:
                parameters.append(parameter)

        if parameters:
            metadata["construct_with_parameters"] = True
            metadata["parameters"] = parameters

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
    if isinstance(component, HasUnits):
        for field, spec in type(component).unit_specs.items():
            if spec.base is None:
                continue
            output_field = type(component).model_fields[field].serialization_alias or field
            value = data.get(output_field)
            if (
                isinstance(value, dict)
                and set(value) == {"value", "unit"}
                and value["unit"] == "pu"
                and isinstance(value["value"], dict)
            ):
                data[output_field] = value["value"]
    data = _add_psy_metadata(component, data)
    data.update(custom_values)
    for field in PSY_INFINITE_VALUES.keys() & data.keys():
        data[field] = _psy_finite_value(field, data[field])

    if isinstance(component, TwoWindingTransformer | ThreeWindingTransformer):
        # PowerSystems.jl derives omitted bases from connected buses; 0 kV would yield NaN impedances.
        for field in ("base_voltage_primary", "base_voltage_secondary", "base_voltage_tertiary"):
            if field in data and not data[field]:
                del data[field]
    for component_type, fields in PSY_DEFAULTED_FIELDS.items():
        if isinstance(component, component_type):
            for field in fields:
                if field in data and data[field] is None:
                    del data[field]

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
