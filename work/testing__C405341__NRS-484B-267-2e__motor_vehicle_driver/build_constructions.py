"""Materialize exact 484B.267(2)(e) source-gated construction bundles."""
from __future__ import annotations
import json
from pathlib import Path
from emergency_construction import CASES
from native_packet import AID, VIEWS

HERE = Path(__file__).resolve().parent
SCRIPTS = ("runner.py", "native_packet.py", "emergency_construction.py", "lane_probe.py", "analysis.py")
SIZES = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))
FALLBACKS = {
    "moving_nonadjacent_lane": ("lane_change_start_s", 15.0, "original ego footprint does not reach reviewed nonadjacent lane before approach"),
    "traffic_unsafe_adjacent": ("lane_change_start_s", 15.0, "traffic occupancy and ego pass are not simultaneously visible"),
    "weather_unsafe_adjacent": ("lane_change_start_s", 15.0, "original weather effect and ego approach are not simultaneously visible"),
    "visible_hand_signal_preparation": ("lane_change_start_s", 15.0, "driver hand signal is not visible in original driver-view frames"),
}


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("construction exceeds 2 MiB")


def description():
    channels = (
        ("sealed_native_original_frames", "frame identity", "byte-sealed 20 Hz Native source"),
        ("unit_motion", "metres", "original unit pose history"),
        ("qualifying_flashing_lights", "on/off", "original qualifying light state"),
        ("visible_preparation_cue", "visible/occluded", "original driver-view pixels and cue source"),
        ("ego_approach", "metres and m/s", "original ego and unit positions and speeds"),
        ("lane_adjacency", "Native lane IDs", "original map adjacency readback and body footprint lane join"),
        ("nonadjacent_lane_access", "route and geometry", "original lane graph and connected route readback"),
        ("ego_lane_trajectory", "Native lane IDs", "original ego footprint lane occupation over full approach"),
        ("traffic_path_occupation", "vehicles and geometry", "original traffic bodies and lane-change corridor"),
        ("roadway_condition", "geometry", "original lane network, closure and drivable surface"),
        ("weather_condition", "weather and road surface", "original weather, visibility and grip readback"),
        ("officer_direction", "direction", "original law-enforcement officer direction"),
        ("video_four_views", "frame identity", "four synchronized original camera views"),
    )
    return {"channels": [{"name": name, "unit": unit, "method": method,
                           "sampling_rate_hz": 20, "time_window": "all 900 original frames",
                           "reference_frame": "reviewed Native lane graph and source packet",
                           "uncertainty": "physical realization and statutory safety/possibility judgment unverified"}
                          for name, unit, method in channels],
            "context_inputs": [], "limitations": [
                "Possible, unsafe and impossible remain statutory judgments without invented numeric thresholds.",
                "An available lane is measured separately from whether using it is safe in the circumstances.",
                "Equipment, authorization, officer authority and hand cue require independent original-source review."]}


def config(case, fallback=False):
    ids = [AID + "__" + item.suffix for item in CASES]
    engineering = {"lane_change_start_s": 17.0, "lane_change_end_s": 24.0,
                   "lane_choice_requested": case.lane_choice,
                   "condition_requested": case.condition,
                   "motion_state_requested": case.motion_state,
                   "officer_requested": case.officer_direction}
    if fallback and case.suffix in FALLBACKS:
        engineering[FALLBACKS[case.suffix][0]] = FALLBACKS[case.suffix][1]
    return {"assignment_id": AID, "law_id": "NRS-484B-267-2e", "cell_id": "C405341",
            "actor": "motor_vehicle_driver", "selected_case_id": AID + "__" + case.suffix,
            "supported_case_ids": ids, "rate_hz": 20, "duration_s": 45, "frame_count": 900,
            "required_atoms": [], "source_packets": [], "engineering": engineering,
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
        raise ValueError("exact eleven-case plan changed")
    plan["selected_branch"] = plan["selected_branches"][0]["branch"]
    plan["observations"] = [{"name": row["name"], "mandatory": True}
                            for row in description()["channels"]]
    plan["source_observation_mapping"] = {}
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary",
        "coverage": [{"view": view, "subject": subject, "interval": "all original 900 frames"}
                     for view, subject in zip(VIEWS, (
                         "ego approach and unit lane positions", "unit flashing lights and motion",
                         "traffic, roadway, weather and officer conditions", "driver-view lane and preparation cues"))]}
    for row in plan["cases"]:
        row["construction_status"] = "source_gated_exact_bundle"
    write(plan_path, plan)
    code = {name: (HERE / name).read_text(encoding="utf-8") for name in SCRIPTS}
    for index, case in enumerate(CASES):
        case_id = ids[index]
        config_text = json.dumps(config(case), indent=2) + "\n"
        test_text = ('"""Exact source-gated lane bundle identity."""\n'
                     'import unittest\nimport sys\nfrom pathlib import Path\n'
                     'sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n'
                     'from runner import check\n\nclass ExactBundleTest(unittest.TestCase):\n'
                     '    def test_selected_identity(self):\n'
                     '        self.assertTrue(check().endswith("__' + case.suffix + '"))\n')
        files = [{"path": name, "content": content} for name, content in code.items()]
        files += [{"path": "config.json", "content": config_text},
                  {"path": "tests/test_bundle.py", "content": test_text}]
        construction = {"law_id": "NRS-484B-267-2e", "cell_id": "C405341",
            "actor": "motor_vehicle_driver", "case_id": case_id,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": description(), "files": files,
            "measurement_plan": "900 original target and ego poses, lane IDs, body footprints, traffic, weather, officer, cue, lighting and four cameras",
            "static_checks": ["reviewed Native lane graph and target lane adjacency", "connected nonadjacent lane access or reviewed absence",
                              "authority, light and blueprint hashes", "four camera frame joins"],
            "termination_rules": ["900 synchronized Native ticks", "restore and read back world"],
            "mechanisms": ["source-gated emergency/regulatory moving unit and paved road",
                           "lane route controller with reviewed traffic/weather/officer conditions",
                           "sealed original histories and four-view capture"]}
        write(HERE / ("construction-" + case.suffix + ".json"), construction)
        if case.suffix in FALLBACKS:
            alternate = dict(construction)
            alternate["files"] = [dict(item) for item in files]
            alternate["files"][-2]["content"] = json.dumps(config(case, True), indent=2) + "\n"
            alternate["measurement_plan"] += "; source-gated engineering fallback " + FALLBACKS[case.suffix][0]
            write(HERE / ("construction-" + case.suffix + "-fallback1.json"), alternate)
        if index == 0:
            (HERE / "config.json").write_text(config_text, encoding="utf-8")
            (HERE / "tests/test_bundle.py").write_text(test_text, encoding="utf-8")
            write(HERE / "construction.json", construction)
    return ids


if __name__ == "__main__":
    print("\n".join(build()))
