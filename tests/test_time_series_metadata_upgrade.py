import json
import sqlite3

from infrasys.time_series_metadata_store import create_associations_table

from r2x_sienna.upgrader.data_upgrader import (
    _reconcile_metadata_uuid_references,
    _repair_deterministic_metadata_periods,
    migrate_metadata,
)


def test_migrate_metadata_from_legacy_ms_schema():
    con = sqlite3.connect(":memory:")
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE time_series_associations(
            id INTEGER PRIMARY KEY,
            time_series_uuid TEXT NOT NULL,
            time_series_type TEXT NOT NULL,
            time_series_category TEXT NOT NULL,
            initial_timestamp TEXT NOT NULL,
            resolution_ms TEXT NULL,
            horizon_ms TEXT,
            interval_ms TEXT,
            window_count INTEGER,
            length INTEGER,
            name TEXT NOT NULL,
            owner_uuid TEXT NOT NULL,
            owner_type TEXT NOT NULL,
            owner_category TEXT,
            features TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        INSERT INTO time_series_associations (
            time_series_uuid, time_series_type, time_series_category, initial_timestamp,
            resolution_ms, horizon_ms, interval_ms, window_count, length, name,
            owner_uuid, owner_type, owner_category, features
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "11111111-1111-1111-1111-111111111111",
            "SingleTimeSeries",
            "Component",
            "2024-01-01 00:00:00",
            "300000",
            None,
            None,
            None,
            24,
            "max_active_power",
            "22222222-2222-2222-2222-222222222222",
            "PowerLoad",
            None,
            "[]",
        ),
    )
    con.commit()

    changed = migrate_metadata(con)
    assert changed

    table_names = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "infrasys_metadata" in table_names
    assert "time_series_associations" in table_names

    columns = [row[1] for row in con.execute("PRAGMA table_info(time_series_associations)").fetchall()]
    assert "resolution" in columns
    assert "metadata_uuid" in columns
    assert "resolution_ms" not in columns

    row = con.execute(
        "SELECT initial_timestamp, resolution, owner_category, metadata_uuid FROM time_series_associations"
    ).fetchone()
    assert row is not None
    assert row[0] == "2024-01-01T00:00:00"
    assert row[1] == "P0DT300.000S"
    assert row[2] == "Component"
    assert row[3]


def test_migrate_metadata_noop_when_schema_is_current():
    con = sqlite3.connect(":memory:")
    create_associations_table(con)

    changed = migrate_metadata(con)
    assert changed is False


def test_repair_deterministic_metadata_periods_normalizes_export_type():
    con = sqlite3.connect(":memory:")
    create_associations_table(con)
    con.execute(
        """
        INSERT INTO time_series_associations (
            time_series_uuid, time_series_type, initial_timestamp, resolution,
            horizon, interval, window_count, length, name, owner_uuid, owner_type,
            owner_category, features, metadata_uuid
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "11111111-1111-1111-1111-111111111111",
            "DeterministicSingleTimeSeries",
            "2024-01-01T00:00:00",
            "P0DT3600.000S",
            None,
            None,
            365,
            8760,
            "inflow",
            "22222222-2222-2222-2222-222222222222",
            "HydroReservoir",
            "Component",
            "[]",
            "33333333-3333-3333-3333-333333333333",
        ),
    )

    updated = _repair_deterministic_metadata_periods(con)

    assert updated == 1
    assert con.execute(
        "SELECT time_series_type, horizon, interval FROM time_series_associations"
    ).fetchone() == (
        "DeterministicSingleTimeSeries",
        "P0DT3600.000S",
        "P0DT3600.000S",
    )


def test_reconcile_metadata_uuid_references_backfills_orphan_metadata_rows():
    con = sqlite3.connect(":memory:")
    cur = con.cursor()
    create_associations_table(con)
    cur.execute(
        """
        CREATE TABLE time_series_metadata(
            id INTEGER PRIMARY KEY,
            metadata_uuid TEXT NOT NULL,
            metadata BLOB NOT NULL
        )
        """
    )

    cur.execute(
        "INSERT INTO time_series_metadata (metadata_uuid, metadata) VALUES (?, ?)",
        ("valid-meta-uuid-0000-0000-000000000001", b"blob"),
    )

    row = {
        "time_series_uuid": "11111111-1111-1111-1111-111111111111",
        "time_series_type": "SingleTimeSeries",
        "initial_timestamp": "2024-01-01T00:00:00",
        "resolution": "P0DT300.000S",
        "horizon": None,
        "interval": None,
        "window_count": None,
        "length": 24,
        "name": "max_active_power",
        "owner_uuid": "22222222-2222-2222-2222-222222222222",
        "owner_type": "PowerLoad",
        "owner_category": "Component",
        "features": "[]",
        "scaling_factor_multiplier": None,
        "units": None,
    }
    cur.execute(
        """
        INSERT INTO time_series_associations (
            time_series_uuid, time_series_type, initial_timestamp, resolution, horizon, interval,
            window_count, length, name, owner_uuid, owner_type, owner_category, features,
            scaling_factor_multiplier, metadata_uuid, units
        ) VALUES (
            :time_series_uuid, :time_series_type, :initial_timestamp, :resolution, :horizon, :interval,
            :window_count, :length, :name, :owner_uuid, :owner_type, :owner_category, :features,
            :scaling_factor_multiplier, :metadata_uuid, :units
        )
        """,
        {**row, "metadata_uuid": "valid-meta-uuid-0000-0000-000000000001"},
    )
    cur.execute(
        """
        INSERT INTO time_series_associations (
            time_series_uuid, time_series_type, initial_timestamp, resolution, horizon, interval,
            window_count, length, name, owner_uuid, owner_type, owner_category, features,
            scaling_factor_multiplier, metadata_uuid, units
        ) VALUES (
            :time_series_uuid, :time_series_type, :initial_timestamp, :resolution, :horizon, :interval,
            :window_count, :length, :name, :owner_uuid, :owner_type, :owner_category, :features,
            :scaling_factor_multiplier, :metadata_uuid, :units
        )
        """,
        {
            **row,
            "owner_uuid": "33333333-3333-3333-3333-333333333333",
            "metadata_uuid": "orphan-meta-uuid-0000-0000-000000000002",
        },
    )
    con.commit()

    inserted = _reconcile_metadata_uuid_references(con)
    assert inserted == 1

    remaining = con.execute(
        "SELECT metadata_uuid FROM time_series_associations ORDER BY metadata_uuid"
    ).fetchall()
    assert remaining == [
        ("orphan-meta-uuid-0000-0000-000000000002",),
        ("valid-meta-uuid-0000-0000-000000000001",),
    ]

    backfilled = con.execute(
        "SELECT metadata_uuid, metadata FROM time_series_metadata ORDER BY metadata_uuid"
    ).fetchall()
    assert [row[0] for row in backfilled] == [
        "orphan-meta-uuid-0000-0000-000000000002",
        "valid-meta-uuid-0000-0000-000000000001",
    ]

    orphan_payload = json.loads(backfilled[0][1].decode("utf-8"))
    assert "__metadata__" in orphan_payload
    assert orphan_payload["__metadata__"]["module"] == "InfrastructureSystems"
    assert orphan_payload["__metadata__"]["type"] == "SingleTimeSeriesMetadata"
