"""Supplemental attributes models."""

from infrasys import SupplementalAttribute
from infrasys.function_data import PiecewiseLinearData, XYCoords

from r2x_sienna.models.enums import ImpedanceCorrectionTransformerControlMode, WindingCategory
from r2x_sienna.models.named_tuples import GeoLocation


class GeographicInfo(SupplementalAttribute):
    """Supplemental attribute that captures location."""

    geo_json: GeoLocation

    @classmethod
    def example(cls) -> "GeographicInfo":
        return GeographicInfo(geo_json=GeoLocation(Latitude=10.5, Longitude=-100))


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
