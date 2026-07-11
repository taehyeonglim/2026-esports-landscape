"""Fail-closed, PII-free operational command line interface."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import sys
from typing import Any

from .db import connect, foreign_key_check, integrity_check
from .git_mutation import promote_mutation
from .extract.json import extract_json
from .migrate import migrate
from .publish import PublicationIndeterminateError, _read_manifest, _verify_bundle, publish_snapshot
from .quality import GateCheck, GateReport, GateState
from .models import BudgetStatus, ReviewStatus
from .policy import PolicySnapshot, load_claim_requirement_policy, load_freshness_policy, load_publisher_policy
from .registry import load_source_registry
from .review import (
    PrimaryReview,
    ProposalStatus,
    RelatedProposal,
    ReviewAction,
    ReviewCommand,
    ReviewState,
    apply_review_command,
)
from .verify import verify_candidate_from_db
EXIT_OK = 0
EXIT_BLOCKED = 2
EXIT_ERROR = 3
class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print(json.dumps({"command": "unknown", "outcome": "blocked", "reason": "invalid_arguments"}, sort_keys=True))
        self.exit(EXIT_BLOCKED)


_LOCK_SHA256 = "abaeb369c2a7f6854453684471d8a9756fa57f00bfd42cfda26d5fbe00edccf6"


def _emit(command: str, outcome: str, **details: object) -> int:
    """Write a compact operational result; never serialize operator input."""
    print(json.dumps({"command": command, "outcome": outcome, **details}, allow_nan=False, sort_keys=True))
    return EXIT_OK if outcome == "completed" else EXIT_BLOCKED


def _load_json(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("input must be a JSON object")
    return value
def _file_sha256(path: str) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def _authorization_key() -> bytes:
    encoded = os.environ.get("PUBLICATION_AUTHORIZATION_KEY", "")
    try:
        if encoded.startswith("hex:"):
            key = bytes.fromhex(encoded[4:])
        elif encoded.startswith("base64:"):
            key = base64.b64decode(encoded[7:], validate=True)
        else:
            raise ValueError
    except (ValueError, base64.binascii.Error) as error:
        raise ValueError("publication authorization key is invalid") from error
    if len(key) < 32:
        raise ValueError("publication authorization key is invalid")
    return key


def _canonical_authorization(value: dict[str, Any]) -> bytes:
    return json.dumps(
        {key: item for key, item in value.items() if key != "signature_hmac_sha256"},
        ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")


def _normalized_output_dir(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
        raise ValueError("publication output directory is invalid")
    return str(path)
def _effective_output_dir(argument: str, environment: str | None, authorized: str) -> Path:
    authorized_dir = _normalized_output_dir(authorized)
    if environment:
        environment_dir = _normalized_output_dir(environment)
        if environment_dir != authorized_dir:
            raise ValueError("publication output directory is invalid")
    argument_path = Path(argument)
    if argument_path.is_absolute():
        argument_dir = _normalized_output_dir(argument_path.name)
    else:
        argument_dir = _normalized_output_dir(argument)
    if argument_dir != authorized_dir:
        raise ValueError("publication output directory is invalid")
    return argument_path



def _canonical_https_origin(value: str) -> str:
    from urllib.parse import urlsplit, urlunsplit

    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.port not in (None, 443)):
        raise ValueError("publication readback origin is invalid")
    path = parsed.path.rstrip("/")
    return urlunsplit(("https", parsed.hostname.lower(), path, "", ""))


def _validate_authorization(
    value: dict[str, Any], *, repository: str, workflow_ref: str, target_ref: str,
    workflow_sha: str, target_sha: str, environment: str, output_dir: str,
    nonce_ledger: str, readback_origin: str,
) -> None:
    from jsonschema import Draft202012Validator, FormatChecker
    from jsonschema.exceptions import SchemaError, ValidationError

    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "publication-authorization-v1.schema.json"
    schema = json.loads(schema_path.read_bytes())
    try:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)
    except (SchemaError, ValidationError) as error:
        raise ValueError("authorization is invalid") from error
    context = {
        "repository": repository, "workflow_ref": workflow_ref, "target_ref": target_ref,
        "workflow_sha": workflow_sha, "target_sha": target_sha, "environment": environment,
        "output_dir": _normalized_output_dir(output_dir), "nonce_ledger": nonce_ledger,
        "readback_origin": _canonical_https_origin(readback_origin),
    }
    if any(not item or value[field] != item for field, item in context.items()):
        raise ValueError("publication authorization context does not match")
    expected_signature = hmac.new(_authorization_key(), _canonical_authorization(value), "sha256").hexdigest()
    if not hmac.compare_digest(value["signature_hmac_sha256"], expected_signature):
        raise ValueError("publication authorization signature is invalid")
    issued_at = datetime.fromisoformat(value["issued_at"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    if issued_at.tzinfo is None or issued_at > now or (now - issued_at.astimezone(timezone.utc)).total_seconds() > value["freshness_seconds"]:
        raise ValueError("authorization is invalid")


def _trusted_quality_report(value: dict[str, Any], *, emergency: bool) -> GateReport:
    if set(value) != {"state", "passed", "checks"} or not isinstance(value["checks"], list):
        raise ValueError("quality report is invalid")
    checks = []
    for check in value["checks"]:
        if not isinstance(check, dict) or set(check) != {"name", "passed", "actual", "required"}:
            raise ValueError("quality report is invalid")
        if not isinstance(check["name"], str) or type(check["passed"]) is not bool:
            raise ValueError("quality report is invalid")
        checks.append(GateCheck(**check))
    expected_names = (
        "core_coverage", "false_publications", "automatic_mismerges",
        "schema_required_field_coverage", "quality_field_coverage", "schema_valid",
        "references_valid", "checksums_valid", "pii_findings", "overdue_count",
        "stop_requested", "budget_status",
    )
    if tuple(check.name for check in checks) != expected_names:
        raise ValueError("quality report is invalid")
    for check in checks:
        if check.name == "budget_status":
            if check.actual != BudgetStatus.PASS.value or check.required != BudgetStatus.PASS.value:
                raise ValueError("quality report is invalid")
        elif not isinstance(check.actual, (bool, int, float)) or not isinstance(check.required, (bool, int, float)):
            raise ValueError("quality report is invalid")
    try:
        report = GateReport(GateState(value["state"]), tuple(checks))
    except (TypeError, ValueError) as error:
        raise ValueError("quality report is invalid") from error
    stop_check = checks[-2]
    if emergency:
        if value["passed"] is not False or report.passed or stop_check.actual is not True or stop_check.required is not False or stop_check.passed:
            raise ValueError("quality report is invalid")
        if any(not check.passed for check in checks if check.name != "stop_requested"):
            raise ValueError("quality report is invalid")
        return report
    if type(value["passed"]) is not bool or value["passed"] is not report.passed or not report.passed or not all(check.passed for check in checks):
        raise ValueError("quality report is invalid")
    return report


def _atomic_json_write(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temporary.exists():
            temporary.unlink()


def _publication_journal(
    root: str | Path,
    nonce: str,
    binding: dict[str, Any],
    *,
    completed_state: str,
) -> tuple[Path, dict[str, Any] | None]:
    journal_dir = Path(root) / ".publication-nonces"
    journal_dir.mkdir(parents=True, exist_ok=True)
    journal = journal_dir / f"{sha256(nonce.encode('utf-8')).hexdigest()}.json"
    try:
        descriptor = os.open(journal, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        try:
            existing = json.loads(journal.read_bytes())
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("publication authorization journal is corrupt") from error
        allowed_states = (
            {completed_state, "completed"}
            if completed_state == "staged"
            else {completed_state}
        )
        if (
            not isinstance(existing, dict)
            or set(existing) != {"binding", "result", "state"}
            or existing["binding"] != binding
            or existing["state"] not in allowed_states
            or not isinstance(existing["result"], dict)
        ):
            raise ValueError("publication authorization nonce journal cannot be replayed")
        return journal, existing["result"]
    with os.fdopen(descriptor, "wb") as output:
        output.write(json.dumps(
            {"binding": binding, "result": None, "state": "pending"},
            ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True,
        ).encode("utf-8"))
        output.flush()
        os.fsync(output.fileno())
    directory_fd = os.open(journal_dir, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return journal, None


def _validate_completed_publication(
    root: str | Path,
    result: dict[str, Any],
    *,
    require_current: bool,
) -> None:
    if set(result) != {"snapshot_id", "manifest_sha256", "prior_pointer", "current_pointer"}:
        raise ValueError("publication journal result is invalid")
    pointer = result["current_pointer"]
    if not isinstance(pointer, dict) or pointer.get("snapshot_id") != result["snapshot_id"]:
        raise ValueError("publication journal result is invalid")
    manifest = _read_manifest(Path(root) / "snapshots" / result["snapshot_id"])
    _verify_bundle(Path(root) / "snapshots" / result["snapshot_id"], manifest)
    if manifest.get("manifest_sha256") != result["manifest_sha256"] or pointer.get("manifest_sha256") != result["manifest_sha256"]:
        raise ValueError("publication journal immutable snapshot is inconsistent")
    if require_current:
        current = json.loads((Path(root) / "current.json").read_bytes())
        if current != pointer:
            raise ValueError("publication journal current pointer is inconsistent")


def _validate_staged_replay(root: str | Path, result: dict[str, Any]) -> None:
    current_path = Path(root) / "current.json"
    if current_path.exists():
        current = json.loads(current_path.read_bytes())
        current_id = current.get("snapshot_id") if isinstance(current, dict) else None
    else:
        current_id = None
    if current_id not in {result["prior_pointer"], result["snapshot_id"]}:
        raise ValueError("staged publication replay failed current-pointer CAS")


def _validate_staged_artifacts(args: argparse.Namespace, receipt: dict[str, Any]) -> None:
    staged: dict[str, Path] = {}
    for entry in args.staged_file:
        name, separator, filename = entry.partition("=")
        if not separator or not name or not filename or name in staged:
            raise ValueError("staged artifact mapping is invalid")
        staged[name] = Path(filename)
    resolved_paths = [path.resolve() for path in staged.values()]
    if len(set(resolved_paths)) != len(resolved_paths):
        raise ValueError("staged artifact files must be distinct")
    changed = receipt["changed_file_sha256"]
    forbidden = (".github/workflows/", "src/", "control/receipts/commands/")
    if (set(staged) != set(changed) or any(name.startswith(forbidden) or name.endswith(".py") for name in changed)
            or any(path.resolve() == Path(args.receipt).resolve() for path in staged.values())):
        raise ValueError("receipt changed-file artifacts are invalid")
    if not any(path.resolve() == Path(args.database).resolve() for path in staged.values()):
        raise ValueError("receipt must stage the database artifact")
    for name, path in staged.items():
        try:
            if _file_sha256(str(path)) != changed[name]:
                raise ValueError("receipt changed-file artifact digest mismatch")
        except OSError as error:
            raise ValueError("receipt changed-file artifact is unavailable") from error
    if _file_sha256(args.database) != receipt["sqlite_file_sha256"]:
        raise ValueError("receipt database digest mismatch")

def _matching(value: Any, expected: Any) -> bool:
    return type(value) is type(expected) and value == expected


def _lock_is_verified() -> bool:
    lock = Path(__file__).resolve().parents[2] / "requirements.lock"
    try:
        return sha256(lock.read_bytes()).hexdigest() == _LOCK_SHA256
    except OSError:
        return False


def _require_verified_lock() -> None:
    if not _lock_is_verified():
        raise RuntimeError("dependency lock is not verified")


def _command_migrate(args: argparse.Namespace) -> int:
    with connect(args.database) as connection:
        versions = migrate(connection, args.migrations)
    return _emit("migrate", "completed", migration_versions=list(versions))


def _command_collect_offline_fixture(args: argparse.Namespace) -> int:
    document = Path(args.fixture).read_bytes()
    result = extract_json(document, salt=args.salt)
    # This is deliberately offline fixture processing, never a production fetch.
    outcome = "completed" if result.status.value == "success" else "blocked"
    return _emit("collect-offline-fixture", outcome, fact_count=len(result.facts), status=result.status.value)


def _command_verify(args: argparse.Namespace) -> int:
    registry = load_source_registry(args.sources)
    policy = PolicySnapshot(
        freshness=load_freshness_policy(args.freshness),
        publishers=load_publisher_policy(args.publishers),
        registry=registry,
        claims=load_claim_requirement_policy(args.claims),
    )
    with connect(args.database) as connection:
        decision = verify_candidate_from_db(
            connection, candidate_id=args.candidate_id, registry=registry, policy=policy,
        )
    return _emit(
        "verify",
        "completed" if decision.status.value in {"verified", "provisional"} else "blocked",
        claim_count=len(decision.claim_decisions),
        status=decision.status.value,
    )


def _command_review(args: argparse.Namespace) -> int:
    request = _load_json(args.input)
    primary_data = request["primary"]
    state = ReviewState(
        primary=PrimaryReview(primary_data["review_id"], ReviewStatus(primary_data.get("status", "active"))),
        proposals=tuple(
            RelatedProposal(item["proposal_id"], ProposalStatus(item.get("status", "active")))
            for item in request.get("proposals", [])
        ),
        version=request.get("version", 0),
    )
    command_data = request["command"]
    command = ReviewCommand(
        command_id=command_data["command_id"],
        actor_id=command_data["actor_id"],
        expected_version=command_data["expected_version"],
        action=ReviewAction(command_data["action"]),
        target_id=command_data["target_id"],
    )
    result = apply_review_command(state, command, allowed_actors=request["allowed_actors"])
    return _emit(
        "review",
        "completed",
        idempotent=result.idempotent,
        resulting_version=result.state.version,
    )


def _command_audit(args: argparse.Namespace) -> int:
    with connect(args.database, readonly=True) as connection:
        integrity_check(connection)
        foreign_key_check(connection)
    return _emit("audit", "completed", checks=["integrity", "foreign_keys"])


def _command_publish(args: argparse.Namespace) -> int:
    _require_verified_lock()
    request = _load_json(args.input)
    authorization = _load_json(args.authorization)
    receipt = _load_json(args.receipt)
    quality = _load_json(args.quality_report)
    budget = _load_json(args.budget_report)
    repository = args.repository or os.environ.get("GITHUB_REPOSITORY", "")
    workflow_ref = args.workflow_ref or os.environ.get("GITHUB_WORKFLOW_REF", "")
    target_ref = args.target_ref or os.environ.get("PUBLICATION_TARGET_REF", "")
    effective_output_dir = _effective_output_dir(
        args.output_dir, os.environ.get("PUBLICATION_OUTPUT_DIR"), authorization["output_dir"],
    )
    _validate_authorization(
        authorization, repository=repository, workflow_ref=workflow_ref, target_ref=target_ref,
        workflow_sha=os.environ.get("PUBLICATION_WORKFLOW_SHA", ""),
        target_sha=os.environ.get("PUBLICATION_TARGET_SHA", ""),
        environment=os.environ.get("PUBLICATION_ENVIRONMENT", ""),
        output_dir=authorization["output_dir"],
        nonce_ledger=".publication-nonces",
        readback_origin=os.environ.get("PUBLICATION_READBACK_ORIGIN", ""),
    )
    emergency = authorization["operation"] == "emergency"
    required = {"content", "schema_hash", "policy_hash", "revision", "epoch", "correction_epoch", "stop_epoch", "expected_current"}
    if emergency:
        required.add("emergency")
    if set(request) != required or (emergency and request["emergency"] is not True):
        raise ValueError("publication request is invalid")
    if not emergency and authorization["operation"] != "normal":
        raise ValueError("publication authorization operation is invalid")
    if emergency and (type(request["stop_epoch"]) is not int or request["stop_epoch"] <= 0):
        raise ValueError("emergency stop epoch is invalid")
    receipt_schema = json.loads((Path(__file__).resolve().parents[2] / "schemas" / "command-receipt-v1.schema.json").read_bytes())
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError, ValidationError
    try:
        Draft202012Validator(receipt_schema).validate(receipt)
    except (SchemaError, ValidationError) as error:
        raise ValueError("command receipt is invalid") from error
    digest_inputs = (
        (args.input, "projection_request_sha256"),
        (args.receipt, "command_receipt_sha256"),
        (args.quality_report, "quality_report_sha256"),
        (args.budget_report, "budget_report_sha256"),
    )
    if any(_file_sha256(path) != authorization[field] for path, field in digest_inputs):
        raise ValueError("publication authorization does not match artifacts")
    receipt_fields = {
        "parent_git_sha": "parent_git_sha",
        "output_revision": "output_revision",
        "sqlite_file_sha256": "sqlite_file_sha256",
        "policy_hash": "policy_hash",
        "schema_sha256": "schema_sha256",
        "migration_sha256": "migration_sha256",
        "correction_epoch": "correction_epoch",
        "stop_epoch": "stop_epoch",
    }
    if any(not _matching(receipt[receipt_field], authorization[authorization_field]) for receipt_field, authorization_field in receipt_fields.items()):
        raise ValueError("publication authorization does not match receipt")
    request_fields = {
        "schema_hash": "schema_sha256",
        "policy_hash": "policy_hash",
        "revision": "output_revision",
        "epoch": "correction_epoch",
        "correction_epoch": "correction_epoch",
        "stop_epoch": "stop_epoch",
        "expected_current": "expected_current",
    }
    if any(not _matching(request[request_field], authorization[authorization_field]) for request_field, authorization_field in request_fields.items()):
        raise ValueError("publication request is not authorized")
    snapshot_schema_path = Path(__file__).resolve().parents[2] / "schemas" / "snapshot-v3.schema.json"
    snapshot_schema_sha256 = _file_sha256(str(snapshot_schema_path))
    if authorization["schema_sha256"] != snapshot_schema_sha256 or request["schema_hash"] != snapshot_schema_sha256:
        raise ValueError("publication schema digest does not match checked-in schema")
    from .publish import snapshot_id
    from jsonschema import Draft202012Validator, FormatChecker
    candidate = {
        "snapshot_id": snapshot_id(
            request["content"], schema_hash=request["schema_hash"], policy_hash=request["policy_hash"],
            revision=request["revision"], epoch=request["epoch"],
        ),
        "schema_hash": request["schema_hash"], "policy_hash": request["policy_hash"],
        "revision": request["revision"], "epoch": request["epoch"], **request["content"],
    }
    try:
        Draft202012Validator(
            json.loads(snapshot_schema_path.read_bytes()), format_checker=FormatChecker(),
        ).validate(candidate)
    except Exception as error:
        raise ValueError("candidate snapshot is invalid") from error
    report = _trusted_quality_report(quality, emergency=emergency)
    if authorization["quality_passed"] is not True or budget.get("status") != "PASS" or authorization["budget_status"] != "PASS":
        raise ValueError("publication gates are not authorized")
    _validate_staged_artifacts(args, receipt)
    binding = {
        "artifact_digests": {field: authorization[field] for _, field in digest_inputs},
        "authorization_sha256": _file_sha256(args.authorization),
        "command_id": receipt["command_id"],
        "receipt_sha256": _file_sha256(args.receipt),
        "staged_artifact_digests": receipt["changed_file_sha256"],
        "stage_only": args.stage_only,
    }
    completed_state = "staged" if args.stage_only else "completed"
    journal, replay_result = _publication_journal(
        effective_output_dir,
        authorization["nonce"],
        binding,
        completed_state=completed_state,
    )
    if replay_result is not None:
        _validate_completed_publication(
            effective_output_dir,
            replay_result,
            require_current=not args.stage_only,
        )
        if args.stage_only:
            _validate_staged_replay(effective_output_dir, replay_result)
        _atomic_json_write(Path(args.result_file), replay_result)
        return _emit("publish", "completed", snapshot_id=replay_result["snapshot_id"])
    pointer = publish_snapshot(
        effective_output_dir,
        request["content"],
        schema_hash=request["schema_hash"],
        policy_hash=request["policy_hash"],
        revision=request["revision"],
        epoch=request["epoch"],
        gate=report,
        expected_current_id=request["expected_current"],
        emergency=emergency,
        update_current=not args.stage_only,
    )
    result = {
        "snapshot_id": pointer["snapshot_id"],
        "manifest_sha256": pointer["manifest_sha256"],
        "prior_pointer": request["expected_current"],
        "current_pointer": pointer,
    }
    _validate_completed_publication(
        effective_output_dir,
        result,
        require_current=not args.stage_only,
    )
    _atomic_json_write(journal, {"binding": binding, "result": result, "state": completed_state})
    _atomic_json_write(Path(args.result_file), result)
    return _emit(
        "publish",
        "completed",
        phase=completed_state,
        snapshot_id=pointer["snapshot_id"],
    )




def _command_promote_mutation(args: argparse.Namespace) -> int:
    result = promote_mutation(
        candidate_ref=args.candidate_ref,
        target_ref=args.target_ref,
        database_path=args.database,
        receipt_path=args.receipt,
        command_id=args.command_id,
        report_path=args.report,
        remote=args.remote,
    )
    return _emit(
        "promote-mutation", result.outcome,
        candidate_sha=result.candidate_sha, target_sha=result.target_sha,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = _SafeArgumentParser(prog="esports-data", description="PII-free esports data operations")
    commands = parser.add_subparsers(dest="command", required=True)

    migrate_parser = commands.add_parser("migrate")
    migrate_parser.add_argument("--database", required=True)
    migrate_parser.add_argument("--migrations")
    migrate_parser.set_defaults(handler=_command_migrate)

    collect_parser = commands.add_parser(
        "collect-offline-fixture",
        help="offline development: extract a local fixture without network retrieval",
    )
    collect_parser.add_argument("--fixture", required=True, help="local development JSON fixture; no network fetch occurs")
    collect_parser.add_argument("--salt", required=True, help="non-output digest salt")
    collect_parser.set_defaults(handler=_command_collect_offline_fixture)

    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--database", required=True)
    verify_parser.add_argument("--candidate-id", required=True)
    verify_parser.add_argument("--claims", required=True)
    verify_parser.add_argument("--sources", required=True)
    verify_parser.add_argument("--freshness", required=True)
    verify_parser.add_argument("--publishers", required=True)
    verify_parser.set_defaults(handler=_command_verify)

    review_parser = commands.add_parser("review")
    review_parser.add_argument("--input", required=True, help="typed worker request JSON")
    review_parser.set_defaults(handler=_command_review)

    audit_parser = commands.add_parser("audit")
    audit_parser.add_argument("--database", required=True)
    audit_parser.set_defaults(handler=_command_audit)

    promote_parser = commands.add_parser("promote-mutation")
    promote_parser.add_argument("--candidate-ref", required=True)
    promote_parser.add_argument("--target-ref", required=True)
    promote_parser.add_argument("--database", required=True)
    promote_parser.add_argument("--receipt", required=True)
    promote_parser.add_argument("--command-id", required=True)
    promote_parser.add_argument("--report")
    promote_parser.add_argument("--remote", default="origin")
    promote_parser.set_defaults(handler=_command_promote_mutation)
    publish_parser = commands.add_parser("publish")
    publish_parser.add_argument("--input", required=True)
    publish_parser.add_argument("--output-dir", required=True)
    publish_parser.add_argument("--authorization", required=True)
    publish_parser.add_argument("--receipt", required=True)
    publish_parser.add_argument("--quality-report", required=True)
    publish_parser.add_argument("--budget-report", required=True)
    publish_parser.add_argument("--result-file", required=True)
    publish_parser.add_argument("--database", required=True)
    publish_parser.add_argument(
        "--staged-file", action="append", required=True, metavar="RECEIPT_PATH=FILE",
        help="receipt changed_file_sha256 path mapped to its staged artifact",
    )
    publish_parser.add_argument("--repository")
    publish_parser.add_argument("--workflow-ref")
    publish_parser.add_argument("--target-ref")
    publish_parser.add_argument(
        "--stage-only",
        action="store_true",
        help="stage an immutable snapshot without advancing current.json; reserved for the protected read-back workflow",
    )
    publish_parser.set_defaults(handler=_command_publish)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        return args.handler(args)
    except PublicationIndeterminateError:
        command = getattr(locals().get("args", None), "command", "unknown")
        print(json.dumps({"command": command, "outcome": "indeterminate", "reason": "recover_current_pointer"}, sort_keys=True))
        return EXIT_ERROR
    except (OSError, ValueError, sqlite3.Error, RuntimeError):
        command = getattr(locals().get("args", None), "command", "unknown")
        return _emit(command, "blocked", reason="operation_rejected")
    except Exception:
        # Do not leak tracebacks or unreviewed payloads through the operational surface.
        command = getattr(locals().get("args", None), "command", "unknown")
        print(json.dumps({"command": command, "outcome": "blocked", "reason": "operation_failed"}, sort_keys=True))
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
