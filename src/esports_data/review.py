"""Pure, optimistic-concurrency review transitions for primary subjects."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import json
import re
import sqlite3
from typing import Iterable
from uuid import NAMESPACE_URL, uuid5
from .db import authorize_review_transition, clear_review_transition_authorization

from .models import Relation, ReviewStatus


class ReviewError(ValueError):
    """Base exception for rejected review commands."""


class UnauthorizedReview(ReviewError):
    """Raised when an actor is not in the supplied allowlist."""


class StaleReviewCommand(ReviewError):
    """Raised when a command's expected version no longer matches."""


class InvalidReviewTransition(ReviewError):
    """Raised when a command cannot transition its target's state."""


class CommandIdConflict(ReviewError):
    """Raised when a command ID is reused for different command contents."""


class ReviewAction(str, Enum):
    RESOLVE_PRIMARY = "resolve_primary"
    SUPERSEDE_PRIMARY = "supersede_primary"
    ACCEPT_PROPOSAL = "accept_proposal"
    REJECT_PROPOSAL = "reject_proposal"
    SUPERSEDE_PROPOSAL = "supersede_proposal"


class ProposalStatus(str, Enum):
    ACTIVE = "active"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


_OPAQUE_ID = re.compile(r"[a-z0-9][a-z0-9._:-]{2,127}")


def _require_opaque(value: str, label: str) -> None:
    if not isinstance(value, str) or not _OPAQUE_ID.fullmatch(value):
        raise ReviewError(f"{label} must be an opaque identifier")


@dataclass(frozen=True, slots=True)
class PrimaryReview:
    """The single blocking review for an authority-less primary candidate."""

    review_id: str
    status: ReviewStatus = ReviewStatus.ACTIVE

    def __post_init__(self) -> None:
        _require_opaque(self.review_id, "review_id")
        if not isinstance(self.status, ReviewStatus):
            raise ReviewError("status must be a ReviewStatus")


@dataclass(frozen=True, slots=True)
class RelatedProposal:
    """A non-blocking proposed authority match related to a primary review."""

    proposal_id: str
    status: ProposalStatus = ProposalStatus.ACTIVE

    def __post_init__(self) -> None:
        _require_opaque(self.proposal_id, "proposal_id")
        if not isinstance(self.status, ProposalStatus):
            raise ReviewError("status must be a ProposalStatus")


@dataclass(frozen=True, slots=True)
class ReviewCommand:
    """An opaque, idempotent command with optimistic concurrency metadata."""

    command_id: str
    actor_id: str
    expected_version: int
    action: ReviewAction
    target_id: str
    resolved_subject_id: str | None = None

    def __post_init__(self) -> None:
        _require_opaque(self.command_id, "command_id")
        _require_opaque(self.actor_id, "actor_id")
        _require_opaque(self.target_id, "target_id")
        if not isinstance(self.expected_version, int) or self.expected_version < 0:
            raise ReviewError("expected_version must be a non-negative integer")
        if not isinstance(self.action, ReviewAction):
            raise ReviewError("action must be a ReviewAction")
        if self.action is ReviewAction.RESOLVE_PRIMARY:
            if self.resolved_subject_id is None:
                raise ReviewError("resolve_primary must name the exact resolved subject")
            _require_opaque(self.resolved_subject_id, "resolved_subject_id")
        elif self.resolved_subject_id is not None:
            raise ReviewError("only resolve_primary may name a resolved subject")


@dataclass(frozen=True, slots=True)
class CommandReceipt:
    """A replay record for an already accepted command."""

    command: ReviewCommand
    resulting_version: int


@dataclass(frozen=True, slots=True)
class ReviewState:
    """An in-memory aggregate suitable for a repository adapter to persist."""

    primary: PrimaryReview
    proposals: tuple[RelatedProposal, ...] = ()
    version: int = 0
    receipts: tuple[CommandReceipt, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.version, int) or self.version < 0:
            raise ReviewError("version must be a non-negative integer")
        proposal_ids = tuple(proposal.proposal_id for proposal in self.proposals)
        if len(proposal_ids) != len(set(proposal_ids)):
            raise ReviewError("proposal IDs must be unique")
        receipt_ids = tuple(receipt.command.command_id for receipt in self.receipts)
        if len(receipt_ids) != len(set(receipt_ids)):
            raise ReviewError("command receipt IDs must be unique")


