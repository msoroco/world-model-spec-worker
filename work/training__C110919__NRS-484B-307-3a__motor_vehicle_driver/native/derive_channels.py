"""Derive diagnostic channels from retained Native sources after capture.

This is a CPU source-join proof, not a claim about CARLA observations.  It writes
only into a fresh output directory and refuses fixture-supplied channel files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError(f"Missing retained Native source: {path.name}")
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def derive(attempt: Path, output: Path) -> dict:
    attempt = attempt.resolve()
    output = output.resolve()
    if output.exists():
        raise ValueError("Derived channel output already exists")
    if (attempt / "channels").exists():
        raise ValueError("Injected fixture channels are not retained Native sources")
    config_path = attempt / "config.json"
    geometry_path = attempt / "road_geometry.json"
    if not config_path.is_file() or not geometry_path.is_file():
        raise ValueError("Missing retained Native config or road geometry")
    config = json.loads(config_path.read_text())
    geometry = json.loads(geometry_path.read_text())
    files = {
        "native": attempt / "native_samples.jsonl",
        "map": attempt / "video_frames.jsonl",
        "trace": attempt / "trace.jsonl",
        "evidence": attempt / "capture/evidence.jsonl",
        "body": attempt / "body_history.jsonl",
    }
    rows = {name: read_rows(path) for name, path in files.items()}
    count = config["rate_hz"] * config["duration_s"]
    if count < 600:
        raise ValueError("Retained capture is shorter than 30 seconds")
    if any(len(value) != count for value in rows.values()):
        raise ValueError("Retained Native source frame count differs")
    source_hashes = {name: digest(path) for name, path in files.items()}
    source_hashes["config"] = digest(config_path)
    source_hashes["road_geometry"] = digest(geometry_path)
    expected_names = set(config["mandatory_channels"])
    if expected_names != {
        "dev.traffic_signal", "st.stop_line", "st.crosswalk", "drv.stopped",
        "kin.velocity", "drv.extreme_lane", "st.one_way_roadway", "drv.yields_to",
        "native_body_pose_control", "camera_frame_join",
    }:
        raise ValueError("Mandatory channel contract differs")
    channels = {name: [] for name in expected_names}
    previous = -1
    previous_time = None
    for index in range(count):
        n, m, t, e, b = (rows[key][index] for key in ("native", "map", "trace", "evidence", "body"))
        frame = n.get("native_frame")
        time_s = n.get("time_s")
        if type(frame) is not int or frame <= previous or m.get("video_frame") != index:
            raise ValueError("Retained Native frame order differs")
        previous = frame
        if any(value != frame for value in (m.get("native_frame"), t.get("frame"),
                                            e.get("original_frame"), b.get("frame"))):
            raise ValueError("Retained Native frame join differs")
        times = (m.get("time_s"), t.get("time_s"), e.get("recording_time_s"), b.get("time_s"))
        if type(time_s) not in (int, float) or not math.isfinite(time_s) or any(
            type(value) not in (int, float) or abs(value - time_s) > 1e-4 for value in times
        ):
            raise ValueError("Retained Native time join differs")
        if previous_time is not None and abs((time_s - previous_time) - 1 / config["rate_hz"]) > 1e-3:
            raise ValueError("Retained Native 20 Hz cadence differs")
        previous_time = time_s
        speed = n.get("speed_mps")
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError("Retained Native speed differs")
        body_xy = {(round(x, 4), round(y, 4)) for x, y in n["native_body_xy_m"]}
        body_3d = {(round(v[0], 4), round(v[1], 4)) for v in b["body_vertices_m"]}
        if len(body_xy) != 4 or body_xy != body_3d:
            raise ValueError("Retained Native body join differs")
        signal = {
            "observed_state": n["signal_state_observed"],
            "right_arrow_state": n["right_arrow_state_observed"],
            "opposing_signal_state": n["opposing_signal_state_observed"],
            "right_arrow_actor_id": n["right_arrow_actor_id"],
            "opposing_signal_actor_id": n["opposing_signal_actor_id"],
            "arrow_glyph_physically_verified": False,
        }
        values = {
            "dev.traffic_signal": signal,
            "st.stop_line": geometry["stop_line_y_m"],
            "st.crosswalk": geometry["nearest_crosswalk_y_m"],
            "drv.stopped": speed < .05,
            "kin.velocity": speed,
            "drv.extreme_lane": geometry["lanes"]["approach_right"],
            "st.one_way_roadway": geometry["lanes"],
            "drv.yields_to": {
                "walker_conflict_occupied": n["walker_conflict_occupied"],
                "cross_traffic_conflict_occupied": n["cross_traffic_conflict_occupied"],
            },
            "native_body_pose_control": n,
            "camera_frame_join": m,
        }
        for name, value in values.items():
            channels[name].append({"time_s": time_s, "value": value})
    output.mkdir(parents=True)
    channel_hashes = {}
    for name in sorted(channels):
        path = output / f"{name}.jsonl"
        path.write_text("".join(json.dumps(row, allow_nan=False, sort_keys=True) + "\n"
                                for row in channels[name]))
        channel_hashes[name] = digest(path)
    receipt = {"format": "c110919-raw-derived-channels-v1", "frames": count,
               "diagnostic_only": True, "source_hashes": source_hashes,
               "channel_hashes": channel_hashes}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(derive(args.attempt, args.output)))


if __name__ == "__main__":
    main()
