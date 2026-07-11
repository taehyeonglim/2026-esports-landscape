import sqlite3
import json
import tempfile
import unittest
from pathlib import Path

from esports_data.db import connect
from esports_data.migrate import migrate
from esports_data.mutation import ArtifactIncompleteError, MutationCommand, MutationError, apply, queue


class MutationRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.connection = connect(Path(self.temp.name) / "control.sqlite")
        migrate(self.connection)
        for key, value in (("input_revision", "r1"), ("policy_version", "p1"), ("policy_epoch", "0")):
            self.connection.execute("INSERT INTO system_state(key, value) VALUES (?, ?)", (key, value))

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def command(self, command_id: str) -> MutationCommand:
        return MutationCommand(command_id, "test", "r1", "p1", 0, {})

    def test_parent_is_bound_once_and_replay_rejects_a_different_parent(self) -> None:
        command = self.command("parent-bound")
        backup_path = Path(self.temp.name) / "parent-bound.sqlite"
        self.assertEqual(queue(self.connection, command), "queued")
        self.assertIsNone(
            self.connection.execute(
                "SELECT parent_git_sha FROM mutation_request WHERE command_id = ?", (command.command_id,)
            ).fetchone()[0]
        )
        apply(self.connection, command, lambda *_: None, parent_git_sha="a" * 40, backup_path=backup_path)
        self.assertEqual(
            self.connection.execute(
                "SELECT parent_git_sha FROM mutation_request WHERE command_id = ?", (command.command_id,)
            ).fetchone()[0],
            "a" * 40,
        )
        with self.assertRaisesRegex(MutationError, "terminal identity"):
            apply(self.connection, command, lambda *_: None, parent_git_sha="b" * 40, backup_path=backup_path)
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE mutation_request SET parent_git_sha = ? WHERE command_id = ?",
                ("b" * 40, command.command_id),
            )

    def test_malformed_parent_is_rejected_before_queueing(self) -> None:
        for parent in ("", "A" * 40, "a" * 39, "g" * 40):
            with self.subTest(parent=parent), self.assertRaisesRegex(MutationError, "40 lowercase hexadecimal"):
                apply(
                    self.connection,
                    self.command(f"bad-parent-{len(parent)}-{parent[:1] or 'empty'}"),
                    lambda *_: None,
                    parent_git_sha=parent,
                    backup_path=Path(self.temp.name) / "bad.sqlite",
                )
        self.assertEqual(self.connection.execute("SELECT count(*) FROM mutation_request").fetchone()[0], 0)

    def test_missing_latest_checkpoint_is_recovered_without_rerunning_handler(self) -> None:
        command = self.command("missing-checkpoint")
        backup_path = Path(self.temp.name) / "missing-checkpoint.sqlite"
        calls = []
        first = apply(
            self.connection,
            command,
            lambda *_: calls.append("first"),
            parent_git_sha="a" * 40,
            backup_path=backup_path,
        )
        backup_path.unlink()
        replay = apply(
            self.connection,
            command,
            lambda *_: calls.append("rerun"),
            parent_git_sha="a" * 40,
            backup_path=backup_path,
        )
        self.assertEqual(calls, ["first"])
        self.assertEqual(first.receipt, replay.receipt)
        self.assertTrue(backup_path.exists())
        self.assertEqual(replay.checkpoint_artifact.integrity_check, ("ok",))
        self.assertEqual(replay.checkpoint_artifact.foreign_key_check, ())

    def test_truncated_checkpoint_fails_closed(self) -> None:
        command = self.command("truncated-checkpoint")
        backup_path = Path(self.temp.name) / "truncated-checkpoint.sqlite"
        apply(self.connection, command, lambda *_: None, parent_git_sha="a" * 40, backup_path=backup_path)
        backup_path.write_bytes(b"truncated")
        with self.assertRaises(ArtifactIncompleteError):
            apply(self.connection, command, lambda *_: None, parent_git_sha="a" * 40, backup_path=backup_path)

    def test_checkpoint_data_tampering_is_not_a_valid_replay(self) -> None:
        command = self.command("data-tamper")
        backup_path = Path(self.temp.name) / "data-tamper.sqlite"
        apply(
            self.connection,
            command,
            lambda db, _: db.execute(
                "INSERT INTO candidate(candidate_id, status, summary) VALUES ('checkpoint-candidate', 'review', 'original')"
            ),
            parent_git_sha="a" * 40,
            backup_path=backup_path,
        )
        artifact = sqlite3.connect(backup_path)
        try:
            artifact.execute("UPDATE candidate SET summary = 'tampered' WHERE candidate_id = 'checkpoint-candidate'")
            artifact.commit()
        finally:
            artifact.close()
        with self.assertRaises(ArtifactIncompleteError):
            apply(self.connection, command, lambda *_: None, parent_git_sha="a" * 40, backup_path=backup_path)

    def test_old_command_checkpoint_cannot_replay_after_a_following_mutation(self) -> None:
        first = self.command("first-command")
        first_backup = Path(self.temp.name) / "first.sqlite"
        apply(self.connection, first, lambda *_: None, parent_git_sha="a" * 40, backup_path=first_backup)
        apply(
            self.connection,
            self.command("second-command"),
            lambda *_: None,
            parent_git_sha="b" * 40,
            backup_path=Path(self.temp.name) / "second.sqlite",
        )
        first_backup.unlink()
        with self.assertRaisesRegex(ArtifactIncompleteError, "checkpoint artifact creation failed") as raised:
            apply(self.connection, first, lambda *_: None, parent_git_sha="a" * 40, backup_path=first_backup)
        self.assertIsInstance(raised.exception.__cause__, MutationError)
        self.assertEqual(
            str(raised.exception.__cause__),
            "only the latest applied command checkpoint may be recovered",
        )

    def test_checkpoint_recovery_uses_sequence_when_applied_timestamps_tie(self) -> None:
        first = self.command("same-clock-first")
        first_backup = Path(self.temp.name) / "same-clock-first.sqlite"
        apply(self.connection, first, lambda *_: None, parent_git_sha="a" * 40, backup_path=first_backup)
        second = self.command("same-clock-second")
        apply(
            self.connection,
            second,
            lambda *_: None,
            parent_git_sha="b" * 40,
            backup_path=Path(self.temp.name) / "same-clock-second.sqlite",
        )
        self.connection.execute("DROP TRIGGER mutation_request_terminal_immutable")
        for command_id in ("same-clock-first", "same-clock-second"):
            applied_at = "2026-01-01T00:00:00.000Z"
            self.connection.execute(
                "UPDATE mutation_request SET applied_at = ?, receipt_json = ? WHERE command_id = ?",
                (
                    applied_at,
                    json.dumps(
                        {"applied_at": applied_at, "command_id": command_id, "status": "applied"},
                        sort_keys=True,
                    ),
                    command_id,
                ),
            )
        first_backup.unlink()
        with self.assertRaisesRegex(ArtifactIncompleteError, "checkpoint artifact creation failed") as raised:
            apply(self.connection, first, lambda *_: None, parent_git_sha="a" * 40, backup_path=first_backup)
        self.assertIsInstance(raised.exception.__cause__, MutationError)
        self.assertEqual(
            str(raised.exception.__cause__),
            "only the latest applied command checkpoint may be recovered",
        )

    def test_applied_sequence_is_required_unique_and_immutable(self) -> None:
        command = self.command("sequenced-command")
        backup_path = Path(self.temp.name) / "sequenced-command.sqlite"
        apply(self.connection, command, lambda *_: None, parent_git_sha="a" * 40, backup_path=backup_path)
        self.assertEqual(
            self.connection.execute(
                "SELECT applied_sequence FROM mutation_request WHERE command_id = ?",
                (command.command_id,),
            ).fetchone()[0],
            1,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE mutation_request SET applied_sequence = 2 WHERE command_id = ?",
                (command.command_id,),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """INSERT INTO mutation_request
                   (command_id, request_kind, input_revision, policy_version, policy_epoch,
                    status, payload_json, applied_sequence)
                   VALUES ('forged-sequence', 'test', 'r1', 'p1', 0, 'queued', '{}', 2)"""
            )
