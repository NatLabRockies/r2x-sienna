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
