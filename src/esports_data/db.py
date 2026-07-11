"""SQLite control-plane connection and durability helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3
from typing import Literal
from .identity import IdentityError, authority_subject_uuid


class _ReviewTransitionGate:
    """One-shot, connection-local authorization for review status triggers."""

    def __init__(self) -> None:
        self.token: tuple[str, str, int, str] | None = None

    def authorize(
        self, candidate_id: str, target_id: str, expected_version: int, status: str
    ) -> None:
        if self.token is not None:
            raise DatabaseError("a review transition authorization is already pending")
        self.token = (candidate_id, target_id, expected_version, status)

    def consume(
        self,
        candidate_id: str,
        target_id: str,
        old_status: object,
        status: str,
        version: int,
    ) -> int:
        token = self.token
        self.token = None
        if token is None or token != (candidate_id, target_id, version, status):
            return 0
        if target_id == "__review_aggregate__":
            return int(old_status == version and status == "increment")
        return int(old_status == "active")

    def clear(self) -> None:
        self.token = None


_review_transition_gates: dict[int, _ReviewTransitionGate] = {}


def _authority_subject_uuid_sql(
    kind: object, namespace: object, key: object
) -> str | None:
    """SQLite wrapper: invalid authority tuples fail closed as SQL NULL."""

    if not isinstance(kind, str) or not isinstance(namespace, str) or not isinstance(key, str):
        return None
    try:
        return str(authority_subject_uuid(kind, namespace, key))
    except IdentityError:
        return None


def authorize_review_transition(
    connection: sqlite3.Connection,
    candidate_id: str,
    target_id: str,
    expected_version: int,
    status: str,
) -> None:
    """Authorize exactly one adapter-owned review status transition."""

    if not connection.in_transaction:
        raise DatabaseError("review transition authorization requires an active transaction")
    _review_transition_gates[id(connection)].authorize(
        candidate_id, target_id, expected_version, status
    )


def clear_review_transition_authorization(connection: sqlite3.Connection) -> None:
    """Discard an unused review transition authorization after a failed statement."""

    _review_transition_gates[id(connection)].clear()


class DatabaseError(RuntimeError):
    """Raised when a database safety invariant cannot be established."""


def connect(path: str | Path, *, readonly: bool = False) -> sqlite3.Connection:
    """Open a SQLite database with foreign keys and WAL enabled for writers."""

    database = Path(path)
    if readonly:
        connection = sqlite3.connect(
            f"file:{database.resolve()}?mode=ro", uri=True, isolation_level=None
        )
    else:
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database, isolation_level=None)
    connection.row_factory = sqlite3.Row
    gate = _ReviewTransitionGate()
    _review_transition_gates[id(connection)] = gate
    connection.create_function(
        "authority_subject_uuid", 3, _authority_subject_uuid_sql, deterministic=True
    )
    connection.create_function(
        "review_transition_authorized", 5, gate.consume, deterministic=False
    )
    connection.execute("PRAGMA foreign_keys = ON")
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        connection.close()
        raise DatabaseError("SQLite foreign-key enforcement is unavailable")
    connection.execute("PRAGMA busy_timeout = 5000")
    if not readonly:
        mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        if mode.lower() != "wal":
            connection.close()
            raise DatabaseError("SQLite WAL mode could not be enabled")
        connection.execute("PRAGMA synchronous = FULL")
    return connection


@contextmanager
def immediate_transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run a transaction that acquires the writer lock before any mutation."""

    if connection.in_transaction:
        raise DatabaseError("immediate_transaction requires no active transaction")
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except BaseException:
        connection.rollback()
        raise
    else:
        try:
            connection.commit()
        except BaseException:
            connection.rollback()
            raise


def checkpoint(connection: sqlite3.Connection, *, mode: Literal["PASSIVE", "FULL", "RESTART", "TRUNCATE"] = "FULL") -> tuple[int, int, int]:
    """Checkpoint WAL and fail if SQLite reports busy frames."""

    busy, log_frames, checkpointed = connection.execute(
        f"PRAGMA wal_checkpoint({mode})"
    ).fetchone()
    if busy:
        raise DatabaseError("WAL checkpoint left busy frames")
    return busy, log_frames, checkpointed


def backup(connection: sqlite3.Connection, destination: str | Path) -> None:
    """Create a consistent, WAL-free SQLite backup at *destination*."""

    if connection.in_transaction:
        raise DatabaseError("cannot back up while the source transaction is active")
    checkpoint(connection, mode="TRUNCATE")
    target_path = Path(destination)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(target_path)) as target:
        connection.backup(target)
        target.execute("PRAGMA journal_mode = DELETE")
        target.commit()
    with closing(sqlite3.connect(target_path)) as target:
        mode = target.execute("PRAGMA journal_mode").fetchone()[0]
    if mode.lower() != "delete":
        raise DatabaseError("backup retains WAL journal mode")


def integrity_check(connection: sqlite3.Connection) -> None:
    """Raise when SQLite's full integrity check reports any defect."""

    rows = tuple(row[0] for row in connection.execute("PRAGMA integrity_check"))
    if rows != ("ok",):
        raise DatabaseError(f"integrity check failed: {rows!r}")


def foreign_key_check(connection: sqlite3.Connection) -> None:
    """Raise when SQLite detects any foreign-key violation."""

    violations = tuple(connection.execute("PRAGMA foreign_key_check"))
    if violations:
        raise DatabaseError(f"foreign-key check failed: {violations!r}")
