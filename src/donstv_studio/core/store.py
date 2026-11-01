"""Speicher: SQLite mit WAL, Schema-Versionen, Migrationen und tägliche Sicherung."""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

# Migrationen: (Version, SQL). Spätere Bausteine hängen neue Einträge an;
# bestehende Einträge werden nie verändert.
MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        "CREATE TABLE settings (key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL)",
    ),
]

BACKUP_PREFIX = "donstv-"
BACKUP_KEEP = 7


class Store:
    def __init__(
        self,
        path: Path,
        migrations: list[tuple[int, str]] | None = None,
    ) -> None:
        self.path = Path(path)
        self._migrations = sorted(migrations if migrations is not None else MIGRATIONS)
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    # --- Schema ---------------------------------------------------------
    @property
    def schema_version(self) -> int:
        return self._db.execute("PRAGMA user_version").fetchone()[0]

    def _migrate(self) -> None:
        with self._lock:
            current = self.schema_version
            latest = self._migrations[-1][0] if self._migrations else 0
            if current > latest:
                raise RuntimeError(
                    f"Datenbank hat Schema {current}, diese Version kennt nur {latest}"
                )
            for version, sql in self._migrations:
                if version <= current:
                    continue
                # Jede Migration in einer eigenen Transaktion.
                self._db.execute("BEGIN")
                try:
                    for stmt in filter(None, (s.strip() for s in sql.split(";"))):
                        self._db.execute(stmt)
                    self._db.execute(f"PRAGMA user_version = {int(version)}")
                    self._db.execute("COMMIT")
                except Exception:
                    self._db.execute("ROLLBACK")
                    raise
                log.info("Datenbank auf Schema %d migriert", version)

    # --- Einstellungen --------------------------------------------------
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            row = self._db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def delete_setting(self, key: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM settings WHERE key = ?", (key,))

    def all_settings(self) -> dict[str, str]:
        with self._lock:
            return dict(self._db.execute("SELECT key, value FROM settings ORDER BY key"))

    def replace_settings(self, values: dict[str, str]) -> None:
        """Ersetzt alle Einstellungen in einer Transaktion."""
        with self._lock:
            self._db.execute("BEGIN")
            try:
                self._db.execute("DELETE FROM settings")
                self._db.executemany(
                    "INSERT INTO settings(key, value) VALUES(?, ?)", list(values.items())
                )
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    # --- Sicherung ------------------------------------------------------
    def backup_if_due(self, backup_dir: Path, today: date | None = None) -> Path | None:
        """Legt höchstens eine Sicherung pro Tag an und behält die letzten 7."""
        today = today or date.today()
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        target = backup_dir / f"{BACKUP_PREFIX}{today.isoformat()}.db"
        if target.exists():
            return None
        tmp = target.with_suffix(".db.tmp")
        with self._lock:
            dest = sqlite3.connect(tmp)
            try:
                self._db.backup(dest)
            finally:
                dest.close()
        tmp.replace(target)
        backups = sorted(backup_dir.glob(f"{BACKUP_PREFIX}*.db"))
        for old in backups[:-BACKUP_KEEP]:
            old.unlink()
        log.info("Sicherung angelegt: %s", target.name)
        return target

    def close(self) -> None:
        with self._lock:
            self._db.close()
