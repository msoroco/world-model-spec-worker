"""Materialize the eight unselected C111294 constructions for the frozen offline runner."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
PREFIX = f"work/{CASE.name}/native"

TEST = '''import json
import sys
import tempfile
import unittest
from pathlib import Path

root = Path.cwd()
native = root / "work" / "''' + CASE.name + '''" / "native"
sys.path.insert(0, str(native))
from check import check
from saved import make_raw, process

class ExactCrossroads(unittest.TestCase):
    def setUp(self):
        self.bundle = native / "drafts" / "{suffix}" / "{candidate}"

    def test_source_bound_request(self):
        result = check(self.bundle)
        self.assertEqual(result["frames"], 600)
        self.assertFalse(result["delivery_ready"])

    def test_synthetic_saved_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw.json"
            raw.write_text(json.dumps(make_raw(self.bundle)))
            saved = process(self.bundle, raw)
            self.assertEqual(saved["frames_joined"], 600)
            self.assertFalse(saved["original_native_observed"])

    def test_rehashed_track_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            for original in self.bundle.iterdir():
                (bundle / original.name).write_bytes(original.read_bytes())
            track = bundle / "requested-tracks.jsonl"
            rows = [json.loads(line) for line in track.read_text().splitlines()]
            rows[1]["requested_other_xyz_m"][1] += 0.25
            track.write_text("".join(json.dumps(row) + "\\n" for row in rows))
            cfg = json.loads((bundle / "config.json").read_text())
            import hashlib
            cfg["tracks_sha256"] = hashlib.sha256(track.read_bytes()).hexdigest()
            (bundle / "config.json").write_text(json.dumps(cfg))
            with self.assertRaises(ValueError):
                check(bundle)
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    cases = []
    for suffix in ("controlled_1", "controlled_2"):
        choices = []
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            bundle = HERE / "drafts" / suffix / candidate
            files = []
            for name in ("assignment-source.json", "case-plan.json", "crossroads.xodr",
                         "requested-tracks.jsonl", "config.json"):
                content = (bundle / name).read_text()
                files.append({"path": f"{PREFIX}/drafts/{suffix}/{candidate}/{name}", "content": content})
                files.append({"path": name, "content": content})
            for name in ("build.py", "check.py", "saved.py", "capture.py", "measurement-contract.json"):
                files.append({"path": f"{PREFIX}/{name}", "content": (HERE / name).read_text()})
            files.extend((
                {"path": f"work/{CASE.name}/case-plan.json", "content": (CASE / "case-plan.json").read_text()},
                {"path": f"inputs/{CASE.name}/assignment.json",
                 "content": (ROOT / "inputs" / CASE.name / "assignment.json").read_text()},
                {"path": "tests/test_exact.py", "content": TEST.replace("{suffix}", suffix).replace("{candidate}", candidate)},
            ))
            construction = {"case_id": CASE.name + "__" + suffix, "cell_id": "C111294",
                            "law_id": "NRS-484B-250-2", "actor": "motor_vehicle_driver",
                            "entrypoint": f"{PREFIX}/capture.py", "files": files,
                            "status": "unselected_cpu_diagnostic",
                            "recording_description": "Authored two-highway intersection request; original physical entry, device governance and legal right of way unverified."}
            path = HERE / "runtime-drafts" / suffix / candidate / "construction.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(construction, indent=2, allow_nan=False) + "\n")
            choices.append({"id": candidate, "construction": str(path.relative_to(HERE)),
                            "construction_sha256": sha(path)})
        cases.append({"case_id": CASE.name + "__" + suffix,
                      "construction": choices[0]["construction"],
                      "construction_sha256": choices[0]["construction_sha256"],
                      "candidates": choices[1:],
                      "candidate_risk": {"status": "physical", "reason": "Original junction, 20 Hz physical entry and statutory applicability unverified."}})
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": CASE.name, "status": "draft_not_selected", "cases": cases,
                "original_native_observed": False, "delivery_ready": False}
    (HERE / "draft-execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    print(json.dumps({"constructions": sum(1 + len(case["candidates"]) for case in build()["cases"])}))
