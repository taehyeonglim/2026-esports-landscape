"""Bare-repository coverage for mutation promotion crash outcomes."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from esports_data.git_mutation import PromotionError, promote_mutation


class MutationPromotionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.remote = root / "remote.git"
        self.worktree = root / "worktree"
        self._run("git", "init", "--bare", str(self.remote), cwd=root)
        self._run("git", "clone", str(self.remote), str(self.worktree), cwd=root)
        self._run("git", "config", "user.email", "test@example.invalid")
        self._run("git", "config", "user.name", "Test")
        (self.worktree / "README").write_text("base\n")
        self._run("git", "add", "README")
        self._run("git", "commit", "-m", "base")
        self._run("git", "branch", "-M", "main")
        self._run("git", "push", "origin", "main")
        self._run("git", "checkout", "-b", "candidate")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _run(self, *arguments: str, cwd: Path | None = None) -> str:
        return subprocess.run(arguments, cwd=cwd or self.worktree, check=True, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()

    def _write_database(
        self,
        *,
        parent: str | None = None,
        status: str = "applied",
        applied_at: str | None = "2026-07-11T00:00:00.000Z",
        receipt_status: str = "applied",
        receipt_applied_at: str | None = "2026-07-11T00:00:00.000Z",
    ) -> None:
        parent = self._run("git", "rev-parse", "main") if parent is None else parent
        database = self.worktree / "control.sqlite"
        if database.exists():
            database.unlink()
        connection = sqlite3.connect(database)
        connection.execute(
            "CREATE TABLE mutation_request ("
            "command_id TEXT, status TEXT, receipt_json TEXT, applied_at TEXT, parent_git_sha TEXT)"
        )
        applied = {
            "command_id": "command-001",
            "status": receipt_status,
            "applied_at": receipt_applied_at,
        }
        connection.execute(
            "INSERT INTO mutation_request VALUES (?, ?, ?, ?, ?)",
            ("command-001", status, json.dumps(applied), applied_at, parent),
        )
        connection.commit()
        connection.close()

    def _write_receipt(self, *, parent: str | None = None, bad_hash: bool = False) -> None:
        parent = self._run("git", "rev-parse", "main") if parent is None else parent
        digest = sha256((self.worktree / "control.sqlite").read_bytes()).hexdigest()
        receipt = {
            "command_id": "command-001", "parent_git_sha": parent, "output_revision": "r1",
            "sqlite_file_sha256": "0" * 64 if bad_hash else digest, "policy_hash": "0" * 64,
            "correction_epoch": 0, "stop_epoch": 0, "schema_sha256": "0" * 64,
            "migration_sha256": "0" * 64, "changed_file_sha256": {"control.sqlite": digest},
        }
        (self.worktree / "receipt.json").write_text(json.dumps(receipt))

    def _candidate(self, *, bad_hash: bool = False, extra: bool = False) -> str:
        parent = self._run("git", "rev-parse", "main")
        self._write_database(parent=parent)
        self._write_receipt(parent=parent, bad_hash=bad_hash)
        if extra:
            (self.worktree / "unexpected.py").write_text("raise RuntimeError\n")
        self._run("git", "add", ".")
        self._run("git", "commit", "-m", "candidate")
        candidate = self._run("git", "rev-parse", "HEAD")
        self._run("git", "push", "origin", "candidate")
        return candidate

    def _promote(self):
        return promote_mutation(candidate_ref="refs/heads/candidate", target_ref="refs/heads/main",
                                database_path="control.sqlite", receipt_path="receipt.json",
                                command_id="command-001")

    def test_normal_promotion_and_exact_duplicate_are_completed(self) -> None:
        candidate = self._candidate()
        with patch("esports_data.git_mutation.subprocess.run", wraps=subprocess.run) as run:
            # The coordinator operates from its trusted checkout, not candidate code.
            with _working_directory(self.worktree):
                self.assertEqual(self._promote().outcome, "completed")
                self.assertEqual(self._promote().outcome, "completed")
        self.assertEqual(self._run("git", "--git-dir", str(self.remote), "rev-parse", "main"), candidate)
        self.assertTrue(run.called)

    def test_completed_replay_still_validates_command_and_artifact_identity(self) -> None:
        self._candidate()
        with _working_directory(self.worktree):
            self.assertEqual(self._promote().outcome, "completed")
            with self.assertRaises(PromotionError):
                promote_mutation(
                    candidate_ref="refs/heads/candidate",
                    target_ref="refs/heads/main",
                    database_path="missing.sqlite",
                    receipt_path="missing-receipt.json",
                    command_id="attacker-command",
                )

    def test_stale_advancement_is_rejected(self) -> None:
        self._candidate()
        self._run("git", "checkout", "main")
        (self.worktree / "README").write_text("advanced\n")
        self._run("git", "commit", "-am", "advance")
        self._run("git", "push", "origin", "main")
        with _working_directory(self.worktree), self.assertRaises(PromotionError):
            self._promote()

    def test_extra_code_is_rejected(self) -> None:
        self._candidate(extra=True)
        with _working_directory(self.worktree), self.assertRaises(PromotionError):
            self._promote()

    def test_wrong_database_hash_is_rejected(self) -> None:
        self._candidate(bad_hash=True)
        with _working_directory(self.worktree), self.assertRaises(PromotionError):
            self._promote()

    def test_database_parent_must_match_target_parent(self) -> None:
        parent = self._run("git", "rev-parse", "main")
        stale_parent = "1" * 40
        self._write_database(parent=stale_parent)
        self._write_receipt(parent=parent)
        self._run("git", "add", ".")
        self._run("git", "commit", "-m", "stale database parent")
        self._run("git", "push", "origin", "candidate")
        with _working_directory(self.worktree), self.assertRaises(PromotionError):
            self._promote()

    def test_terminal_database_receipt_must_match_status_and_applied_at(self) -> None:
        parent = self._run("git", "rev-parse", "main")
        self._write_database(parent=parent, receipt_applied_at="2026-07-11T00:00:01.000Z")
        self._write_receipt(parent=parent)
        self._run("git", "add", ".")
        self._run("git", "commit", "-m", "mismatched terminal receipt")
        self._run("git", "push", "origin", "candidate")
        with _working_directory(self.worktree), self.assertRaises(PromotionError):
            self._promote()

    def test_stale_external_receipt_parent_is_rejected(self) -> None:
        parent = self._run("git", "rev-parse", "main")
        stale_parent = "2" * 40
        self._write_database(parent=parent)
        self._write_receipt(parent=stale_parent)
        self._run("git", "add", ".")
        self._run("git", "commit", "-m", "stale external receipt")
        self._run("git", "push", "origin", "candidate")
        with _working_directory(self.worktree), self.assertRaises(PromotionError):
            self._promote()

    def test_one_sided_database_or_receipt_candidate_is_rejected(self) -> None:
        parent = self._run("git", "rev-parse", "main")
        self._write_database(parent=parent)
        self._run("git", "add", "control.sqlite")
        self._run("git", "commit", "-m", "database only")
        self._run("git", "push", "origin", "candidate")
        with _working_directory(self.worktree), self.assertRaises(PromotionError):
            self._promote()

        self._run("git", "checkout", "-B", "candidate", "main")
        self._write_database(parent=parent)
        self._write_receipt(parent=parent)
        self._run("git", "add", ".")
        self._run("git", "commit", "-m", "baseline artifacts")
        self._run("git", "checkout", "main")
        self._run("git", "merge", "--ff-only", "candidate")
        self._run("git", "push", "origin", "main")
        new_parent = self._run("git", "rev-parse", "main")
        self._run("git", "checkout", "-B", "candidate", "main")
        self._write_receipt(parent=new_parent)
        self._run("git", "add", "receipt.json")
        self._run("git", "commit", "-m", "receipt only")
        self._run("git", "push", "--force", "origin", "candidate")
        with _working_directory(self.worktree), self.assertRaises(PromotionError):
            self._promote()

    def test_split_commit_database_and_receipt_candidate_is_rejected(self) -> None:
        parent = self._run("git", "rev-parse", "main")
        self._write_database(parent=parent)
        self._run("git", "add", "control.sqlite")
        self._run("git", "commit", "-m", "database split")
        database_commit = self._run("git", "rev-parse", "HEAD")
        self._run("git", "checkout", "main")
        self._run("git", "merge", "--ff-only", database_commit)
        self._run("git", "push", "origin", "main")
        self._run("git", "checkout", "candidate")
        self._write_receipt(parent=parent)
        self._run("git", "add", "receipt.json")
        self._run("git", "commit", "-m", "receipt split")
        self._run("git", "push", "origin", "candidate")
        with _working_directory(self.worktree), self.assertRaises(PromotionError):
            self._promote()
    def test_wrong_parent_is_rejected(self) -> None:
        (self.worktree / "noise.txt").write_text("not a paired artifact\n")
        self._run("git", "add", "noise.txt")
        self._run("git", "commit", "-m", "intermediate")
        self._candidate()
        with _working_directory(self.worktree), self.assertRaises(PromotionError):
            self._promote()

    def test_push_ack_loss_is_completed_when_remote_contains_candidate(self) -> None:
        candidate = self._candidate()
        from esports_data import git_mutation
        original = git_mutation._git

        def lost_ack(arguments, *, check=True):
            result = original(arguments, check=check)
            return "" if arguments[0] == "push" else result

        with _working_directory(self.worktree), patch.object(git_mutation, "_git", side_effect=lost_ack):
            self.assertEqual(self._promote().outcome, "completed")
        self.assertEqual(self._run("git", "--git-dir", str(self.remote), "rev-parse", "main"), candidate)


class _working_directory:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.previous: Path | None = None

    def __enter__(self) -> None:
        import os
        self.previous = Path.cwd()
        os.chdir(self.path)

    def __exit__(self, *unused: object) -> None:
        import os
        os.chdir(self.previous)
