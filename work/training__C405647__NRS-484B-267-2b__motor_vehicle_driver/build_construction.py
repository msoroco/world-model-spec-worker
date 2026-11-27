"""Materialize five exact statutory-alternative Native construction bundles."""
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
AID = HERE.name
CHANNELS = (
    "drv.responding_emergency", "drv.approaching", "rel.visible",
    "drv.time_to_conflict", "rel.surface_gap", "kin.speed",
    "drv.hard_deceleration", "dev.human_direction",
)
FILES = ("runner.py", "road_geometry.py", "hand_signal_pose.py",
         "source_review.py", "measure_emergency.py", "saved_measure.py", "finalize.py",
         "tests/test_emergency_caution.py")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    template = json.loads((HERE / "config.json").read_text())
    recording = {
        "channels": [{"name": name, "unit": "structured", "sampling_rate_hz": 20,
                      "method": "Original Native body, speed, lamp and pixel frames joined to independently hashed emergency, visibility and officer sources",
                      "time_window": "all 600 original approach frames",
                      "reference_frame": "authored road 405647 with Native lane readback",
                      "uncertainty": "Qualitative caution, visible qualification and officer override require independent original review"}
                     for name in CHANNELS],
        "context_inputs": [],
        "limitations": ["Speed, gap, time to conflict and deceleration are diagnostics, not a legal caution cutoff",
                        "Requested hand pose is not proof of visible driver or officer signaling",
                        "Synthetic source packets establish software compatibility only"]}
    for i in range(1, 6):
        suffix = f"probe_0{i}"
        case = AID + "__" + suffix
        directory = HERE / "cases" / suffix
        config = dict(template)
        config.update(case_id=case, selected_case_id=case,
                      requested_response="fast_narrow" if i == 2 else "slow_wide",
                      requested_source_mode="visible_hand_signal" if i == 4 else "moving_vehicle",
                      requested_role="official_regulatory" if i == 3 else "authorized_emergency",
                      adverse_traffic_and_rain_requested=False,
                      officer_direction_requested=i == 5,
                      required_atoms=[], source_packets=[],
                      recording_description=recording,
                      case={"case_id": case, "recording_description": recording})
        write(directory / "config.json", config)
        files = [{"path": name, "content": (HERE / name).read_text()} for name in FILES]
        files.append({"path": "config.json", "content": (directory / "config.json").read_text()})
        construction = {
            "format": "worker-inline-construction", "case_id": case,
            "law_id": "NRS-484B-267-2b", "cell_id": "C405647",
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
            "static_checks": ["Two-way authored road with emergency in -1 and ego in -2; original Native lane readback required",
                              "Four synchronized 20 Hz cameras for 600 original frames",
                              "Distinct speed/clearance, official regulatory, hand-signal preparation and officer-direction requests"],
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
