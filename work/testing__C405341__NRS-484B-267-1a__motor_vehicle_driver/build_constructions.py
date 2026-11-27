"""Materialize ten exact emergency-unit construction bundles."""

from __future__ import annotations

import json
from pathlib import Path

from emergency_construction import CASES
from native_packet import AID, VIEWS

HERE = Path(__file__).resolve().parent
SCRIPTS = ("runner.py", "native_packet.py", "emergency_construction.py", "emergency_movement_observations.py", "analysis.py")
SIZES = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("construction exceeds 2 MiB")


def description():
    channels = (
        ("sealed_native_original_frames", "frame identity", "byte-sealed 20 Hz Native source"),
        ("unit_motion", "metres", "original vehicle pose difference"),
        ("qualifying_flashing_lights", "on/off", "original emergency light state"),
        ("target_authorization", "source", "reviewed authorized emergency or regulatory official status"),
        ("driver_view_movement_cue", "visible/occluded", "reviewed driver-view original pixels and pose"),
        ("driver_hand_signal", "visible/absent", "original driver signal and reviewed view pixels"),
        ("ego_approach", "metres and m/s", "original ego/unit positions and speed"),
        ("ego_response", "control", "original brake and speed history"),
        ("officer_direction", "direction", "source-bound original direction if any"),
        ("video_four_views", "frame identity", "four synchronized original camera views"))
    return {"channels": [{"name": name, "unit": unit, "method": method,
                          "sampling_rate_hz": 20, "time_window": "all 900 original frames",
                          "reference_frame": "reviewed Native route and source packet",
                          "uncertainty": "physical realization and preparedness judgment remain unverified"}
                         for name, unit, method in channels],
            "context_inputs": [], "limitations": [
                "About-to-move and proceed-with-caution are judgment phrases with no invented numeric threshold.",
                "Equipment qualification and target authorization need independent source review.",
                "Actual driver-view cue visibility requires original pixels and independent review."]}


def config(case):
    ids = [AID + "__" + item.suffix for item in CASES]
    return {"assignment_id": AID, "law_id": "NRS-484B-267-1a", "cell_id": "C405341",
            "actor": "motor_vehicle_driver", "selected_case_id": AID + "__" + case.suffix,
            "supported_case_ids": ids, "rate_hz": 20, "duration_s": 45, "frame_count": 900,
            "required_atoms": [], "source_packets": [],
            "engineering": {"movement_start_s": 17.0, "movement_end_s": 19.0,
                            "movement_cue": case.cue,
                            "light_request": case.light_request,
                            "occluder_requested": case.cue == "occluded_movement",
                            "officer_requested": case.officer_direction,
                            "approaching_requested": case.approaching},
            "cameras": [{"name": name, "width": width, "height": height,
                         "pose_strategy": "reviewed Native route and four-view source survey", "fov_deg": 90}
                        for name, (width, height) in zip(VIEWS, SIZES)],
            "case": {"case_id": AID + "__" + case.suffix,
                     "recording_description": description()}}


def build():
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    ids = [AID + "__" + case.suffix for case in CASES]
    if [row["case_id"] for row in plan["cases"]] != ids:
        raise ValueError("exact ten-case plan changed")
    branch = plan["selected_branches"][0]
    plan["selected_branch"] = branch["branch"]
    plan["requirement_dispositions"] = [{
        "requirement": branch["requirement"], "source": branch["source"],
        "status": "selected_required", "case_ids": ids,
        "evidence_or_gap": "Frozen evidence inventory has no accepted recordings.",
        "reason": "Original emergency-unit motion, visible cue, light use and cautious response needed."}]
    plan["observations"] = [{"name": row["name"], "mandatory": True}
                            for row in description()["channels"]]
    plan["source_observation_mapping"] = {}
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary",
        "coverage": [{"view": view, "subject": subject, "interval": "all original 900 frames"}
                     for view, subject in zip(VIEWS, (
                         "ego approach and emergency unit", "unit flashing lights and movement",
                         "occluder, officer and unit route", "driver-view movement and hand-signal cues"))]}
    for row in plan["cases"]:
        row["new_capture_selected"] = True
        row["construction_status"] = "source_gated_exact_bundle"
    write(plan_path, plan)
    code = {name: (HERE / name).read_text(encoding="utf-8") for name in SCRIPTS}
    for index, case in enumerate(CASES):
        case_id = ids[index]
        config_text = json.dumps(config(case), indent=2) + "\n"
        test_text = ('"""Exact source-gated emergency bundle identity."""\n'
                     'import unittest\nimport sys\nfrom pathlib import Path\n'
                     'sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n'
                     'from runner import check\n\nclass ExactBundleTest(unittest.TestCase):\n'
                     '    def test_selected_identity(self):\n'
                     '        self.assertTrue(check().endswith("__' + case.suffix + '"))\n')
        files = [{"path": name, "content": content} for name, content in code.items()]
        files += [{"path": "config.json", "content": config_text},
                  {"path": "tests/test_bundle.py", "content": test_text}]
        construction = {"law_id": "NRS-484B-267-1a", "cell_id": "C405341",
            "actor": "motor_vehicle_driver", "case_id": case_id,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": description(), "files": files,
            "measurement_plan": "900 original unit poses, driver-view pixels, light and ego controls",
            "static_checks": ["reviewed Native map, authority, equipment and blueprint hashes",
                              "occluder geometry for hidden cue", "four camera frame joins"],
            "termination_rules": ["900 synchronized Native ticks", "restore and read back world"],
            "mechanisms": ["source-gated emergency/regulatory unit and paved road",
                           "flashing light, movement, hand signal and ego response controllers",
                           "sealed original histories and four-view capture"]}
        write(HERE / ("construction-" + case.suffix + ".json"), construction)
        if index == 0:
            (HERE / "config.json").write_text(config_text, encoding="utf-8")
            (HERE / "tests/test_bundle.py").parent.mkdir(exist_ok=True)
            (HERE / "tests/test_bundle.py").write_text(test_text, encoding="utf-8")
            write(HERE / "construction.json", construction)
    return ids


if __name__ == "__main__":
    print("\n".join(build()))
