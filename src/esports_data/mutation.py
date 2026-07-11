"""Idempotent control-plane mutation execution."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import closing
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from .db import DatabaseError, backup, connect, immediate_transaction
from .pii import scan_text


class MutationError(DatabaseError):
    """Raised when a command cannot be safely queued or applied."""


class PiiPersistenceError(MutationError):
    """Raised before a command payload containing minor PII is persisted."""


class ArtifactIncompleteError(MutationError):
    """Raised when an applied command has no usable checkpoint artifact yet."""

    def __init__(self, receipt: MutationReceipt, cause: Exception):
        super().__init__("command was applied but checkpoint artifact creation failed")
        self.receipt = receipt
        self.__cause__ = cause


@dataclass(frozen=True, slots=True)
class MutationCommand:
    command_id: str
    request_kind: str
    input_revision: str
    policy_version: str
    policy_epoch: int
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class MutationReceipt:
    """A database-terminal fact, deliberately independent of filesystem artifacts."""

    command_id: str
    status: str
    applied_at: str

    def payload(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CheckpointArtifact:
    """Evidence for a WAL-free backup that callers may bind into an external receipt."""

    path: str
    sqlite_file_sha256: str
    integrity_check: tuple[str, ...]
    foreign_key_check: tuple[tuple[Any, ...], ...]

    def payload(self) -> dict[str, object]:
        return {
            "path": self.path,
            "sqlite_file_sha256": self.sqlite_file_sha256,
            "integrity_check": list(self.integrity_check),
            "foreign_key_check": [list(row) for row in self.foreign_key_check],
        }


@dataclass(frozen=True, slots=True)
class MutationResult:
    receipt: MutationReceipt
    checkpoint_artifact: CheckpointArtifact


MutationHandler = Callable[[sqlite3.Connection, Mapping[str, Any]], None]


def _canonical_payload(payload: Mapping[str, Any]) -> str:
    try:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as error:
        raise MutationError("payload must be JSON serializable") from error


def _reject_pii(value: Any) -> None:
    if isinstance(value, str):
        if not scan_text(value).is_clean:
            raise PiiPersistenceError("command payload contains disallowed minor PII")
    elif isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise MutationError("payload object keys must be strings")
            _reject_pii(key)
            _reject_pii(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_pii(child)
    elif value is not None and not isinstance(value, (bool, int, float)):
        raise MutationError("payload contains an unsupported JSON value")


def _state(connection: sqlite3.Connection, key: str) -> str:
    row = connection.execute("SELECT value FROM system_state WHERE key = ?", (key,)).fetchone()
    if row is None:
        raise MutationError(f"required system state is missing: {key}")
    return str(row[0])


def _receipt(
    command_id: str, receipt_json: str | None, applied_at: str | None
) -> MutationReceipt:
    try:
        receipt = MutationReceipt(**json.loads(receipt_json or "null"))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise MutationError("applied command has an invalid receipt") from error
    if (
        receipt.command_id != command_id
        or receipt.status != "applied"
        or receipt.applied_at != applied_at
    ):
        raise MutationError("applied command receipt does not match its terminal state")
    return receipt
def _validate_parent_git_sha(parent_git_sha: str) -> None:
    if not isinstance(parent_git_sha, str) or re.fullmatch(r"[0-9a-f]{40}", parent_git_sha) is None:
        raise MutationError("parent_git_sha must be 40 lowercase hexadecimal characters")


def _quoted_identifier(identifier: str) -> str:
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


def _logical_database_state(connection: sqlite3.Connection) -> tuple[object, ...]:
    """Return a deterministic logical schema-and-data representation."""
    schema = tuple(
        tuple(row)
        for row in connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY type, name, tbl_name"
        )
    )
    tables = tuple(
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type = 'table' ORDER BY name"
        )
    )
    data = []
    for table in tables:
        columns = tuple(
            str(row[1]) for row in connection.execute(f"PRAGMA table_xinfo({_quoted_identifier(table)})")
        )
        order_by = ", ".join(_quoted_identifier(column) for column in columns)
        rows = tuple(
            tuple(row)
            for row in connection.execute(
                f"SELECT * FROM {_quoted_identifier(table)} ORDER BY {order_by}"
            )
        )
        data.append((table, rows))
    return schema, tuple(data)




def _checkpoint_artifact(
    connection: sqlite3.Connection,
    destination: str | Path,
    *,
    reuse_existing: bool = False,
    receipt: MutationReceipt | None = None,
) -> CheckpointArtifact:
    """Back up after commit, or verify a duplicate-command checkpoint against live state."""
    path = Path(destination)
    if reuse_existing:
        if not path.is_file():
            raise MutationError("applied command checkpoint artifact is missing")
    else:
        backup(connection, path)
    with closing(connect(path, readonly=True)) as artifact_connection:
        integrity = tuple(str(row[0]) for row in artifact_connection.execute("PRAGMA integrity_check"))
        foreign_keys = tuple(tuple(row) for row in artifact_connection.execute("PRAGMA foreign_key_check"))
        journal_mode = str(artifact_connection.execute("PRAGMA journal_mode").fetchone()[0])
        if integrity != ("ok",):
            raise MutationError(f"checkpoint integrity check failed: {integrity!r}")
        if foreign_keys:
            raise MutationError(f"checkpoint foreign-key check failed: {foreign_keys!r}")
        if journal_mode.lower() != "delete":
            raise MutationError("checkpoint artifact retains WAL journal mode")
        if reuse_existing:
            if receipt is None:
                raise MutationError("duplicate checkpoint verification requires a receipt")
            if _logical_database_state(connection) != _logical_database_state(artifact_connection):
                raise MutationError(
                    "checkpoint artifact does not exactly match the live database logical state"
                )
    digest = sha256()
    with path.open("rb") as artifact_file:
        for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return CheckpointArtifact(str(path), digest.hexdigest(), integrity, foreign_keys)

def _live_database_is_valid(connection: sqlite3.Connection) -> None:
    integrity = tuple(str(row[0]) for row in connection.execute("PRAGMA integrity_check"))
    foreign_keys = tuple(tuple(row) for row in connection.execute("PRAGMA foreign_key_check"))
    if integrity != ("ok",):
        raise MutationError(f"live database integrity check failed: {integrity!r}")
    if foreign_keys:
        raise MutationError(f"live database foreign-key check failed: {foreign_keys!r}")


def _is_latest_applied_command(connection: sqlite3.Connection, command_id: str) -> bool:
    row = connection.execute(
        """SELECT command_id
           FROM mutation_request
           WHERE status = 'applied'
           ORDER BY applied_sequence DESC
           LIMIT 1"""
    ).fetchone()
    if row is None or row[0] != command_id:
        return False
    return True


def _recover_missing_checkpoint(
    connection: sqlite3.Connection,
    receipt: MutationReceipt,
    backup_path: str | Path,
) -> CheckpointArtifact:
    path = Path(backup_path)
    if path.exists():
        raise MutationError("applied command checkpoint artifact is invalid")
    if not _is_latest_applied_command(connection, receipt.command_id):
        raise MutationError("only the latest applied command checkpoint may be recovered")
    _live_database_is_valid(connection)
    return _checkpoint_artifact(connection, path, reuse_existing=False, receipt=receipt)



def _artifact_result(
    connection: sqlite3.Connection,
    receipt: MutationReceipt,
    backup_path: str | Path,
    *,
    reuse_existing: bool = False,
) -> MutationResult:
    try:
        artifact = _checkpoint_artifact(
            connection, backup_path, reuse_existing=reuse_existing, receipt=receipt
        )
    except Exception as error:
        if reuse_existing:
            try:
                artifact = _recover_missing_checkpoint(connection, receipt, backup_path)
            except Exception as recovery_error:
                raise ArtifactIncompleteError(receipt, recovery_error) from recovery_error
        else:
            raise ArtifactIncompleteError(receipt, error) from error
    return MutationResult(receipt, artifact)


def queue(connection: sqlite3.Connection, command: MutationCommand) -> str:
    """Persist a PII-screened command once, returning its current status idempotently."""

    if not command.command_id or command.policy_epoch < 0:
        raise MutationError("command_id must be non-empty and policy_epoch non-negative")
    _reject_pii(command.payload)
    payload_json = _canonical_payload(command.payload)
    with immediate_transaction(connection):
        existing = connection.execute(
            "SELECT request_kind, input_revision, policy_version, policy_epoch, payload_json, status "
            "FROM mutation_request WHERE command_id = ?",
            (command.command_id,),
        ).fetchone()
        identity = (
            command.request_kind,
            command.input_revision,
            command.policy_version,
            command.policy_epoch,
            payload_json,
        )
        if existing is not None:
            if tuple(existing[:5]) != identity:
                raise MutationError("command_id was reused with different content")
            return str(existing[5])
        connection.execute(
            """INSERT INTO mutation_request
               (command_id, request_kind, input_revision, policy_version, policy_epoch, status, payload_json)
               VALUES (?, ?, ?, ?, ?, 'queued', ?)""",
            (command.command_id, *identity[:4], payload_json),
        )
    return "queued"


def _terminalize_handler_failure(
    connection: sqlite3.Connection, command_id: str, parent_git_sha: str
) -> None:
    """Record handler failure and its first-apply parent after rollback to queued."""
    with immediate_transaction(connection):
        updated = connection.execute(
            "UPDATE mutation_request SET status = 'failed', error_code = 'handler_failed', "
            "parent_git_sha = ? WHERE command_id = ? AND status = 'queued' AND parent_git_sha IS NULL",
            (parent_git_sha, command_id),
        )
        if updated.rowcount != 1:
            raise MutationError("command could not be terminalized after handler failure")


def apply(
    connection: sqlite3.Connection,
    command: MutationCommand,
    handler: MutationHandler,
    *,
    parent_git_sha: str,
    backup_path: str | Path,
) -> MutationResult:
    """Apply once atomically, then produce separately attestable backup evidence."""

    _validate_parent_git_sha(parent_git_sha)
    queue(connection, command)
    handler_started = False
    receipt: MutationReceipt | None = None
    replayed = False
    try:
        with immediate_transaction(connection):
            row = connection.execute(
                "SELECT status, receipt_json, applied_at, error_code, parent_git_sha "
                "FROM mutation_request WHERE command_id = ?",
                (command.command_id,),
            ).fetchone()
            if row is None:
                raise MutationError("queued command disappeared")
            if row[0] in ("applied", "failed") and row[4] != parent_git_sha:
                raise MutationError("command parent_git_sha does not match its terminal identity")
            if row[0] == "applied":
                receipt = _receipt(command.command_id, row[1], row[2])
                replayed = True
            elif row[0] == "failed":
                raise MutationError(f"command previously failed: {row[3] or 'unknown'}")
            elif row[0] != "queued":
                raise MutationError(f"command is not applicable from status {row[0]!r}")
            elif row[4] is not None:
                raise MutationError("queued command already has a bound parent_git_sha")
            else:
                if _state(connection, "input_revision") != command.input_revision:
                    raise MutationError("input revision does not match system state")
                if _state(connection, "policy_version") != command.policy_version:
                    raise MutationError("policy version does not match system state")
                if _state(connection, "policy_epoch") != str(command.policy_epoch):
                    raise MutationError("policy epoch does not match system state")
                updated = connection.execute(
                    "UPDATE mutation_request SET status = 'running', parent_git_sha = ?, "
                    "started_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
                    "WHERE command_id = ? AND status = 'queued' AND parent_git_sha IS NULL",
                    (parent_git_sha, command.command_id),
                )
                if updated.rowcount != 1:
                    raise MutationError("command could not bind parent_git_sha for first apply")
                handler_started = True
                handler(connection, command.payload)
                connection.execute(
                    "INSERT INTO system_state(key, value) VALUES ('parent_git_sha', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                    "updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')",
                    (parent_git_sha,),
                )
                applied_at = connection.execute(
                    "SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
                ).fetchone()[0]
                receipt = MutationReceipt(command.command_id, "applied", applied_at)
                updated = connection.execute(
                    "UPDATE mutation_request SET status = 'applied', applied_at = ?, "
                    "applied_sequence = (SELECT COALESCE(MAX(applied_sequence), 0) + 1 FROM mutation_request), "
                    "receipt_json = ? WHERE command_id = ? AND status = 'running'",
                    (applied_at, json.dumps(receipt.payload(), sort_keys=True), command.command_id),
                )
                if updated.rowcount != 1:
                    raise MutationError("command terminal state changed during execution")
    except Exception:
        if handler_started:
            _terminalize_handler_failure(connection, command.command_id, parent_git_sha)
        raise
    if receipt is None:
        raise MutationError("command did not produce an applied receipt")
    return _artifact_result(connection, receipt, backup_path, reuse_existing=replayed)
