import sqlite3

from infrasys.time_series_metadata_store import create_associations_table

from r2x_sienna.upgrader.data_upgrader import migrate_metadata


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
