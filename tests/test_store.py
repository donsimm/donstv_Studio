"""F-03: Speicher, Migration, Sicherung."""

import sqlite3
from datetime import date, timedelta

import pytest

from donstv_studio.core.store import MIGRATIONS, Store

LATEST = MIGRATIONS[-1][0]


def test_f03_wal_and_settings(tmp_path):
    s = Store(tmp_path / "a.db")
    assert s._db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    s.set_setting("k", "v")
    s.set_setting("k", "w")
    assert s.get_setting("k") == "w"
    assert s.get_setting("fehlt", "d") == "d"
    s.close()


def test_f03_migration_from_old_version(tmp_path):
    path = tmp_path / "a.db"
    s = Store(path, migrations=MIGRATIONS[:1])
    s.set_setting("k", "v")
    s.close()
    nxt = LATEST + 1
    more = [*MIGRATIONS, (nxt, "CREATE TABLE extra (id INTEGER PRIMARY KEY)")]
    s2 = Store(path, migrations=more)
    assert s2.schema_version == nxt
    assert s2.get_setting("k") == "v"
    s2.close()


def test_f03_failed_migration_rolls_back(tmp_path):
    path = tmp_path / "a.db"
    Store(path).close()
    bad = [*MIGRATIONS, (LATEST + 1, "CREATE TABLE t (id INTEGER); INSERT INTO gibtsnicht VALUES (1)")]
    with pytest.raises(sqlite3.OperationalError):
        Store(path, migrations=bad)
    s = Store(path)
    assert s.schema_version == LATEST
    s.close()


def test_f03_newer_schema_refused(tmp_path):
    path = tmp_path / "a.db"
    Store(path, migrations=[*MIGRATIONS, (LATEST + 1, "CREATE TABLE t (id INTEGER)")]).close()
    with pytest.raises(RuntimeError):
        Store(path)


def test_f03_backup_daily_keep_seven(tmp_path):
    s = Store(tmp_path / "a.db")
    s.set_setting("k", "v")
    bdir = tmp_path / "b"
    day = date(2026, 1, 1)
    first = s.backup_if_due(bdir, day)
    assert first is not None
    assert s.backup_if_due(bdir, day) is None  # nur einmal pro Tag
    for i in range(1, 10):
        s.backup_if_due(bdir, day + timedelta(days=i))
    files = sorted(p.name for p in bdir.glob("donstv-*.db"))
    assert len(files) == 7
    assert files[-1] == "donstv-2026-01-10.db"
    restored = Store(bdir / files[-1])
    assert restored.get_setting("k") == "v"
    restored.close()
    s.close()
