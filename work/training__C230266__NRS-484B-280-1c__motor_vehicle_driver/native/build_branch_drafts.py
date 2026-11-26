"""Build 14 exact offline constructions from the reviewed statutory alternatives."""

import hashlib
import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSIGNMENT = ROOT.name
SCRATCH = Path(__import__("os").environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ".runtime-work/nrs280-drafts"))
BRANCHES = ("road", "transit_stop", "boarding", "school_zone", "school_crossing",
            "marked_crosswalk", "unmarked_crosswalk")
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case_id(branch, mode):
    suffix = f"probe_{1 if mode == 'caution' else 2}" if branch == "road" else f"{branch}_{mode}"
    return f"{ASSIGNMENT}__{suffix}"


def offline_test(cid, branch, mode):
    return f'''import copy
import json
import unittest
from pathlib import Path
from runner import check, control, read_survey


class BranchNativeContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())

    def test_exact_case_window_and_sources(self):
        result = check(self.config)
        self.assertEqual(result["case_id"], "{cid}")
        self.assertEqual((result["branch"], result["mode"]), ("{branch}", "{mode}"))
        self.assertEqual((result["frames"], result["rate_hz"]), (600, 20))
        self.assertEqual(len(result["source_views"]), 4)
        self.assertFalse(result["physical_completion"])

    def test_wrong_identity_short_window_and_missing_camera_rejected(self):
        for key, value in (("law_id", "NRS-484B-280-1a"), ("frames", 599),
                           ("physical_completion", True), ("legal_verdict", "compliant")):
            bad = copy.deepcopy(self.config)
            bad[key] = value
            with self.assertRaises(ValueError):
                check(bad)
        bad = copy.deepcopy(self.config)
        bad["cameras"].pop()
        with self.assertRaises(ValueError):
            check(bad)

    def test_source_and_control(self):
        with self.assertRaises(FileNotFoundError):
            read_survey("missing-original-context-survey.json")
        self.assertEqual(control(25, 8)["phase"], "approach_request")
        self.assertEqual(control(10, 8)["phase"], "{'slow_request' if mode == 'caution' else 'approach_request'}")
        with self.assertRaisesRegex(ValueError, "Measured"):
            control(float("nan"), 8)


if __name__ == "__main__":
    unittest.main()
'''


def build():
    template = (HERE / "branch_runner.py").read_text()
    old_config = json.loads((HERE / "road-probe-1/config.json").read_text())
    staging = SCRATCH / "branch-cases-staging"
    staging.mkdir(parents=True, exist_ok=True)
    entries = []
    for branch in BRANCHES:
        for mode in ("caution", "maintain"):
            cid = case_id(branch, mode)
            target = staging / cid.rsplit("__", 1)[-1]
            target.mkdir(parents=True, exist_ok=True)
            runner = template.replace("__CASE__", cid).replace("__BRANCH__", branch).replace("__MODE__", mode)
            (target / "runner.py").write_text(runner)
            config = dict(old_config)
            config.update({"case_id": cid, "selected_case_id": cid, "branch": branch,
                           "mode": mode, "status": "exact_unselected_cpu_draft",
                           "controller": ("distance_triggered_slow_request" if mode == "caution"
                                          else "maintain_approach_request")})
            dump(target / "config.json", config)
            test = offline_test(cid, branch, mode)
            (target / "test_offline.py").write_text(test)
            construction = {
                "format": "worker-inline-construction", "case_id": cid,
                "law_id": "NRS-484B-280-1c", "cell_id": "C230266",
                "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
                "files": [{"path": ("tests/test_offline.py" if name == "test_offline.py" else name),
                           "content": (target / name).read_text()}
                          for name in ("runner.py", "config.json", "test_offline.py")],
                "recording_description": {
                    "duration_s": 30, "rate_hz": 20, "source_cameras": list(VIEWS),
                    "channels": [
                        {"name": "native_vehicle_pedestrian_pose_and_control",
                         "method": "Native actor transform, velocity and requested control at 20 Hz",
                         "sampling_rate_hz": 20, "time_window": "600 frames"},
                        {"name": "four_camera_video",
                         "method": "four synchronized named RGB source cameras",
                         "sampling_rate_hz": 20, "time_window": "600 frames"}],
                    "limitations": ["Original statutory-position source, driver observation, Native motion and pixels remain unverified",
                                    "Controller distance trigger is engineering policy, not legal threshold"]},
                "status": "exact_unselected_cpu_draft"}
            draft = staging / f"{cid.rsplit('__', 1)[-1]}-construction.json"
            dump(draft, construction)
            entries.append({"case_id": cid,
                            "construction": f"native/branch-cases/{draft.name}",
                            "construction_sha256": digest(draft),
                            "candidate_risk": {"status": "physical", "reason": "Physical source survey, actor path and camera visibility remain unverified"},
                            "candidates": []})
    destination = HERE / "branch-cases"
    destination.mkdir(parents=True, exist_ok=True)
    for staged in sorted(staging.rglob("*")):
        if staged.is_file():
            final = destination / staged.relative_to(staging)
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, final)
    for directory in sorted((p for p in staging.rglob("*") if p.is_dir()), reverse=True):
        directory.rmdir()
    staging.rmdir()
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": ASSIGNMENT, "status": "draft_not_selected",
                "cases": entries, "original_native_observed": False,
                "delivery_ready": False}
    path = ROOT / "draft-all-branches-manifest.json"
    tmp = SCRATCH / "draft-all-branches-manifest.json"
    dump(tmp, manifest)
    os.replace(tmp, path)
    print(json.dumps({"cases": len(entries), "manifest_sha256": digest(path)}))


if __name__ == "__main__":
    build()
