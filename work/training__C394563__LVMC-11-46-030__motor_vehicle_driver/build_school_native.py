"""Materialize two exact, still-unselected school-warning Native bundles."""

from __future__ import annotations

import hashlib
import json
import copy
from pathlib import Path

from school_warning_scene import CASE_VARIANTS


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
TERMS = ("st.crosswalk", "dev.crossing_warning_signal", "dev.human_direction",
         "ru.child", "rel.centre_distance", "drv.stopped", "drv.approaching",
         "kin.velocity", "dev.position")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def build(variant=True):
    common = [{"path": name, "content": (ROOT / name).read_text()}
              for name in ("runner.py", "school_native_plan.py", "school_warning_scene.py",
                           "finalize.py", "measure_school_warning.py")]
    test = ("import unittest\nfrom runner import check\nfrom finalize import derive\n"
            "class ExactSchoolWarning(unittest.TestCase):\n"
            " def test_selected_native_request(self):\n"
            "  self.assertEqual(check()['pair']['frames'],600)\n"
            "  self.assertFalse(check()['original_native_observed'])\n"
            " def test_missing_original_source_rejected(self):\n"
            "  with self.assertRaisesRegex(ValueError,'Missing sealed original'):\n"
            "   derive('.')\n")
    common.append({"path": "tests/test_offline.py", "content": test})
    cases = []
    specifications = CASE_VARIANTS if variant else {
        name: CASE_VARIANTS[name] for name in ("probe_1", "probe_2")}
    construction_root = "draft-variant-exact" if variant else "draft-exact"
    manifest_name = "draft-variant-manifest.json" if variant else "draft-native-manifest.json"
    for suffix, (target, role, release) in specifications.items():
        case_id = ASSIGNMENT + "__" + suffix
        config = {"assignment_id": ASSIGNMENT, "case_id": case_id,
            "selected_case_id": case_id, "supported_case_ids":
                [ASSIGNMENT + "__" + name for name in specifications],
            "law_id": "LVMC-11-46-030", "cell_id": "C394563",
            "actor": "motor_vehicle_driver", "rate_hz": 20,
            "duration_s": 30, "frame_count": 600,
            "requested_stop_center_ft": target,
            "requested_release_event": release,
            "warning_role": role,
            "controller_throttle_scale": 1.0,
            "required_atoms": ["ru.motor_vehicle", "kin.position", "kin.speed"],
            "source_packets": [],
            "cameras": [{"name": name, "width": 1920 if index == 0 else 1280,
                         "height": 1080 if index == 0 else 720,
                         "fov_deg": 80,
                         "pose_strategy": "school pedestrian lane, warning actor, child and ego"}
                        for index, name in enumerate(CAMERAS)],
            "case": {"case_id": case_id, "target_type": "controlled_stop_request",
                     "recording_description": "warned school lane, source-bound stop and release"},
            "physical_or_legal_outcome_claimed": False}
        selected = {"suffix": suffix, "case_id": case_id}
        files = common + [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                          {"path": "selected-case.json", "content": json.dumps(selected, indent=2) + "\n"}]
        channels = [{"name": term, "unit": "structured", "sampling_rate_hz": 20,
                     "method": "same-frame original school warning Native and camera source join",
                     "time_window": "600 frames over 30 seconds",
                     "reference_frame": "original Native frame and school lane near side",
                     "uncertainty": "original source and pixel review pending"}
                    for term in TERMS]
        construction = {"case_id": case_id, "law_id": config["law_id"],
            "cell_id": config["cell_id"], "actor": config["actor"],
            "entrypoint": "runner.py", "files": files,
            "recording_description": {"channels": channels,
                "context_inputs": [{"name": "school_lane_child_warning_review",
                                    "unit": "structured", "method": "sealed original review sources"}],
                "limitations": ["Original school lane, child identity and warning pixels require review",
                                "Requested stop station does not prove actual stop or legal outcome"]},
            "measurement_plan": "measure_school_warning.py observes all 600 frames, not controller targets",
            "static_checks": ["exact two-way road", "school lane marker request", "four camera and frame contract"],
            "termination_rules": ["retain Native exit and all source files", "restore exclusive world"],
            "mechanisms": ["source-reviewed school lane and child", "observed stop and " + release],
            "status": "draft_offline_only"}
        path = ROOT / construction_root / suffix / "primary" / "construction.json"
        write(path, construction)
        fallback = copy.deepcopy(construction)
        fallback_config = copy.deepcopy(config)
        fallback_config["controller_throttle_scale"] = 0.8
        for item in fallback["files"]:
            if item["path"] == "config.json":
                item["content"] = json.dumps(fallback_config, indent=2) + "\n"
        fallback_path = ROOT / construction_root / suffix / "fallback1" / "construction.json"
        write(fallback_path, fallback)
        cases.append({"case_id": case_id,
                      "construction": str(path.relative_to(ROOT)),
                      "construction_sha256": sha(path),
                      "candidate_risk": {"status": "physical",
                          "reason": "Observed Native stop station can miss the requested stop target under model acceleration"},
                      "candidates": [{"id": "fallback1",
                          "construction": str(fallback_path.relative_to(ROOT)),
                          "construction_sha256": sha(fallback_path),
                          "trigger": {"source": "sealed original native-rows.jsonl and result.json",
                                      "metric": "observed centre stop distance versus unchanged request",
                                      "failure_condition": "absolute difference exceeds 2 feet after source completeness review"},
                          "changed_knobs": ["approach and release throttle scale 1.0 to 0.8"]}]})
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": ASSIGNMENT, "status": "draft_not_selected",
                "cases": cases, "delivery_ready": False,
                "original_native_observed": False}
    write(ROOT / manifest_name, manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps({"cases": [entry["case_id"] for entry in build()["cases"]]}))
