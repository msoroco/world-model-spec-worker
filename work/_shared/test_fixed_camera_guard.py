"""Source-shaped CPU probes for the queued fixed-camera comparison guard."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixed_camera_guard import check, effective_plan


CASES = (
    ("testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator",
     "speed_under_clear_conditions"),
    ("testing__C188132__LVMC-11-30-060-B__pedestrian", "entry_timing"),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attempt(path, assignment, case, candidate):
    manifest_path = ROOT / "work" / assignment / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    entry = next(row for row in manifest["cases"] if row["case_id"] == case)
    selected = ({"id": "primary", "construction": entry["construction"],
                 "construction_sha256": entry["construction_sha256"]}
                if candidate == "primary" else
                next(row for row in entry["candidates"] if row["id"] == candidate))
    construction = json.loads((manifest_path.parent / selected["construction"]).read_text())
    path.mkdir()
    (path / "construction.json").write_text(json.dumps(construction))
    camera = next(row["content"] for row in construction["files"]
                  if row["path"] == "native_capture.py")
    (path / "native_capture.py").write_text(camera)
    for item in construction["files"]:
        if item["path"] == "scene.json":
            (path / "scene.json").write_text(item["content"])
    (path / "candidate-selection.json").write_text(json.dumps({
        "format": "worker-candidate-selection", "case_id": case,
        "candidate_id": candidate,
        "construction_sha256": selected["construction_sha256"],
        "manifest_sha256": sha(manifest_path)}))


class FixedCameraGuardTests(unittest.TestCase):
    def test_matched_primary_and_mixed_fallback(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work") as parent:
            for assignment, comparison in CASES:
                with self.subTest(assignment=assignment):
                    plan = json.loads((ROOT / "work" / assignment / "case-plan.json").read_text())
                    cases = next(row["case_ids"] for row in plan["comparisons"]
                                 if row["comparison_id"] == comparison)
                    first = Path(parent) / (assignment + "-first")
                    second = Path(parent) / (assignment + "-second")
                    attempt(first, assignment, cases[0], "primary")
                    attempt(second, assignment, cases[1], "primary")
                    key = assignment + "::" + comparison
                    check(ROOT, key, first, second)
                    second.rename(second.with_name(second.name + "-old"))
                    attempt(second, assignment, cases[1], "fallback1")
                    with self.assertRaisesRegex(ValueError, "fixed camera positions"):
                        check(ROOT, key, first, second)
                    left_key, right_key = (("LEFT_ATTEMPT", "RIGHT_ATTEMPT")
                                           if "C10307" in assignment else
                                           ("FIRST_ATTEMPT", "SECOND_ATTEMPT"))
                    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
                    env[left_key], env[right_key] = str(first), str(second)
                    dispatched = subprocess.run(
                        [sys.executable, str(ROOT / "work/_shared/queue_dispatch.py"),
                         key, "comparison"], cwd=ROOT, env=env,
                        capture_output=True, text=True, check=False)
                    self.assertNotEqual(dispatched.returncode, 0)
                    self.assertIn("changed fixed camera positions", dispatched.stderr)

    def test_unbound_original_source_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work") as parent:
            assignment, comparison = CASES[0]
            plan = json.loads((ROOT / "work" / assignment / "case-plan.json").read_text())
            cases = next(row["case_ids"] for row in plan["comparisons"]
                         if row["comparison_id"] == comparison)
            first, second = Path(parent) / "first", Path(parent) / "second"
            attempt(first, assignment, cases[0], "primary")
            attempt(second, assignment, cases[1], "primary")
            receipt = json.loads((second / "candidate-selection.json").read_text())
            receipt["manifest_sha256"] = "0" * 64
            (second / "candidate-selection.json").write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "candidate selection"):
                check(ROOT, assignment + "::" + comparison, first, second)
            receipt["manifest_sha256"] = sha(ROOT / "work" / assignment / "execution-manifest.json")
            (second / "candidate-selection.json").write_text(json.dumps(receipt))
            (second / "native_capture.py").write_text("# changed camera source\n")
            with self.assertRaisesRegex(ValueError, "camera implementation differs"):
                check(ROOT, assignment + "::" + comparison, first, second)

    def test_effective_pose_change_with_same_declared_table(self):
        assignment = CASES[0][0]
        source = (ROOT / "work" / assignment / "native_capture.py").read_text()
        changed = source.replace("position, angles = POSITIONS[name]",
                                 "position, angles = POSITIONS[name]\n    position = (position[0] + 1, position[1], position[2])")
        self.assertNotEqual(effective_plan(source, assignment),
                            effective_plan(changed, assignment))


if __name__ == "__main__":
    unittest.main()
