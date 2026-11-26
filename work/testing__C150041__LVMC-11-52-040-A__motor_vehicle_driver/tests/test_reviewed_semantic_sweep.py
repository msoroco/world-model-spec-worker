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

    def test_duplicate_selected_case_rejected(self):
        altered = copy.deepcopy(self.proposal)
        altered["cases"].append(copy.deepcopy(next(case for case in altered["cases"]
            if case["case_id"].endswith("__park_parallel_lawful"))))
        with self.assertRaisesRegex(ValueError, "exactly six selected cases"):
            expand(altered, self.packets["park"], self.packets["stand"])

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

    def test_duplicate_rebound_case_and_candidate_rejected(self):
        rebound = self.root / "rebound"
        rebind(self.packets["park"], self.packets["stand"], rebound)
        expanded = expand(self.proposal, self.packets["park"], self.packets["stand"])
        source_path = rebound / "rebound-manifest.json"
        original = source_path.read_text()
        source = json.loads(original)
        source["cases"].append(copy.deepcopy(source["cases"][0]))
        source_path.write_text(json.dumps(source) + "\n")
        with self.assertRaisesRegex(ValueError, "selected sweep and rebound manifest differ"):
            bind_rebound(expanded, rebound)
        source_path.write_text(original)
        source = json.loads(original)
        source["cases"][0]["variants"].append(copy.deepcopy(source["cases"][0]["variants"][0]))
        source_path.write_text(json.dumps(source) + "\n")
        with self.assertRaisesRegex(ValueError, "candidate set differs"):
            bind_rebound(expanded, rebound)


if __name__ == "__main__":
    unittest.main()
