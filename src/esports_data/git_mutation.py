"""Fail-closed promotion of paired SQLite mutation artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import sqlite3
import subprocess
import tempfile
from typing import Sequence

from .db import foreign_key_check, integrity_check
from .pii import scan_text


class PromotionError(ValueError):
    """Raised when a candidate cannot safely advance a protected ref."""


@dataclass(frozen=True, slots=True)
class PromotionResult:
    outcome: str
    candidate_sha: str
    target_sha: str


def _git(arguments: Sequence[str], *, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *arguments], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="strict",
    )
    if check and completed.returncode:
        raise PromotionError("git operation rejected")
    return completed.stdout.strip()


def _safe_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
        raise PromotionError("artifact path is invalid")
    return str(path)


def _branch_ref(value: str) -> bool:
    return (
        value.startswith("refs/heads/") and not value.endswith("/") and ".." not in value
        and all(ord(character) > 32 and character not in {"~", "^", ":", "?", "*", "[", "\\"}
                for character in value)
    )


def _remote_sha(remote: str, target_ref: str) -> str:
    if not _branch_ref(target_ref):
        raise PromotionError("target ref is invalid")
    output = _git(["ls-remote", "--refs", remote, target_ref])
    fields = output.split()
    if len(fields) != 2 or fields[1] != target_ref or len(fields[0]) != 40:
        raise PromotionError("target ref is unavailable")
    return fields[0]


def _candidate_sha(candidate_ref: str, remote: str) -> str:
    if not _branch_ref(candidate_ref):
        raise PromotionError("candidate ref is invalid")
    # Fetching only Git objects is safe; candidate worktree code is never checked out or run.
    _git(["fetch", "--no-tags", remote, f"{candidate_ref}:refs/gjc/mutation-candidate"])
    candidate = _git(["rev-parse", "refs/gjc/mutation-candidate^{commit}"])
    if len(candidate) != 40:
        raise PromotionError("candidate commit is invalid")
    return candidate


def _blob(candidate: str, path: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{candidate}:{path}"], check=False, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        raise PromotionError("candidate artifact is missing")
    return completed.stdout


def _validate_receipt(receipt_bytes: bytes, *, parent: str, command_id: str, database_path: str,
                      database_bytes: bytes, report_path: str | None) -> dict[str, object]:
    try:
        receipt = json.loads(receipt_bytes)
        from jsonschema import Draft202012Validator
        schema = json.loads((Path(__file__).resolve().parents[2] / "schemas" / "command-receipt-v1.schema.json").read_bytes())
        Draft202012Validator(schema).validate(receipt)
    except Exception as error:
        raise PromotionError("command receipt is invalid") from error
    if receipt["parent_git_sha"] != parent or receipt["command_id"] != command_id:
        raise PromotionError("command receipt does not bind the target and command")
    expected_hashes = {database_path: sha256(database_bytes).hexdigest()}
    if report_path is not None:
        expected_hashes[report_path] = None
    changed = receipt["changed_file_sha256"]
    if set(changed) != set(expected_hashes) or any(path == "" for path in changed):
        raise PromotionError("receipt changed-file allowlist is invalid")
    if changed[database_path] != receipt["sqlite_file_sha256"] or changed[database_path] != expected_hashes[database_path]:
        raise PromotionError("database digest does not match receipt")
    return receipt


def _validate_database(
    database_bytes: bytes, *, parent: str, command_id: str, external_receipt: dict[str, object]
) -> None:
    with tempfile.NamedTemporaryFile(suffix=".sqlite") as temporary:
        temporary.write(database_bytes)
        temporary.flush()
        connection = sqlite3.connect(f"file:{temporary.name}?mode=ro", uri=True)
        try:
            integrity_check(connection)
            foreign_key_check(connection)
            row = connection.execute(
                "SELECT status, receipt_json, applied_at, parent_git_sha "
                "FROM mutation_request WHERE command_id = ?",
                (command_id,),
            ).fetchone()
        except sqlite3.Error as error:
            raise PromotionError("candidate database is invalid") from error
        finally:
            connection.close()
    if row is None or row[0] != "applied" or not row[1] or row[2] is None:
        raise PromotionError("candidate command is not applied")
    if row[3] != parent:
        raise PromotionError("candidate command parent does not match target")
    try:
        applied_receipt = json.loads(row[1])
    except (TypeError, json.JSONDecodeError) as error:
        raise PromotionError("candidate command receipt is invalid") from error
    if (
        applied_receipt.get("command_id") != command_id
        or applied_receipt.get("command_id") != external_receipt["command_id"]
        or applied_receipt.get("status") != row[0]
        or applied_receipt.get("status") != "applied"
        or applied_receipt.get("applied_at") != row[2]
    ):
        raise PromotionError("candidate command receipt does not match applied state")


def promote_mutation(*, candidate_ref: str, target_ref: str, database_path: str, receipt_path: str,
                     command_id: str, report_path: str | None = None, remote: str = "origin") -> PromotionResult:
    """Validate and atomically fast-forward a protected target to one candidate commit."""
    database_path = _safe_path(database_path)
    receipt_path = _safe_path(receipt_path)
    report_path = _safe_path(report_path) if report_path is not None else None
    artifact_paths = (database_path, receipt_path) + ((report_path,) if report_path is not None else ())
    if any(path.startswith(("src/", ".github/")) or path.endswith(".py") for path in artifact_paths):
        raise PromotionError("artifact paths cannot name source or workflow files")
    if len(set(artifact_paths)) != len(artifact_paths):
        raise PromotionError("artifact paths must be distinct")
    parent = _remote_sha(remote, target_ref)
    candidate = _candidate_sha(candidate_ref, remote)
    if candidate == parent:
        database_bytes = _blob(candidate, database_path)
        receipt_bytes = _blob(candidate, receipt_path)
        receipt = json.loads(receipt_bytes)
        receipt_parent = receipt.get("parent_git_sha")
        receipt = _validate_receipt(
            receipt_bytes,
            parent=receipt_parent,
            command_id=command_id,
            database_path=database_path,
            database_bytes=database_bytes,
            report_path=report_path,
        )
        if report_path is not None:
            report_bytes = _blob(candidate, report_path)
            if not scan_text(report_bytes.decode("utf-8")).is_clean:
                raise PromotionError("candidate report is not PII-free")
            if receipt["changed_file_sha256"][report_path] != sha256(report_bytes).hexdigest():
                raise PromotionError("report digest does not match receipt")
        _validate_database(database_bytes, parent=receipt_parent, command_id=command_id, external_receipt=receipt)
        if _git(["rev-parse", f"{candidate}^"]) != receipt_parent:
            raise PromotionError("promoted commit parent does not match receipt")
        changed = set(
            _git([
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                receipt_parent,
                candidate,
            ]).splitlines()
        )
        allowed = {database_path, receipt_path} | ({report_path} if report_path else set())
        if changed != allowed:
            raise PromotionError("promoted commit changes files outside the paired artifact allowlist")
        return PromotionResult("completed", candidate, parent)
    if _git(["rev-parse", f"{candidate}^"]) != parent:
        raise PromotionError("candidate is not a direct child of target")
    changed = set(_git(["diff-tree", "--no-commit-id", "--name-only", "-r", parent, candidate]).splitlines())
    allowed = {database_path, receipt_path} | ({report_path} if report_path else set())
    if changed != allowed:
        raise PromotionError("candidate changes files outside the paired artifact allowlist")
    database_bytes = _blob(candidate, database_path)
    receipt_bytes = _blob(candidate, receipt_path)
    receipt = _validate_receipt(receipt_bytes, parent=parent, command_id=command_id, database_path=database_path,
                                database_bytes=database_bytes, report_path=report_path)
    if report_path is not None:
        report_bytes = _blob(candidate, report_path)
        if scan_text(report_bytes.decode("utf-8")).is_clean is False:
            raise PromotionError("candidate report is not PII-free")
        receipt = json.loads(receipt_bytes)
        if receipt["changed_file_sha256"][report_path] != sha256(report_bytes).hexdigest():
            raise PromotionError("report digest does not match receipt")
    _validate_database(database_bytes, parent=parent, command_id=command_id, external_receipt=receipt)
    if _remote_sha(remote, target_ref) != parent:
        raise PromotionError("target advanced before promotion")
    _git(["push", remote, f"{candidate}:{target_ref}"], check=False)
    current = _remote_sha(remote, target_ref)
    if current == candidate:
        return PromotionResult("completed", candidate, current)
    if current == parent:
        raise PromotionError("promotion push is retryable")
    raise PromotionError("target advanced during promotion")