@dataclass(frozen=True, slots=True)
class ReviewResult:
    state: ReviewState
    idempotent: bool


def apply_review_command(
    state: ReviewState,
    command: ReviewCommand,
    *,
    allowed_actors: Iterable[str],
) -> ReviewResult:
    """Apply one authorized command or return its recorded idempotent result.

    Callers persist the returned aggregate atomically with its new version.  No
    database API is assumed by this module.
    """

    allowed = frozenset(allowed_actors)
    if command.actor_id not in allowed:
        raise UnauthorizedReview("actor is not permitted to review")

    for receipt in state.receipts:
        if receipt.command.command_id == command.command_id:
            if receipt.command != command:
                raise CommandIdConflict("command_id was already used with different contents")
            return ReviewResult(state, idempotent=True)

    if command.expected_version != state.version:
        raise StaleReviewCommand(
            f"expected version {command.expected_version}, current version {state.version}"
        )

    primary, proposals = _transition(state, command)
    next_version = state.version + 1
    return ReviewResult(
        replace(
            state,
            primary=primary,
            proposals=proposals,
            version=next_version,
            receipts=state.receipts + (CommandReceipt(command, next_version),),
        ),
        idempotent=False,
    )


def _transition(
    state: ReviewState, command: ReviewCommand
) -> tuple[PrimaryReview, tuple[RelatedProposal, ...]]:
    primary_actions = {ReviewAction.RESOLVE_PRIMARY, ReviewAction.SUPERSEDE_PRIMARY}
    proposal_actions = {
        ReviewAction.ACCEPT_PROPOSAL,
        ReviewAction.REJECT_PROPOSAL,
        ReviewAction.SUPERSEDE_PROPOSAL,
    }
    if command.action in primary_actions:
        if command.target_id != state.primary.review_id:
            raise InvalidReviewTransition("primary command target does not match primary review")
        if state.primary.status is not ReviewStatus.ACTIVE:
            raise InvalidReviewTransition("only an active primary review may transition")
        status = (
            ReviewStatus.RESOLVED
            if command.action is ReviewAction.RESOLVE_PRIMARY
            else ReviewStatus.SUPERSEDED
        )
        return replace(state.primary, status=status), state.proposals

    if command.action not in proposal_actions:
        raise InvalidReviewTransition("unsupported review action")
    for index, proposal in enumerate(state.proposals):
        if proposal.proposal_id == command.target_id:
            if proposal.status is not ProposalStatus.ACTIVE:
                raise InvalidReviewTransition("only an active proposal may transition")
            status = {
                ReviewAction.ACCEPT_PROPOSAL: ProposalStatus.ACCEPTED,
                ReviewAction.REJECT_PROPOSAL: ProposalStatus.REJECTED,
                ReviewAction.SUPERSEDE_PROPOSAL: ProposalStatus.SUPERSEDED,
            }[command.action]
            return state.primary, state.proposals[:index] + (replace(proposal, status=status),) + state.proposals[index + 1 :]
    raise InvalidReviewTransition("proposal command target does not exist")


@dataclass(frozen=True, slots=True)
class PublicationCandidate:
    """The minimal candidate projection needed for publication eligibility."""

    candidate_id: str
    relation: Relation
    active: bool
    identity_attested: bool = False

    def __post_init__(self) -> None:
        _require_opaque(self.candidate_id, "candidate_id")
        if not isinstance(self.relation, Relation):
            raise ReviewError("relation must be a Relation")
        if type(self.active) is not bool:
            raise ReviewError("active must be a bool")
        if type(self.identity_attested) is not bool:
            raise ReviewError("identity_attested must be a bool")


@dataclass(frozen=True, slots=True)
class PublicationEligibility:
    eligible: bool
    active_primary_count: int
    unresolved_primary_review_count: int


