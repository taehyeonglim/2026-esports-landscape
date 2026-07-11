import sqlite3
import unittest

from esports_data.mutation import MutationCommand, PiiPersistenceError, queue
from esports_data.pii import PiiKind, scan_text, scan_url
from esports_data.sanitize import (
    InvalidExternalValueError,
    UnsupportedFieldError,
    sanitize_external_values,
    sanitize_url,
)


class FoundationPrivacyTests(unittest.TestCase):
    def test_all_six_text_pii_paths_are_detected(self):
        cases = {
            PiiKind.PHONE: "010-1234-5678",
            PiiKind.EMAIL: "minor@example.test",
            PiiKind.ACCOUNT_HANDLE: "@student_01",
            PiiKind.STUDENT_NAME_MARKER: "student name: Synthetic",
            PiiKind.PHOTO_CAPTION: "photo caption: Synthetic",
            PiiKind.PRECISE_ADDRESS: "123 Example Street",
        }
        for kind, value in cases.items():
            with self.subTest(kind=kind):
                self.assertIn(kind, {finding.kind for finding in scan_text(value).findings})

    def test_allowlist_is_exact_case_insensitive_not_a_general_bypass(self):
        self.assertTrue(scan_text("minor@example.test", allowlist=["MINOR@EXAMPLE.TEST"]).is_clean)
        self.assertFalse(scan_text("other@example.test", allowlist=["minor@example.test"]).is_clean)

    def test_url_query_and_fragment_are_blocked_unless_full_url_allowlisted(self):
        url = "https://example.test/path?token=synthetic#private"
        self.assertEqual(scan_url(url).findings[0].kind, PiiKind.URL_QUERY_FRAGMENT)
        self.assertTrue(scan_url(url, allowlist=[url]).is_clean)
        self.assertIn(PiiKind.URL_QUERY_FRAGMENT, {item.kind for item in scan_text(url).findings})

    def test_queue_rejects_pii_in_nested_payload_before_persistence(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.execute("CREATE TABLE mutation_request (command_id TEXT PRIMARY KEY, request_kind TEXT, input_revision TEXT, policy_version TEXT, policy_epoch INTEGER, status TEXT, payload_json TEXT)")
        command = MutationCommand("synthetic-command", "test", "r1", "p1", 0, {"nested": ["minor@example.test"]})
        with self.assertRaises(PiiPersistenceError):
            queue(connection, command)
        self.assertIsNone(connection.execute("SELECT 1 FROM mutation_request").fetchone())
    def test_sanitizers_require_salt_and_preserve_host_only_urls_with_empty_mapping(self):
        with self.assertRaises(InvalidExternalValueError):
            sanitize_url("https://publisher.example.test", salt="")
        with self.assertRaises(InvalidExternalValueError):
            sanitize_url("https://publisher.example.test", salt=b"")
        host_only = sanitize_url("https://Publisher.Example.Test", salt="synthetic-salt")
        self.assertEqual((host_only.value, host_only.path_digest), ("https://publisher.example.test", None))
        default_https_port = sanitize_url("https://Publisher.Example.Test:443/path", salt="synthetic-salt")
        self.assertEqual(default_https_port.value, "https://publisher.example.test")
        default_http_port = sanitize_url("http://Publisher.Example.Test:80/path", salt="synthetic-salt")
        self.assertEqual(default_http_port.value, "http://publisher.example.test")
        for blocked in (
            "https://",
            "https://publisher.example.test:0/path",
            "https://publisher.example.test:8443/path",
            "http://publisher.example.test:443/path",
            "https://publisher.example.test:bad/path",
            "https://publisher.example.test:99999/path",
        ):
            with self.subTest(blocked=blocked):
                with self.assertRaises(InvalidExternalValueError):
                    sanitize_url(blocked, salt="synthetic-salt")
        self.assertEqual(sanitize_external_values({}, salt="synthetic-salt"), {})
    def test_unknown_external_field_error_does_not_reflect_the_key(self):
        pii_bearing_key = "minor@example.test"
        with self.assertRaises(UnsupportedFieldError) as caught:
            sanitize_external_values({pii_bearing_key: "value"}, salt="synthetic-salt")
        self.assertEqual(str(caught.exception), "unsupported_external_field")
        self.assertNotIn(pii_bearing_key, str(caught.exception))
