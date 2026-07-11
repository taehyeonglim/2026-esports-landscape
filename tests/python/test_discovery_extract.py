import json
import inspect
from dataclasses import asdict, replace
import socket
import tempfile
import sys
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from esports_data.discover.html_list import HtmlListError, parse_html_list
from esports_data.discover.json_list import JsonListError, parse_json_list
from esports_data.discover.rss import RssError, parse_rss_or_atom
from esports_data.discover.sitemap import SitemapError, parse_sitemap
from esports_data.db import connect
from esports_data.extract.json import ExtractResult, ExtractStatus, extract_json, facts_from_items
from esports_data.extract.pdf import extract_pdf
from esports_data.ingest import IngestError, IngestStatus, ingest_extraction
from esports_data.migrate import migrate
from esports_data.models import SubjectKind
from esports_data.registry import RegistryValidationError, SourceRegistry, load_source_registry
import esports_data.fetch as fetch
from esports_data.fetch import FetchStatus, fetch_and_process_registered


class DiscoveryAndExtractionTests(unittest.TestCase):
    base_url = "https://publisher.example.test/feed"
    salt = "synthetic-test-salt"
    @classmethod
    def setUpClass(cls):
        cls.registry = load_source_registry(
            Path(__file__).resolve().parents[2] / "config" / "sources.toml"
        )
        cls.registered_source = cls.registry.by_id("moe")

    def registered_url(self, path: str = "/notices/synthetic") -> str:
        return f"https://{self.registered_source.canonical_origin[1]}{path}"


    def test_rss_sitemap_json_and_html_return_clean_urls_and_digested_titles(self):
        cases = (
            (parse_rss_or_atom, b"<rss><channel><item><title>Public event</title><link>/event</link></item></channel></rss>"),
            (parse_sitemap, b"<urlset><url><loc>/event</loc></url></urlset>"),
            (parse_json_list, json.dumps([{ "url": "/event", "title": "Public event" }]).encode()),
            (parse_html_list, b'<a href="/event">Public event</a>'),
        )
        for parser, document in cases:
            with self.subTest(parser=parser.__name__):
                result = parser(document, base_url=self.base_url, salt=self.salt)
                self.assertEqual(len(result.entries), 1)
                self.assertEqual(result.entries[0].url, "https://publisher.example.test/event")
                self.assertNotIn("Public event", repr(result.entries[0]))

    def test_malformed_and_zero_discovery_fail_closed(self):
        self.assertEqual(parse_rss_or_atom(b"<rss", base_url=self.base_url, salt=self.salt).error, RssError.MALFORMED_XML)
        self.assertEqual(parse_sitemap(b"<urlset/>", base_url=self.base_url, salt=self.salt).error, SitemapError.EMPTY_SITEMAP)
        self.assertEqual(parse_json_list(b"{}", base_url=self.base_url, salt=self.salt).error, JsonListError.INVALID_LIST)
        self.assertEqual(parse_html_list(b"<a href='mailto:x@example.test'>x</a>", base_url=self.base_url, salt=self.salt).error, HtmlListError.EMPTY_LIST)

    def test_discovery_strips_queries_and_refuses_credentials_and_pii_titles(self):
        result = parse_json_list(json.dumps([
            {"url": "/event?token=private#fragment", "title": "minor@example.test"},
            "https://user:password@publisher.example.test/private",
        ]), base_url=self.base_url, salt=self.salt)
        self.assertEqual(len(result.entries), 1)
        self.assertEqual(result.entries[0].url, "https://publisher.example.test/event")
        self.assertIsNone(result.entries[0].title_digest)

    def test_registered_fetch_rejects_unregistered_origin_redirect(self):
        response = MagicMock()
        response.status = 302
        response.headers = {"Location": "http://127.0.0.1/private"}
        with patch("esports_data.fetch._PinnedHTTPSConnection") as connection_class, patch(
            "esports_data.fetch.socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 443))],
        ):
            connection_class.return_value.getresponse.return_value = response
            result = fetch_and_process_registered(
                self.registry, "moe", self.registered_url(), "json",
                salt=self.salt,
            )
        self.assertEqual(result.status, FetchStatus.DISALLOWED_REDIRECT)

    def test_registered_fetch_rejects_explicit_zero_port_direct_and_redirect(self):
        with patch("esports_data.fetch._PinnedHTTPSConnection") as connection_class:
            direct = fetch_and_process_registered(
                self.registry, "moe", f"https://{self.registered_source.canonical_origin[1]}:0/notices/synthetic", "json",
                salt=self.salt,
            )
        self.assertEqual(direct.status, FetchStatus.INVALID_URL)
        connection_class.assert_not_called()

        response = MagicMock()
        response.status = 302
        response.headers = {"Location": f"https://{self.registered_source.canonical_origin[1]}:0/redirect"}
        with patch("esports_data.fetch._PinnedHTTPSConnection") as connection_class, patch(
            "esports_data.fetch.socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 443))],
        ):
            connection_class.return_value.getresponse.return_value = response
            redirect = fetch_and_process_registered(
                self.registry, "moe", self.registered_url(), "json",
                salt=self.salt,
            )
        self.assertEqual(redirect.status, FetchStatus.DISALLOWED_REDIRECT)

    def test_json_extraction_blocks_malformed_zero_and_pii_without_raw_text(self):
        self.assertEqual(extract_json(b"{", salt=self.salt).status, ExtractStatus.MALFORMED)
        self.assertEqual(extract_json(b'{"facts":[]}', salt=self.salt).status, ExtractStatus.ZERO_TEXT)
        pii = extract_json(b'{"facts":[{"predicate":"school_name","value":"minor@example.test"}]}', salt=self.salt)
        self.assertEqual(pii.status, ExtractStatus.PII_BLOCKED)
        success = extract_json(b'{"facts":[{"predicate":"official_status","value":true,"evidence":"public notice"}]}', salt=self.salt)
        self.assertEqual(success.status, ExtractStatus.SUCCESS)
        self.assertIs(success.facts[0].value, True)
        self.assertNotIn("public notice", repr(success))
    def test_pdf_extraction_accepts_only_clean_synthetic_text_pages(self):
        class SyntheticPage(dict):
            def extract_text(self):
                return "Public aggregate"

        reader = SimpleNamespace(
            is_encrypted=False,
            trailer={"/Root": {}},
            pages=[SyntheticPage({"/Resources": {"/Font": {}}})],
        )
        with patch.dict(sys.modules, {"pypdf": SimpleNamespace(PdfReader=lambda _: reader)}):
            result = extract_pdf(b"synthetic-document", salt=self.salt)

        self.assertEqual(result.status, ExtractStatus.SUCCESS)
        self.assertEqual(len(result.facts), 1)
        self.assertNotIn("Public aggregate", repr(result))

    def test_pdf_extraction_rejects_unscannable_synthetic_surfaces(self):
        class SyntheticPage(dict):
            def extract_text(self):
                return "Public aggregate"

        cases = (
            ("document metadata", {"/Info": {"Author": "private@example.test"}}, {}, {}, ExtractStatus.PII_BLOCKED),
            ("XMP metadata", {"/Root": {"/Metadata": {}}}, {}, {}, ExtractStatus.PII_BLOCKED),
            ("embedded names", {"/Root": {"/Names": {"/EmbeddedFiles": {}}}}, {}, {}, ExtractStatus.PII_BLOCKED),
            ("attachment", {"/Root": {"/AF": [{}]}}, {}, {}, ExtractStatus.PII_BLOCKED),
            ("AcroForm", {"/Root": {"/AcroForm": {}}}, {}, {}, ExtractStatus.PII_BLOCKED),
            ("JavaScript action", {"/Root": {"/OpenAction": {"/S": "/JavaScript"}}}, {}, {}, ExtractStatus.PII_BLOCKED),
            ("annotation", {"/Root": {}}, {"/Annots": [{}]}, {}, ExtractStatus.PII_BLOCKED),
            ("image XObject", {"/Root": {}}, {}, {"/XObject": {"/Image": {}}}, ExtractStatus.UNSUPPORTED),
            ("unknown resource", {"/Root": {}}, {}, {"/Shading": {}}, ExtractStatus.UNSUPPORTED),
        )
        for name, trailer, page_surface, resources, expected_status in cases:
            with self.subTest(surface=name):
                page = SyntheticPage({"/Resources": {"/Font": {}, **resources}, **page_surface})
                reader = SimpleNamespace(is_encrypted=False, trailer=trailer, pages=[page])
                with patch.dict(sys.modules, {"pypdf": SimpleNamespace(PdfReader=lambda _: reader)}):
                    result = extract_pdf(b"synthetic-document", salt=self.salt)
                self.assertEqual(result.status, expected_status)
                self.assertNotIn("private@example.test", repr(result))
    def test_dtd_xml_and_deep_json_fail_closed(self):
        rss = b'<!DOCTYPE rss [<!ENTITY item "https://publisher.example.test/event">]><rss><channel><item><link>&item;</link></item></channel></rss>'
        self.assertEqual(parse_rss_or_atom(rss, base_url=self.base_url, salt=self.salt).error, RssError.MALFORMED_XML)
        deeply_nested = b'{"facts":' + (b"[" * 1_100) + (b"]" * 1_100) + b"}"
        self.assertEqual(extract_json(deeply_nested, salt=self.salt).status, ExtractStatus.MALFORMED)

    def test_json_fact_ceiling_rejects_the_first_excess_fact(self):
        facts = (
            {"predicate": "team_count", "value": 1, "evidence": "synthetic aggregate"}
            for _ in range(10_001)
        )
        self.assertEqual(
            facts_from_items(facts, salt=self.salt, fingerprint="a" * 64).status,
            ExtractStatus.OVERSIZE,
        )

    def test_registered_fetch_returns_only_digested_response_metadata(self):
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"facts":[{"predicate":"team_count","value":3,"evidence":"public aggregate"}]}'
        response.headers = {"ETag": "opaque-validator", "Last-Modified": "2026-01-01"}
        public_answer = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 443))]
        private_rebinding = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.1", 443))]
        with patch("esports_data.fetch._PinnedHTTPSConnection") as connection_class, patch(
            "esports_data.fetch.socket.getaddrinfo",
            side_effect=[public_answer, private_rebinding],
        ) as getaddrinfo:
            connection_class.return_value.getresponse.return_value = response
            result = fetch_and_process_registered(
                self.registry, "moe", self.registered_url(), "json",
                salt=self.salt,
            )
        self.assertEqual(result.status, FetchStatus.SUCCESS)
        self.assertEqual(result.extraction.status, ExtractStatus.SUCCESS)
        self.assertEqual(result.extraction.facts[0].value, 3)
        connection_class.assert_called_once_with(
            self.registered_source.canonical_origin[1],
            (socket.AF_INET, ("8.8.8.8", 443)),
            timeout=10.0,
        )
        connection_class.return_value.request.assert_called_once_with(
            "GET",
            "/notices/synthetic",
            headers={
                "Accept-Encoding": "identity",
                "Host": self.registered_source.canonical_origin[1],
                "User-Agent": "esports-data-discovery/1.0",
            },
        )
        self.assertEqual(getaddrinfo.call_count, 1)
        self.assertRegex(result.etag_digest, r"^[0-9a-f]{64}$")
        self.assertRegex(result.last_modified_digest, r"^[0-9a-f]{64}$")
        rendered = json.dumps(asdict(result))
        self.assertNotIn("opaque-validator", rendered)
        self.assertNotIn("2026-01-01", rendered)
        self.assertNotIn("body", rendered)

    def test_pinned_connection_uses_approved_ipv6_peer_and_canonical_sni(self):
        host = self.registered_source.canonical_origin[1]
        peer = (socket.AF_INET6, ("2001:4860:4860::8888", 443, 0, 0))
        raw_socket = MagicMock()
        tls_socket = MagicMock()
        context = MagicMock()
        connection = fetch._PinnedHTTPSConnection(host, peer, timeout=10.0)
        connection._context = context

        with patch("esports_data.fetch.socket.socket", return_value=raw_socket):
            context.wrap_socket.return_value = tls_socket
            connection.connect()

        raw_socket.connect.assert_called_once_with(peer[1])
        context.wrap_socket.assert_called_once_with(raw_socket, server_hostname=host)
        self.assertIs(connection.sock, tls_socket)
    def test_registered_fetch_has_no_source_record_or_callback_surface(self):
        parameters = inspect.signature(fetch_and_process_registered).parameters
        self.assertNotIn("source", parameters)
        self.assertNotIn("processor", parameters)
        forged = replace(self.registered_source, source_id="forged")
        result = fetch_and_process_registered(
            forged, "forged", self.registered_url(), "json",
            salt=self.salt,
        )
        self.assertEqual(result.status, FetchStatus.INVALID_URL)

    def test_registered_fetch_preflights_global_dns_before_extraction(self):
        cases = (
            [(0, 0, 0, "", ("127.0.0.1", 443))],
            [(0, 0, 0, "", ("8.8.8.8", 443)), (0, 0, 0, "", ("10.0.0.1", 443))],
            [],
            OSError(),
        )
        for response in cases:
            with self.subTest(response=response), patch(
                "esports_data.fetch.socket.getaddrinfo",
                side_effect=response if isinstance(response, OSError) else None,
                return_value=None if isinstance(response, OSError) else response,
            ):
                result = fetch_and_process_registered(
                    self.registry, "moe", self.registered_url(), "json", salt=self.salt,
                )
                self.assertEqual(result.status, FetchStatus.DNS_REJECTED)
                self.assertIsNone(result.extraction)

    def test_registered_fetch_never_returns_raw_decoded_or_base64_body(self):
        raw_body = b"minor@example.test c2VjcmV0QGV4YW1wbGUudGVzdA=="
        response = MagicMock()
        response.status = 200
        response.read.return_value = raw_body
        response.headers = {}
        with patch("esports_data.fetch._PinnedHTTPSConnection") as connection_class, patch(
            "esports_data.fetch.socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 443))],
        ):
            connection_class.return_value.getresponse.return_value = response
            result = fetch_and_process_registered(
                self.registry, "moe", self.registered_url(), "json",
                salt=self.salt,
            )
        rendered = json.dumps(asdict(result))
        self.assertEqual(result.extraction.status, ExtractStatus.MALFORMED)
        self.assertNotIn("minor@example.test", rendered)
        self.assertNotIn("c2VjcmV0QGV4YW1wbGUudGVzdA==", rendered)
        self.assertNotIn("body", rendered)