def publication_eligibility(
    candidates: Iterable[PublicationCandidate], reviews: Iterable[PrimaryReview]
) -> PublicationEligibility:
    """Evaluate the blocking publication invariant.

    Exactly one active primary candidate with an immutable positive identity
    attestation is required and active primary reviews must be zero. Related
    proposals are intentionally absent: they never block publication.
    """
    active_primaries = tuple(
        candidate
        for candidate in candidates
        if candidate.active and candidate.relation is Relation.PRIMARY
    )
    active_primary_count = len(active_primaries)
    unresolved_count = sum(review.status is ReviewStatus.ACTIVE for review in reviews)
    return PublicationEligibility(
        eligible=(
            active_primary_count == 1
            and active_primaries[0].identity_attested
            and unresolved_count == 0
        ),
        active_primary_count=active_primary_count,
        unresolved_primary_review_count=unresolved_count,
    )
def apply_review_command_sqlite(
    connection: sqlite3.Connection,
    candidate_id: str,
    command: ReviewCommand,
    *,
    allowed_actors: Iterable[str],
) -> ReviewResult:
    """Apply and receipt a review command in one ``BEGIN IMMEDIATE`` transaction."""

    _require_opaque(candidate_id, "candidate_id")
    command_payload = _command_payload(command)
    command_json = json.dumps(command_payload, sort_keys=True, separators=(",", ":"))

    connection.execute("BEGIN IMMEDIATE")
    try:
        receipt = connection.execute(
            """SELECT candidate_id, command_json, resulting_version
               FROM review_command_receipt WHERE command_id = ?""",
            (command.command_id,),
        ).fetchone()
        if receipt is not None:
            recorded_candidate, recorded_command, resulting_version = receipt
            if recorded_candidate != candidate_id or recorded_command != command_json:
                raise CommandIdConflict("command_id was already used with different contents")
            _validate_replayed_identity_binding(connection, candidate_id, command, resulting_version)
            state = _load_replayed_review_state(connection, candidate_id, command)
            if state.version < resulting_version:
                raise ReviewError("review aggregate is behind the recorded receipt")
            connection.commit()
            return ReviewResult(state, idempotent=True)

        state = _load_review_state(connection, candidate_id)
        result = apply_review_command(state, command, allowed_actors=allowed_actors)
        _persist_transition(connection, candidate_id, command, result.state)
        receipt_payload = {
            "command_id": command.command_id,
            "resulting_version": result.state.version,
        }
        authorize_review_transition(
            connection, candidate_id, command.command_id, result.state.version, "receipt"
        )
        connection.execute(
            """INSERT INTO review_command_receipt
               (command_id, candidate_id, command_json, receipt_json, resulting_version)
               VALUES (?, ?, ?, ?, ?)""",
            (
                command.command_id,
                candidate_id,
                command_json,
                json.dumps(receipt_payload, sort_keys=True, separators=(",", ":")),
                result.state.version,
            ),
        )
        connection.commit()
        return result
    except BaseException:
        clear_review_transition_authorization(connection)
        connection.rollback()
        raise


def _command_payload(command: ReviewCommand) -> dict[str, object]:
    return {
        "action": command.action.value,
        "actor_id": command.actor_id,
        "command_id": command.command_id,
        "expected_version": command.expected_version,
        "resolved_subject_id": command.resolved_subject_id,
        "target_id": command.target_id,
    }


