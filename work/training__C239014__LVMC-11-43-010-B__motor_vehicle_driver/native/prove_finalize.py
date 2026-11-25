"""Source-shaped finalizer CPU checks; fixtures are never Native evidence."""
import argparse
import json
from pathlib import Path

from finalize import analyze, finalize
from gap_request import request_row
from geometry import open_drive


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))


def create(root, condition):
    root.mkdir(parents=True, exist_ok=True)
    case = "training__C239014__LVMC-11-43-010-B__motor_vehicle_driver__selected_a60a4f45__" + condition
    release = 17.0 if condition == "condition_a" else 12.5
    config = {"case_id": case, "selected_case_id": case,
              "law_id": "LVMC-11-43-010-B", "cell_id": "C239014",
              "rate_hz": 20, "duration_s": 30, "entry_release_s": release,
              "recording_description": {"channels": [], "context_inputs": [],
                                        "limitations": ["synthetic CPU fixture"]}}
    (root / "config.json").write_text(json.dumps(config) + "\n")
    (root / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "synthetic_fixture", "native_executed": False}) + "\n")
    (root / "road.xodr").write_text(open_drive())
    (root / "roundabout-map-readback.json").write_text(json.dumps({
        "source_kind": "native_map_readback", "samples": [
            {"road_id": 1}, {"road_id": 2}]}) + "\n")
    raw, controls, frames, trace = [], [], [], []
    for i in range(600):
        request = request_row(i, "waited_entry" if condition == "condition_a" else "early_entry")
        actors = []
        for role, source in (("ego", request["ego"]),
                             ("lead", request["circulating"][0]),
                             ("follower", request["circulating"][1])):
            actors.append({"role": role, "actor_id": {"ego": 1, "lead": 2, "follower": 3}[role],
                "blueprint_id": "vehicle.synthetic.cpu", "x_m": source["x_m"],
                "y_m": source["y_m"], "speed_mps": source["speed_mps"],
                "bbox_half_length_m": 2.0, "bbox_half_width_m": 1.0,
                "road_id": 2 if role == "ego" and source["phase"] != "circulation" else 1,
                "lane_id": -1})
        frame = 1000 + i
        t = i / 20
        raw.append({"video_frame": i, "native_frame": frame, "time_s": t,
                    "case_id": case, "actors": actors})
        controls.append({"video_frame": i, "native_frame": frame, "time_s": t,
                         "controls": {role: {} for role in ("ego", "lead", "follower")}})
        frames.append({"video_frame": i, "carla_frame": frame,
                       "native_frame": frame, "time_s": t,
                       "camera_native_frames": {name: frame for name in
                           ("overview", "approach", "reference_corner", "driver_reference")}})
        trace.append({"frame": frame, "time_s": t,
                      "position": {"x": actors[0]["x_m"], "y": actors[0]["y_m"], "z": 0},
                      "speed_mps": actors[0]["speed_mps"]})
    for name, values in (("native-raw-actors.jsonl", raw),
                         ("control-intent.jsonl", controls),
                         ("video_frames.jsonl", frames), ("trace.jsonl", trace)):
        write_rows(root / name, values)
    for camera in ("overview", "approach", "reference_corner", "driver_reference"):
        (root / (camera + ".mkv")).write_text("CPU fixture placeholder, not footage\n")


def prove(root):
    outcomes = {}
    for condition in ("condition_a", "condition_b"):
        attempt = root / condition
        create(attempt, condition)
        report = analyze(attempt)
        if report["frames"] != 600 or report["physical_completion_claimed"]:
            raise AssertionError("Source fixture meter contract differs")
        outcomes[condition] = {"first_entry_frame": report["first_entry_frame"],
                               "previous_gap_s": report["previous_gap_s"],
                               "next_gap_s": report["next_gap_s"],
                               "traffic_near_at_entry": report["traffic_near_at_entry"]}
        source = attempt / "native-raw-actors.jsonl"
        original = source.read_text()
        lines = original.splitlines()
        changed = json.loads(lines[0])
        changed["actors"].pop()
        lines[0] = json.dumps(changed)
        source.write_text("\n".join(lines) + "\n")
        try:
            analyze(attempt)
        except ValueError as error:
            if str(error) != "Required circulating actor source missing":
                raise
        else:
            raise AssertionError("Missing circulating source accepted")
        source.write_text(original)
        frame_map = attempt / "video_frames.jsonl"
        original = frame_map.read_text()
        frame_map.write_text("\n".join(original.splitlines()[:-1]) + "\n")
        try:
            analyze(attempt)
        except ValueError as error:
            if str(error) != "Incomplete 600-frame original source join":
                raise
        else:
            raise AssertionError("Incomplete frame map accepted")
        frame_map.write_text(original)
        finalized = finalize(attempt, root / (condition + "-finalized.json"))
        if finalized["case_id"] != report["case_id"] or not (attempt / "result.json").is_file():
            raise AssertionError("Saved result writer failed")
    return {"format": "c239014-finalizer-source-proof-v1", "conditions": outcomes,
            "negative_missing_actor": True, "negative_missing_frame": True,
            "saved_result_writer_passed": True,
            "native_executed": False, "physical_completion_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(prove(Path(args.output)), indent=2, sort_keys=True))
