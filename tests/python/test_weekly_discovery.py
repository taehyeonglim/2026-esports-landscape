from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from esports_data.review_discovery import review
from esports_data.weekly_discovery import (
    DiscoveredLink,
    Surface,
    bootstrap_seen,
    canonicalize_url,
    merge_discovery,
    parse_feed,
    parse_homepage,
    title_digest,
)


ROOT = Path(__file__).parents[2]


class WeeklyDiscoveryTests(unittest.TestCase):
    def test_canonicalization_preserves_identity_and_removes_tracking(self):
        first = canonicalize_url("https://EXAMPLE.com/board/view.do?nttSn=42&utm_source=x&ref=archive#part")
        second = canonicalize_url("https://example.com/board/view.do?nttSn=43")
        self.assertEqual(first, "https://example.com/board/view.do?nttSn=42&ref=archive")
        self.assertNotEqual(first, second)
        self.assertIsNone(canonicalize_url("http://example.com/post/42"))
        self.assertIsNone(canonicalize_url("https://user@example.com/post/42"))

    def test_homepage_and_feed_keep_only_relevant_public_links(self):
        surface = Surface("fixture", "homepage", "https://example.com/")
        homepage = b"""
          <html><head><link rel="alternate" type="application/rss+xml" href="/feed.xml"></head>
          <body><a href="/post?id=42&utm_medium=social">School esports event</a>
          <a href="/lunch">Lunch</a></body></html>
        """
        links, feeds = parse_homepage(homepage, surface)
        self.assertEqual([link.url for link in links], ["https://example.com/post?id=42"])
        self.assertEqual(feeds, ("https://example.com/feed.xml",))
        self.assertNotIn("School esports event", repr(links))

        feed = """<?xml version="1.0"?><rss><channel><item>
          <title>학교 e스포츠 대회</title><link>https://example.com/news?article=77&amp;utm_campaign=x</link>
        </item><item><title>급식 안내</title><link>https://example.com/lunch</link></item></channel></rss>""".encode()
        feed_links = parse_feed(feed, Surface("fixture-feed", "rss", "https://example.com/feed.xml"))
        self.assertEqual([link.url for link in feed_links], ["https://example.com/news?article=77"])

    def test_merge_skips_seen_url_and_flags_matching_title(self):
        old_url = "https://example.com/post?id=42"
        digest = title_digest("학교 e스포츠 대회")
        seen = {
            "canonicalization_version": 1,
            "items": [{
                "canonical_url": old_url,
                "decision": "accepted",
                "entry_ids": ["entry-1"],
                "first_seen_at": "2026-07-19",
                "title_sha256": [digest],
                "url_sha256": sha256(old_url.encode()).hexdigest(),
            }],
            "schema_version": 1,
        }
        candidates = {"candidates": [], "schema_version": 1}
        counts = merge_discovery(seen, candidates, (
            DiscoveredLink("source-a", old_url, digest),
            DiscoveredLink("source-b", "https://example.com/post?id=43", digest),
        ), discovered_at="2026-07-20")
        self.assertEqual(counts, {"discovered": 2, "duplicates": 1, "new_candidates": 1})
        self.assertTrue(candidates["candidates"][0]["possible_duplicate"])
        self.assertEqual(seen["items"][1]["decision"], "needs_review")

    def test_bootstrap_is_idempotent_and_review_decision_stays_in_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = root / "site.json"
            seen_path = root / "seen.json"
            candidates_path = root / "candidates.json"
            site.write_text(json.dumps({"entries": [{
                "id": "entry-1", "name": "학교 e스포츠", "source": "자료 https://example.com/post?id=42"
            }]}), encoding="utf-8")
            seen = {"canonicalization_version": 1, "items": [], "schema_version": 1}
            self.assertEqual(bootstrap_seen(site, seen, imported_at="2026-07-19"), 1)
            self.assertEqual(bootstrap_seen(site, seen, imported_at="2026-07-19"), 0)
            new_url = "https://example.com/post?id=43"
            candidates = {"candidates": [], "schema_version": 1}
            merge_discovery(seen, candidates, (
                DiscoveredLink("source", new_url, title_digest("새 e스포츠 자료")),
            ), discovered_at="2026-07-20")
            seen_path.write_text(json.dumps(seen), encoding="utf-8")
            candidates_path.write_text(json.dumps(candidates), encoding="utf-8")
            candidate_id = candidates["candidates"][0]["id"]
            result = review(
                candidate_id, "rejected", entry_id=None, reviewed_at="2026-07-21T00:00:00Z",
                site_path=site, seen_path=seen_path, candidates_path=candidates_path,
            )
            self.assertEqual(result["decision"], "rejected")
            ledger = json.loads(seen_path.read_text(encoding="utf-8"))
            self.assertEqual(next(item for item in ledger["items"] if item["canonical_url"] == new_url)["decision"], "rejected")


if __name__ == "__main__":
    unittest.main()
