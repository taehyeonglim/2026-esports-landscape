"""Immutable local-filesystem snapshot publication."""

from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterator, Mapping

from .quality import GateReport, is_publishable_gate


class PublishError(RuntimeError):
    """A publication was rejected without changing the current pointer."""


class CompareAndSwapError(PublishError):
    """The current pointer did not match the caller's expected snapshot."""


class PublicationIndeterminateError(PublishError):
    """The pointer replacement may have committed; recover by reading current.json."""


def canonical_json(value: Any) -> bytes:
    """Encode JSON deterministically for hashes, manifests, and snapshots."""
    return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def snapshot_id(
    content: Any, *, schema_hash: str, policy_hash: str, revision: str, epoch: int | str
) -> str:
    """Derive a snapshot identifier from public content and decision inputs."""
    identity = {
        "content_sha256": sha256(canonical_json(content)).hexdigest(),
        "schema_hash": _sha256_value(schema_hash, "schema_hash"),
        "policy_hash": _sha256_value(policy_hash, "policy_hash"),
        "revision": _nonempty(revision, "revision"),
        "epoch": _epoch(epoch),
    }
    return sha256(canonical_json(identity)).hexdigest()


def publish_snapshot(
    root: str | Path,
    content: Mapping[str, Any],
    *,
    schema_hash: str,
    policy_hash: str,
    revision: str,
    epoch: int | str,
    gate: GateReport,
    expected_current_id: str | None,
    emergency: bool = False,
    update_current: bool = True,
) -> dict[str, Any]:
    """Stage and verify an immutable bundle before optionally replacing current."""
    if not is_publishable_gate(gate, emergency=emergency):
        raise PublishError("publication quality gate failed")
    public_content = _public_content(content)
    root_path = Path(root)
    snapshots = root_path / "snapshots"
    _validate_schema_hash(schema_hash)
    snapshots.mkdir(parents=True, exist_ok=True)
    identifier = snapshot_id(public_content, schema_hash=schema_hash, policy_hash=policy_hash, revision=revision, epoch=epoch)
    bundle = {
        "snapshot_id": identifier,
        "schema_hash": _sha256_value(schema_hash, "schema_hash"),
        "policy_hash": _sha256_value(policy_hash, "policy_hash"),
        "revision": _nonempty(revision, "revision"),
        "epoch": _epoch(epoch),
        **public_content,
    }
    _validate_snapshot_schema(bundle)
    with _pointer_lock(root_path):
        current = _read_current(root_path / "current.json")
        if current is not None:
            _verify_current_pointer(current, snapshots)
        current_id = current.get("snapshot_id") if current else None
        if current_id != expected_current_id:
            raise CompareAndSwapError("current pointer does not match expected snapshot")
        if emergency:
            if current is None:
                raise PublishError("emergency publication requires a current snapshot")
            _require_removal_only(_read_bundle(snapshots / current_id), bundle)
        manifest = _stage_bundle(snapshots, identifier, bundle)
        _verify_bundle(snapshots / identifier, manifest)
        pointer = {
            "snapshot_id": identifier,
            "manifest_sha256": manifest["manifest_sha256"],
            "schema_hash": bundle["schema_hash"],
            "policy_hash": bundle["policy_hash"],
            "revision": bundle["revision"],
            "epoch": bundle["epoch"],
        }
        if not update_current:
            return pointer
        try:
            _atomic_write(root_path / "current.json", canonical_json(pointer))
        except PublicationIndeterminateError as error:
            _recover_pointer_write(root_path / "current.json", pointer, current, snapshots, error)
        try:
            stored_pointer = _read_current(root_path / "current.json")
            if stored_pointer != pointer:
                raise PublishError("current pointer read-back mismatch")
            _verify_current_pointer(stored_pointer, snapshots)
        except PublicationIndeterminateError:
            raise
        except Exception as error:
            raise PublicationIndeterminateError(
                "current pointer read-back is indeterminate"
            ) from error
        return pointer


