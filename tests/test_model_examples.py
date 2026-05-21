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