class CandidateFactIngestTests(unittest.TestCase):
    salt = "synthetic-test-salt"
    hint_digest = "c" * 64

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.connection = connect(Path(self.temp.name) / "control.sqlite")
        migrate(self.connection)
        self.registry_path = Path(__file__).resolve().parents[2] / "config" / "sources.toml"
        self.registry = load_source_registry(self.registry_path)
        self.source = self.registry.by_id("moe")

    def tearDown(self):
        self.connection.close()
        self.temp.cleanup()

    def registered_fetch(self, registry=None):
        registry = registry or self.registry
        source = registry.by_id("moe")
        response = MagicMock()
        response.status = 200
        response.read.return_value = (
            b'{"facts":[{"predicate":"team_count","value":3,'
            b'"evidence":"synthetic aggregate"}]}'
        )
        response.headers = {}
        with patch("esports_data.fetch._PinnedHTTPSConnection") as connection_class, patch(
            "esports_data.fetch.socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 443))],
        ):
            connection_class.return_value.getresponse.return_value = response
            return fetch_and_process_registered(
                registry,
                "moe",
                f"https://{source.canonical_origin[1]}/notices/synthetic",
                "json",
                salt=self.salt,
            )

    def ingest(self, registered_fetch):
        return ingest_extraction(
            self.connection,
            registry=self.registry,
            registered_fetch=registered_fetch,
            retrieved_at="2026-01-01T00:00:00Z",
            salt=self.salt,
            proposed_kind=SubjectKind.SCHOOL,
            hint_digest=self.hint_digest,
            reason_code="authority_key_missing",
        )

    def count(self, table: str) -> int:
        return self.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    def ingest_side_counts(self) -> dict[str, int]:
        return {
            table: self.count(table)
            for table in (
                "source",
                "source_revision",
                "candidate",
                "review_identity",
                "review_item",
                "candidate_fact",
            )
        }


    def test_ingest_requires_attested_registered_fetch_not_raw_extractor_inputs(self):
        parameters = inspect.signature(ingest_extraction).parameters
        for forbidden in ("source_id", "fetched_url", "extraction", "fetch_fingerprint"):
            self.assertNotIn(forbidden, parameters)
        with self.assertRaises(TypeError):
            ingest_extraction(
                self.connection,
                registry=self.registry,
                retrieved_at="2026-01-01T00:00:00Z",
                salt=self.salt,
                proposed_kind=SubjectKind.SCHOOL,
                hint_digest=self.hint_digest,
                reason_code="authority_key_missing",
            )

    def test_manually_constructed_and_replaced_receipts_reject_before_transaction(self):
        valid = self.registered_fetch()
        manual = type(valid)(
            valid.status,
            valid.status_code,
            valid.etag_digest,
            valid.last_modified_digest,
            valid.extraction,
            valid.registry_hash,
            valid.source_id,
            valid.canonical_origin,
            valid.url_path_digest,
            valid.extractor_kind,
            valid.extractor_version,
            valid.extraction_fingerprint,
        )
        for forged in (manual, replace(valid, source_id="seoul")):
            with self.subTest(forged=forged):
                with self.assertRaises(IngestError):
                    self.ingest(forged)
                self.assertEqual(self.count("source"), 0)

    def test_registry_mismatch_rejects_before_transaction(self):
        receipt = self.registered_fetch()
        other_registry = load_source_registry(self.registry_path)
        with self.assertRaises(IngestError):
            ingest_extraction(
                self.connection,
                registry=other_registry,
                registered_fetch=receipt,
                retrieved_at="2026-01-01T00:00:00Z",
                salt=self.salt,
                proposed_kind=SubjectKind.SCHOOL,
                hint_digest=self.hint_digest,
                reason_code="authority_key_missing",
            )
        self.assertEqual(self.count("source"), 0)

    def test_valid_registered_fetch_ingests_only_review_candidate_facts(self):
        result = self.ingest(self.registered_fetch())
        self.assertEqual(result.status, IngestStatus.INSERTED)
        self.assertEqual(self.count("subject"), 0)
        self.assertEqual(self.count("candidate_fact"), 1)
        self.assertEqual(self.count("source_revision"), 1)

    def test_duplicate_attested_replay_is_a_no_op(self):
        receipt = self.registered_fetch()
        first = self.ingest(receipt)
        duplicate = self.ingest(receipt)
        self.assertEqual(first.status, IngestStatus.INSERTED)
        self.assertEqual(duplicate.status, IngestStatus.DUPLICATE)
        self.assertEqual(duplicate.revision_id, first.revision_id)
        self.assertEqual(self.count("candidate"), 1)
        self.assertEqual(self.count("candidate_fact"), 1)


    def test_direct_source_registry_constructor_enforces_core_allowlist(self):
        with self.assertRaises(RegistryValidationError):
            SourceRegistry((self.source,))

    def test_ingest_accepts_clean_string_and_rejects_nested_pii_before_persistence(self):
        clean_receipt = self.registered_fetch()
        clean_fact = replace(
            clean_receipt.extraction.facts[0],
            predicate="document_text_digest",
            value="a" * 64,
        )
        object.__setattr__(clean_receipt.extraction, "facts", (clean_fact,))
        result = self.ingest(clean_receipt)
        self.assertEqual(result.status, IngestStatus.INSERTED)
        self.assertEqual(self.count("candidate_fact"), 1)

        for label, value in (
            ("nested value", {"nested": ["minor@example.test"]}),
            ("dict key", {"minor@example.test": "public aggregate"}),
        ):
            with self.subTest(label=label):
                pii_receipt = self.registered_fetch()
                nested_fact = replace(
                    pii_receipt.extraction.facts[0],
                    predicate="official_status",
                    value=value,
                )
                object.__setattr__(pii_receipt.extraction, "facts", (nested_fact,))
                before_counts = self.ingest_side_counts()
                with self.assertRaises(IngestError):
                    self.ingest(pii_receipt)
                self.assertEqual(self.ingest_side_counts(), before_counts)

    def test_non_core_clone_config_is_rejected_despite_approval_reason(self):
        clone = """
[[source]]
id = "discovery-clone"
name = "Discovery clone"
tier = "discovery"
adapter = "official_website"
access_basis = "official_public_website"
owner = "test"
slo_tier = "standard"
active = true
endpoint = "https://www.moe.go.kr/discovery"
publisher_id = "moe"
control_cluster = "moe-national-control"
origin_cluster = "moe-public-origin"
authority_scopes = ["national:program"]
approval_reason = "not an allowlist"
"""
        path = Path(self.temp.name) / "non-core.toml"
        path.write_text(self.registry_path.read_text() + clone)
        with self.assertRaises(RegistryValidationError) as error:
            load_source_registry(path)
        self.assertIn("compiled 18-source core allowlist", str(error.exception))