"""Bind the selected active officer construction to owned, readable sources."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C157964__NRS-484B-257-1__motor_vehicle_driver"
SUFFIXES = ("officer_active_stop_then_go", "officer_active_hold",
            "officer_present_inactive", "no_officer_yield_nearest_view")
SOURCES = ("runner.py", "officer_native_capture.py", "officer_camera.py",
           "officer_capture_sources.py", "officer_direction.py",
           "officer_construction.py", "officer_site.py", "officer-site.xodr",
           "officer_measurements.py", "comparison_audit.py", "finalizer.py",
           "build_primary_construction.py", "tests/test_officer.py")


def build(case_id=None):
    config = json.loads((ROOT / "config.json").read_text())
    case_id = case_id or config["selected_case_id"]
    if case_id not in {ASSIGNMENT + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("Officer construction has wrong exact case")
    config["selected_case_id"] = case_id
    config["case"] = {"case_id": case_id}
    if case_id.endswith("__no_officer_yield_nearest_view"):
        config["officer_context"]["authority_source"] = None
        config["officer_context"]["uniform_video_source"] = None
    files = [{"path": name, "source": "work/" + ASSIGNMENT + "/" + name,
              "content": (ROOT / name).read_text()} for name in SOURCES]
    files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
    return {
        "case_id": case_id, "law_id": config["law_id"],
        "cell_id": config["cell_id"], "actor": config["actor"],
        "entrypoint": "runner.py", "status": "draft",
        "recording_description": config["recording_description"],
        "measurement_plan": {
            "raw_sources": ["officer_context.json", "officer_history.jsonl",
                            "video_frames.jsonl", "trace.jsonl",
                            "capture/evidence.jsonl",
                            *(name + ".mkv" for name in
                              ("overview", "approach", "reference_corner", "driver_reference"))],
            "analysis_entrypoint": "finalizer.py",
            "saved_processing_status": "saved finalizer CPU-tested; full compatibility pending"},
        "files": files,
        "static_checks": [
            "officer_site validates authored signed junction and both through approaches",
            "runner --check validates exact case, source cameras, source map hash and actors without CARLA",
            "officer_capture_sources rejects stale frames and prelabels no observed officer control"],
        "termination_rules": [
            "Capture exactly 600 original frames at 20 Hz or fail the attempt",
            "Close the original graph recorder before actor destruction",
            "Seal only after all camera encoders exit and original world restoration succeeds"],
        "mechanisms": [
            "Generate authored OpenDRIVE yield-sign junction in a dedicated Native world",
            "Spawn source-reviewed officer performer and ego/through vehicles",
            "Apply arm-bone stop then go program with Native readback; camera observation remains independent",
            "Retain four synchronized original FFV1 camera streams, source histories and graph capture"]}


def main():
    for suffix in SUFFIXES:
        case_id = ASSIGNMENT + "__" + suffix
        target = ROOT / ("construction.json" if suffix == SUFFIXES[0] else
                         suffix + "-construction.json")
        target.write_text(json.dumps(build(case_id), indent=2, allow_nan=False) + "\n")
        print(target)


if __name__ == "__main__":
    main()
