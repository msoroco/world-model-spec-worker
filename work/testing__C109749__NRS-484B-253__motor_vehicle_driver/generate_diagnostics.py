"""Build explicit, source-hashed compatibility fixtures for exact cases.

Every output is diagnostic text. The four video sources are generated separately
by the pinned fixture generator; no generated frame is physical CARLA evidence.
Reciprocal cases use a 900-frame separate third-actor source for their saved join.
"""

import hashlib
import json
from pathlib import Path

from construction import POLICIES
from requirement_finalizer import ASSIGNMENT_ID

ROOT = Path(__file__).resolve().parent


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def body(x, y):
    return [[x + dx, y + dy, dz] for dz in (-0.5, 0.5)
            for dx in (-0.5, 0.5) for dy in (-0.5, 0.5)]


def make(suffix):
    case_id = ASSIGNMENT_ID + "__" + suffix
    packet = json.loads((ROOT / "cases/inside_yield/diagnostic-map.json").read_text())
    packet["source_ref"] = "diagnostic-only-source-shaped-map"
    packet["reviewed_original_map"] = False
    packet_text = encode(packet)
    road_text = (ROOT / "diagnostic-road.xodr").read_text(encoding="utf-8")
    approaching = suffix.startswith("approaching")
    wait = POLICIES[suffix][1]
    signal = POLICIES[suffix][2]
    rows = []
    trace = []
    mapping = []
    motion = []
    evidence = []
    graphs = []
    reciprocal = suffix.startswith("reciprocal_")
    count = 900 if reciprocal else 2
    later = []
    for index in range(count):
        time_s = index / 20
        ego_y = 0 if index == 0 else 0.5
        other_y = (1 if index < 100 else 7) if reciprocal else (
            7 if approaching and index == 0 else 1 + index)
        rows.append({"frame": index, "time_s": time_s,
                     "ego_actor_id": 11, "opponent_actor_id": 12,
                     "ego_driver_control_source": "diag",
                     "opponent_driver_control_source": "diag",
                     "ego_vertices": body(0, ego_y),
                     "opponent_vertices": body(1, other_y),
                     "ego_heading": [0, 1], "opponent_heading": [0, -1],
                     "ego_speed_mps": 1,
                     "opponent_speed_mps": 3 if suffix == "reciprocal_no_yield" else 2,
                     "ego_signal_left": signal,
                     "ego_turn_committed": (index >= 110 if reciprocal else index == 1 and not wait),
                     "opponent_cleared": False, "ego_braking": wait})
        if reciprocal:
            later_y = 9 if index < 120 else 1
            later.append({"frame": index, "time_s": time_s,
                          "later_opponent_actor_id": 13,
                          "later_opponent_vertices": body(2, later_y),
                          "later_opponent_heading": [0, -1],
                          "later_opponent_speed_mps": 2.0,
                          "later_opponent_braking": suffix == "reciprocal_yield" and index >= 110,
                          "later_opponent_driver_control_source": "diag"})
        trace.append({"frame": index, "time_s": time_s,
                      "control": {},
                      "position": {"x": 0, "y": ego_y, "z": 0},
                      "heading_deg": 90.0, "speed_mps": 1.0,
                      "speed_mph": 2.236936 if reciprocal else 1.0 / 0.44704,
                      "position_m": [0, ego_y, 0]})
        trace[-1]["velocity_mps"] = [0, 1, 0]
        mapping.append({"video_frame": index, "carla_frame": index,
                        "native_frame": index, "time_s": time_s})
        motion.append({"frame": index, "time_s": time_s,
                       "subject_body_vertices_m": body(0, ego_y)})
        observed = {"frame": index, "time_s": time_s,
                    "participants": [], "map_context": {"junction_id": 9}}
        evidence.append({"actor_id": 11,
                         "ego": {"body_vertices_m": body(0, ego_y),
                                 "heading_deg": 90.0,
                                 "position_m": [0, ego_y, 0],
                                 "speed_mps": 1.0,
                                 "speed_provenance": "synthetic_native_sample"},
                         "world": {"weather": {}},
                         "original_frame": index, "replay_frame": index,
                         "recording_time_s": time_s,
                         "replay_simulation_time_s": time_s,
                         "original_observations": observed})
        graphs.append({"path": f"capture/native/graphs/base/{index:08d}.adapter.json",
                       "attributes": {"frame": index, "time_s": time_s,
                                      "observed_evidence": observed},
                       "nodes": [], "edges": []})
    rows_text = "".join(encode(row) for row in rows)
    receipt = {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
               "map_sha256": digest(packet_text), "trace_sha256": digest(rows_text),
               "native_map_sha256": packet["map_sha256"],
               "source_id": "diagnostic-" + suffix, "frame_count": count,
               "simulator_frame_rate_hz": 20, "diagnostic_fixture": True}
    if reciprocal:
        later_text = "".join(encode(row) for row in later)
        receipt["later_opponent_trace_sha256"] = digest(later_text)
    files = {"original-map.json": packet_text,
             "road.xodr": road_text,
             "original-trace.jsonl": rows_text,
             "acquisition-receipt.json": encode(receipt),
             "acquisition-provenance.json": encode({"provenance_kind": "synthetic_fixture",
                                                     "diagnostic_fixture": True}),
             "trace.jsonl": "".join(encode(row) for row in trace),
             "video_frames.jsonl": "".join(encode(row) for row in mapping),
             "interaction_history.jsonl": "".join(encode(row) for row in motion),
             "road_geometry.json": encode({"intersection_xy_m": packet["intersection_polygon"]}),
             "capture/evidence.jsonl": "".join(encode(row) for row in evidence),
             "capture/native/frames.jsonl": "".join(encode({"frame": i,
                 "simulation_time": i / 20,
                 "adapter_graph": f"graphs/base/{i:08d}.adapter.json"}) for i in range(count)),
             "capture/recorder_info.txt": "Create 11: vehicle.ego (diagnostic) at (0, 0, 0)\n",
             "capture/manifest.json": encode({"case_id": case_id,
                 "frames": count, "status": "draft", "extraction_confirmed": True,
                 "acquisition": "diagnostic_fixture",
                 "sources": {"trace.jsonl": digest("".join(encode(row) for row in trace)),
                             "road.xodr": digest(road_text)}})}
    if reciprocal:
        files["later-opponent-original.jsonl"] = later_text
    videos = [{"path": name + ".mkv", "frames": count, "width": width,
               "height": height, "fps": 20, "color": "black"}
              for name, width, height in (("overview", 1920, 1080),
                                          ("approach", 1280, 720),
                                          ("reference_corner", 1280, 720),
                                          ("driver_reference", 1280, 720))]
    folder = ROOT / "cases" / suffix
    diagnostic = folder / "diagnostic.json"
    diagnostic.write_text(encode({"files": files, "graphs": graphs,
                                  "videos": videos}), encoding="utf-8")
    note = folder / "diagnostic-source-note.json"
    note.write_text(encode({"case_id": case_id, "scope": "synthetic software compatibility only",
                            "physical_acceptance": "unverified"}), encoding="utf-8")
    source = str(note.relative_to(ROOT.parents[1]))
    generator = str(diagnostic.relative_to(ROOT.parents[1]))
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": "diagnostic-source-note.json", "source": source,
                           "sha256": hashlib.sha256(note.read_bytes()).hexdigest()}],
              "generator": {"source": generator,
                            "sha256": hashlib.sha256(diagnostic.read_bytes()).hexdigest()}}
    (folder / "fixture-recipe.json").write_text(encode(recipe), encoding="utf-8")


if __name__ == "__main__":
    for suffix in POLICIES:
        make(suffix)
    print("generated", len(POLICIES), "source-shaped diagnostic recipes")
