"""Materialize exact, unselected school-bus Native construction drafts."""
import hashlib
import json
from pathlib import Path

from bus_capture import AID, SPEEDS, capture_plan


ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def main():
    runner = (ROOT / "bus_capture.py").read_text()
    tests = (ROOT / "test_bus_capture.py").read_text().replace(
        "from bus_capture import", "from runner import")
    entries = []
    for speed in SPEEDS:
        plan = capture_plan(speed)
        config = {"assignment_id": AID, "selected_case_id": plan["case_id"],
                  "case_id": plan["case_id"], "cell_id": "C230281",
                  "law_id": "NRS-484B-360-1", "actor": "motor_vehicle_driver",
                  "requested_speed_mph": speed, "required_atoms": [],
                  "source_packets": ["bus_motion.jsonl", "video_frames.jsonl",
                                     "passenger_trip_review.json"],
                  "rate_hz": 20, "duration_s": 30,
                  "cameras": list(plan["camera_names"]), "case": plan}
        config_text = json.dumps(config, sort_keys=True, allow_nan=False) + "\n"
        proposal = {"format": "school-bus-speed-native-draft-v1",
                    "case_id": plan["case_id"], "law_id": "NRS-484B-360-1",
                    "cell_id": "C230281", "actor": "motor_vehicle_driver",
                    "entrypoint": "runner.py",
                    "recording_description": "30 seconds of source-joined school-bus travel, four cameras and original driver/trip review",
                    "files": [{"path": "runner.py", "content": runner},
                              {"path": "config.json", "content": config_text},
                              {"path": "tests/test_runner.py", "content": tests}]}
        relative = f"selected/{speed}/construction.json"
        path = PACKAGE / relative
        write(path, proposal)
        entries.append({"case_id": plan["case_id"], "kind": "delivery",
                        "construction": relative,
                        "construction_sha256": sha(path),
                        "recording_description": proposal["recording_description"]})
    write(PACKAGE / "draft-native-manifest.json", {
        "format": "worker-execution-manifest", "assignment_id": AID,
        "status": "draft_unselected_incomplete_proofs",
        "physical_acceptance_claimed": False, "cases": entries})
    print(json.dumps({"cases": len(entries), "manifest_sha256": sha(
        PACKAGE / "draft-native-manifest.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