def _load_review_state(connection: sqlite3.Connection, candidate_id: str) -> ReviewState:
    aggregate = connection.execute(
        "SELECT version FROM review_aggregate WHERE candidate_id = ?", (candidate_id,)
    ).fetchone()
    if aggregate is None:
        authorize_review_transition(
            connection, candidate_id, "__review_aggregate__", 0, "increment"
        )
        connection.execute(
            "INSERT INTO review_aggregate(candidate_id, version) VALUES (?, 0)", (candidate_id,)
        )
        version = 0
    else:
        version = aggregate[0]

    primaries = tuple(
        connection.execute(
            """SELECT review_identity_id, status FROM review_identity
               WHERE candidate_id = ? AND status = 'active'
               ORDER BY created_at, review_identity_id""",
            (candidate_id,),
        )
    )
    if len(primaries) != 1:
        raise InvalidReviewTransition(
            "candidate must have exactly one active primary review"
        )
    primary = primaries[0]
    proposals = tuple(
        RelatedProposal(row[0], ProposalStatus(row[1]))
        for row in connection.execute(
            """SELECT proposal_id, status FROM identity_proposal
               WHERE candidate_id = ? ORDER BY created_at, proposal_id""",
            (candidate_id,),
        )
    )
    receipts = tuple(
        CommandReceipt(
            ReviewCommand(
                command_id=payload["command_id"],
                actor_id=payload["actor_id"],
                expected_version=payload["expected_version"],
                action=ReviewAction(payload["action"]),
                target_id=payload["target_id"],
                resolved_subject_id=payload.get("resolved_subject_id"),
            ),
            row[1],
        )
        for row in connection.execute(
            """SELECT command_json, resulting_version FROM review_command_receipt
               WHERE candidate_id = ? ORDER BY resulting_version""",
            (candidate_id,),
        )
        for payload in (json.loads(row[0]),)
    )
    return ReviewState(
        primary=PrimaryReview(primary[0], ReviewStatus(primary[1])),
        proposals=proposals,
        version=version,
        receipts=receipts,
    )
