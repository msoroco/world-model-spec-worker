"""Materialize eight exact C10365 requests for the pinned offline runtime."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent.parent
NAMES = ("assignment-source.json", "case-plan.json", "alley-stop.xodr",
         "config.json", "requested-tracks.jsonl", "build.py", "check.py",
         "capture.py", "measurement-contract.json", "saved.py", "prove_saved.py")

TEST = '''import json
import tempfile
import unittest
from pathlib import Path
from check import check
from prove_saved import fixture
from saved import process

class ExactOfficer(unittest.TestCase):
    def test_source_and_unverified_status(self):
        row = check(Path.cwd())
        self.assertFalse(row["delivery_ready"])
        self.assertIsNone(row["officer_direction_observed"])
        self.assertIsNone(row["legal_verdict"])

    def test_requested_pair_behavior(self):
        row = check(Path.cwd())
        if row["case_id"].endswith("probe_a"):
            self.assertGreater(row["requested_stop_frames"], 0)
            self.assertFalse(row["requested_crossing"])
        else:
            self.assertEqual(row["requested_stop_frames"], 0)
            self.assertTrue(row["requested_crossing"])

    def test_synthetic_saved_join(self):
        with tempfile.TemporaryDirectory() as folder:
            raw, video, review = fixture(Path.cwd(), Path(folder))
            row = process(Path.cwd(), raw, video, review, synthetic=True)
            self.assertEqual(row["frames"], 480)
            self.assertFalse(row["delivery_ready"])
            self.assertIsNone(row["physical_legal_verdict"])
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    cases = []
    for suffix in ("probe_a", "probe_b"):
        choices = []
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            bundle = HERE / "drafts" / suffix / candidate
            files = [{"path": name, "content": (bundle / name).read_text()
                      if (bundle / name).is_file() else (HERE / name).read_text()}
                     for name in NAMES]
            files.append({"path": "tests/test_exact.py", "content": TEST})
            construction = {
                "case_id": CASE.name + "__" + suffix, "cell_id": "C10365",
                "law_id": "LVMC-11-40-070", "actor": "cycle_or_scooter_operator",
                "entrypoint": "capture.py", "files": files,
                "status": "unselected_cpu_diagnostic",
                "recording_description": "Authored alley bicycle/officer request; authority, actual instruction, official device and legal response unverified."}
            path = HERE / "runtime-drafts" / suffix / candidate / "construction.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(construction, indent=2, allow_nan=False) + "\n")
            choices.append({"id": candidate, "construction": str(path.relative_to(HERE)),
                            "construction_sha256": sha(path)})
        cases.append({
            "case_id": CASE.name + "__" + suffix,
            "construction": choices[0]["construction"],
            "construction_sha256": choices[0]["construction_sha256"],
            "candidates": choices[1:],
            "candidate_risk": {"status": "physical",
                "reason": "Original Native and visual statutory evidence absent."}})
    manifest = {
        "format": "worker-unselected-draft-construction-manifest-v1",
        "assignment_id": CASE.name, "status": "draft_not_selected", "cases": cases,
        "original_native_observed": False, "delivery_ready": False}
    (HERE / "draft-execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    result = build()
    print(json.dumps({"cases": len(result["cases"]), "constructions": 8}))
