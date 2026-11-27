"""Build explicit, source-hashed CPU rail fixtures; no physical capture claim."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

from rail_native_capture import CAMERAS
from rail_sight_measurement import measure

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c410753-fixture-build"


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def build_one(case):
    key = case["case_id"].removeprefix(HERE.name + "__")
    scratch = Path(tempfile.mkdtemp(prefix=key + "-", dir=SCRATCH))
    files = {}

    def add(name, value):
        text = value if isinstance(value, str) else encoded(value)
        files[name] = text
        path = scratch / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return {"path": name, "sha256": sha(text)}

    road = "<OpenDRIVE><road name=\"diagnostic-rail-fixture\"/></OpenDRIVE>\n"
    map_ref = add("diagnostic-road.xodr", road)
    review_ref = add("diagnostic-review.json", {
        "road_sha256": sha(road), "grade_crossing": True,
        "railway_kind": "electric", "track_extent_each_direction_ft": 400,
        "approach_extent_ft": 100, "municipal_jurisdiction": True,
        "diagnostic_fixture": True})
    packet = {"assignment_id": HERE.name, "case_id": case["case_id"],
              "diagnostic_fixture": True, "road_sha256": sha(road),
              "original_map_source": map_ref, "railway_review_source": review_ref}
    packet_ref = add("reviewed-rail-packet.json", packet)
    mph = case["engineering_target_traversal_mph"]
    speed = mph / 2.2369362920544
    obstructed = case["engineering_sight_setup"] == "obscured"
    exception = case["exception_setup"]
    frames, cameras = [], []
    observed_keys = ("original_frame", "time_s", "route_station_m", "speed_mps",
                     "position_xy_m", "body_on_crossing", "flagman_on_duty",
                     "signal_installed", "signal_clearly_visible",
                     "signal_immediate_train_approach")
    for index in range(900):
        frame = {"original_frame": index, "time_s": index * .05,
                 "route_station_m": index * speed * .05,
                 "speed_mps": speed, "position_xy_m": [index * speed * .05, 0.0],
                 "body_on_crossing": 300 <= index < 350,
                 "flagman_on_duty": exception == "flagman_on_duty" and 300 <= index < 350,
                 "signal_installed": exception in ("visible_nonwarning_signal", "visible_warning_signal"),
                 "signal_clearly_visible": exception in ("visible_nonwarning_signal", "visible_warning_signal"),
                 "signal_immediate_train_approach": exception == "visible_warning_signal"}
        ray = {"frame": index, "crossing": True,
               "rail_minus_400ft": not (obstructed and index == 299),
               "rail_plus_400ft": True}
        exception_ref = add(f"original-exceptions/{index:08d}.json", {
            "frame": index, **{name: frame[name] for name in observed_keys[6:]}})
        source_ref = add(f"original-frames/{index:08d}.json", {
            **frame, "exception_source_trace": exception_ref})
        ray_ref = add(f"original-rays/{index:08d}.json", ray)
        frames.append({**frame, "sight_crossing_clear": ray["crossing"],
                       "sight_rail_negative_400ft_clear": ray["rail_minus_400ft"],
                       "sight_rail_positive_400ft_clear": ray["rail_plus_400ft"],
                       "frame_source_path": source_ref["path"],
                       "frame_source_sha256": source_ref["sha256"],
                       "sight_source_path": ray_ref["path"],
                       "sight_source_sha256": ray_ref["sha256"]})
        cameras.append({"original_frame": index,
                        "sources": {name: {"sha256": "0" * 64} for name in CAMERAS}})
    frame_ref = add("native-rail-frames.json", frames)
    camera_ref = add("native-rail-camera-map.json", cameras)
    files["video_frames.jsonl"] = "".join(encoded({
        "video_frame": frame["original_frame"],
        "carla_frame": frame["original_frame"],
        "native_frame": frame["original_frame"],
        "time_s": frame["time_s"],
    }) for frame in frames)
    measurement = measure(scratch, packet, road, frames)
    add("native-rail-receipt.json", {
        "case_id": case["case_id"], "capture_kind": "diagnostic_fixture",
        "fps": 20, "duration_s": 45, "frame_count": 900,
        "packet": packet_ref, "frames": frame_ref, "camera_map": camera_ref,
        "measurement": measurement, "legal_conclusion": None})
    spec = {"files": files, "graphs": [],
            "videos": [{"path": name + ".mkv", "frames": 900,
                        "width": size[0], "height": size[1], "fps": 20,
                        "color": "black"} for name, size in CAMERAS.items()]}
    folder = HERE / "diagnostic-fixtures" / key
    folder.mkdir(parents=True, exist_ok=True)
    spec_path = folder / "fixture-spec.json"
    spec_path.write_text(json.dumps(spec, sort_keys=True, separators=(",", ":")) + "\n")
    recipe = {"format": "worker-fixture-recipe", "sources": [
        {"path": "fixture-source.txt", "source": "work/" + HERE.name + "/diagnostic-source.txt",
         "sha256": sha((HERE / "diagnostic-source.txt").read_text())}],
        "generator": {"source": str(spec_path.relative_to(REPO)),
                      "sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest()}}
    (folder / "fixture-recipe.json").write_text(json.dumps(recipe, indent=2, sort_keys=True) + "\n")
    if spec_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("diagnostic fixture spec exceeds work file limit")
    return key, spec_path.stat().st_size


def build():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    marker = HERE / "diagnostic-source.txt"
    marker.write_text("Synthetic rail compatibility fixture; no original CARLA observation.\n")
    plan = json.loads((HERE / "case-plan.json").read_text())
    return [build_one(case) for case in plan["cases"]]


if __name__ == "__main__":
    print(build())
