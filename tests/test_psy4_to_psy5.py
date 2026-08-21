from r2x_sienna.upgrader.upgrade_steps import upgrade_hydro_energy_reservoir, upgrade_hydro_pumped_storage


def test_hydro_upgrade(old_system_data):
    """Test that HydroEnergyReservoir and HydroPumpedStorage upgrades to
    HydroReservoir + Turbine/HydroPumpTurbine.
    """
    legacy_pumped_storage_uuid = next(
        c["internal"]["uuid"] for c in old_system_data["data"]["components"] if c["name"] == "PumpedStorage1"
    )

    new_system = upgrade_hydro_energy_reservoir(old_system_data)
    new_system = upgrade_hydro_pumped_storage(new_system)

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

    head_reservoir = next(
        c for c in new_system["data"]["components"] if c["name"] == "PumpedStorage1_HeadReservoir"
    )
    upgraded_pump_turbine = next(
        c for c in new_system["data"]["components"] if c["name"] == "PumpedStorage1_PumpTurbine"
    )
    assert head_reservoir["internal"]["uuid"] == legacy_pumped_storage_uuid
    assert upgraded_pump_turbine["internal"]["uuid"] != legacy_pumped_storage_uuid
