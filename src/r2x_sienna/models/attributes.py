"""Supplemental attributes models."""

import math
from typing import Annotated, Any

from infrasys import SupplementalAttribute
from infrasys.function_data import PiecewiseLinearData, XYCoords
from infrasys.value_curves import LinearCurve, ValueCurve
from pydantic import Field, field_validator, model_validator

from r2x_sienna.models.enums import (
    EmissionBasis,
    EnergyUnit,
    ImpedanceCorrectionTransformerControlMode,
    MassUnit,
    PollutantType,
    WindingCategory,
)
from r2x_sienna.models.named_tuples import GeoLocation


class GeographicInfo(SupplementalAttribute):
    """Supplemental attribute that captures location."""

    geo_json: GeoLocation

    @classmethod
    def example(cls) -> "GeographicInfo":
        return GeographicInfo(geo_json=GeoLocation(coordinates=[10.5, -100], type="Point"))


class ImpedanceCorrectionData(SupplementalAttribute):
    """Attribute that contains information regarding the Impedance Correction Table (ICT) rows defined in the Table.

    Attributes
    ----------
    table_number : int
        Row number of the ICT to be linked with a specific Transformer component.
    impedance_correction_curve : PiecewiseLinearData
        Function to define intervals (tap ratio/angle shift) in the Transformer component.
    transformer_winding : WindingCategory
        Indicates the winding to which the ICT is linked to for a Transformer component.
    transformer_control_mode : ImpedanceCorrectionTransformerControlMode
        Defines the control modes of the Transformer, whether it is for off-nominal turns ratio or phase angle shifts.
    """

    table_number: int
    impedance_correction_curve: PiecewiseLinearData
    transformer_winding: WindingCategory
    transformer_control_mode: ImpedanceCorrectionTransformerControlMode

    @classmethod
    def example(cls) -> "ImpedanceCorrectionData":
        return ImpedanceCorrectionData(
            table_number=1,
            impedance_correction_curve=PiecewiseLinearData(
                points=[XYCoords(x=0, y=0), XYCoords(x=50, y=10), XYCoords(x=100, y=25)]
            ),
            transformer_winding=WindingCategory.PRIMARY_WINDING,
            transformer_control_mode=ImpedanceCorrectionTransformerControlMode.TAP_RATIO,
        )


class GeometricDistributionForcedOutage(SupplementalAttribute):
    """
    Attribute that contains information regarding forced outages where the transition probabilities
    are modeled with geometric distributions. The outage probabilities and recovery probabilities can be modeled as time series.
    """

    mean_time_to_recovery: float = 0.0
    outage_transition_probability: float = 0.0
    internal: dict = {}

    @classmethod
    def example(cls) -> "GeometricDistributionForcedOutage":
        return GeometricDistributionForcedOutage(
            mean_time_to_recovery=1000.0,
            outage_transition_probability=0.05,
            internal={},
        )


class EmissionsData(SupplementalAttribute):
    """Supplemental attribute describing the emission of a single pollutant from a host component.

    Combines pollutant identity (CO2, NOx, etc.) with an emission rate expressed as a
    :class:`ValueCurve` (supporting constant, linear, or piecewise relationships between
    fuel consumption / power output and emissions). One ``EmissionsData`` instance can be
    attached to one or many components via ``add_supplemental_attribute``.

    Attributes
    ----------
    name : str
        Identifier for this emissions attribute.
    pollutant : PollutantType
        Pollutant type (CO2, CO2E, CH4, N2O, NOX, SO2, PM25, PM10, HG, HAP, CUSTOM).
    emission_rate : ValueCurve
        Emission rate as a :class:`ValueCurve`. A scalar ``float`` is also accepted and is
        automatically wrapped in a :class:`LinearCurve` with constant rate.
    basis : EmissionBasis
        ``FUEL_INPUT`` (mass per unit of heat input) or ``POWER_OUTPUT`` (mass per unit of
        electrical output).
    energy_unit : EnergyUnit
        Energy unit for the rate denominator (MMBTU, GJ, or MWH). Must be consistent with
        ``basis``: MMBTU/GJ require ``FUEL_INPUT``; MWH requires ``POWER_OUTPUT``.
    start_up_adder : float
        Per-start emission pulse, in ``mass_unit``. Must be finite and >= 0.
    mass_unit : MassUnit
        KG, LB, SHORT_TON, or METRIC_TON.
    gwp : float
        GWP100 multiplier for CO2-equivalent reporting. Must be finite and >= 0.
    available : bool
        Whether this attribute is active.
    ext : dict[str, Any]
        Extra metadata dictionary.
    """

    name: str
    pollutant: PollutantType
    emission_rate: Annotated[
        ValueCurve,
        Field(description="Emission rate curve; a scalar float is wrapped in a LinearCurve."),
    ]
    basis: EmissionBasis
    energy_unit: EnergyUnit
    start_up_adder: Annotated[float, Field(default=0.0, ge=0.0)] = 0.0
    mass_unit: MassUnit = MassUnit.KG
    gwp: Annotated[float, Field(default=1.0, ge=0.0)] = 1.0
    available: bool = True
    ext: dict[str, Any] = {}

    @field_validator("emission_rate", mode="before")
    @classmethod
    def _coerce_scalar_emission_rate(cls, v: Any) -> ValueCurve:
        if isinstance(v, (int, float)):
            if not math.isfinite(v) or v < 0.0:
                raise ValueError(f"emission_rate must be finite and >= 0.0, got {v}")
            return LinearCurve(v)
        return v

    @field_validator("start_up_adder", "gwp", mode="before")
    @classmethod
    def _validate_nonneg_finite(cls, v: Any) -> float:
        fv = float(v)
        if not math.isfinite(fv) or fv < 0.0:
            raise ValueError(f"Value must be finite and >= 0.0, got {v}")
        return fv

    @model_validator(mode="after")
    def _validate_basis_energy_unit(self) -> "EmissionsData":
        if self.basis == EmissionBasis.FUEL_INPUT:
            if self.energy_unit not in (EnergyUnit.MMBTU, EnergyUnit.GJ):
                raise ValueError(
                    f"energy_unit must be MMBTU or GJ when basis is FUEL_INPUT, got {self.energy_unit}"
                )
        elif self.basis == EmissionBasis.POWER_OUTPUT:
            if self.energy_unit != EnergyUnit.MWH:
                raise ValueError(
                    f"energy_unit must be MWH when basis is POWER_OUTPUT, got {self.energy_unit}"
                )
        return self

    @classmethod
    def example(cls) -> "EmissionsData":
        return EmissionsData(
            name="co2_rate",
            pollutant=PollutantType.CO2,
            emission_rate=LinearCurve(0.4),
            basis=EmissionBasis.POWER_OUTPUT,
            energy_unit=EnergyUnit.MWH,
        )
