"""Test model example methods."""


def test_renewable_models():
    """Test renewable models specifically."""
    from r2x_sienna.models.generators import RenewableDispatch, RenewableNonDispatch

    assert RenewableDispatch.example()
    assert RenewableNonDispatch.example()


def test_thermal_standard_model():
    """Test ThermalStandard model."""
    from r2x_sienna.models.generators import ThermalStandard

    ts = ThermalStandard.example()
    ts_dict = ts.model_dump()

    required_fields = [
        "name",
        "active_power",
        "reactive_power",
        "rating",
        "base_power",
        "must_run",
        "prime_mover_type",
        "status",
        "operation_cost",
        "fuel",
    ]

    assert all(field in ts_dict for field in required_fields)


def test_service_and_topology_examples():
    """Test service and topology example constructors."""
    from r2x_sienna.models.services import Reserve, TransmissionInterface
    from r2x_sienna.models.topology import DCBus

    reserve = Reserve.example()
    interface = TransmissionInterface.example()
    dc_bus = DCBus.example()

    assert reserve.name == "ExampleReserve"
    assert reserve.region is not None
    assert interface.active_power_flow_limits.min == -100
    assert "line-01" in interface.direction_mapping
    assert dc_bus.base_voltage is not None


def test_load_examples():
    """Test load-related example constructors."""
    from r2x_sienna.models.load import FACTSControlDevice, FixedAdmittance, PowerLoad, SwitchedAdmittance

    facts = FACTSControlDevice.example()
    power_load = PowerLoad.example()
    fixed = FixedAdmittance.example()
    switched = SwitchedAdmittance.example()

    assert facts.control_mode is not None
    assert power_load.active_power is not None
    assert fixed.Y.imag < 0
    assert len(switched.number_of_steps) == 3


def test_emissions_data_example():
    """Test EmissionsData example constructor and default field values."""
    from r2x_sienna.models.attributes import EmissionsData

    ed = EmissionsData.example()
    assert ed.name == "co2_rate"
    assert ed.start_up_adder == 0.0
    assert ed.gwp == 1.0
    assert ed.available is True


def test_emissions_data_scalar_coercion():
    """Scalar float emission_rate is coerced to a LinearCurve."""
    from infrasys.value_curves import InputOutputCurve
    from r2x_sienna.models.attributes import EmissionsData
    from r2x_sienna.models.enums import EmissionBasis, EnergyUnit, PollutantType

    ed = EmissionsData(
        name="nox",
        pollutant=PollutantType.NOX,
        emission_rate=0.1,
        basis=EmissionBasis.POWER_OUTPUT,
        energy_unit=EnergyUnit.MWH,
    )
    assert isinstance(ed.emission_rate, InputOutputCurve)


def test_emissions_data_fuel_input_valid_energy_units():
    """FUEL_INPUT basis accepts MMBTU and GJ energy units."""
    from infrasys.value_curves import LinearCurve
    from r2x_sienna.models.attributes import EmissionsData
    from r2x_sienna.models.enums import EmissionBasis, EnergyUnit, PollutantType

    for unit in (EnergyUnit.MMBTU, EnergyUnit.GJ):
        ed = EmissionsData(
            name="co2_fuel",
            pollutant=PollutantType.CO2,
            emission_rate=LinearCurve(0.05),
            basis=EmissionBasis.FUEL_INPUT,
            energy_unit=unit,
        )
        assert ed.energy_unit == unit


def test_emissions_data_invalid_basis_energy_unit():
    """FUEL_INPUT + MWH must raise a validation error."""
    import pytest
    from infrasys.value_curves import LinearCurve
    from pydantic import ValidationError
    from r2x_sienna.models.attributes import EmissionsData
    from r2x_sienna.models.enums import EmissionBasis, EnergyUnit, PollutantType

    with pytest.raises(ValidationError):
        EmissionsData(
            name="bad",
            pollutant=PollutantType.CO2,
            emission_rate=LinearCurve(0.05),
            basis=EmissionBasis.FUEL_INPUT,
            energy_unit=EnergyUnit.MWH,
        )


def test_emissions_data_negative_gwp_rejected():
    """Negative gwp must raise a validation error."""
    import pytest
    from infrasys.value_curves import LinearCurve
    from pydantic import ValidationError
    from r2x_sienna.models.attributes import EmissionsData
    from r2x_sienna.models.enums import EmissionBasis, EnergyUnit, PollutantType

    with pytest.raises(ValidationError):
        EmissionsData(
            name="bad_gwp",
            pollutant=PollutantType.CH4,
            emission_rate=LinearCurve(0.1),
            basis=EmissionBasis.POWER_OUTPUT,
            energy_unit=EnergyUnit.MWH,
            gwp=-1.0,
        )


def test_emissions_data_enums():
    """PollutantType, EmissionBasis, MassUnit, and EnergyUnit have expected members."""
    from r2x_sienna.models.enums import EmissionBasis, EnergyUnit, MassUnit, PollutantType

    assert PollutantType.CO2 == "CO2"
    assert PollutantType.NOX == "NOX"
    assert EmissionBasis.FUEL_INPUT == "FUEL_INPUT"
    assert EmissionBasis.POWER_OUTPUT == "POWER_OUTPUT"
    assert MassUnit.KG == "KG"
    assert MassUnit.METRIC_TON == "METRIC_TON"
    assert EnergyUnit.MMBTU == "MMBTU"
    assert EnergyUnit.MWH == "MWH"
