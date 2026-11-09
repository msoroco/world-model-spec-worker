"""Pin eight unselected divided-highway opening requests into frozen CPU packages."""
import json
from pathlib import Path

from build import CASE, HERE, ROOT, POLICIES, sha
from divided_opening import BRANCH, CENTERS

PREFIX = f"work/{CASE.name}/native"
TEST = '''import json
import sys
import unittest
from pathlib import Path

root=Path.cwd()
native=root/'work'/'NAME'/'native'
sys.path.insert(0,str(native))
from divided_opening import check,measure
from prove_original_divided import prove

class DividedOpening(unittest.TestCase):
    def setUp(self):
        self.bundle=native/'divided-opening'/'drafts'/'SUFFIX'/'CANDIDATE'

    def test_exact_source_bound_request(self):
        result=check(self.bundle)
        self.assertEqual(result['frames'],800)
        self.assertFalse(result['delivery_ready'])

    def test_synthetic_crossing_measurement(self):
        result=measure(self.bundle)
        self.assertEqual(result['crossing_in_authored_opening'],IS_OPEN)
        self.assertFalse(result['original_native_observed'])

    def test_median_and_opening_topology(self):
        xml=(self.bundle/'divided-highway.xodr').read_text()
        self.assertIn('type="median"',xml)
        self.assertIn('type="broken"',xml)
        self.assertEqual(xml.count('<road id='),3)

    def test_original_processor_synthetic_source_shape(self):
        result=prove(self.bundle)
        self.assertEqual(result['positive_count'],1)
        self.assertEqual(result['negative_count'],7)
        self.assertFalse(result['original_native_observed'])
        self.assertFalse(result['delivery_ready'])
'''


def build():
    cases = []
    for suffix in CENTERS:
        choices = []
        for candidate in POLICIES:
            bundle = BRANCH / "drafts" / suffix / candidate
            files = []
            for name in ("assignment-source.json", "divided-highway.xodr",
                         "requested-tracks.jsonl", "config.json"):
                content = (bundle / name).read_text()
                files.extend(({"path": f"{PREFIX}/divided-opening/drafts/{suffix}/{candidate}/{name}",
                               "content": content},
                              {"path": name, "content": content}))
            for name in ("build.py", "check.py", "capture.py", "divided_opening.py",
                         "capture_divided.py", "process_original.py",
                         "process_original_divided.py", "prove_original_processing.py",
                         "prove_original_divided.py"):
                files.append({"path": f"{PREFIX}/{name}",
                              "content": (HERE / name).read_text()})
            files.extend((
                {"path": f"work/{CASE.name}/case-plan.json",
                 "content": (CASE / "case-plan.json").read_text()},
                {"path": f"inputs/{CASE.name}/assignment.json",
                 "content": (ROOT / "inputs" / CASE.name / "assignment.json").read_text()},
                {"path": "tests/test_divided.py",
                 "content": TEST.replace("NAME", CASE.name)
                                .replace("SUFFIX", suffix)
                                .replace("CANDIDATE", candidate)
                                .replace("IS_OPEN", str(suffix == "divided_opening"))},
            ))
            construction = {
                "case_id": CASE.name + "__" + suffix,
                "cell_id": "C111662", "law_id": "NRS-484B-403-3",
                "actor": "motor_vehicle_driver",
                "entrypoint": f"{PREFIX}/capture_divided.py",
                "files": files, "status": "unselected_cpu_diagnostic",
                "recording_description":
                    "Authored median and opening U-turn pair; generated topology, physical turn, "
                    "district designation and statutory exception unverified."}
            path = BRANCH / "runtime-drafts" / suffix / candidate / "construction.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(construction, indent=2, allow_nan=False) + "\n")
            choices.append({"id": candidate,
                            "construction": str(path.relative_to(BRANCH)),
                            "construction_sha256": sha(path)})
        cases.append({"case_id": CASE.name + "__" + suffix,
                      "construction": choices[0]["construction"],
                      "construction_sha256": choices[0]["construction_sha256"],
                      "candidates": choices[1:],
                      "candidate_risk": {
                          "status": "physical",
                          "reason": "Original generated opening and physical U-turn unverified."}})
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": CASE.name, "status": "draft_not_selected",
                "cases": cases, "original_native_observed": False,
                "delivery_ready": False}
    (BRANCH / "draft-execution-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    print(json.dumps({"constructions": sum(
        1 + len(case["candidates"]) for case in build()["cases"])}))
