"""Materialize one explicitly synthetic exact-case source packet for CPU proofs."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from prove_statutory_measurement import packet
from stop_yield_scene import CASES, request

HERE = Path(__file__).resolve().parent
BASE = HERE / "selected-source/complete_stop_then_yield"


def write(path, value):
    path.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n")


def series(path, values):
    path.write_text("".join(json.dumps(v, separators=(",", ":"), allow_nan=False) + "\n"
                            for v in values))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body(center_x, center_y, heading):
    if heading == 0:
        return [[center_x + dx, center_y + dy, z]
                for dx in (-2.25, 2.25) for dy in (-.9, .9) for z in (0, 1.5)]
    return [[center_x + dx, center_y + dy, z]
            for dx in (-.9, .9) for dy in (-2.25, 2.25) for z in (0, 1.5)]


def materialize(slug):
    if slug not in CASES or slug == "complete_stop_then_yield":
        raise ValueError("Select a different statutory diagnostic case")
    target = HERE / "selected-source" / slug
    if target.exists():
        raise ValueError("Exact selected source already exists")
    shutil.copytree(BASE, target)
    context, motions = packet(slug)
    scene = request(slug)
    (target / "road.xodr").write_text(scene["road_opendrive"] + "\n")
    map_sha = sha(target / "road.xodr")
    sign_id = scene["governing_sign"]
    write(target / "governing_sign.json", {"synthetic_diagnostic": True,
          "id": sign_id, "map_readback_sha256": map_sha})
    write(target / "governing_controls.json", {"synthetic_diagnostic": True,
          "police_controlling": scene["police_controlling"],
          "signal_controlling": scene["signal_controlling"],
          "map_readback_sha256": map_sha})
    write(target / "stopping_reference.json", {"synthetic_diagnostic": True,
          "kind": scene["stopping_reference"],
          "stop_line_x_m": scene["stop_line_x_m"], "map_readback_sha256": map_sha})
    write(target / "through_road.json", {"synthetic_diagnostic": True,
          "road_id": 111326, "map_readback_sha256": map_sha})
    write(target / "control_context.json", {"case_id": context["case_id"],
          "source_kind": "synthetic_diagnostic",
          "intersection_xy_m": [[-3.5, -3.5], [3.5, -3.5], [3.5, 3.5], [-3.5, 3.5]],
          "governing_sign_id": sign_id, "map_readback_sha256": map_sha})
    ego_rows, through_rows, traces, interactions, evidence = [], [], [], [], []
    for row in motions:
        frame, time = row["native_frame"], row["time_s"]
        x, speed, y = row["ego_x_m"], row["ego_speed_mps"], row["through_y_m"]
        ego_vertices = body(x, -1.75, 0)
        through_vertices = body(1.75, y, 90)
        ego_rows.append({"native_frame": frame, "actor_id": 1,
                         "body_vertices_m": ego_vertices, "synthetic_diagnostic": True})
        through_rows.append({"native_frame": frame, "actor_id": 2,
                             "body_vertices_m": through_vertices, "synthetic_diagnostic": True})
        traces.append({"frame": frame, "time_s": time,
                       "position": {"x": x, "y": -1.75, "z": .5},
                       "position_m": [x, -1.75, .5], "heading_deg": 0,
                       "speed_mps": speed, "speed_mph": speed * 2.2369362921,
                       "control": {"throttle": 0, "brake": 0, "hand_brake": False},
                       "velocity_mps": [speed, 0, 0], "synthetic_diagnostic": True,
                       "speed_provenance": "synthetic_native_sample"})
        interactions.append({"frame": frame, "time_s": time,
                             "ego": {"actor_id": 1, "body_vertices_m": ego_vertices},
                             "through": {"actor_id": 2, "body_vertices_m": through_vertices},
                             "synthetic_diagnostic": True})
        evidence.append({"original_frame": frame, "replay_frame": frame,
                         "actor_id": 1, "recording_time_s": time,
                         "replay_simulation_time_s": time,
                         "ego": {"position_m": [x, -1.75, .5], "heading_deg": 0,
                                 "speed_mps": speed, "speed_provenance": "synthetic_native_sample",
                                 "body_vertices_m": ego_vertices},
                         "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                                "wetness": 0, "fog_density": 0},
                                   "road_projection": {"road_id": 111325, "section_id": 0,
                                                       "lane_id": -1, "s_m": x + 80}},
                         "synthetic_diagnostic": True})
    series(target / "ego_body.jsonl", ego_rows)
    series(target / "through_body.jsonl", through_rows)
    series(target / "trace.jsonl", traces)
    series(target / "interaction_history.jsonl", interactions)
    series(target / "stop_yield_motion.jsonl", motions)
    series(target / "capture/evidence.jsonl", evidence)
    context["source_files"] = {"map": "road.xodr", "sign": "governing_sign.json",
                               "reference": "stopping_reference.json",
                               "controls": "governing_controls.json",
                               "through_road": "through_road.json",
                               "ego_body": "ego_body.jsonl", "through_body": "through_body.jsonl"}
    for name, path in context["source_files"].items():
        context[name + "_sha256"] = sha(target / path)
    (target / "stop_yield_context.json").write_text(json.dumps(context, indent=2) + "\n")
    manifest = json.loads((target / "capture/manifest.json").read_text())
    manifest["sources"] = {"road.xodr": sha(target / "road.xodr"),
                           "trace.jsonl": sha(target / "trace.jsonl")}
    (target / "capture/manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"case_id": context["case_id"], "frames": len(motions),
                      "synthetic_diagnostic": True}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("slug", choices=sorted(CASES - {"complete_stop_then_yield"}))
    materialize(parser.parse_args().slug)
