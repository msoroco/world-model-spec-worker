"""Embed the current exact source-gated implementation in every case bundle."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / "case-plan.json").read_text())
CASE_IDS = [row["case_id"] for row in PLAN["cases"]]
FILES = (
    "runner.py", "crossing_scene.py", "school_timing.py", "native_operator.py",
    "native_capture.py", "native_output_bridge.py", "crossing_observations.py", "saved_finalizer.py",
    "comparison_audit.py", "analysis.py", "case-plan.json",
    "tests/test_crossing_scene.py", "tests/test_crossing_observations.py",
    "tests/test_native_operator.py",
    "tests/test_comparison_audit.py", "tests/test_saved_finalizer.py",
    "tests/test_analysis.py",
)
CHANNELS = (
    "heavy_body_speed_and_crossing_zone_membership", "children_positions", "school_calendar_and_clock",
    "beacon_lamps_and_sign", "original_four_camera_pixels",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(case):
    case_id = case["case_id"]
    config = {"assignment_id": PLAN["assignment_id"], "cell_id": PLAN["cell_id"],
              "law_id": PLAN["law_id"], "actor": PLAN["actor"],
              "selected_case_id": case_id, "supported_case_ids": CASE_IDS,
              "plan_sha256": sha(ROOT / "case-plan.json"),
              "duration_s": 45, "rate_hz": 20, "required_atoms": [],
              "source_packets": [], "case": case,
              "cameras": [{"name": name, "width": 1920 if name == "overview" else 1280,
                           "height": 1080 if name == "overview" else 720,
                           "fov_deg": 80,
                           "pose_strategy": "reviewed original heavy vehicle, children, zone, beacon/sign sightline"}
                          for name in ("overview", "approach", "reference_corner", "driver_reference")]}
    description = {"channels": [
        {"name": name, "unit": "structured", "sampling_rate_hz": 20,
         "time_window": "all 900 frames", "reference_frame": "original school-crossing-zone map",
         "method": "source-sealed original Native readback and four-camera capture",
         "uncertainty": "original school sources and physical motion pending"}
        for name in CHANNELS],
        "context_inputs": [{"name": "reviewed_original_school_sources", "unit": "source",
                            "method": "SHA-256 sealed site, calendar, clock, beacon and sign survey"}],
        "limitations": ["Heavy vehicle speed target is an engineering command; actual speed requires original readback.",
                        "School exceptions and legal speed-rule judgment require independent source review."]}
    files = [{"path": name, "content": (ROOT / name).read_text()} for name in FILES]
    files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
    proposal = {"cell_id": PLAN["cell_id"], "law_id": PLAN["law_id"],
                "actor": PLAN["actor"], "case_id": case_id, "status": "draft",
                "files": files, "entrypoint": "runner.py",
                "mechanisms": ["reviewed original school-crossing-zone map and heavy vehicle route",
                               "source-hashed heavy vehicle and children construction",
                               "original calendar, half-hour clock and alternating beacon",
                               "45-second, 20-Hz four-camera Native capture"],
                "measurement_plan": {"case_id": case_id, "procedure": "saved_finalizer.py",
                                     "source_packets": ["reviewed_school_site", "original_context",
                                                        "original_trace", "original_camera_manifest"],
                                     "legal_judgment": "unresolved"},
                "recording_description": description,
                "static_checks": ["exact assignment and plan hash",
                                  "reviewed source records and Native map",
                                  "900 consecutive 20-Hz frames and four cameras"],
                "termination_rules": ["stop on source or Native readback mismatch",
                                      "restore world settings and destroy owned actors"]}
    folder = ROOT / "cases" / case_id.split("__")[-1]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "construction.json").write_text(json.dumps(proposal, indent=2) + "\n")
    return folder / "construction.json"


def main():
    for case in PLAN["cases"]:
        print(build(case))
    first = json.loads((ROOT / "cases" / CASE_IDS[0].split("__")[-1] / "construction.json").read_text())
    (ROOT / "construction.json").write_text(json.dumps(first, indent=2) + "\n")
    config = next(item for item in first["files"] if item["path"] == "config.json")
    (ROOT / "config.json").write_text(config["content"])


if __name__ == "__main__":
    main()
