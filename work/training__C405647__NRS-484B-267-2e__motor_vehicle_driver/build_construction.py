"""Materialize five exact statutory-alternative Native construction bundles."""
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
AID = HERE.name
CHANNELS = (
    "drv.responding_emergency", "st.lane", "st.lane_adjacency",
    "rel.occupies", "drv.lane_change_feasible", "env.precipitation",
    "env.wet_road", "st.obstruction", "drv.queue_behind",
    "dev.human_direction",
)
FILES = ("runner.py", "road_geometry.py", "hand_signal_pose.py",
         "source_review.py", "saved_measure.py", "finalize.py",
         "tests/test_current_runner.py", "tests/test_geometry.py",
         "tests/test_saved_measure.py", "tests/test_source_review.py")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    template = json.loads((HERE / "config.json").read_text())
    recording = {
        "channels": [{"name": name, "unit": "structured", "sampling_rate_hz": 20,
                      "method": "Original Native actor, lane, lamp and pixel frames joined to independently hashed emergency, topology, condition and officer sources",
                      "time_window": "all 600 original approach frames",
                      "reference_frame": "authored road 405647 with Native lane readback",
                      "uncertainty": "Possibility, safety, visible qualification and officer override require independent original review"}
                     for name in CHANNELS],
        "context_inputs": [],
        "limitations": ["Lane count and 0.05 m/s motion tolerance are not legal possibility or safety cutoffs",
                        "Requested hand pose is not proof of visible driver or officer signaling",
                        "Synthetic source packets establish software compatibility only"]}
    for i in range(1, 6):
        suffix = f"probe_0{i}"
        case = AID + "__" + suffix
        directory = HERE / "cases" / suffix
        config = dict(template)
        config.update(case_id=case, selected_case_id=case,
                      requested_response="move_nonadjacent" if i == 1 else "stay_adjacent",
                      requested_source_mode="visible_hand_signal" if i == 4 else "moving_vehicle",
                      adverse_traffic_and_rain_requested=i == 3,
                      officer_direction_requested=i == 5,
                      required_atoms=[], source_packets=[],
                      recording_description=recording,
                      case={"case_id": case, "recording_description": recording})
        write(directory / "config.json", config)
        files = [{"path": name, "content": (HERE / name).read_text()} for name in FILES]
        files.append({"path": "config.json", "content": (directory / "config.json").read_text()})
        construction = {
            "format": "worker-inline-construction", "case_id": case,
            "law_id": "NRS-484B-267-2e", "cell_id": "C405647",
            "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
            "files": files, "recording_description": recording,
            "measurement_plan": {"entrypoint": "finalize.py", "source_review_required": True,
                                 "required_sources": ["emergency-review.json", "video_frames.jsonl",
                                      "emergency-native.jsonl", "lamp-pixel-review.json",
                                      "signal-pixel-review.json", "trace.jsonl",
                                      "source_context/vehicle_authorization.txt",
                                      "source_context/flashing_equipment.txt",
                                      "source_context/flashing_qualification.txt",
                                      "source_context/lamp_pixels.txt",
                                      "source_context/lane_topology.txt",
                                      "source_context/roadway_conditions.txt",
                                      "source_context/traffic_conditions.txt",
                                      "source_context/weather_conditions.txt",
                                      "source_context/officer_direction.txt",
                                      "source_context/hand_signal_pixels.txt"]},
            "static_checks": ["Three same-direction 3.5 m lanes with emergency in -1, ego initially -2 and nonadjacent -3",
                              "Four synchronized 20 Hz cameras for 600 original frames",
                              "Distinct moving, hand-signal preparation, adverse-condition and officer-direction requests"],
            "mechanisms": ["Authored OpenDRIVE with Native lane readback",
                           "Original ego, emergency, traffic and signal actor acquisition",
                           "Hashed original authorization, lamp, lane, condition and direction sources"],
            "termination_rules": ["600 original Native frames", "Destroy owned actors and restore world"],
            "status": "cpu_construction_physical_unverified"}
        write(directory / "construction.json", construction)
        if i == 1:
            write(HERE / "config.json", config)
            write(HERE / "construction.json", construction)
    print(json.dumps({"selected_case_ids": [AID + f"__probe_0{i}" for i in range(1, 6)]}))


if __name__ == "__main__":
    main()
