"""Bind exact source files into four draft Native constructions."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = "training__C228817__NRS-484B-153-3__motor_vehicle_driver"
SOURCES = {
    "runner.py": "runner.py",
    "controller.py": "controller.py",
    "door_actuation.py": "door_actuation.py",
    "measure_door.py": "measure_door.py",
    "finalize.py": "finalize.py",
    "tests/test_offline.py": "test_offline.py",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    manifest = {"format": "draft-execution-manifest", "assignment_id": ASSIGNMENT,
                "status": "draft_not_selected", "cases": []}
    for number in (1, 2, 3, 4):
        case_id = ASSIGNMENT + "__probe_" + str(number)
        files = [{"path": name, "content": (ROOT / source).read_text()}
                 for name, source in SOURCES.items()]
        channels = ("sig.door_open", "kin.time", "drv.standing_or_parked",
                    "ru.occupant_count", "ru.pedestrian", "st.lane")
        description = {
            "channels": [{"name": name, "unit": "structured",
                          "method": "original Native source frame join and reviewed four-camera pixels",
                          "sampling_rate_hz": 20, "time_window": "all 600 frames",
                          "reference_frame": "original Native tick and camera frame map",
                          "uncertainty": "actuator request does not establish observed physical state; necessity remains unresolved"}
                         for name in channels],
            "context_inputs": [],
            "limitations": [
                "Door pose, occupant transfer and camera visibility require original-source review",
                "Legal necessity duration remains unresolved"]}
        config_path = ROOT / f"config-probe-{number}.json"
        config = json.loads(config_path.read_text())
        config["selected_case_id"] = case_id
        config["recording_description"] = description
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
        files.append({"path": "config.json", "content": config_path.read_text()})
        construction = {
            "format": "worker-inline-construction", "case_id": case_id,
            "cell_id": "C228817", "actor": "motor_vehicle_driver",
            "entrypoint": "runner.py", "files": files,
            "recording_description": description,
            "measurement_plan": {
                "procedure": "source-hashed per-frame Native door and transfer measurements",
                "sources": ["original-map.json", "original-road.json",
                            "original-transfer.json", "native-door-trace.jsonl",
                            "video_frames.jsonl", "overview.mkv", "approach.mkv",
                            "reference_corner.mkv", "driver_reference.mkv"],
                "selected_measurements": ["open_duration_s", "post_transfer_open_s",
                                          "passing_side"],
                "legal_necessity": None},
            "static_checks": ["exact case and frozen-cell identity",
                              "20 Hz, 600 frames and four source cameras",
                              "door command distinct from observed door state",
                              "source-hashed map, road and transfer setup"],
            "termination_rules": ["retain exactly 600 original Native frames",
                                  "close four source-video encoders",
                                  "restore world settings and destroy owned actors"],
            "mechanisms": ["source-bound original map and lane setup",
                           "stationary ego door actuator transitions",
                           "passing vehicle and pedestrian transfer requests",
                           "full source camera and actor trajectory capture"]}
        path = ROOT / f"probe-{number}-construction.json"
        path.write_text(json.dumps(construction, indent=2, ensure_ascii=False) + "\n")
        manifest["cases"].append({
            "case_id": case_id, "construction": path.name,
            "construction_sha256": sha(path), "candidates": [],
            "candidate_risk": {"status": "physical",
                               "reason": "Door pose, passing path and transfer visibility need original CARLA readback; fallback construction pending"}})
    (ROOT / "draft-execution-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return {"case_ids": [item["case_id"] for item in manifest["cases"]],
            "manifest_sha256": sha(ROOT / "draft-execution-manifest.json")}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
