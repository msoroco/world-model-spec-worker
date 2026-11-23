"""Build the shared draft C227824 construction from current source files.

The scene/map and official device reviews remain separate source-bound assets.
This builder does not claim that they exist or that CARLA motion was realized.
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CASE = ROOT.name + "__red_no_device_entry"
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
MODULES = ("runner.py", "materialize_cases.py", "native_case_bundles.py",
           "native_world.py", "native_attempt.py",
           "native_packets.py", "native_signal.py", "native_cameras.py",
           "native_recorder.py", "walker_control.py", "saved_entry.py",
           "entry_measurement.py", "analysis.py", "delivery_audit.py",
           "comparison_audit.py")


def build(case_id=CASE):
    plan = json.loads((ROOT / "case-plan.json").read_text())
    proposals = json.loads((ROOT / "proposals/cases.json").read_text())
    ids = [case["case_id"] for case in plan["cases"]]
    selected = {case["case_id"]: case for case in proposals["cases"]
                if case["target_type"] != "baseline"}
    if set(ids) != set(selected) or case_id not in selected:
        raise ValueError("construction case selection differs from exact plan")
    description = selected[case_id]["recording_description"]
    channels = {item["name"] for item in description["channels"]}
    mandatory = {item["name"] for item in plan["observations"]
                 if item.get("mandatory", True)}
    if not mandatory <= channels:
        raise ValueError("mandatory source observations lack recorded channels")
    if {item["name"] for item in description["context_inputs"]} != {"highway_boundary"}:
        raise ValueError("full highway boundary context missing")
    config = {
        "law_id": plan["law_id"], "cell_id": plan["cell_id"],
        "actor": plan["actor"], "selected_case_id": case_id,
        "supported_case_ids": ids, "case": selected[case_id],
        "duration_s": 12, "rate_hz": 20,
        "capture_provenance": "original Native samples required",
        "required_atoms": [], "source_packets": [],
        "cameras": [{"name": name, "width": width, "height": height,
                     "pose_strategy": "source-reviewed original world location and target",
                     "fov_deg": 75} for name, width, height in CAMERAS],
        "physical_completion": {
            "criterion": "travel_progress",
            "motion_source": "trace.jsonl",
            "position_key": "position_m",
            "minimum_progress_m": 1.0,
            "engineering_tolerances_not_legal": True,
        },
    }
    measurement = {
        "format": "worker-measurement-contract",
        "case_id": case_id,
        "law_id": plan["law_id"],
        "requirements": [{
            "requirement": "Steady-red pedestrian highway entry and separate-device exception",
            "source": "inputs/" + ROOT.name + "/assignment.json",
            "output_key": "pedestrian_highway_entry",
            "method": "source-joined original walker body/highway contact and device snapshot",
            "value_type": "object", "kind": "measured",
            "inputs": ["walker-body-history.jsonl", "signal-history.jsonl",
                       "device-history.jsonl", "video_frames.jsonl", "scene.json"],
        }],
        "negative": {"remove": ["device-history.jsonl"],
                     "error_contains": "Missing required source"},
        "legal_judgment": "unresolved",
    }
    files = [{"path": name, "content": (ROOT / name).read_text()}
             for name in MODULES]
    files.extend(({"path": name, "content": json.dumps(value, indent=2) + "\n"}
                  for name, value in (("config.json", config),
                                      ("measurement-contract.json", measurement))))
    construction = {
        "law_id": plan["law_id"], "cell_id": plan["cell_id"],
        "actor": plan["actor"], "case_id": case_id,
        "status": "draft",
        "entrypoint": "runner.py", "files": files,
        "mechanisms": {
            "walker": "Original CARLA walker control and world-body vertices",
            "signal": "Source-reviewed route-facing red head and complete other-device inventory",
            "cameras": "Four synchronized original RGB streams at 20 Hz",
            "scene_asset_status": "candidate map and official device reviews pending",
        },
        "measurement_plan": measurement["requirements"],
        "recording_description": description,
        "static_checks": ["runner.py --check requires exact scene/map/review hashes",
                          "saved_entry rejects missing original packets",
                          "analysis validates Native result shape"],
        "termination_rules": ["240 original ticks at 20 Hz",
                              "abort on stale source frames or failed actor/readback",
                              "destroy owned actors and restore operator world before sealing"],
    }
    return config, measurement, construction


def main():
    config, measurement, construction = build()
    for name, value in (("config.json", config),
                        ("measurement-contract.json", measurement),
                        ("construction.json", construction)):
        (ROOT / name).write_text(json.dumps(value, indent=2) + "\n")
    print("draft shared construction bound to", len(config["supported_case_ids"]), "cases")


if __name__ == "__main__":
    main()
