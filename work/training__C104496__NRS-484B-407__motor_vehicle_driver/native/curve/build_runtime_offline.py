"""Materialize four unselected exact curve CPU constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parents[1]
ROOT = CASE.parents[1]
TEST = '''import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path.cwd()
CASE = ROOT / "work" / "''' + CASE.name + '''"
CURVE = CASE / "native" / "curve"
sys.path.insert(0, str(CURVE))
from prove import check
from saved import make_raw, process
from prove_original_processing import fixture
from process_original import process as process_capture

class ExactCurve(unittest.TestCase):
    def setUp(self):
        self.bundle = CURVE / "drafts" / "probe_03" / "''' + '{candidate}' + '''"

    def test_source_and_curve_request(self):
        self.assertEqual(check(self.bundle), 700)
        cfg = json.loads((self.bundle / "config.json").read_text())
        self.assertEqual(cfg["status"], "unselected_native_request")
        self.assertFalse(cfg["original_native_observed"])

    def test_synthetic_saved_join(self):
        raw = make_raw(self.bundle)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw.json"
            path.write_text(json.dumps(raw))
            result = process(self.bundle, path)
            self.assertEqual(result["frames_joined"], 700)
            self.assertFalse(result["delivery_ready"])

    def test_rehashed_curve_mutation_rejected(self):
        from prove import sha, put
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            for file in self.bundle.iterdir():
                (target / file.name).write_bytes(file.read_bytes())
            road = target / "curve.xodr"
            road.write_text(road.read_text().replace('curvature="0.003333333333333"', 'curvature="0.004000000000000"'))
            cfg = json.loads((target / "config.json").read_text())
            cfg["road_sha256"] = sha(road)
            put(target / "config.json", cfg)
            with self.assertRaises(ValueError):
                check(target)

    def test_synthetic_original_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "fixture"
            review = fixture(self.bundle, directory)
            result = process_capture(self.bundle, directory, review, synthetic_fixture=True)
            self.assertEqual(result["frames_joined"], 700)
            self.assertFalse(result["original_native_observed"])
            with self.assertRaises(ValueError):
                process_capture(self.bundle, directory, review)
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    choices = []
    for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
        bundle = HERE / "drafts" / "probe_03" / candidate
        prefix = f"work/{CASE.name}/native/curve"
        files = []
        for name in ("assignment-source.json", "case-plan.json", "curve.xodr",
                     "config.json", "requested-tracks.jsonl"):
            files.append({"path": f"{prefix}/drafts/probe_03/{candidate}/{name}",
                          "content": (bundle / name).read_text()})
            files.append({"path": name, "content": (bundle / name).read_text()})
        for name in ("prove.py", "saved.py", "capture.py", "process_original.py",
                     "prove_original_processing.py", "measurement-contract.json"):
            files.append({"path": f"{prefix}/{name}", "content": (HERE / name).read_text()})
        files.extend([
            {"path": f"work/{CASE.name}/native/crest/build.py",
             "content": (HERE.parent / "crest" / "build.py").read_text()},
            {"path": f"work/{CASE.name}/case-plan.json", "content": (CASE / "case-plan.json").read_text()},
            {"path": f"inputs/{CASE.name}/assignment.json",
             "content": (ROOT / "inputs" / CASE.name / "assignment.json").read_text()},
            {"path": "tests/test_exact.py", "content": TEST.replace("{candidate}", candidate)},
        ])
        construction = {"case_id": CASE.name + "__probe_03", "cell_id": "C104496",
                        "law_id": "NRS-484B-407", "actor": "motor_vehicle_driver",
                        "entrypoint": f"{prefix}/capture.py", "files": files,
                        "status": "unselected_cpu_diagnostic",
                        "recording_description": "Authored 300 m radius grade curve and three-point reversal; original generated curve, 500-foot body rays and reviewed visibility unverified."}
        path = HERE / "runtime-drafts" / "probe_03" / candidate / "construction.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(construction, indent=2, allow_nan=False) + "\n")
        choices.append({"id": candidate, "construction": str(path.relative_to(HERE)),
                        "construction_sha256": sha(path)})
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": CASE.name, "status": "draft_not_selected",
                "cases": [{"case_id": CASE.name + "__probe_03",
                           "construction": choices[0]["construction"],
                           "construction_sha256": choices[0]["construction_sha256"],
                           "candidates": choices[1:],
                           "candidate_risk": {"status": "physical", "reason": "Original generated curve, body rays, reviewed pixels and statutory comparison absent."}}],
                "original_native_observed": False, "delivery_ready": False}
    (HERE / "draft-execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    print(json.dumps({"constructions": len(build()["cases"][0]["candidates"]) + 1}))
