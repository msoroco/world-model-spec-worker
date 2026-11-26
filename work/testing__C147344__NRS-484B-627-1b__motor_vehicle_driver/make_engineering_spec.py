"""Generate bounded engineering-case 900-frame synthetic converter fixtures.

All labels identify CPU fixtures. The map is an authored diagnostic road,
not reviewed public-highway or statutory source evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from reviewed_scene import ASSIGNMENT
from engineering_sweep_station import engineering_station

ROOT = Path(__file__).resolve().parent


def compact(data):
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def lines(rows):
    return "".join(compact(row) + "\n" for row in rows)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build(suffix):
    case_id = ASSIGNMENT + "__" + suffix
    station = engineering_station(case_id)
    if station is None:
        raise ValueError("unassigned engineering fixture")
    anchor, role, requested = station
    right = False
    immediate = True
    passing = anchor == "slow_middle_passing"
    ego_speed = requested if role == "ego" else 5.0
    slower_speed = requested if role == "slower_vehicle" else 3.0
    ego_lane = "-1" if right else "-2"
    following_lane = ego_lane if immediate else "-1"
    trace = {"assignment_id": ASSIGNMENT, "case_id": case_id,
             "original_trace_id": "synthetic-fixture-" + suffix, "diagnostic_fixture": True,
             "frames": [{"frame": i, "time_s": i / 20, "ego_speed_mps": ego_speed,
                         "follower_gap_m": 20.0 - i * .001,
                         "follower_speed_mps": 8.0,
                         "slower_vehicle_speed_mps": slower_speed,
                         "ego_lane_id": ego_lane,
                         "rightmost_same_direction_lane_id": "-1",
                         "follower_actor_id": "fixture-follower",
                         "follower_lane_id": following_lane,
                         "passing_slower_vehicle_observed": passing and i >= 450,
                         "same_direction_marked_lane_count": 2} for i in range(900)]}
    relation = {"case_id": case_id, "source_kind": "original_native_relation",
                "relation_basis_source": "synthetic ordering fixture only",
                "samples": [{"frame": i, "time_s": i / 20,
                             "follower_actor_id": "fixture-follower",
                             "immediately_behind": immediate} for i in range(900)]}
    frames = [{"video_frame": i, "carla_frame": i, "native_frame": i,
               "time_s": i / 20} for i in range(900)]
    traces = [{"frame": i, "time_s": i / 20,
               "position_m": [20 + ego_speed / 20 * i, -5.25 if not right else -1.75, 0],
               "position": {"x": 20 + ego_speed / 20 * i,
                            "y": -5.25 if not right else -1.75, "z": 0},
               "speed_mps": ego_speed, "speed_mph": ego_speed / .44704,
               "velocity_mps": [ego_speed, 0, 0], "heading_deg": 0, "control": {}}
              for i in range(900)]
    evidence = [{"original_frame": i, "replay_frame": i, "actor_id": 11,
                 "recording_time_s": i / 20, "replay_simulation_time_s": i / 20,
                 "world": {"weather": {}},
                 "ego": {"position_m": traces[i]["position_m"], "heading_deg": 0,
                         "speed_mps": ego_speed, "speed_provenance": "synthetic_native_sample",
                         "body_vertices_m": [[20 + ego_speed / 20 * i + dx,
                                              (-5.25 if not right else -1.75) + dy, z]
                                             for dx, dy, z in ((-2,-1,0),(-2,-1,1.5),(2,-1,0),(2,-1,1.5),(-2,1,0),(-2,1,1.5),(2,1,0),(2,1,1.5))]},
                 "original_observations": {"frame": i, "time_s": i / 20,
                                           "participants": [], "map_context": {"declared_public_way_road_ids": []}}}
                for i in range(900)]
    graphs = [{"path": f"capture/native/graphs/base/{i:08d}.adapter.json",
               "attributes": {"frame": i, "time_s": i / 20,
                              "observed_evidence": evidence[i]["original_observations"]},
               "nodes": [], "edges": []} for i in range(900)]
    native_frames = [{"frame": i, "simulation_time": i / 20,
                      "adapter_graph": f"graphs/base/{i:08d}.adapter.json"}
                     for i in range(900)]
    files = {"trace.json": compact(trace) + "\n", "relation.json": compact(relation) + "\n",
             "trace.jsonl": lines(traces), "video_frames.jsonl": lines(frames),
             "capture/evidence.jsonl": lines(evidence),
             "capture/native/frames.jsonl": lines(native_frames),
             "capture/recorder_info.txt": "Create 11: vehicle.tesla.model3 (diagnostic) at (0, 0, 0)\n",
             "capture/manifest.json": compact({"status": "draft", "acquisition": "synthetic_cpu_fixture",
                "case_id": case_id, "frames": 900, "extraction_confirmed": True,
                "complete_driving_lanes": False,
                "sources": {"road.xodr": sha(ROOT / "diagnostic-map.xodr"),
                            "trace.jsonl": hashlib.sha256(lines(traces).encode()).hexdigest()}}) + "\n",
             "acquisition-provenance.json": compact({"provenance_kind": "synthetic_fixture",
                                                      "diagnostic_fixture": True}) + "\n"}
    videos = [{"path": name + ".mkv", "frames": 900, "width": size[0],
               "height": size[1], "fps": 20, "color": "black"}
              for name, size in (("overview", (1920,1080)), ("approach", (1280,720)),
                                 ("reference_corner", (1280,720)),
                                 ("driver_reference", (1280,720)))]
    spec = {"files": files, "graphs": graphs, "videos": videos}
    rel = f"cases/{suffix}/diagnostic-spec.json"
    write(ROOT / rel, spec)
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": "road.xodr", "source": str((ROOT / "diagnostic-map.xodr").relative_to(ROOT.parent.parent)),
                           "sha256": sha(ROOT / "diagnostic-map.xodr")}],
              "generator": {"source": str((ROOT / rel).relative_to(ROOT.parent.parent)),
                            "sha256": sha(ROOT / rel)}}
    write(ROOT / f"cases/{suffix}/diagnostic-recipe.json", recipe)
    return rel


def main():
    for suffix in (f"{axis}-{rank:04d}" for axis in ("impediment", "passing_necessity")
                   for rank in range(3)):
        rel = build(suffix)
        print(rel, (ROOT / rel).stat().st_size)


if __name__ == "__main__":
    main()
