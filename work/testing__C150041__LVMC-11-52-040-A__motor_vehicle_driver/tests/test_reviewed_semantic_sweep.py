"""A fake Native map tests the source join, without certifying a real site."""
import copy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewed_semantic_sweep import bind_rebound, expand
from rebind_reviewed_execution import rebind
from test_bind_reviewed_site import pair


class ReviewedSemanticSweepTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work" / "c150041-reviewed-sweep-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packets = pair(self.root)
        self.proposal = json.loads((ROOT / "proposals/cases.json").read_text())

    def test_exact_alternatives_and_fixed_source_join(self):
        result = expand(self.proposal, self.packets["park"], self.packets["stand"])
        sweep = result["sweep_specs"][0]
        rows = sweep["case_measurements"]
        self.assertTrue(result["sweeps_expanded"])
        self.assertEqual(len(rows), 6)
        self.assertEqual({row["activity"] for row in rows}, {"park", "stand"})
        self.assertEqual({row["engineering_angle_request_deg"] for row in rows}, {0, 30})
        self.assertEqual({row["heading_request"] for row in rows}, {"lawful", "reverse"})
        self.assertEqual(len(set(row["target_center_xy_m"][0] for row in rows)), 1)
        self.assertTrue(all(row["legal_judgment"] == "unresolved" for row in rows))
        self.assertTrue(all(row["actual_motion_reviewed"] is False for row in rows))

    def test_changed_case_and_stale_original_source_rejected(self):
        altered = copy.deepcopy(self.proposal)
        selected = next(case for case in altered["cases"] if
                        case["case_id"].endswith("__park_angled_lawful"))
        selected["variable_assignments"]["orientation_request"]["value"] = "parallel"
        with self.assertRaisesRegex(ValueError, "selected case differs"):
            expand(altered, self.packets["park"], self.packets["stand"])
        source = self.packets["stand"].parent / "reviewed_sources/activity.txt"
        source.write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "source hash changed"):
            expand(self.proposal, self.packets["park"], self.packets["stand"])

    def test_six_selected_manifest_bindings_and_tamper_rejection(self):
        rebound = self.root / "rebound"
        rebind(self.packets["park"], self.packets["stand"], rebound)
        expanded = expand(self.proposal, self.packets["park"], self.packets["stand"])
        bound = bind_rebound(expanded, rebound)["selected_rebound_binding"]
        self.assertEqual(len(bound["cases"]), 6)
        self.assertTrue(all({item["candidate"] for item in row["candidates"]}
                            == {"primary", "fallback1"} for row in bound["cases"]))
        manifest_path = rebound / "execution-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["cases"][0]["candidates"][0]["construction_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest) + "\n")
        with self.assertRaisesRegex(ValueError, "construction hash"):
            bind_rebound(expanded, rebound)


if __name__ == "__main__":
    unittest.main()
