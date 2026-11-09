"""Materialize eight unselected source-exact crest CPU packages."""
import hashlib
import json
from pathlib import Path
from build import CASES, HERE, POLICIES

CASE = HERE.parents[1]
FILES = ("assignment-source.json", "case-plan.json", "crest.xodr", "config.json",
         "requested-tracks.jsonl", "build.py", "check.py", "saved.py",
         "capture.py", "process_original.py", "prove_original_processing.py",
         "measurement-contract.json")
TEST = '''import tempfile
import unittest
from pathlib import Path
from check import check
from saved import make_raw, process
from prove_original_processing import fixture
from process_original import process as process_capture
from build import put

class CrestExact(unittest.TestCase):
    def test_copied_source_and_status(self):
        row = check(Path.cwd())
        self.assertFalse(row["delivery_ready"])
        self.assertFalse(row["original_visibility_verified"])
    def test_swept_path(self):
        row = check(Path.cwd())
        if row["candidate"] == "fallback3":
            self.assertIn("stop_before_crest", row["requested_phases"])
        else:
            self.assertIn("reverse_right", row["requested_phases"])
    def test_synthetic_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw_path = Path(tmp) / "raw.json"
            put(raw_path, make_raw(Path.cwd()))
            row = process(Path.cwd(), raw_path)
            self.assertEqual(row["frames_joined"], 700)
            self.assertFalse(row["delivery_ready"])
    def test_synthetic_original_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "fixture"
            review = fixture(Path.cwd(), directory)
            row = process_capture(Path.cwd(), directory, review, synthetic_fixture=True)
            self.assertEqual(row["frames_joined"], 700)
            self.assertFalse(row["original_native_observed"])
            self.assertFalse(row["delivery_ready"])
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    cases = []
    for suffix in CASES:
        choices = []
        for candidate in POLICIES:
            bundle = HERE / "drafts" / suffix / candidate
            files = [{"path": name, "content": (bundle / name).read_text() if
                      (bundle / name).is_file() else (HERE / name).read_text()} for name in FILES]
            files.append({"path": "tests/test_exact.py", "content": TEST})
            construction = {"case_id": CASE.name + "__" + suffix, "cell_id": "C104496",
                            "law_id": "NRS-484B-407", "actor": "motor_vehicle_driver",
                            "entrypoint": "capture.py", "files": files,
                            "status": "unselected_cpu_diagnostic",
                            "recording_description": "Authored grade crest and three-point request; original 500-foot body rays and human visibility unverified."}
            path = HERE / "runtime-drafts" / suffix / candidate / "construction.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(construction, indent=2, allow_nan=False) + "\n")
            choices.append({"id": candidate, "construction": str(path.relative_to(HERE)),
                            "construction_sha256": sha(path)})
        cases.append({"case_id": CASE.name + "__" + suffix,
                      "construction": choices[0]["construction"],
                      "construction_sha256": choices[0]["construction_sha256"],
                      "candidates": choices[1:],
                      "candidate_risk": {"status": "physical",
                                         "reason": "Original generated crest, body rays, reviewed pixels and statutory comparison absent."}})
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": CASE.name, "status": "draft_not_selected", "cases": cases,
                "original_native_observed": False, "delivery_ready": False}
    path = HERE / "draft-execution-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    print(json.dumps({"cases": len(build()["cases"]), "constructions": 8}))
