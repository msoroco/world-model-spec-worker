"""Diagnostic contract tests; they do not claim original Native acceptance."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from production_comparison_audit import run as compare, sha
from production_delivery_audit import run as delivery

SCRATCH = ROOT.parents[1] / ".runtime-work" / "c158196-audit-tests"
SCRATCH.mkdir(parents=True, exist_ok=True)


class AuditTest(unittest.TestCase):
    def test_production_rejects_unsealed_diagnostic_attempt(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            root = Path(temporary)
            (root / "capture-seal.json").write_text(json.dumps({
                "format": "worker-sealed-capture", "provenance_kind": "synthetic_fixture",
                "diagnostic_fixture": True, "frames": 900}) + "\n")
            with self.assertRaisesRegex(ValueError, "original Native capture"):
                delivery(ROOT.name + "__sign_within_stop", root, root)

    def test_declared_authority_pair_keeps_route_and_site_fixed(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            root = Path(temporary)
            cases = [ROOT.name + "__sign_within_stop", ROOT.name + "__yield_within"]
            attempts = [root / "left", root / "right"]
            audits = [root / "left-audit.json", root / "right-audit.json"]
            for index, attempt in enumerate(attempts):
                attempt.mkdir()
                (attempt / "capture-seal.json").write_text("{}\n")
                (attempt / "site.json").write_text(json.dumps({"map": "same"}) + "\n")
                (attempt / "routes.json").write_text(json.dumps({
                    "case_id": cases[index], "ego_approach": {"road_id": 1},
                    "counterpart_route": {"road_id": 2, "lane_id": -1,
                                           "vehicle_blueprint": "vehicle.test"}}) + "\n")
                (attempt / "devices.json").write_text(json.dumps({
                    "control_context": "stop_sign" if index == 0 else "yield_sign"}) + "\n")
                (attempt / "config.json").write_text(json.dumps({
                    "rate_hz": 20, "duration_s": 45, "cameras": [{}, {}, {}, {}]}) + "\n")
                (attempt / "original-history.json").write_text(json.dumps({
                    "case_id": cases[index], "frames": [{} for _ in range(900)]}) + "\n")
                audits[index].write_text(json.dumps({"case_id": cases[index],
                    "capture_seal_sha256": sha(attempt / "capture-seal.json"),
                    "checks": ["independent_original_review"],
                    "legal_verdict_claimed": False}) + "\n")
            result = compare("within_stop_vs_yield", *attempts, *audits)
            self.assertEqual(result["case_ids"], cases)
            (attempts[1] / "site.json").write_text('{"map":"changed"}\n')
            with self.assertRaisesRegex(ValueError, "geometry"):
                compare("within_stop_vs_yield", *attempts, *audits)