def _public_content(content: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(content, Mapping):
        raise PublishError("snapshot content must be an object")
    required = {"records", "evidence", "sources"}
    reserved = {"snapshot_id", "schema_hash", "policy_hash", "revision", "epoch", "manifest_sha256"}
    if set(content) != required or set(content) & reserved:
        raise PublishError("snapshot content must contain only records, evidence, and sources")
    projection = dict(content)
    _validate_references(projection)
    return projection


def _stage_bundle(snapshots: Path, identifier: str, bundle: Mapping[str, Any]) -> dict[str, Any]:
    destination = snapshots / identifier
    if destination.exists():
        manifest = _read_manifest(destination)
        _verify_bundle(destination, manifest)
        if _read_bundle(destination) != dict(bundle):
            raise PublishError("snapshot identifier collision")
        return manifest
    staging = Path(tempfile.mkdtemp(prefix=f".{identifier}.", dir=snapshots))
    try:
        snapshot_bytes = canonical_json(bundle)
        _write_file(staging / "snapshot.json", snapshot_bytes)
        manifest = {"snapshot_id": identifier, "files": {"snapshot.json": sha256(snapshot_bytes).hexdigest()}}
        manifest_bytes = canonical_json(manifest)
        manifest = {**manifest, "manifest_sha256": sha256(manifest_bytes).hexdigest()}
        _write_file(staging / "manifest.json", canonical_json(manifest))
        _fsync_directory(staging)
        os.replace(staging, destination)
        _fsync_directory(snapshots)
        return manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _verify_bundle(path: Path, manifest: Mapping[str, Any]) -> None:
    stored_manifest = _read_manifest(path)
    if stored_manifest != dict(manifest):
        raise PublishError("bundle manifest read-back mismatch")
    if set(manifest) != {"snapshot_id", "files", "manifest_sha256"} or not isinstance(manifest.get("files"), Mapping) or set(manifest["files"]) != {"snapshot.json"}:
        raise PublishError("bundle manifest is invalid")
    manifest_body = {"snapshot_id": manifest["snapshot_id"], "files": {"snapshot.json": manifest["files"]["snapshot.json"]}}
    try:
        _sha256_value(manifest_body["snapshot_id"], "bundle snapshot_id")
        _sha256_value(manifest_body["files"]["snapshot.json"], "bundle checksum")
        _sha256_value(manifest["manifest_sha256"], "bundle manifest_sha256")
    except (KeyError, PublishError) as error:
        raise PublishError("bundle manifest is invalid") from error
    if manifest["manifest_sha256"] != sha256(canonical_json(manifest_body)).hexdigest():
        raise PublishError("bundle manifest checksum is invalid")
    snapshot_bytes = (path / "snapshot.json").read_bytes()
    if sha256(snapshot_bytes).hexdigest() != manifest_body["files"]["snapshot.json"]:
        raise PublishError("bundle checksum read-back mismatch")
    bundle = _read_bundle(path)
    _validate_schema_hash(bundle.get("schema_hash"))
    _validate_snapshot_schema(bundle)
    try:
        public_content = _bundle_content(bundle)
        calculated = snapshot_id(public_content, schema_hash=bundle["schema_hash"], policy_hash=bundle["policy_hash"], revision=bundle["revision"], epoch=bundle["epoch"])
    except (KeyError, PublishError) as error:
        raise PublishError("snapshot bundle is invalid") from error
    if path.name != manifest_body["snapshot_id"] or bundle.get("snapshot_id") != manifest_body["snapshot_id"] or calculated != manifest_body["snapshot_id"]:
        raise PublishError("bundle content-address read-back mismatch")


def _read_current(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError, TypeError) as error:
        raise PublishError("current pointer is unreadable") from error
    if not isinstance(value, dict):
        raise PublishError("current pointer is invalid")
    try:
        if set(value) != {"snapshot_id", "manifest_sha256", "schema_hash", "policy_hash", "revision", "epoch"}:
            raise PublishError("unexpected pointer fields")
        _sha256_value(value["snapshot_id"], "current snapshot_id")
        _sha256_value(value["manifest_sha256"], "current manifest_sha256")
        _sha256_value(value["schema_hash"], "current schema_hash")
        _sha256_value(value["policy_hash"], "current policy_hash")
        _nonempty(value["revision"], "current revision")
        _epoch(value["epoch"])
    except (KeyError, PublishError) as error:
        raise PublishError("current pointer is invalid") from error
    return value


def _verify_current_pointer(pointer: Mapping[str, Any], snapshots: Path) -> None:
    manifest = _read_manifest(snapshots / pointer["snapshot_id"])
    _verify_bundle(snapshots / pointer["snapshot_id"], manifest)
    bundle = _read_bundle(snapshots / pointer["snapshot_id"])
    if pointer["manifest_sha256"] != manifest["manifest_sha256"] or any(pointer[key] != bundle.get(key) for key in ("snapshot_id", "schema_hash", "policy_hash", "revision", "epoch")):
        raise PublishError("current pointer does not match its immutable bundle")


def _recover_pointer_write(path: Path, expected: Mapping[str, Any], previous: Mapping[str, Any] | None, snapshots: Path, error: Exception) -> None:
    try:
        observed = _read_current(path)
        if observed == dict(expected):
            _verify_current_pointer(observed, snapshots)
            _fsync_directory(path.parent)
            return
        if observed == previous:
            raise PublicationIndeterminateError("pointer write left the previous pointer intact; retry after recovery") from error
    except PublicationIndeterminateError:
        raise
    except (PublishError, OSError):
        pass
    raise PublicationIndeterminateError("pointer write outcome is indeterminate; recover current.json before retrying") from error


def _read_bundle(path: Path) -> dict[str, Any]:
    try:
        value = json.loads((path / "snapshot.json").read_bytes())
    except (OSError, ValueError, TypeError) as error:
        raise PublishError("snapshot bundle is unreadable") from error
    if not isinstance(value, dict):
        raise PublishError("snapshot bundle is invalid")
    return value


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads((path / "manifest.json").read_bytes())
    except (OSError, ValueError, TypeError) as error:
        raise PublishError("snapshot manifest is unreadable") from error
    if not isinstance(value, dict):
        raise PublishError("snapshot manifest is invalid")
    return value


def _require_removal_only(previous: Mapping[str, Any], candidate: Mapping[str, Any]) -> None:
    old_content = _bundle_content(previous)
    new_content = _bundle_content(candidate)
    for key, identifier in (("records", "record_id"), ("evidence", "evidence_id"), ("sources", "source_id")):
        old_items = old_content[key]
        new_items = new_content[key]
        new_by_id = _items_by_id(new_items, identifier, key)
        _items_by_id(old_items, identifier, key)
        expected = [item for item in old_items if item[identifier] in new_by_id]
        if len(new_items) != len(expected) or any(canonical_json(actual) != canonical_json(original) for actual, original in zip(new_items, expected)):
            raise PublishError(f"emergency publication may only remove unchanged {key}")

def _validate_schema_hash(schema_hash: str) -> None:
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "snapshot-v3.schema.json"
    try:
        raw = schema_path.read_bytes()
        canonical = canonical_json(json.loads(raw))
    except (OSError, ValueError, TypeError) as error:
        raise PublishError("snapshot schema is unavailable") from error
    if _sha256_value(schema_hash, "schema_hash") not in {
        sha256(raw).hexdigest(),
        sha256(canonical).hexdigest(),
    }:
        raise PublishError("schema_hash does not match snapshot-v3 schema")
def _validate_snapshot_schema(bundle: Mapping[str, Any]) -> None:
    try:
        from jsonschema import Draft202012Validator

        schema_path = Path(__file__).resolve().parents[2] / "schemas" / "snapshot-v3.schema.json"
        schema = json.loads(schema_path.read_bytes())
        Draft202012Validator(schema).validate(dict(bundle))
    except (OSError, ValueError, TypeError) as error:
        raise PublishError("snapshot schema is unavailable") from error
    except Exception as error:
        raise PublishError("snapshot does not satisfy snapshot-v3 schema") from error

def _bundle_content(bundle: Mapping[str, Any]) -> dict[str, Any]:
    metadata = {"snapshot_id", "schema_hash", "policy_hash", "revision", "epoch"}
    if set(bundle) != metadata | {"records", "evidence", "sources"}:
        raise PublishError("snapshot bundle has invalid fields")
    return _public_content({key: bundle[key] for key in ("records", "evidence", "sources")})



def _validate_references(content: Mapping[str, Any]) -> None:
    records, evidence, sources = (content[name] for name in ("records", "evidence", "sources"))
    evidence_by_id = _items_by_id(evidence, "evidence_id", "evidence")
    source_by_id = _items_by_id(sources, "source_id", "sources")
    for record in _items_by_id(records, "record_id", "records").values():
        if not isinstance(record, Mapping):
            raise PublishError("records must be objects")
        evidence_ids, source_ids, claims = record.get("evidence_ids"), record.get("source_ids"), record.get("claims")
        if not isinstance(evidence_ids, list) or not isinstance(source_ids, list) or not isinstance(claims, list):
            raise PublishError("records must contain reference lists and claims")
        if any(not isinstance(value, str) or value not in evidence_by_id for value in evidence_ids) or any(not isinstance(value, str) or value not in source_by_id for value in source_ids):
            raise PublishError("record references are invalid")
        for claim in claims:
            if not isinstance(claim, Mapping) or claim.get("evidence_id") not in evidence_by_id or claim.get("source_id") not in source_by_id:
                raise PublishError("claim references are invalid")
    for item in evidence_by_id.values():
        if not isinstance(item, Mapping) or item.get("source_id") not in source_by_id:
            raise PublishError("evidence references are invalid")


def _items_by_id(items: Any, identifier: str, name: str) -> dict[str, Any]:
    if not isinstance(items, list):
        raise PublishError(f"{name} must be lists")
    result: dict[str, Any] = {}
    for item in items:
        if not isinstance(item, Mapping) or not isinstance(item.get(identifier), str) or item[identifier] in result:
            raise PublishError(f"{name} must have unique {identifier} values")
        result[item[identifier]] = item
    return result


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    replaced = False
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        replaced = True
        _fsync_directory(path.parent)
    except Exception as error:
        if replaced:
            raise PublicationIndeterminateError("pointer replace completed but durability is unknown") from error
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _write_file(path: Path, payload: bytes) -> None:
    with path.open("xb") as output:
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def _pointer_lock(root: Path) -> Iterator[None]:
    import fcntl

    root.mkdir(parents=True, exist_ok=True)
    with (root / ".current.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _sha256_value(value: str, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise PublishError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _nonempty(value: str, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise PublishError(f"{name} must be non-empty")
    return value


def _epoch(value: int | str) -> int | str:
    if isinstance(value, bool) or not isinstance(value, (int, str)) or value == "" or isinstance(value, int) and value < 0:
        raise PublishError("epoch must be a non-negative integer or non-empty string")
    return value
