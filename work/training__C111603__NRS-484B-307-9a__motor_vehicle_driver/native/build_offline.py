"""Pin unselected C111603 CPU requests into frozen runtime offline packages."""
import json
from pathlib import Path

from build import CASE, HERE, ROOT, digest, write

PREFIX = f"work/{CASE.name}/native"
TEST = '''import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

root = Path.cwd()
native = root / "work" / "NAME" / "native"
sys.path.insert(0, str(native))
from build import check
from saved import fixture, process

class ArrowRequest(unittest.TestCase):
    def setUp(self):
        self.bundle = native / "drafts" / "SUFFIX" / "CANDIDATE"

    def test_exact_request(self):
        result = check(self.bundle)
        self.assertEqual(result["frames"], 480)
        self.assertFalse(result["delivery_ready"])

    def test_synthetic_saved_join(self):
        saved = process(self.bundle, fixture(self.bundle))
        self.assertEqual(saved["joined_video_frames"], 480)
        self.assertFalse(saved["original_native_observed"])
        self.assertIsNone(saved["legal_verdict"])

    def test_rehashed_signal_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            changed = Path(name)
            for file in self.bundle.iterdir():
                (changed / file.name).write_bytes(file.read_bytes())
            road = changed / "arrow-intersection.xodr"
            road.write_text(road.read_text().replace("green-right-arrow", "green-left-arrow"))
            config = changed / "config.json"
            value = json.loads(config.read_text())
            value["road_sha256"] = hashlib.sha256(road.read_bytes()).hexdigest()
            config.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                check(changed)
'''


def build():
    cases = []
    for suffix in ("witness_1", "witness_2"):
        choices = []
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            bundle = HERE / "drafts" / suffix / candidate
            files = []
            for name in ("assignment-source.json", "arrow-intersection.xodr",
                         "requested-tracks.jsonl", "config.json"):
                content = (bundle / name).read_text()
                files.append({"path": f"{PREFIX}/drafts/{suffix}/{candidate}/{name}",
                              "content": content})
            for name in ("build.py", "saved.py", "road-template.xodr", "measurement-contract.json"):
                files.append({"path": f"{PREFIX}/{name}", "content": (HERE / name).read_text()})
            files.extend((
                {"path": f"work/{CASE.name}/case-plan.json", "content": (CASE / "case-plan.json").read_text()},
                {"path": f"inputs/{CASE.name}/assignment.json", "content":
                 (ROOT / "inputs" / CASE.name / "assignment.json").read_text()},
                {"path": "tests/test_arrow.py", "content": TEST.replace("NAME", CASE.name)
                 .replace("SUFFIX", suffix).replace("CANDIDATE", candidate)},
            ))
            construction = {
                "case_id": CASE.name + "__" + suffix, "cell_id": "C111603",
                "law_id": "NRS-484B-307-9a", "actor": "motor_vehicle_driver",
                "entrypoint": f"{PREFIX}/build.py", "files": files,
                "status": "unselected_cpu_diagnostic",
                "recording_description": "Authored red-plus-right-arrow request with other vehicle; original signal, physical yielding and legal verdict unverified."}
            path = HERE / "runtime-drafts" / suffix / candidate / "construction.json"
            write(path, construction)
            choices.append({"id": candidate, "construction": str(path.relative_to(HERE)),
                            "construction_sha256": digest(path)})
        cases.append({"case_id": CASE.name + "__" + suffix,
                      "construction": choices[0]["construction"],
                      "construction_sha256": choices[0]["construction_sha256"],
                      "candidates": choices[1:],
                      "candidate_risk": {"status": "physical", "reason":
                         "Original signal readback, physical actors, yielding and review unverified."}})
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": CASE.name, "status": "draft_not_selected",
                "cases": cases, "original_native_observed": False,
                "delivery_ready": False}
    write(HERE / "draft-execution-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps({"constructions": sum(1 + len(c["candidates"]) for c in build()["cases"])}))
