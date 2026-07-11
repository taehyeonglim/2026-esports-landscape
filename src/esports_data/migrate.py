"""Ordered, checksum-verified SQLite schema migrations."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import sqlite3

from .db import DatabaseError, immediate_transaction


class MigrationError(DatabaseError):
    """Raised when migration history or a migration application is unsafe."""


class _DryMigrationComplete(Exception):
    """Internal rollback sentinel carrying an otherwise successful dry run."""

    def __init__(self, versions: tuple[int, ...]) -> None:
        self.versions = versions


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    checksum: str
    sql: str


def default_migrations_path() -> Path:
    """Return the repository migration directory for the installed source tree."""

    return Path(__file__).resolve().parents[2] / "migrations"


def discover_migrations(directory: str | Path | None = None) -> tuple[Migration, ...]:
    """Load consecutively numbered ``NNNN_name.sql`` migrations."""

    root = Path(directory) if directory is not None else default_migrations_path()
    migrations: list[Migration] = []
    for path in sorted(root.glob("[0-9][0-9][0-9][0-9]_*.sql")):
        prefix, _, name = path.stem.partition("_")
        sql = path.read_text(encoding="utf-8")
        migrations.append(
            Migration(int(prefix), name, hashlib.blake2b(sql.encode(), digest_size=32).hexdigest(), sql)
        )
    if not migrations:
        raise MigrationError(f"no migrations found in {root}")
    versions = [migration.version for migration in migrations]
    if versions != list(range(1, len(versions) + 1)):
        raise MigrationError("migration versions must be unique and consecutive from 0001")
    return tuple(migrations)


def _execute_sql(connection: sqlite3.Connection, script: str) -> None:
    """Execute a script statement-by-statement without executescript's implicit commit."""

    statement = ""
    for line in script.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            if statement.strip():
                connection.execute(statement)
            statement = ""
    if statement.strip():
        raise MigrationError("migration ends with an incomplete SQL statement")


def _ensure_history(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migration (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        ) STRICT
        """
    )


def schema_versions(connection: sqlite3.Connection) -> tuple[int, ...]:
    """Return applied migration versions after verifying the history table exists."""

    if connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migration'"
    ).fetchone() is None:
        raise MigrationError("schema migration history is missing")
    return tuple(row[0] for row in connection.execute("SELECT version FROM schema_migration ORDER BY version"))


def migrate(
    connection: sqlite3.Connection,
    directory: str | Path | None = None,
    *,
    dry_run: bool = False,
) -> tuple[int, ...]:
    """Apply migrations atomically, or validate them without persistent writes."""
    migrations = discover_migrations(directory)
    try:
        with immediate_transaction(connection):
            _ensure_history(connection)
            applied = {
                row[0]: (row[1], row[2])
                for row in connection.execute(
                    "SELECT version, name, checksum FROM schema_migration"
                )
            }
            known = {migration.version for migration in migrations}
            unknown = set(applied) - known
            if unknown:
                raise MigrationError(f"database has unknown migrations: {sorted(unknown)}")
            for migration in migrations:
                prior = applied.get(migration.version)
                if prior is not None:
                    if prior != (migration.name, migration.checksum):
                        raise MigrationError(
                            f"checksum mismatch for migration {migration.version:04d}"
                        )
                    continue
                if any(version > migration.version for version in applied):
                    raise MigrationError("migration history is not sequential")
                _execute_sql(connection, migration.sql)
                connection.execute(
                    "INSERT INTO schema_migration(version, name, checksum) VALUES (?, ?, ?)",
                    (migration.version, migration.name, migration.checksum),
                )
                applied[migration.version] = (migration.name, migration.checksum)
            versions = tuple(sorted(applied))
            if dry_run:
                raise _DryMigrationComplete(versions)
            return versions
    except _DryMigrationComplete as complete:
        return complete.versions
    except sqlite3.Error as error:
        raise MigrationError("migration failed") from error
