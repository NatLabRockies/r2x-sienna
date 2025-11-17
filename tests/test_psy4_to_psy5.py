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

    turbine_fields = list(turbine.keys())
    assert "reservoirs" in turbine, (
        f"'reservoirs' field not found in turbine. Available fields: {turbine_fields}"
    )
