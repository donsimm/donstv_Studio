"""Speicher: SQLite mit WAL, Schema-Versionen, Migrationen und tägliche Sicherung."""

from __future__ import annotations

import contextlib
import logging
import sqlite3
import threading
from collections.abc import Iterator
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
    (
        # F-10, F-11, F-12, F-66: Overlays und Quellen. Lage und Grösse als INTEGER (F-65).
        2,
        """
        CREATE TABLE overlays (
            id TEXT PRIMARY KEY NOT NULL,
            name TEXT NOT NULL,
            width INTEGER NOT NULL CHECK (width >= 1),
            height INTEGER NOT NULL CHECK (height >= 1),
            output TEXT NOT NULL,
            token TEXT NOT NULL UNIQUE
        );
        CREATE TABLE sources (
            id TEXT PRIMARY KEY NOT NULL,
            overlay_id TEXT NOT NULL REFERENCES overlays(id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            width INTEGER NOT NULL CHECK (width >= 1),
            height INTEGER NOT NULL CHECK (height >= 1),
            rotation REAL NOT NULL,
            z INTEGER NOT NULL,
            visible INTEGER NOT NULL CHECK (visible IN (0, 1)),
            props TEXT NOT NULL
        );
        CREATE INDEX sources_overlay ON sources(overlay_id, z)
        """,
    ),
    (
        # F-16: Bibliothek für Bilder (Dateien liegen im Ordner «media», hier nur die Angaben).
        3,
        """
        CREATE TABLE media (
            id TEXT PRIMARY KEY NOT NULL,
            name TEXT NOT NULL,
            mime TEXT NOT NULL,
            ext TEXT NOT NULL,
            size INTEGER NOT NULL CHECK (size >= 1),
            created_at REAL NOT NULL
        )
        """,
    ),
    (
        # F-15: Stilschlüssel wie im Original; «comic_thick» heisst jetzt «thick».
        4,
        """
        UPDATE sources SET props = json_set(props, '$.style', 'thick')
        WHERE kind = 'text' AND json_extract(props, '$.style') = 'comic_thick'
        """,
    ),
    (
        # F-43, F-44: Commands des Chat-Bots. Cooldowns in ganzen Sekunden.
        # F-45: Protokoll der Bot-Aktivität (die ältesten Einträge werden gelöscht, siehe bot/log.py).
        5,
        """
        CREATE TABLE bot_commands (
            id TEXT PRIMARY KEY NOT NULL,
            name TEXT NOT NULL,
            trigger TEXT NOT NULL,
            permission TEXT NOT NULL
                CHECK (permission IN ('everyone', 'subscriber', 'moderator', 'broadcaster')),
            cooldown_global INTEGER NOT NULL CHECK (cooldown_global >= 0),
            cooldown_user INTEGER NOT NULL CHECK (cooldown_user >= 0),
            response TEXT NOT NULL,
            enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
            position INTEGER NOT NULL
        );
        CREATE TABLE bot_log (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            kind TEXT NOT NULL,
            message TEXT NOT NULL,
            data TEXT NOT NULL
        )
        """,
    ),
    (
        # F-74: Name einer Quelle (nur Bezeichnung). Bestehende Quellen bekommen den Namen, den die Liste bisher
        # automatisch zeigte (overlays/models.py: default_source_name): «Text: <erste Zeile, 30 Zeichen>…»,
        # «Bild: <Dateiname>», sonst «Text» oder «Bild». Erste Zeile: nach dem Entfernen von Leerraum am Anfang
        # und Ende bis zum ersten Zeilenwechsel.
        6,
        """
        ALTER TABLE sources ADD COLUMN name TEXT NOT NULL DEFAULT '';
        UPDATE sources SET name = 'Text: ' || rtrim(substr(
                trim(coalesce(json_extract(props, '$.text'), ''), char(32, 9, 10, 13, 11, 12)), 1,
                instr(trim(coalesce(json_extract(props, '$.text'), ''), char(32, 9, 10, 13, 11, 12))
                      || char(10), char(10)) - 1), char(13))
        WHERE kind = 'text';
        UPDATE sources SET name = substr(name, 1, 36) || CASE WHEN length(name) > 36 THEN '…' ELSE '' END
        WHERE kind = 'text';
        UPDATE sources SET name = 'Text' WHERE kind = 'text' AND name = 'Text: ';
        UPDATE sources SET name = coalesce((SELECT 'Bild: ' || m.name FROM media m
                                            WHERE m.id = json_extract(sources.props, '$.media_id')
                                              AND m.name <> ''), 'Bild')
        WHERE kind = 'image'
        """,
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
        self._db.execute("PRAGMA foreign_keys=ON")
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

    # --- Allgemeiner Zugriff für Bausteine (Overlays usw.) ---------------
    @contextlib.contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Eine Transaktion; bei Fehler Rollback."""
        with self._lock:
            self._db.execute("BEGIN")
            try:
                yield self._db
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            else:
                self._db.execute("COMMIT")

    def query(self, sql: str, params: tuple = ()) -> list[tuple]:
        with self._lock:
            return self._db.execute(sql, params).fetchall()

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
