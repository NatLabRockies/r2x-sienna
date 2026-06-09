from r2x_sienna.upgrader.upgrade_steps import upgrade_hydro_energy_reservoir


def test_hydro_upgrade(old_system_data):
    """Test that HydroEnergyReservoir and HydroPumpedStorage upgrades to
    HydroReservoir + Turbine/HydroPumpTurbine.
    """

    new_system = upgrade_hydro_energy_reservoir(old_system_data)

    reservoir = None
    for c in new_system["data"]["components"]:
        comp_type = c.get("__metadata__", {}).get("type")
        if comp_type == "HydroReservoir":
            reservoir = c
            break

    assert reservoir is not None

    turbine = None
    for c in new_system["data"]["components"]:
        comp_type = c.get("__metadata__", {}).get("type")
        if comp_type in ["HydroTurbine", "HydroPumpTurbine"]:
            turbine = c
            break

    assert turbine is not None

    reservoir_fields = list(reservoir.keys())
    assert "travel_time" not in reservoir, (
        f"'travel_time' field found in reservoir. Available fields: {reservoir_fields}"
    )

    turbine_fields = list(turbine.keys())
    assert "reservoirs" in turbine, (
        f"'reservoirs' field not found in turbine. Available fields: {turbine_fields}"
    )
    assert turbine["travel_time"] == 2.5
