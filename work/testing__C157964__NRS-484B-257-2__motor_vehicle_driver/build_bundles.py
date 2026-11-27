"""Materialize exact source-gated officer cases for offline construction tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
CAMERAS = [{"name": name, "width": 1920 if name == "overview" else 1280,
            "height": 1080 if name == "overview" else 720, "fov_deg": 75,
            "pose_strategy": "reviewed officer gesture, approach, entry and other participant"}
           for name in VIEWS]
CHANNELS = [{"name": name, "method": method, "unit": unit,
             "reference_frame": "source-sealed original Native frame map",
             "sampling_rate_hz": 20, "time_window": "full 45-second episode",
             "uncertainty": "physical realization and legal judgment unresolved"}
            for name, method, unit in (
                ("officer_control", "original actor state plus independent four-view review", "source record"),
                ("officer_directive", "original gesture and control state", "source record"),
                ("ego_entry", "original body geometry and reviewed intersection boundary", "m"),
                ("ego_speed", "original Native velocity magnitude", "m/s"),
                ("other_phase", "original body geometry within/approaching history", "source record"),
                ("other_station", "original counterpart body station", "m"),
                ("entrance_controls", "source-reviewed all-entrance inventory", "source record"))]
RECORDING = {"channels": CHANNELS,
             "context_inputs": [{"name": "reviewed_officer_site_packet",
                                 "method": "source-hashed map, officer, entrance, route and sightline review",
                                 "unit": "source record"}],
             "limitations": ["No original officer capture is in the frozen input.",
                             "Requested gesture and station are not physical measurements."]}
TEST = '''import unittest
from pathlib import Path
from runner import check

class BundleTests(unittest.TestCase):
    def test_exact_officer_construction(self):
        config = check(Path(__file__).resolve().parents[1])
        self.assertEqual(config["frame_count"], 900)
        self.assertEqual(len(config["cameras"]), 4)

if __name__ == "__main__":
    unittest.main()
'''


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan_path = ROOT / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    rows = []
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.removeprefix(ROOT.name + "__")
        config = {"assignment_id": ROOT.name, "law_id": plan["law_id"],
                  "cell_id": plan["cell_id"], "actor": plan["actor"],
                  "selected_case_id": case_id,
                  "supported_case_ids": sorted(item["case_id"] for item in plan["cases"]),
                  "case": {"case_id": case_id, "draft_variables": case["draft_variables"],
                           "recording_description": RECORDING},
                  "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                  "rate_hz": 20, "frame_count": 900, "duration_s": 45,
                  "control": {"officer_directive": case["draft_variables"]["officer_directive"]},
                  "cameras": CAMERAS, "required_atoms": [], "source_packets": [],
                  "diagnostic_only": True, "recording_description": RECORDING}
        files = [{"path": "config.json", "content": json.dumps(config, indent=2,
                   sort_keys=True) + "\n"},
                 {"path": "case-plan.json", "content": plan_path.read_text(),
                  "source": f"work/{ROOT.name}/case-plan.json"},
                 {"path": "tests/test_bundle.py", "content": TEST}]
        for name in ("runner.py", "analysis.py", "officer_scene.py",
                     "officer_site_packet.py", "officer_native_capture.py",
                     "officer_motion.py", "officer_control_measurement.py"):
            files.append({"path": name, "content": (ROOT / name).read_text(),
                          "source": f"work/{ROOT.name}/{name}"})
        construction = {"case_id": case_id, "cell_id": plan["cell_id"],
                        "law_id": plan["law_id"], "actor": plan["actor"],
                        "candidate_id": "primary", "entrypoint": "runner.py",
                        "files": files, "recording_description": RECORDING,
                        "measurement_plan": {"case_id": case_id, "original_frames": 900,
                                             "procedure": "analysis.py",
                                             "legal_judgment": "unresolved",
                                             "source_packets": ["reviewed_officer_site_packet",
                                                                "history", "frame_map",
                                                                "four_camera_png", "independent_officer_review"]},
                        "static_checks": ["exact officer cell and case identity",
                                          "source-hashed reviewed map and officer packet",
                                          "20 Hz original actor/camera joins"],
                        "termination_rules": ["900 original frames at 20 Hz",
                                              "fail closed on absent reviewed site"],
                        "mechanisms": ["reviewed original officer-controlled intersection",
                                       "ego, other vehicle and officer actors",
                                       "source-sealed four-camera original capture"]}
        relative = f"cases/{suffix}/construction.json"
        digest = write(ROOT / relative, construction)
        (ROOT / f"cases/{suffix}/config.json").write_text(files[0]["content"])
        requirements = []
        for index, disposition in enumerate(plan["requirement_dispositions"]):
            requirements.append({"disposition_index": index,
                                 "requirement": disposition["requirement"],
                                 "source": disposition["source"],
                                 "kind": "measured", "method": "build",
                                 "value_type": "object",
                                 "output_key": ("officer_exception_context" if index == 0 else
                                                "officer_intersection_motion"),
                                 "inputs": ["original-attempt/history.json",
                                            "original-attempt/frame-map.json",
                                            "original-attempt/site-packet.json",
                                            "original-attempt/officer-review.json"]})
        write(ROOT / f"measurement-{suffix}.json", {
            "format": "worker-measurement-contract", "case_id": case_id,
            "requirements": requirements,
            "negative": {"remove": ["original-attempt/officer-review.json"],
                         "error_contains": "Missing required source: original-attempt/officer-review.json"}})
        rows.append({"case_id": case_id, "kind": "delivery",
                     "construction": relative, "construction_sha256": digest,
                     "diagnostic_only": True,
                     "measurement_contract": f"measurement-{suffix}.json",
                     "measurement_procedure": {"entrypoint": "analysis.py"},
                     "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                        "host_env_var": "CARLA_HOST",
                                        "port_env_var": "CARLA_PORT"},
                     "candidate_risk": {"status": "physical",
                                        "reason": "Original gesture visibility and officer/vehicle timing require CARLA review."},
                     "candidates": []})
    write(ROOT / "execution-manifest.json", {
        "format": "worker-execution-manifest", "assignment_id": ROOT.name,
        "runtime_manifest_sha256": hashlib.sha256(
            (REPO / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest(),
        "diagnostic_only": True, "cases": rows})
    first = ROOT / rows[0]["construction"]
    (ROOT / "config.json").write_text((ROOT / "cases" /
        plan["cases"][0]["case_id"].removeprefix(ROOT.name + "__") / "config.json").read_text())
    (ROOT / "construction.json").write_text(first.read_text())
    print("built", len(rows), "officer construction bundles")


if __name__ == "__main__":
    main()
