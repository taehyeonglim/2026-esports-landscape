import contextlib
import importlib.util
import io
import json
import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


LEGACY = load_script("extract_legacy")


def budget_fixture(name):
    return json.loads((ROOT / "tests" / "fixtures" / "budget" / name).read_text())


def deep_update(target, updates):
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_update(target[key], value)
        else:
            target[key] = value


def run_budget(config, verify_at="2026-01-15T12:00:00Z"):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "budget.json"
        path.write_text(json.dumps(config))
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "budget_projection.py"),
                str(path),
                "--billing-evidence-key",
                "fixture-hmac-key",
                "--verify-at",
                verify_at,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    stream = completed.stdout if completed.stdout else completed.stderr
    return completed.returncode, json.loads(stream)


class BudgetAndLegacyTests(unittest.TestCase):
    def test_pass_v4_fixture_is_1009_scheduled_47_reserve_1056_projected_1700_headroom(self):
        config = budget_fixture("pass-v4.json")
        status, report = run_budget(config)
        self.assertEqual(status, 0)
        self.assertEqual(report["status"], config["oracle"]["status"])
        self.assertEqual(
            (
                report["minute"]["scheduled"],
                report["minute"]["retry_reserve"],
                report["minute"]["projected"],
                report["minute"]["account_headroom"],
            ),
            tuple(config["oracle"]["minute"]),
        )
        self.assertEqual(report["shared_storage"]["current_stored_limit_gb"], 10)
        self.assertEqual(report["shared_storage"]["projection_basis"], "remaining_hours")
        self.assertEqual(report["cache"]["retained_key_count"], 2)
        self.assertTrue(report["cache"]["inventory_complete"])

    def test_signed_billing_evidence_is_bound_to_budget_measurements(self):
        config = budget_fixture("pass-v4.json")
        config["account_minutes"]["limit"] = 999999
        status, report = run_budget(config)
        self.assertEqual(status, 2)
        self.assertEqual(report["status"], "HARD")
        self.assertIn("BILLING_EVIDENCE_UNVERIFIED", report["reason_codes"])

    def test_hard_v4_fixture_oracles_execute_through_cli(self):
        baseline = budget_fixture("pass-v4.json")
        hard = budget_fixture("hard-v4.json")
        for case in hard["cases"]:
            with self.subTest(name=case["name"]):
                config = copy.deepcopy(baseline)
                deep_update(config, case["override"])
                status, report = run_budget(config, hard["verify_at"])
                self.assertEqual(status, 2)
                self.assertEqual(report["status"], "HARD")
                self.assertIn(case["reason_code"], report["reason_codes"])

    def test_missing_or_unknown_kind_and_retained_cache_are_invalid(self):
        cases = (
            {"jobs": [{"name": "missing", "runs": 1, "setup_p95": 0, "batch_p95": 1}]},
            {"jobs": [{"name": "unknown", "kind": "deploy", "runs": 1, "setup_p95": 0, "batch_p95": 1}]},
            {"cache": {"inventory": [{"key": "third", "mb": 1, "role": "third", "observed_at": "2026-01-15T12:00:00Z"}]}},
        )
        for override in cases:
            with self.subTest(override=override):
                config = copy.deepcopy(budget_fixture("pass-v4.json"))
                deep_update(config, override)
                status, report = run_budget(config)
                self.assertEqual(status, 2)
                self.assertEqual(report["reason_codes"], ["BUDGET_INPUT_INVALID"])


    def test_externalized_v2_baselines_have_230_entries_and_matching_17_region_feature_collections(self):
        baseline = json.loads((ROOT / "baseline/v2/site.v2.json").read_text())
        region_geo = json.loads((ROOT / "baseline/v2/region-geo.v2.json").read_text())
        ids = LEGACY.validate_v2(baseline)
        region_ids = {region["id"] for region in baseline["regions"]}
        self.assertEqual((len(ids), len(region_ids), len(region_geo)), (230, 17, 17))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {entry["id"] for entry in baseline["entries"]})
        self.assertEqual(region_ids, set(region_geo))
        self.assertTrue(all(value.get("type") == "FeatureCollection" for value in region_geo.values()))
        self.assertEqual(
            {Path(region["geojson_ref"]).stem for region in baseline["regions"]},
            region_ids,
        )
        mismatched = json.loads(json.dumps(baseline))
        mismatched["regions"][0]["geojson_ref"] = "geo/regions/missing.geojson"
        with self.assertRaises(ValueError):
            LEGACY.validate_v2(mismatched)

    def test_legacy_extractor_uses_synthetic_temp_html_and_preserves_id_contract(self):
        entries = [{"id": f"synthetic-{index}", "name": "Synthetic"} for index in range(230)]
        regions = [{"id": f"region-{index}", "geojson_ref": f"geo/regions/region-{index}.geojson"} for index in range(17)]
        payload = {"schema_version": 2, "meta": {"entry_count": 230, "region_count": 17}, "regions": regions, "entries": entries}
        with tempfile.TemporaryDirectory() as directory:
            html = Path(directory) / "legacy.html"
            output = Path(directory) / "baseline.json"
            ids = Path(directory) / "ids.txt"
            html.write_text(f'<script id="site-data" type="application/json">{json.dumps(payload)}</script>')
            with patch.object(sys, "argv", ["extract_legacy.py", str(html), "--output", str(output), "--ids-output", str(ids)]):
                self.assertEqual(LEGACY.main(), 0)
            self.assertEqual(json.loads(output.read_text())["entries"], entries)
            self.assertEqual(ids.read_text().splitlines(), [entry["id"] for entry in entries])

    def test_legacy_extractor_accepts_externalized_v2_json_directly(self):
        baseline = ROOT / "baseline/v2/site.v2.json"
        expected = json.loads(baseline.read_text())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "baseline.json"
            report_output = io.StringIO()
            with patch.object(sys, "argv", ["extract_legacy.py", str(baseline), "--output", str(output)]), contextlib.redirect_stdout(report_output):
                self.assertEqual(LEGACY.main(), 0)
            report = json.loads(report_output.getvalue())
            self.assertEqual((report["source_format"], report["entry_count"], report["region_count"]), ("json", 230, 17))
            self.assertEqual(json.loads(output.read_text()), expected)
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                json.dumps(expected, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            )
