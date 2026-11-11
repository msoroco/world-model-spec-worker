"""Independent comparison checks on retained source-shaped CPU packets."""
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from comparison_audit import audit_group

FILES = ("motion_history.jsonl", "video_frames.jsonl", "trace.jsonl",
         "capture/evidence.jsonl", "turn_history.jsonl", "curve_context.json")
GROUPS = {
    "curve_visibility_boundary": (
        ("", "curve", "short_of_500ft"), ("-at", "curve", "at_500ft"),
        ("-beyond", "curve", "beyond_500ft")),
    "crest_visibility_boundary": (
        ("-crest-short", "crest", "short_of_500ft"),
        ("-crest-at", "crest", "at_500ft"),
        ("-crest-beyond", "crest", "beyond_500ft"))}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def prepare(root, suffix, feature, probe):
    root.mkdir()
    config_source = PACKAGE / ("config" + suffix + ".json")
    site_source = PACKAGE / ("diagnostic-site" + suffix + ".json")
    shutil.copyfile(config_source, root / "config.json")
    shutil.copyfile(site_source, root / site_source.name)
    sources = PACKAGE / ("diagnostic-sources" + suffix)
    for name in FILES:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sources / name, target)
    config = json.loads((root / "config.json").read_text())
    assert config["selected_case_id"].endswith("__" + feature + "__" + probe)
    names = ("config.json", site_source.name, *FILES)
    dump(root / "result.json", {"case_id": config["selected_case_id"],
        "provenance_kind": "synthetic_fixture", "physical_acceptance_claimed": False,
        "source_evidence_hashes": {name: sha(root / name) for name in names}})
    return root


class ComparisonAuditTests(unittest.TestCase):
    def test_curve_and_crest_three_probe_source_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            for group, specs in GROUPS.items():
                attempts = [prepare(Path(temp) / (group + str(i)), *spec)
                            for i, spec in enumerate(specs)]
                report = audit_group(group, attempts, diagnostic=True)
                self.assertTrue(report["software_checks_passed"])
                self.assertFalse(report["passed"])
                self.assertLess(report["source_horizon_m"]["short_of_500ft"], 152.4)
                self.assertEqual(report["source_horizon_m"]["at_500ft"], 152.4)
                self.assertGreater(report["source_horizon_m"]["beyond_500ft"], 152.4)

    def test_missing_rays_and_changed_fixed_camera_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            attempts = [prepare(Path(temp) / str(i), *spec)
                        for i, spec in enumerate(GROUPS["curve_visibility_boundary"])]
            rays = attempts[1] / "capture/evidence.jsonl"
            original = rays.read_text()
            rays.write_text("\n".join(original.splitlines()[1:]) + "\n")
            with self.assertRaisesRegex(ValueError, "source hash changed"):
                audit_group("curve_visibility_boundary", attempts, diagnostic=True)
            rays.write_text(original)
            root = attempts[1]
            config = json.loads((root / "config.json").read_text())
            site_path = root / config["site_source"]["path"]
            site = json.loads(site_path.read_text())
            site["camera_poses"]["overview"][2] += 3
            dump(site_path, site)
            config["site_source"]["sha256"] = sha(site_path)
            dump(root / "config.json", config)
            motion = [json.loads(line) for line in (root / "motion_history.jsonl").read_text().splitlines()]
            for row in motion:
                row["site_source_sha256"] = config["site_source"]["sha256"]
            (root / "motion_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in motion))
            context = json.loads((root / "curve_context.json").read_text())
            context["site_source_sha256"] = config["site_source"]["sha256"]
            dump(root / "curve_context.json", context)
            result = json.loads((root / "result.json").read_text())
            for name in (site_path.name, "config.json", "motion_history.jsonl", "curve_context.json"):
                result["source_evidence_hashes"][name] = sha(root / name)
            dump(root / "result.json", result)
            with self.assertRaisesRegex(ValueError, "Fixed comparison condition differs: site_fixed"):
                audit_group("curve_visibility_boundary", attempts, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