def _load_replayed_review_state(
    connection: sqlite3.Connection, candidate_id: str, command: ReviewCommand
) -> ReviewState:
    """Load current state for a recorded command after its target may have closed."""

    try:
        return _load_review_state(connection, candidate_id)
    except InvalidReviewTransition:
        primary = _load_terminal_primary(connection, candidate_id, command)
        aggregate = connection.execute(
            "SELECT version FROM review_aggregate WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()
        if aggregate is None:
            raise ReviewError("review aggregate is missing")
        proposals = tuple(
            RelatedProposal(row[0], ProposalStatus(row[1]))
            for row in connection.execute(
                """SELECT proposal_id, status FROM identity_proposal
                   WHERE candidate_id = ? ORDER BY created_at, proposal_id""",
                (candidate_id,),
            )
        )
        receipts = tuple(
            CommandReceipt(
                ReviewCommand(
                    command_id=payload["command_id"],
                    actor_id=payload["actor_id"],
                    expected_version=payload["expected_version"],
                    action=ReviewAction(payload["action"]),
                    target_id=payload["target_id"],
                    resolved_subject_id=payload.get("resolved_subject_id"),
                ),
                row[1],
            )
            for row in connection.execute(
                """SELECT command_json, resulting_version FROM review_command_receipt
                   WHERE candidate_id = ? ORDER BY resulting_version""",
                (candidate_id,),
            )
            for payload in (json.loads(row[0]),)
        )
        return ReviewState(
            primary=primary,
            proposals=proposals,
            version=aggregate[0],
            receipts=receipts,
        )


def _load_terminal_primary(
    connection: sqlite3.Connection, candidate_id: str, command: ReviewCommand
) -> PrimaryReview:
    active_count = connection.execute(
        "SELECT count(*) FROM review_identity WHERE candidate_id = ? AND status = 'active'",
        (candidate_id,),
    ).fetchone()[0]
    if active_count:
        raise InvalidReviewTransition("candidate must have exactly one active primary review")
    if command.action in {ReviewAction.RESOLVE_PRIMARY, ReviewAction.SUPERSEDE_PRIMARY}:
        row = connection.execute(
            """SELECT review_identity_id, status FROM review_identity
               WHERE candidate_id = ? AND review_identity_id = ?""",
            (candidate_id, command.target_id),
        ).fetchone()
    else:
        row = connection.execute(
            """SELECT ri.review_identity_id, ri.status
               FROM identity_proposal ip
               JOIN review_identity ri
                 ON ri.candidate_id = ip.candidate_id
                AND ri.review_identity_id = ip.review_identity_id
               WHERE ip.candidate_id = ? AND ip.proposal_id = ?""",
            (candidate_id, command.target_id),
        ).fetchone()
    if row is None:
        raise InvalidReviewTransition("recorded review command target does not exist")
    return PrimaryReview(row[0], ReviewStatus(row[1]))




def _persist_transition(
    connection: sqlite3.Connection,
    candidate_id: str,
    command: ReviewCommand,
    state: ReviewState,
) -> None:
    if command.action is ReviewAction.RESOLVE_PRIMARY:
        if command.resolved_subject_id is None:
            raise ReviewError("resolve_primary must name the exact resolved subject")
        subject = connection.execute(
            "SELECT provenance_digest FROM subject WHERE subject_id = ?",
            (command.resolved_subject_id,),
        ).fetchone()
        if subject is None:
            raise InvalidReviewTransition("resolved subject does not exist")
        receipt_id = str(uuid5(NAMESPACE_URL, f"identity-link:{command.command_id}"))
        authorize_review_transition(
            connection,
            candidate_id,
            state.primary.review_id,
            state.version - 1,
            "human_review_receipt",
        )
        connection.execute(
            """INSERT INTO identity_link_receipt(
                   identity_link_receipt_id, candidate_id, subject_id, attestation_type,
                   review_identity_id, actor_id, command_id, resulting_version, authority_identity_digest)
               VALUES (?, ?, ?, 'human_review', ?, ?, ?, ?, ?)""",
            (
                receipt_id,
                candidate_id,
                command.resolved_subject_id,
                state.primary.review_id,
                command.actor_id,
                command.command_id,
                state.version,
                subject[0],
            ),
        )
        authorize_review_transition(
            connection, candidate_id, state.primary.review_id, state.version - 1, "primary_link"
        )
        connection.execute(
            """INSERT INTO candidate_subject(candidate_id, subject_id, relation, active)
               VALUES (?, ?, 'primary', 1)""",
            (candidate_id, command.resolved_subject_id),
        )
        clear_review_transition_authorization(connection)
        target_id = state.primary.review_id
        status = state.primary.status.value
        table = "review_identity"
        id_column = "review_identity_id"
    elif command.action is ReviewAction.SUPERSEDE_PRIMARY:
        target_id = state.primary.review_id
        status = state.primary.status.value
        table = "review_identity"
        id_column = "review_identity_id"
    else:
        proposal = next(
            proposal for proposal in state.proposals if proposal.proposal_id == command.target_id
        )
        target_id = proposal.proposal_id
        status = proposal.status.value
        table = "identity_proposal"
        id_column = "proposal_id"
    authorize_review_transition(
        connection, candidate_id, target_id, state.version - 1, status
    )
    connection.execute(
        f"""UPDATE {table}
            SET status = ?, resolved_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE {id_column} = ? AND candidate_id = ?""",
        (status, target_id, candidate_id),
    )
    authorize_review_transition(
        connection,
        candidate_id,
        "__review_aggregate__",
        state.version - 1,
        "increment",
    )
    updated = connection.execute(
        """UPDATE review_aggregate
           SET version = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
           WHERE candidate_id = ? AND version = ?""",
        (state.version, candidate_id, state.version - 1),
    )
    if updated.rowcount != 1:
        raise StaleReviewCommand("review aggregate changed concurrently")


def _validate_replayed_identity_binding(
    connection: sqlite3.Connection,
    candidate_id: str,
    command: ReviewCommand,
    resulting_version: int,
) -> None:
    if command.action is not ReviewAction.RESOLVE_PRIMARY:
        return
    if command.resolved_subject_id is None:
        raise ReviewError("resolve_primary replay lacks its exact subject")
    binding = connection.execute(
        """SELECT 1
           FROM identity_link_receipt ilr
           JOIN candidate_subject cs
             ON cs.candidate_id = ilr.candidate_id
            AND cs.subject_id = ilr.subject_id
            AND cs.relation = 'primary'
            AND cs.active = 1
           JOIN subject s ON s.subject_id = ilr.subject_id
           WHERE ilr.candidate_id = ?
             AND ilr.subject_id = ?
             AND ilr.review_identity_id = ?
             AND ilr.actor_id = ?
             AND ilr.command_id = ?
             AND ilr.resulting_version = ?
             AND ilr.attestation_type = 'human_review'
             AND ilr.authority_identity_digest = s.provenance_digest""",
        (
            candidate_id,
            command.resolved_subject_id,
            command.target_id,
            command.actor_id,
            command.command_id,
            resulting_version,
        ),
    ).fetchone()
    if binding is None:
        raise ReviewError("review command replay identity receipt is corrupt")
